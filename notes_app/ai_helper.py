import base64
import os

DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"


def _raise_api_error(response, provider):
    """Raise a readable error for a non-200 response without exposing the request URL."""
    try:
        msg = response.json()["error"]["message"]
    except Exception:
        msg = f"HTTP {response.status_code} {response.reason or ''}".strip()
    raise ValueError(f"{provider}: {msg}")


def call_gemini_api(api_key, prompt, pdf_path=None, workspace_info=None, model=None):
    model = (model or DEFAULT_GEMINI_MODEL).strip()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    # Key goes in a header, not the query string, so it can't leak via error messages or logs.
    headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}
    
    system_instruction = (
        "You are a helpful notes assistant. You assist the user with editing, writing, and searching notes.\n"
        "You MUST adopt Australian spelling, dates, and number formats in all your responses. Examples:\n"
        "- Use Australian spelling (e.g. colour, organise, realise, centre, travelled).\n"
        "- Use Australian date format: Day Month Year (e.g. 12 July 2026), without commas.\n"
        "- Use Australian/UK number format: No comma separators for thousands (e.g. write 2388 instead of 2,388, write 10000 instead of 10,000).\n"
    )
    
    parts = []
    if pdf_path and os.path.exists(pdf_path):
        try:
            with open(pdf_path, "rb") as f:
                pdf_data = base64.b64encode(f.read()).decode("utf-8")
            parts.append({
                "inlineData": {
                    "mimeType": "application/pdf",
                    "data": pdf_data
                }
            })
        except Exception as e:
            raise ValueError(f"Failed to read/encode PDF file: {e}")
    
    gemini_prompt = prompt
    if workspace_info:
        gemini_prompt = f"Workspace Note Information:\n{workspace_info}\n\nUser Question:\n{prompt}"
        
    parts.append({"text": gemini_prompt})
    payload = {
        "contents": [{
            "parts": parts
        }],
        "systemInstruction": {
            "parts": [{"text": system_instruction}]
        }
    }

    import requests
    response = requests.post(url, json=payload, headers=headers, timeout=45)
    if response.status_code != 200:
        _raise_api_error(response, "Gemini")
    res_data = response.json()
    
    try:
        return res_data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        raise ValueError("Invalid response structure received from Gemini API.")

def _deepseek_system_prompt(workspace_info, note_content):
    prompt = (
        "You are a helpful notes assistant. You assist the user with editing, writing, and searching notes.\n"
        "You MUST adopt Australian spelling, dates, and number formats in all your responses. Examples:\n"
        "- Use Australian spelling (e.g. colour, organise, realise, centre, travelled).\n"
        "- Use Australian date format: Day Month Year (e.g. 12 July 2026), without commas.\n"
        "- Use Australian/UK number format: No comma separators for thousands (e.g. write 2388 instead of 2,388, write 10000 instead of 10,000).\n"
    )
    if workspace_info:
        prompt += f"\n\nWorkspace Note Information:\n{workspace_info}"
    if note_content:
        prompt += f"\n\nActive Note Content:\n---\n{note_content}\n---"
    return prompt


def call_deepseek_api(api_key, prompt, note_content=None, workspace_info=None):
    import requests
    url = "https://api.deepseek.com/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": _deepseek_system_prompt(workspace_info, note_content)},
            {"role": "user", "content": prompt}
        ],
        "stream": False
    }
    response = requests.post(url, json=payload, headers=headers, timeout=45)
    if response.status_code != 200:
        _raise_api_error(response, "DeepSeek")
    try:
        return response.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        raise ValueError("Invalid response structure received from DeepSeek API.")


def call_deepseek_api_streaming(api_key, prompt, note_content=None, workspace_info=None, on_chunk=None):
    """Stream DeepSeek response; calls on_chunk(text) for each token as it arrives."""
    import json
    import requests
    url = "https://api.deepseek.com/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": _deepseek_system_prompt(workspace_info, note_content)},
            {"role": "user", "content": prompt}
        ],
        "stream": True
    }
    response = requests.post(url, json=payload, headers=headers, timeout=60, stream=True)
    if response.status_code != 200:
        _raise_api_error(response, "DeepSeek")
    full_text = ""
    for line in response.iter_lines():
        if not line:
            continue
        if isinstance(line, bytes):
            line = line.decode("utf-8")
        if not line.startswith("data: "):
            continue
        data = line[6:]
        if data == "[DONE]":
            break
        try:
            chunk = json.loads(data)
            text = chunk["choices"][0]["delta"].get("content", "")
            if text:
                full_text += text
                if on_chunk:
                    on_chunk(text)
        except (json.JSONDecodeError, KeyError, IndexError):
            pass
    return full_text
