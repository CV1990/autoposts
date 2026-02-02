# Scripts (Node)

## generate-post.js

Genera un post en JSON usando la API de Gemini **con reintentos ante 429** (Too Many Requests).

### Uso local (AutoPosts)

```bash
cd scripts
npm install @google/generative-ai
GEMINI_API_KEY=tu_api_key node generate-post.js
```

### Uso en GitHub Actions (otro repo, ej. margora-landing)

1. **Opción A – Usar retry en tu script existente**

   En tu `scripts/generate-post.js`, envuelve la llamada a `generateContent` con un retry con backoff:

   ```js
   const MAX_RETRIES = 4;
   const INITIAL_DELAY_MS = 2000;

   async function withRetry(fn) {
     let lastError;
     let delay = INITIAL_DELAY_MS;
     for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
       try {
         return await fn();
       } catch (err) {
         lastError = err;
         const status = err?.status ?? err?.statusCode;
         if (attempt === MAX_RETRIES || (status !== 429 && status !== 503)) throw lastError;
         console.warn(`429/503, reintento en ${delay/1000}s (${attempt+1}/${MAX_RETRIES+1})`);
         await new Promise((r) => setTimeout(r, delay));
         delay = Math.min(delay * 2, 60000);
       }
     }
     throw lastError;
   }

   // Uso:
   const result = await withRetry(() => model.generateContent(prompt));
   ```

2. **Opción B – Reducir frecuencia del cron**

   Si el 429 es por límite de solicitudes por minuto/día, espacia las ejecuciones (por ejemplo cada 6 h en lugar de cada 3 h).

3. **Opción C – Modelo con más cuota**

   Prueba `gemini-1.5-flash` (a veces mayor cuota en free tier):

   ```bash
   GEMINI_MODEL=gemini-1.5-flash node scripts/generate-post.js
   ```

### Variables de entorno

| Variable         | Descripción                          |
|-----------------|--------------------------------------|
| `GEMINI_API_KEY` | API key de Google AI Studio (Gemini) |
| `GEMINI_MODEL`   | Opcional. Por defecto `gemini-2.0-flash` |
