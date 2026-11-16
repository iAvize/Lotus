/** Gemini REST client — same BYOK model as desktop Lotus.
 *  The user's own key calls the API directly; nothing is proxied or stored
 *  anywhere but the device keychain.
 */
import AsyncStorage from "@react-native-async-storage/async-storage";

const KEY_MODEL = "lotus:last_model";
const REQUEST_TIMEOUT_MS = 25000;

const MODELS = [
  "gemini-3.8-flash",
  "gemini-3.5-flash",
  "gemini-3.5-flash-lite",
  "gemini-flash-latest",
  "gemini-2.5-flash",
];

const SYSTEM = `You are Lotus, a cybersecurity AI assistant (mobile beta).
Focus: SOC analysis, AppSec, DevSecOps, defense, safe automation.
Answer quickly and concisely; keep replies short unless detail is requested.
Be professional. You run as a beta on the user's phone — never
claim actions you did not actually take.`;

export class GeminiError extends Error {}

export async function generateReply(
  apiKey: string,
  history: { role: string; content: string }[],
  voice = "",
): Promise<string> {
  if (!apiKey) throw new GeminiError("No Gemini key set — open Settings to add one.");

  const contents = history.slice(-6).map((m) => ({
    role: m.role === "user" ? "user" : "model",
    parts: [{ text: m.content }],
  }));

  // Try the last model that worked first — dead/slow models ahead of it in
  // the ladder cost a full round trip each otherwise.
  const lastGood = (await AsyncStorage.getItem(KEY_MODEL)) || "";
  const order = lastGood && MODELS.includes(lastGood)
    ? [lastGood, ...MODELS.filter((m) => m !== lastGood)]
    : MODELS;

  let lastErr = "unknown";
  for (const model of order) {
    try {
      const url =
        `https://generativelanguage.googleapis.com/v1beta/models/` +
        `${model}:generateContent?key=${apiKey}`;
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
        body: JSON.stringify({
          contents,
          systemInstruction: { parts: [{ text: voice ? `${SYSTEM}\n\n${voice}` : SYSTEM }] },
          generationConfig: { temperature: 0.6, maxOutputTokens: 1024 },
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        lastErr = `${model}: ${data?.error?.message || res.status}`;
        if (res.status === 400 || res.status === 403) break; // key problem — don't retry models
        continue;
      }
      const text =
        data?.candidates?.[0]?.content?.parts
          ?.map((p: any) => p.text || "")
          .join("") || "";
      if (text.trim()) {
        AsyncStorage.setItem(KEY_MODEL, model).catch(() => {});
        return text.trim();
      }
      lastErr = `${model}: empty response`;
    } catch (e: any) {
      lastErr = `${model}: ${e?.message || e}`;
    }
  }
  throw new GeminiError(`Gemini could not answer. ${lastErr}`);
}
