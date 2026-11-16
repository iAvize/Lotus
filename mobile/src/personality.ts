import { Personality } from "./store";

export const ARCHETYPES: Record<string, { label: string; voice: string }> = {
  neutral: {
    label: "Neutral",
    voice: "neutral-professional tone; moderately concise answers; moderate technical depth; answer what's asked without pushing suggestions",
  },
  analyst: {
    label: "Analyst",
    voice: "formal tone; detailed answers; expert-level technical depth; answer what's asked without pushing suggestions",
  },
  friendly: {
    label: "Friendly",
    voice: "casual tone; concise answers; light dry humor welcome; suggest useful next steps unprompted; moderate technical depth",
  },
  "strict-pro": {
    label: "Strict Pro",
    voice: "formal tone; concise answers; keep humor out; expert-level technical depth; answer what's asked without pushing suggestions",
  },
};

export function voicePrompt(personality: Personality): string {
  const base = ARCHETYPES[personality.archetype]?.voice || ARCHETYPES.neutral.voice;
  let block = `Voice calibration for this user: ${base}.`;
  const notes = personality.notes.trim();
  if (notes) block += `\nUser style notes: ${notes.slice(0, 400)}`;
  block += "\nApply this voice to conversation only — scan results, threat alerts, and security reports always stay literal and professional.";
  return block;
}
