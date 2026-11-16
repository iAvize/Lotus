export type PatchNote = {
  version: string;
  date: string;
  notes: string[];
};

export const PATCH_NOTES: PatchNote[] = [
  {
    version: "0.1.0-beta.4",
    date: "2026-11-15",
    notes: [
      "Files orb storage audit: device free/total space, Lotus storage breakdown, largest files, picked-item audit",
      "Shortcuts to iPhone Storage and App Store settings for manual offload/uninstall",
      "iOS limit documented: apps cannot enumerate or uninstall other installed apps",
    ],
  },
  {
    version: "0.1.0-beta.3",
    date: "2026-11-15",
    notes: [
      "Mobile orb suite: Ask, Files, Privacy Sweep, Personality, Patch Notes, Settings",
      "Files orb scans app storage or picked Files-app items for suspicious files/secrets",
      "Privacy Sweep: HIBP breach check + data-broker opt-out tracker",
      "Personality orb: voice presets + custom style notes for Gemini chat",
      "Settings renamed from Setup with theme picker, feedback, report, and GitHub scanner",
      "Gemini model ladder starts at gemini-3.8-flash",
    ],
  },
  {
    version: "0.1.0-beta.2",
    date: "2026-11-15",
    notes: [
      "Vertical orb menu for phone layout",
      "Logs section for on-device chat history",
      "Settings section with secure Gemini key entry and AI Studio link",
      "First free-account iPhone Release build",
    ],
  },
];
