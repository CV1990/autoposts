# AutoPosts – Bot de contenido técnico en Cloudflare Workers (Python)

Bot automatizado que publica contenido técnico/educativo en **Facebook** e **Instagram** cada 3 horas, usando:

- **Runtime:** Cloudflare Workers (Python)
- **Trigger:** Cron (cada 3 h) o llamada HTTP desde GitHub Actions
- **LLM:** Google Gemini API (`gemini-1.5-flash`) para generar el texto y el prompt de imagen
- **Imagen:** Cloudflare Workers AI (`@cf/bytedance/stable-diffusion-xl-lightning`) para generar la ilustración
- **Notificaciones:** Telegram (éxito o error)

## Estructura del proyecto

```
├── .github/workflows/
│   └── autoposts-cron.yml   # Cron cada 3h vía GitHub Actions (opcional)
├── src/
│   ├── main.py              # Entrypoint: fetch + scheduled, flujo principal
│   ├── gemini.py            # Llamada a Gemini → JSON (post_text, image_prompt)
│   ├── workers_ai_image.py  # Generación de imagen con Workers AI
│   ├── meta_publish.py      # Publicación en Facebook e Instagram (Graph API)
│   └── telegram_notify.py   # Notificaciones por Telegram (sendMessage, HTML)
├── wrangler.toml            # Configuración del Worker (cron, AI, KV, vars)
└── README.md
```

## Seguridad – Sin claves en código

Todas las claves y IDs se configuran como **secrets** o **variables** en Cloudflare (o en GitHub para el workflow). No se hardcodea ninguna llave.

### Secrets / variables en Cloudflare

Configura en el dashboard o con Wrangler:

| Nombre | Descripción |
|--------|-------------|
| `GEMINI_API_KEY` | API key de Google AI Studio (Gemini) |
| `META_PAGE_ACCESS_TOKEN` | Token de acceso de la Page de Facebook (con permisos de publicación) |
| `META_PAGE_ID` | ID de la Facebook Page |
| `INSTAGRAM_ACCOUNT_ID` | ID de la cuenta de Instagram profesional vinculada |
| `WORKER_PUBLIC_URL` | URL pública del Worker (ej. `https://autoposts.<account>.workers.dev`) |
| `TELEGRAM_BOT_TOKEN` | Token del bot de Telegram |
| `TELEGRAM_CHAT_ID` | ID del chat donde recibir notificaciones |
| `CRON_SECRET` | (Opcional) Secret para autorizar llamadas a `/run` desde GitHub Actions |

Ejemplo con Wrangler:

```bash
wrangler secret put GEMINI_API_KEY
wrangler secret put META_PAGE_ACCESS_TOKEN
wrangler secret put META_PAGE_ID
wrangler secret put INSTAGRAM_ACCOUNT_ID
wrangler secret put WORKER_PUBLIC_URL
wrangler secret put TELEGRAM_BOT_TOKEN
wrangler secret put TELEGRAM_CHAT_ID
wrangler secret put CRON_SECRET   # si usas GitHub Actions
```

### KV namespace

Instagram requiere que la imagen esté en una **URL pública**. El Worker guarda la imagen en KV y la sirve en `GET /image/<key>`.

1. Crea un namespace KV:
   ```bash
   wrangler kv namespace create POST_IMAGES
   ```
2. En `wrangler.toml`, sustituye `<KV_NAMESPACE_ID>` por el `id` que te devuelve el comando anterior (en `[[kv_namespaces]]`).

## Flujo de Gemini

La llamada a Gemini devuelve un **JSON** con:

- **`post_text`:** Texto del post (Facebook/Instagram), profesional y educativo, sobre temas de tu negocio o hobby.
- **`image_prompt`:** Prompt para Stable Diffusion (ilustración minimalista relacionada con el post).

Las instrucciones del agente están en `src/gemini.py`; puedes editarlas para ajustar tono, temas o formato.

## Telegram

- **Éxito:** mensaje con formato HTML:  
  `✅ Post publicado con éxito sobre: **<tema>**`
- **Error:**  
  `❌ Error en el Bot de LinkedIn: <detalle del error>`

Se usa `parse_mode="HTML"` en la API de Telegram para que el título se vea en negrita.

**Si no llega el mensaje de Telegram:**  
1. Comprueba que los secrets **TELEGRAM_BOT_TOKEN** y **TELEGRAM_CHAT_ID** estén configurados en el Worker (Cloudflare Dashboard → Workers & Pages → autoposts → Settings → Variables and Secrets, o `wrangler secret put TELEGRAM_BOT_TOKEN` y `wrangler secret put TELEGRAM_CHAT_ID`).  
2. Al llamar a `/run`, la respuesta incluye `"telegram_sent": true/false`. Si es `false`, el token o el chat_id son incorrectos o faltan.  
3. Verifica el token con @BotFather y el chat_id con `https://api.telegram.org/bot<TOKEN>/getUpdates` (después de escribir algo al bot).

## Cron cada 3 horas

- **Opción 1 – Solo Cloudflare:** En `wrangler.toml` está definido el trigger `0 */3 * * *` (cada 3 horas en punto, UTC). No necesitas GitHub Actions.
- **Opción 2 – GitHub Actions:** El workflow `.github/workflows/autoposts-cron.yml` ejecuta el mismo cron y llama a tu Worker en `/run?secret=<CRON_SECRET>`. Configura en el repo:
  - **Secrets:** `WORKER_RUN_URL` (ej. `https://autoposts.<account>.workers.dev/run`), `CRON_SECRET` (mismo valor que en el Worker).

## Desarrollo y despliegue

**Importante:** Los Python Workers deben desplegarse con **pywrangler**, no con `wrangler` solo. Usar `wrangler deploy` puede provocar error 1101.

Requisitos: **uv** y Node.js instalados.

### Instalar uv (Windows)

En PowerShell (como administrador o en tu usuario):

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Cierra y vuelve a abrir la terminal; luego comprueba con `uv --version`.

Alternativa con winget: `winget install --id=astral-sh.uv -e`

### Despliegue

**Node.js y Wrangler:** pywrangler usa `npx wrangler`. En la raíz del proyecto ejecuta `npm install` (hay un `package.json` con wrangler como devDependency).

```bash
# En la raíz del proyecto: instalar wrangler para que npx wrangler funcione
npm install

# Instalar workers-py (CLI para Python Workers)
uv tool install workers-py

# Sincronizar dependencias Python
uv sync

# Login en Cloudflare
uv run pywrangler login

# Crear KV y configurar secrets con wrangler (ver arriba)
wrangler kv namespace create POST_IMAGES
wrangler secret put GEMINI_API_KEY
# ... etc.

# Desplegar (usar pywrangler, no wrangler)
uv run pywrangler deploy
```

**Si en Windows aparece "Python interpreter not found" (Pyodide/emscripten-wasm32):** el intérprete Pyodide para Workers **no está soportado en Windows**. Tienes dos opciones:

1. **Desplegar desde GitHub Actions (recomendado, sin WSL):** sube el repo a GitHub, configura los secrets `CLOUDFLARE_API_TOKEN` y `CLOUDFLARE_ACCOUNT_ID` en el repositorio (Settings > Secrets and variables > Actions), y ejecuta el workflow **Deploy Worker** (pestaña Actions). El workflow `.github/workflows/deploy.yml` despliega desde Linux. Se ejecuta en cada push a `main` o manualmente con "Run workflow".
2. **Usar WSL (Ubuntu):** abre el proyecto en WSL (`/mnt/d/Cursor/AutoPosts`) y ejecuta ahí `uv sync`, `npm install`, `uv run pywrangler deploy`.

Para probar en local:

```bash
uv run pywrangler dev
# En otra terminal:
curl "http://localhost:8787/"
curl "http://localhost:8787/cdn-cgi/handler/scheduled"
```

Para probar el flujo por HTTP (con `CRON_SECRET` configurado):

```bash
curl "https://<tu-worker>.workers.dev/run?secret=<CRON_SECRET>"
```

## Requisitos Meta (Facebook / Instagram)

- **Facebook:** Page con token que tenga permisos `pages_manage_posts`, `pages_read_engagement`, etc. Publicación con foto por URL (`POST /{page-id}/photos` con `url` y `caption`).
- **Instagram:** Cuenta profesional vinculada a la Page; permisos `instagram_content_publish` (Facebook Login) o `instagram_business_content_publish` (Instagram Login). La imagen debe estar en una URL pública; el Worker la sirve desde KV en `/image/<key>`.

## Licencia

Uso libre para tu negocio o hobby. Ajusta instrucciones de Gemini y mensajes de Telegram a tu gusto.
