# Generación de imagen con Cloudflare Workers AI (Stable Diffusion XL Lightning).
# Usa el binding env.AI; no se hardcodean claves.

WORKERS_AI_MODEL = "@cf/bytedance/stable-diffusion-xl-lightning"


async def generate_image_bytes(image_prompt: str, env) -> bytes:
    """
    Genera una imagen a partir del prompt usando Workers AI.
    Devuelve los bytes de la imagen (PNG/JPEG).
    """
    ai = getattr(env, "AI", None)
    if not ai:
        raise ValueError("Binding AI no configurado en wrangler.toml")

    inputs = {"prompt": image_prompt}
    try:
        result = await ai.run(WORKERS_AI_MODEL, inputs)
    except Exception as e:
        raise RuntimeError(f"Workers AI run error: {e}") from e

    # El binding puede devolver body/stream; intentar obtener bytes.
    if result is None:
        raise RuntimeError("Workers AI devolvió resultado vacío")
    if isinstance(result, bytes):
        return result
    if hasattr(result, "bytes"):
        return await result.bytes()
    if hasattr(result, "arrayBuffer"):
        ab = await result.arrayBuffer()
        return bytes(ab)
    # Response-like con body (stream)
    if hasattr(result, "body") and result.body:
        reader = result.body.get_reader()
        return await _read_stream(reader)
    # ReadableStream directo (Workers AI puede devolver el body como stream)
    if hasattr(result, "getReader"):
        reader = result.get_reader()
        return await _read_stream(reader)
    raise RuntimeError("No se pudo extraer bytes de la respuesta de Workers AI")


async def _read_stream(reader) -> bytes:
    chunks = []
    while True:
        done = await reader.read()
        if getattr(done, "get", None):
            if done.get("done"):
                break
            chunk = done.get("value")
        else:
            if getattr(done, "done", False):
                break
            chunk = getattr(done, "value", None)
        if chunk:
            chunks.append(bytes(chunk) if not isinstance(chunk, bytes) else chunk)
    return b"".join(chunks)
