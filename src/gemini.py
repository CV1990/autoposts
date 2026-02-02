# Módulo para llamar a la API de Google Gemini y obtener post + prompt de imagen en JSON.
# No se hardcodea ninguna llave; GEMINI_API_KEY debe venir de env.

import json
from workers import fetch


GEMINI_MODEL = "gemini-1.5-flash"
GEMINI_JSON_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent"
)

# Instrucciones para el agente: contenido técnico/educativo sobre tu negocio o hobby.
GEMINI_SYSTEM_INSTRUCTION = """Eres un asistente que genera contenido para redes sociales (Facebook e Instagram).
Tu tarea es devolver ÚNICAMENTE un JSON válido, sin markdown ni texto extra, con exactamente estas dos claves:

- "post_text": Un post profesional y educativo (2-4 párrafos breves) sobre temas de interés técnico, tu negocio o tu hobby. Lenguaje claro y motivador. Incluye un título corto al inicio.
- "image_prompt": Un prompt en inglés, optimizado para Stable Diffusion, que genere una ilustración minimalista y profesional relacionada con el tema del post. Estilo: limpio, moderno, sin texto en la imagen. Ejemplo: "minimalist flat illustration of [tema], soft colors, professional, no text".

Genera contenido variado y de valor. El JSON debe ser parseable directamente."""


async def fetch_gemini_json(env) -> dict:
    """
    Llama a la API de Gemini y devuelve un dict con 'post_text' e 'image_prompt'.
    Las llaves nunca se hardcodean; se usa env.GEMINI_API_KEY.
    """
    api_key = getattr(env, "GEMINI_API_KEY", None) or (env.get("GEMINI_API_KEY") if callable(getattr(env, "get", None)) else None)
    if not api_key:
        raise ValueError("GEMINI_API_KEY no configurado (secret o variable de entorno)")

    url = f"{GEMINI_JSON_URL}?key={api_key}"
    payload = {
        "contents": [{"role": "user", "parts": [{"text": GEMINI_SYSTEM_INSTRUCTION}]}],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 1024,
            "responseMimeType": "application/json",
        },
    }

    try:
        response = await fetch(
            url,
            method="POST",
            headers={"Content-Type": "application/json"},
            body=json.dumps(payload),
        )
    except Exception as e:
        raise RuntimeError(f"Error de red al llamar a Gemini: {e}") from e

    if not response.status == 200:
        body = await response.text()
        raise RuntimeError(f"Gemini API error {response.status}: {body}")

    try:
        data = await response.json()
    except Exception as e:
        raise RuntimeError(f"Respuesta de Gemini no es JSON válido: {e}") from e

    text = None
    try:
        candidates = data.get("candidates") or []
        if not candidates:
            raise ValueError("Gemini no devolvió candidatos")
        parts = (candidates[0].get("content") or {}).get("parts") or []
        if not parts:
            raise ValueError("Gemini no devolvió parts en el contenido")
        text = (parts[0].get("text") or "").strip()
        if not text:
            raise ValueError("Gemini devolvió texto vacío")
    except (KeyError, IndexError, TypeError) as e:
        raise RuntimeError(f"Formato de respuesta Gemini inesperado: {e}") from e

    # Limpiar posible markdown (```json ... ```)
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Gemini no devolvió JSON válido: {e}") from e

    if not isinstance(parsed, dict):
        raise ValueError("El JSON de Gemini debe ser un objeto")
    if "post_text" not in parsed or "image_prompt" not in parsed:
        raise ValueError("El JSON debe contener 'post_text' e 'image_prompt'")

    return {
        "post_text": str(parsed["post_text"]).strip(),
        "image_prompt": str(parsed["image_prompt"]).strip(),
    }
