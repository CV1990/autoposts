# Publicación en Facebook (Page) e Instagram mediante Meta Graph API.
# Usa env: META_PAGE_ACCESS_TOKEN, META_PAGE_ID, INSTAGRAM_ACCOUNT_ID, WORKER_PUBLIC_URL.
# La imagen debe estar en una URL pública; el Worker sirve la imagen desde KV.

import json
from workers import fetch

META_GRAPH_BASE = "https://graph.facebook.com/v21.0"


async def publish_facebook_post(page_id: str, access_token: str, image_url: str, caption: str, env) -> dict:
    """
    Publica una foto en la Facebook Page usando la URL de la imagen.
    POST /{page-id}/photos con url y caption.
    """
    url = f"{META_GRAPH_BASE}/{page_id}/photos"
    params = {
        "url": image_url,
        "caption": caption,
        "published": "true",
        "access_token": access_token,
    }
    body = __urlencode(params)
    try:
        response = await fetch(
            url,
            method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            body=body,
        )
    except Exception as e:
        raise RuntimeError(f"Error de red al publicar en Facebook: {e}") from e

    text = await response.text()
    if response.status != 200:
        raise RuntimeError(f"Facebook API error {response.status}: {text}")

    try:
        return json.loads(text) if text else {}
    except json.JSONDecodeError:
        return {"raw": text}


async def create_instagram_container(ig_user_id: str, access_token: str, image_url: str, caption: str, env) -> str:
    """
    Crea un contenedor de media en Instagram (image_url debe ser accesible públicamente).
    Devuelve el ID del contenedor.
    """
    url = f"{META_GRAPH_BASE}/{ig_user_id}/media"
    params = {
        "image_url": image_url,
        "caption": caption,
        "access_token": access_token,
    }
    body = __urlencode(params)
    try:
        response = await fetch(
            url,
            method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            body=body,
        )
    except Exception as e:
        raise RuntimeError(f"Error de red al crear contenedor Instagram: {e}") from e

    text = await response.text()
    if response.status != 200:
        raise RuntimeError(f"Instagram container API error {response.status}: {text}")

    try:
        data = json.loads(text) if text else {}
        cid = data.get("id")
        if not cid:
            raise RuntimeError(f"Instagram no devolvió container id: {text}")
        return str(cid)
    except json.JSONDecodeError:
        raise RuntimeError(f"Instagram respuesta no JSON: {text}")


async def publish_instagram_container(ig_user_id: str, access_token: str, creation_id: str, env) -> dict:
    """Publica el contenedor en Instagram. POST /{ig-user-id}/media_publish."""
    url = f"{META_GRAPH_BASE}/{ig_user_id}/media_publish"
    params = {
        "creation_id": creation_id,
        "access_token": access_token,
    }
    body = __urlencode(params)
    try:
        response = await fetch(
            url,
            method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            body=body,
        )
    except Exception as e:
        raise RuntimeError(f"Error de red al publicar en Instagram: {e}") from e

    text = await response.text()
    if response.status != 200:
        raise RuntimeError(f"Instagram publish API error {response.status}: {text}")

    try:
        return json.loads(text) if text else {}
    except json.JSONDecodeError:
        return {"raw": text}


def __urlencode(params):
    from urllib.parse import urlencode
    return urlencode(params)
