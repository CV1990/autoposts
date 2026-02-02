# AutoPosts: bot automatizado en Cloudflare Workers (Python)
# Publica contenido técnico en Facebook e Instagram cada 3h (cron o GitHub Actions).
# Usa Gemini para texto, Workers AI para imagen, Telegram para notificaciones.

import json
import traceback
from urllib.parse import urlparse
from workers import WorkerEntrypoint, Response


def _get_env(env, key: str, default=None):
    v = getattr(env, key, None)
    if v is not None and v != "":
        return v
    if callable(getattr(env, "get", None)):
        v = env.get(key)
        if v is not None and v != "":
            return v
    return default


def _extract_tema(post_text: str, max_len: int = 60) -> str:
    """Extrae un título/tema corto del post (primera línea o inicio)."""
    if not post_text:
        return "Contenido técnico"
    first_line = post_text.split("\n")[0].strip()
    if not first_line:
        first_line = post_text.strip()
    if len(first_line) > max_len:
        return first_line[: max_len - 3].rstrip() + "..."
    return first_line or "Contenido técnico"


async def _run_publish_flow(env):
    """
    Flujo principal: Gemini -> Workers AI -> KV -> Facebook -> Instagram.
    Devuelve (éxito: bool, tema: str, detalle_error: str | None).
    """
    import gemini
    import meta_publish
    import telegram_notify
    import workers_ai_image

    tema = "Contenido técnico"
    try:
        # 1) Gemini: post_text + image_prompt (JSON)
        data = await gemini.fetch_gemini_json(env)
        post_text = data["post_text"]
        image_prompt = data["image_prompt"]
        tema = _extract_tema(post_text)
    except Exception as e:
        return False, tema, f"Gemini: {e}"

    try:
        # 2) Workers AI: generar imagen
        image_bytes = await workers_ai_image.generate_image_bytes(image_prompt, env)
    except Exception as e:
        return False, tema, f"Workers AI: {e}"

    # 3) Guardar imagen en KV y construir URL pública
    kv = getattr(env, "POST_IMAGES", None)
    worker_url = _get_env(env, "WORKER_PUBLIC_URL")
    if not kv or not worker_url:
        return False, tema, "POST_IMAGES o WORKER_PUBLIC_URL no configurado"

    import time
    key = f"img/{int(time.time())}"
    try:
        await kv.put(key, image_bytes)
    except Exception as e:
        return False, tema, f"KV put: {e}"

    image_url = f"{worker_url.rstrip('/')}/image/{key}"

    # 4) Facebook
    page_id = _get_env(env, "META_PAGE_ID")
    meta_token = _get_env(env, "META_PAGE_ACCESS_TOKEN")
    if page_id and meta_token:
        try:
            await meta_publish.publish_facebook_post(
                page_id, meta_token, image_url, post_text, env
            )
        except Exception as e:
            return False, tema, f"Facebook: {e}"

    # 5) Instagram (crear contenedor + publicar)
    ig_id = _get_env(env, "INSTAGRAM_ACCOUNT_ID")
    if ig_id and meta_token:
        try:
            creation_id = await meta_publish.create_instagram_container(
                ig_id, meta_token, image_url, post_text, env
            )
            await meta_publish.publish_instagram_container(
                ig_id, meta_token, creation_id, env
            )
        except Exception as e:
            return False, tema, f"Instagram: {e}"

    return True, tema, None


async def send_telegram_notification(text: str, env) -> bool:
    """Reexportar para uso en main."""
    import telegram_notify
    return await telegram_notify.send_telegram_notification(text, env)


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        try:
            # Asegurar string para urlparse (request.url puede ser JsProxy en Workers Python)
            url_str = str(getattr(request, "url", "") or "")
            url = urlparse(url_str)
            path = (getattr(url, "path", "") or "").rstrip("/")
            env = self.env

            # Servir imagen desde KV: /image/<key>
            if path.startswith("/image/"):
                key = path[len("/image/"):].lstrip("/")
                if not key:
                    return Response("Bad request", status=400)
                kv = getattr(env, "POST_IMAGES", None)
                if not kv:
                    return Response("KV not configured", status=503)
                try:
                    value = await kv.get(key)
                except Exception:
                    return Response("Error reading image", status=500)
                if value is None:
                    return Response("Not found", status=404)
                return Response(value, headers={"Content-Type": "image/png"})

            # Trigger manual (p. ej. desde GitHub Actions): GET/POST /run?secret=CRON_SECRET
            if path == "/run" or path == "/run/":
                try:
                    cron_secret = _get_env(env, "CRON_SECRET")
                    if cron_secret:
                        from urllib.parse import parse_qs
                        qs = parse_qs(url.query or "")
                        provided = (qs.get("secret") or [None])[0]
                        if provided != cron_secret:
                            return Response("Unauthorized", status=401)
                    success, tema, err = await _run_publish_flow(env)
                    if success:
                        msg = f'✅ Post publicado con éxito sobre: <b>{_escape_html(tema)}</b>'
                        await send_telegram_notification(msg, env)
                        return Response(
                            json.dumps({"ok": True, "tema": tema}),
                            headers={"Content-Type": "application/json"},
                        )
                    msg = f"❌ Error en el Bot de LinkedIn: {_escape_html(err or 'Unknown')}"
                    await send_telegram_notification(msg, env)
                    return Response(
                        json.dumps({"ok": False, "error": err}),
                        status=500,
                        headers={"Content-Type": "application/json"},
                    )
                except Exception as e:
                    tb = traceback.format_exc()
                    return Response(
                        f"Error 1101 (exception):\n\n{tb}\n\n---\n{type(e).__name__}: {e}",
                        status=500,
                        headers={"Content-Type": "text/plain; charset=utf-8"},
                    )

            return Response("AutoPosts worker. Use /run with CRON_SECRET or wait for cron.", status=200)
        except BaseException as e:
            tb = traceback.format_exc()
            return Response(
                f"Error 1101 (exception en fetch):\n\n{tb}\n\n---\n{type(e).__name__}: {e}",
                status=500,
                headers={"Content-Type": "text/plain; charset=utf-8"},
            )

    async def scheduled(self, controller, env, ctx):
        try:
            success, tema, err = await _run_publish_flow(env)
            if success:
                msg = f'✅ Post publicado con éxito sobre: <b>{_escape_html(tema)}</b>'
                await send_telegram_notification(msg, env)
            else:
                msg = f"❌ Error en el Bot de LinkedIn: {_escape_html(err or 'Unknown')}"
                await send_telegram_notification(msg, env)
        except Exception as e:
            try:
                await send_telegram_notification(
                    f"❌ Error en el Bot de LinkedIn: {_escape_html(str(e))}", env
                )
            except Exception:
                pass


def _escape_html(s: str) -> str:
    if not s:
        return ""
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
