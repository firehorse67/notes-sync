import base64
import os
import requests

def call_gemini_api(api_key, prompt, pdf_path=None, workspace_info=None):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    
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
    
    response = requests.post(url, json=payload, headers=headers, timeout=45)
    if response.status_code != 200:
        try:
            err_json = response.json()
            err_msg = err_json["error"]["message"]
            raise ValueError(err_msg)
        except Exception:
            response.raise_for_status()
    res_data = response.json()
    
    try:
        return res_data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        raise ValueError("Invalid response structure received from Gemini API.")

def call_deepseek_api(api_key, prompt, note_content=None, workspace_info=None):
    url = "https://api.deepseek.com/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    system_prompt = (
        "You are a helpful notes assistant. You assist the user with editing, writing, and searching notes.\n"
        "You MUST adopt Australian spelling, dates, and number formats in all your responses. Examples:\n"
        "- Use Australian spelling (e.g. colour, organise, realise, centre, travelled).\n"
        "- Use Australian date format: Day Month Year (e.g. 12 July 2026), without commas.\n"
        "- Use Australian/UK number format: No comma separators for thousands (e.g. write 2388 instead of 2,388, write 10000 instead of 10,000).\n"
    )
    if workspace_info:
        system_prompt += f"\n\nWorkspace Note Information:\n{workspace_info}"
    if note_content:
        system_prompt += f"\n\nActive Note Content:\n---\n{note_content}\n---"
        
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "stream": False
    }
    
    response = requests.post(url, json=payload, headers=headers, timeout=45)
    if response.status_code != 200:
        try:
            err_json = response.json()
            err_msg = err_json["error"]["message"]
            raise ValueError(err_msg)
        except Exception:
            response.raise_for_status()
    res_data = response.json()
    
    try:
        return res_data["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        raise ValueError("Invalid response structure received from DeepSeek API.")
