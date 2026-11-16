export type PatchNote = {
  version: string;
  date: string;
  notes: string[];
};

export const PATCH_NOTES: PatchNote[] = [
  {
    version: "0.1.0-beta.16",
    date: "2026-11-16",
    notes: [
      "OTA cellular test build — if this patch note is visible, service-data updates work end to end",
    ],
  },
  {
    version: "0.1.0-beta.15",
    date: "2026-11-16",
    notes: [
      "OTA updates now work over service data, not just WiFi: the update check retries with backoff on slow networks and re-runs every time the app comes to the foreground",
      "Native builds now wait up to 10s for the update manifest on launch (was 3s), so slow cellular pulls land instead of timing out",
    ],
  },
  {
    version: "0.1.0-beta.14",
    date: "2026-11-16",
    notes: [
      "OTA self-repair: update bundles now download under unique filenames, so a stale cached file can no longer shadow new code",
    ],
  },
  {
    version: "0.1.0-beta.13",
    date: "2026-11-16",
    notes: [
      "Updates now apply automatically on launch — no banner tap needed. Open the app and new versions are simply there",
      "Fixed the root cause of updates never applying: the app used to launch before the update check finished, leaving downloads stranded",
    ],
  },
  {
    version: "0.1.0-beta.12",
    date: "2026-11-16",
    notes: [
      "Fixed the OTA loop — the update server timestamp format confused the client into re-prompting forever",
      "Diagnostics now include the internal update log and emergency-launch reason",
      "Crash reports send in the background — the screen confirms instantly instead of waiting on the relay",
    ],
  },
  {
    version: "0.1.0-beta.11",
    date: "2026-11-16",
    notes: [
      "Banner fix round 2 — remember the fetched update id and stay quiet once running a downloaded bundle",
      "Diagnostics now report whether the app is running embedded or OTA code",
    ],
  },
  {
    version: "0.1.0-beta.10",
    date: "2026-11-16",
    notes: [
      "Update banner no longer sticks after applying — the app now recognises when it's already running the fetched update",
    ],
  },
  {
    version: "0.1.0-beta.9",
    date: "2026-11-16",
    notes: [
      "Keyboard fix round 2 — edge-to-edge blocks window resize, so the composer now pads by real keyboard height",
      "Faster replies — the app remembers which Gemini model answered and tries it first",
      "OTA updates actually work now — the update server serves a real protocol manifest",
    ],
  },
  {
    version: "0.1.0-beta.8",
    date: "2026-11-16",
    notes: [
      "Android keyboard now lifts the composer while typing and drops back when the reply lands",
      "Gemini model ladder refreshed — dead model names removed, flash-latest fallback added",
    ],
  },
  {
    version: "0.1.0-beta.7",
    date: "2026-11-15",
    notes: [
      "Android port: status/nav bar theming, hardware back returns to Ask, edge-to-edge layout",
      "Platform-aware settings links (App settings / Play Store on Android)",
      "Diagnostics now report the real platform instead of assuming iOS",
    ],
  },
  {
    version: "0.1.0-beta.6",
    date: "2026-11-15",
    notes: [
      "Report error sends silently to the business inbox — paste the error, tap Send, done (no Mail or GitHub)",
      "Update-ready banner: new updates offer 'tap to restart and apply' like desktop",
      "Self-hosted OTA updates via GitHub Pages — app checks for updates on every launch",
    ],
  },
  {
    version: "0.1.0-beta.5",
    date: "2026-11-15",
    notes: [
      "Faster Ask Lotus chat: shorter history window, lower token cap, quicker Gemini settings",
      "Feedback/report now include version, install ID, platform, and last error",
      "Copy diagnostics button for pasting into email or GitHub reports",
      "Feedback email template tells users how to attach screenshots/videos in Mail",
    ],
  },
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
