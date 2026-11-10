/** Gemini REST client — same BYOK model as desktop Lotus.
 *  The user's own key calls the API directly; nothing is proxied or stored
 *  anywhere but the device keychain.
 */

const MODELS = [
  "gemini-2.5-flash",
  "gemini-2.5-flash-lite",
  "gemini-2.0-flash",
];

const SYSTEM = `You are Lotus, a cybersecurity AI assistant (mobile beta).
Focus: SOC analysis, AppSec, DevSecOps, defense, safe automation.
Be concise and professional. You run as a beta on the user's phone — never
claim actions you did not actually take.`;

export class GeminiError extends Error {}

export async function generateReply(
  apiKey: string,
  history: { role: string; content: string }[],
): Promise<string> {
  if (!apiKey) throw new GeminiError("No Gemini key set — open Settings to add one.");

  const contents = history.slice(-12).map((m) => ({
    role: m.role === "user" ? "user" : "model",
    parts: [{ text: m.content }],
  }));

  let lastErr = "unknown";
  for (const model of MODELS) {
    try {
      const url =
        `https://generativelanguage.googleapis.com/v1beta/models/` +
        `${model}:generateContent?key=${apiKey}`;
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          contents,
          systemInstruction: { parts: [{ text: SYSTEM }] },
          generationConfig: { temperature: 0.7, maxOutputTokens: 2048 },
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
      if (text.trim()) return text.trim();
      lastErr = `${model}: empty response`;
    } catch (e: any) {
      lastErr = `${model}: ${e?.message || e}`;
    }
  }
  throw new GeminiError(`Gemini could not answer. ${lastErr}`);
}
