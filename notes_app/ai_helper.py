import base64
import os
import requests

def call_gemini_api(api_key, prompt, pdf_path=None):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    
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
    
    parts.append({"text": prompt})
    payload = {
        "contents": [{
            "parts": parts
        }]
    }
    
    response = requests.post(url, json=payload, headers=headers, timeout=45)
    response.raise_for_status()
    res_data = response.json()
    
    try:
        return res_data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        raise ValueError("Invalid response structure received from Gemini API.")

def call_deepseek_api(api_key, prompt, note_content=None):
    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    system_prompt = "You are a helpful notes assistant. You assist the user with editing, writing, and searching notes."
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
    response.raise_for_status()
    res_data = response.json()
    
    try:
        return res_data["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        raise ValueError("Invalid response structure received from DeepSeek API.")
