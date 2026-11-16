import * as DocumentPicker from "expo-document-picker";
import * as FileSystem from "expo-file-system/legacy";

export type Severity = "low" | "medium" | "high";
export type Finding = { path: string; kind: string; detail: string; severity: Severity };
export type ScanReport = {
  scanned: number;
  skipped: number;
  findings: Finding[];
  quarantined: number;
  errors: string[];
  note?: string;
};

const MAX_FILE_SIZE = 600_000;
const MAX_APP_FILES = 300;
const MAX_GH_FILES = 60;
const MAX_DEPTH = 4;

const TEXT_EXT = new Set([
  "txt", "md", "json", "js", "jsx", "ts", "tsx", "py", "rb", "go", "rs", "java", "c", "cpp", "h", "hpp",
  "cs", "php", "swift", "kt", "yml", "yaml", "xml", "html", "css", "sh", "bash", "zsh", "env", "ini", "cfg",
]);
const DANGER_EXT = new Set([
  "exe", "dll", "bat", "cmd", "com", "pif", "scr", "msi", "apk", "ipa", "dylib", "so", "jar", "class", "app",
]);
const SECRET_PATTERNS: [RegExp, string][] = [
  [/-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----/, "private key block"],
  [/AIza[0-9A-Za-z_-]{20,}/, "Google API key"],
  [/ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}/, "GitHub token"],
  [/xox[baprs]-[A-Za-z0-9-]{10,}/, "Slack token"],
  [/sk-[A-Za-z0-9_-]{20,}/, "API secret key"],
  [/AKIA[0-9A-Z]{16}/, "AWS access key"],
  [/(?:api[_-]?key|token|secret|password|passwd|pwd)\s*[:=]\s*["'][^"']{8,}["']/i, "hard-coded credential"],
];
const CODE_PATTERNS: [RegExp, string][] = [
  [/eval\s*\(/, "eval() usage"],
  [/new Function\s*\(/, "dynamic Function constructor"],
  [/child_process|os\.system|subprocess\.|shell\s*=\s*True/i, "command execution"],
  [/base64\s+-d|certutil\s+-decode|powershell\s+-enc/i, "encoded payload command"],
  [/rm\s+-rf\s+\/|mkfs\.|dd\s+if=/i, "destructive command"],
];

function emptyReport(note?: string): ScanReport {
  return { scanned: 0, skipped: 0, findings: [], quarantined: 0, errors: [], note };
}

function extOf(path: string): string {
  const name = path.split("/").pop() || path;
  const i = name.lastIndexOf(".");
  return i >= 0 ? name.slice(i + 1).toLowerCase() : "";
}

function scanContent(rel: string, text: string, findings: Finding[]): void {
  for (const [re, kind] of SECRET_PATTERNS) {
    if (re.test(text)) findings.push({ path: rel, kind, detail: "possible exposed secret", severity: "high" });
  }
  for (const [re, kind] of CODE_PATTERNS) {
    if (re.test(text)) findings.push({ path: rel, kind, detail: "suspicious code pattern", severity: "medium" });
  }
}

async function scanFile(path: string, quarantine: boolean, findings: Finding[]): Promise<{ scanned: number; skipped: number }> {
  try {
    const info: any = await FileSystem.getInfoAsync(path);
    if (!info?.exists || info?.isDirectory) return { scanned: 0, skipped: 1 };
    const size = Number(info.size || 0);
    const ext = extOf(path);
    if (DANGER_EXT.has(ext)) {
      findings.push({ path, kind: `.${ext}`, detail: "executable/binary file type", severity: "high" });
      return { scanned: 1, skipped: 0 };
    }
    if (size > MAX_FILE_SIZE) return { scanned: 0, skipped: 1 };
    const text = await FileSystem.readAsStringAsync(path, { encoding: FileSystem.EncodingType.UTF8 });
    scanContent(path, text.slice(0, 200_000), findings);
    return { scanned: 1, skipped: 0 };
  } catch {
    return { scanned: 0, skipped: 1 };
  }
}

async function walk(
  dir: string,
  depth: number,
  quarantine: boolean,
  findings: Finding[],
  counters: { scanned: number; skipped: number; files: number },
  progress?: (msg: string) => void,
): Promise<void> {
  if (depth > MAX_DEPTH || counters.files >= MAX_APP_FILES) return;
  let names: string[] = [];
  try {
    names = await FileSystem.readDirectoryAsync(dir);
  } catch {
    return;
  }
  for (const name of names) {
    if (counters.files >= MAX_APP_FILES) break;
    const path = `${dir.replace(/\/$/, "")}/${name}`;
    if (path.includes("/quarantine/")) continue;
    try {
      const info: any = await FileSystem.getInfoAsync(path);
      if (!info?.exists) continue;
      if (info.isDirectory) {
        await walk(path, depth + 1, quarantine, findings, counters, progress);
      } else {
        counters.files += 1;
        progress?.(`Scanning ${name}`);
        const r = await scanFile(path, quarantine, findings);
        counters.scanned += r.scanned;
        counters.skipped += r.skipped;
      }
    } catch {
      counters.skipped += 1;
    }
  }
}

async function quarantineFindings(findings: Finding[], roots: string[]): Promise<number> {
  const dir = `${FileSystem.documentDirectory || ""}quarantine/`;
  if (!FileSystem.documentDirectory) return 0;
  let moved = 0;
  try {
    await FileSystem.makeDirectoryAsync(dir, { intermediates: true });
    for (const f of findings.filter((x) => x.severity === "high" && x.path.startsWith(roots[0] || "\0"))) {
      const name = `${Date.now()}_${f.path.split("/").pop() || "file"}`;
      try {
        await FileSystem.moveAsync({ from: f.path, to: `${dir}${name}` });
        moved += 1;
      } catch {}
    }
  } catch {}
  return moved;
}

export async function scanAppStorage(progress?: (msg: string) => void): Promise<ScanReport> {
  const roots = [FileSystem.documentDirectory, FileSystem.cacheDirectory].filter(Boolean) as string[];
  if (!roots.length) return emptyReport("No app storage available.");
  const findings: Finding[] = [];
  const counters = { scanned: 0, skipped: 0, files: 0 };
  for (const root of roots) await walk(root, 0, true, findings, counters, progress);
  const quarantined = await quarantineFindings(findings, roots);
  return { ...counters, findings: findings.slice(0, 200), quarantined, errors: [] };
}

export async function pickAndScan(progress?: (msg: string) => void): Promise<ScanReport | null> {
  const res = await DocumentPicker.getDocumentAsync({ type: "*/*", multiple: true, copyToCacheDirectory: true });
  if (res.canceled || !res.assets?.length) return null;
  const findings: Finding[] = [];
  let scanned = 0;
  let skipped = 0;
  for (const asset of res.assets.slice(0, 50)) {
    progress?.(`Scanning ${asset.name || asset.uri}`);
    const r = await scanFile(asset.uri, false, findings);
    scanned += r.scanned;
    skipped += r.skipped;
  }
  return { scanned, skipped, findings: findings.slice(0, 200), quarantined: 0, errors: [], note: "Picked files are scanned read-only; Lotus cannot quarantine outside its app storage." };
}

export function parseGithubRepo(value: string): { owner: string; repo: string } {
  const v = value.trim();
  if (!v) throw new Error("Enter owner/repo or a github.com URL.");
  let path = v;
  if (v.includes("github.com")) {
    path = v.split("github.com/")[1] || v;
  } else if (/^[^/\s]+\/[^/\s]+$/.test(v)) {
    path = v;
  } else {
    const parts = v.split("/").filter(Boolean);
    if (parts.length >= 2) path = `${parts[parts.length - 2]}/${parts[parts.length - 1]}`;
  }
  const clean = path.replace(/\.git$/, "").split("?")[0].split("#")[0];
  const [owner, repo, ...rest] = clean.split("/").filter(Boolean);
  if (!owner || !repo || rest.length) throw new Error("Use owner/repo or a github.com repository URL.");
  return { owner, repo };
}

async function ghFetch(url: string): Promise<any> {
  const res = await fetch(url, { headers: { "User-Agent": "Lotus-Mobile", Accept: "application/vnd.github+json" } });
  if (!res.ok) throw new Error(`GitHub ${res.status}`);
  return res.json();
}

export async function scanGitHubRepo(value: string, progress?: (msg: string) => void): Promise<ScanReport & { repo?: string; branch?: string; truncated?: boolean }> {
  const { owner, repo } = parseGithubRepo(value);
  const meta = await ghFetch(`https://api.github.com/repos/${owner}/${repo}`);
  const branch = meta.default_branch || "main";
  const tree = await ghFetch(`https://api.github.com/repos/${owner}/${repo}/git/trees/${encodeURIComponent(branch)}?recursive=1`);
  const blobs = (tree.tree || []).filter((n: any) => n.type === "blob" && TEXT_EXT.has(extOf(n.path)) && Number(n.size || 0) <= 200_000).slice(0, MAX_GH_FILES);
  const findings: Finding[] = [];
  let scanned = 0;
  let skipped = 0;
  for (const blob of blobs) {
    progress?.(`Scanning ${blob.path}`);
    try {
      const raw = `https://raw.githubusercontent.com/${owner}/${repo}/${encodeURIComponent(branch)}/${blob.path.split("/").map(encodeURIComponent).join("/")}`;
      const res = await fetch(raw, { headers: { "User-Agent": "Lotus-Mobile" } });
      if (!res.ok) { skipped += 1; continue; }
      const text = await res.text();
      scanContent(blob.path, text.slice(0, 200_000), findings);
      scanned += 1;
    } catch {
      skipped += 1;
    }
  }
  return {
    scanned,
    skipped,
    findings: findings.slice(0, 200),
    quarantined: 0,
    errors: [],
    repo: `${owner}/${repo}`,
    branch,
    truncated: !!tree.truncated,
    note: `Read-only GitHub scan of ${owner}/${repo}@${branch}.`,
  };
}

export async function breachCheck(email: string): Promise<{ breaches: string[]; pastes: number } | { error: string }> {
  const mail = email.trim();
  if (!mail) return { error: "Enter an email address first." };
  try {
    const res = await fetch(`https://haveibeenpwned.com/unifiedsearch/${encodeURIComponent(mail)}`, {
      headers: { "User-Agent": "Lotus-PrivacySweep", Accept: "application/json" },
    });
    if (res.status === 404) return { breaches: [], pastes: 0 };
    if (!res.ok) return { error: `HIBP ${res.status}` };
    const data = await res.json();
    return {
      breaches: (data?.Breaches || []).map((b: any) => b?.Name || "?").slice(0, 50),
      pastes: Array.isArray(data?.Pastes) ? data.Pastes.length : 0,
    };
  } catch (e: any) {
    return { error: e?.message || String(e) };
  }
}

export type Broker = { name: string; site: string; optout: string; contact: string };
export const BROKERS: Broker[] = [
  { name: "Acxiom", site: "acxiom.com", optout: "https://acxiom.com/optout", contact: "privacy@acxiom.com" },
  { name: "Epsilon", site: "epsilon.com", optout: "https://epsilon.com", contact: "privacy@epsilon.com" },
  { name: "Oracle Advertising", site: "oracle.com", optout: "https://oracle.com", contact: "privacy_ww@oracle.com" },
  { name: "Experian", site: "experian.com", optout: "https://experian.com/privacy/opting-out.html", contact: "privacy@experian.com" },
  { name: "Equifax", site: "equifax.com", optout: "https://equifax.com", contact: "privacy@equifax.com" },
  { name: "TransUnion", site: "transunion.com", optout: "https://transunion.com", contact: "privacy@transunion.com" },
  { name: "LexisNexis", site: "lexisnexis.com", optout: "https://lexisnexis.com", contact: "privacy@lexisnexis.com" },
  { name: "Whitepages", site: "whitepages.com", optout: "https://whitepages.com/suppression_requests", contact: "privacy@whitepages.com" },
  { name: "Spokeo", site: "spokeo.com", optout: "https://spokeo.com/optout", contact: "privacy@spokeo.com" },
  { name: "BeenVerified", site: "beenverified.com", optout: "https://beenverified.com/app/optout/search", contact: "privacy@beenverified.com" },
  { name: "Intelius", site: "intelius.com", optout: "https://intelius.com/optout", contact: "privacy@intelius.com" },
  { name: "PeopleFinder", site: "peoplefinder.com", optout: "https://peoplefinder.com/optout", contact: "privacy@peoplefinder.com" },
  { name: "FastPeopleSearch", site: "fastpeoplesearch.com", optout: "https://fastpeoplesearch.com/removal", contact: "privacy@fastpeoplesearch.com" },
  { name: "TruePeopleSearch", site: "truepeoplesearch.com", optout: "https://truepeoplesearch.com/removal", contact: "privacy@truepeoplesearch.com" },
  { name: "Radaris", site: "radaris.com", optout: "https://radaris.com/control/privacy", contact: "privacy@radaris.com" },
  { name: "MyLife", site: "mylife.com", optout: "https://mylife.com/ccpa", contact: "privacy@mylife.com" },
  { name: "Instant Checkmate", site: "instantcheckmate.com", optout: "https://instantcheckmate.com/optout", contact: "privacy@instantcheckmate.com" },
  { name: "TruthFinder", site: "truthfinder.com", optout: "https://truthfinder.com/opt-out", contact: "privacy@truthfinder.com" },
  { name: "US Search", site: "ussearch.com", optout: "https://ussearch.com/opt-out", contact: "privacy@ussearch.com" },
  { name: "Nuwber", site: "nuwber.com", optout: "https://nuwber.com/removal", contact: "privacy@nuwber.com" },
  { name: "ClustrMaps", site: "clustrmaps.com", optout: "https://clustrmaps.com/bl/opt-out", contact: "privacy@clustrmaps.com" },
  { name: "ThatsThem", site: "thatsthem.com", optout: "https://thatsthem.com/optout", contact: "privacy@thatsthem.com" },
  { name: "PeekYou", site: "peekyou.com", optout: "https://peekyou.com/about/contact/optout", contact: "privacy@peekyou.com" },
  { name: "Cyber Background Checks", site: "cyberbackgroundchecks.com", optout: "https://cyberbackgroundchecks.com/optout", contact: "privacy@cyberbackgroundchecks.com" },
  { name: "CocoFinder", site: "cocofinder.com", optout: "https://cocofinder.com/remove-my-info", contact: "privacy@cocofinder.com" },
];

export const PRIVACY_STATUSES = ["not_started", "requested", "confirmed"] as const;
export function nextPrivacyStatus(status: string): string {
  const i = PRIVACY_STATUSES.indexOf(status as any);
  return PRIVACY_STATUSES[(i + 1) % PRIVACY_STATUSES.length];
}
