import httpx
from app.config import settings

def generate(prompt: str, model: str | None = None) -> str:
    m = model or settings.ollama_model
    url = f"{settings.ollama_base_url}/api/generate"

    payload = {"model": m, "prompt": prompt, "stream": False}

    with httpx.Client(timeout=60.0) as client:
        r = client.post(url, json=payload)
        r.raise_for_status()
        data = r.json()
        return data.get("response", "")