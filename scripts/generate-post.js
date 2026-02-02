/**
 * Genera un post usando la API de Gemini con retry ante 429 (Too Many Requests).
 * Uso: GEMINI_API_KEY=xxx node generate-post.js
 *
 * Si usas este script en otro repo (ej. margora-landing), copia la función
 * withRetry() y envuelve tu llamada a model.generateContent() con ella.
 */

import { GoogleGenerativeAI } from "@google/generative-ai";

const MODEL_ID = process.env.GEMINI_MODEL || "gemini-2.0-flash";
const MAX_RETRIES = 4;
const INITIAL_DELAY_MS = 2000;
const MAX_DELAY_MS = 60000;

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Ejecuta fn() con reintentos y backoff exponencial ante 429 (y 503).
 */
async function withRetry(fn) {
  let lastError;
  let delay = INITIAL_DELAY_MS;

  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    try {
      return await fn();
    } catch (err) {
      lastError = err;
      const status = err?.status ?? err?.statusCode;
      const isRetryable = status === 429 || status === 503;

      if (attempt === MAX_RETRIES || !isRetryable) {
        throw lastError;
      }

      console.warn(
        `[generate-post] ${status} (intento ${attempt + 1}/${MAX_RETRIES + 1}). Reintento en ${delay / 1000}s...`
      );
      await sleep(delay);
      delay = Math.min(delay * 2, MAX_DELAY_MS);
    }
  }

  throw lastError;
}

async function main() {
  const apiKey = process.env.GEMINI_API_KEY;
  if (!apiKey) {
    console.error("GEMINI_API_KEY no está definido.");
    process.exit(1);
  }

  const genAI = new GoogleGenerativeAI(apiKey);
  const model = genAI.getGenerativeModel({
    model: MODEL_ID,
    generationConfig: {
      temperature: 0.7,
      maxOutputTokens: 1024,
      responseMimeType: "application/json",
    },
  });

  const prompt = `Devuelve ÚNICAMENTE un JSON válido con estas claves:
- "post_text": un post corto profesional y educativo (2-4 párrafos) sobre tecnología o negocio.
- "image_prompt": un prompt en inglés para Stable Diffusion, ilustración minimalista relacionada.

Sin markdown ni texto extra.`;

  const result = await withRetry(async () => {
    const res = await model.generateContent(prompt);
    const text = res?.response?.text?.();
    if (!text) throw new Error("Gemini no devolvió texto");
    return text;
  });

  console.log(result);
}

main().catch((err) => {
  console.error(err?.message || err);
  process.exit(1);
});
