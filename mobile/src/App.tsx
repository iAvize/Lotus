import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Alert,
  AppState,
  BackHandler,
  FlatList,
  Keyboard,
  KeyboardAvoidingView,
  Linking,
  Platform,
  Pressable,
  SafeAreaView,
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { generateReply } from "./gemini";
import * as Clipboard from "expo-clipboard";
import * as Updates from "expo-updates";
import { ARCHETYPES, voicePrompt } from "./personality";
import { PATCH_NOTES } from "./patchNotes";
import {
  BROKERS,
  Finding,
  ScanReport,
  StorageReport,
  auditAppStorage,
  breachCheck,
  formatBytes,
  nextPrivacyStatus,
  pickAndScan,
  pickStorageAudit,
  scanAppStorage,
  scanGitHubRepo,
} from "./security";
import {
  Msg,
  Personality,
  PrivacyState,
  getKey,
  getPersonality,
  getPrivacyState,
  getTheme,
  installId,
  loadHistory,
  saveHistory,
  setKey,
  setPersonality,
  setPrivacyState,
  setTheme,
} from "./store";
import { PALETTES, Palette, THEME_NAMES, ThemeName } from "./theme";

const VERSION = "0.1.0-beta.15";
const AI_STUDIO_URL = "https://aistudio.google.com/apikey";
const SUPPORT_EMAIL = "bizwithavize@outlook.com";
const REPORT_ENDPOINT = `https://formsubmit.co/ajax/${SUPPORT_EMAIL}`;

type Section = "ask" | "files" | "privacy" | "personality" | "patches" | "settings";
type GithubReport = ScanReport & { repo?: string; branch?: string; truncated?: boolean };
type BreachResult = { breaches: string[]; pastes: number } | { error: string } | null;

const SECTIONS: { id: Section; icon: string; label: string }[] = [
  { id: "ask", icon: "✦", label: "Ask" },
  { id: "files", icon: "▣", label: "Files" },
  { id: "privacy", icon: "◉", label: "Privacy" },
  { id: "personality", icon: "☺", label: "Persona" },
  { id: "patches", icon: "≣", label: "Notes" },
  { id: "settings", icon: "⚙", label: "Settings" },
];

export default function App() {
  const [section, setSection] = useState<Section>("ask");
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [draft, setDraft] = useState("");
  const [thinking, setThinking] = useState(false);
  const [key, setKeyState] = useState("");
  const [keyDraft, setKeyDraft] = useState("");
  const [iid, setIid] = useState("");
  const [themeName, setThemeName] = useState<ThemeName>("purple");
  const [person, setPerson] = useState<Personality>({ archetype: "neutral", notes: "" });
  const [privacyState, setPrivacyStateLocal] = useState<PrivacyState>({});
  const [scanReport, setScanReport] = useState<ScanReport | GithubReport | null>(null);
  const [storageReport, setStorageReport] = useState<StorageReport | null>(null);
  const [storageBusy, setStorageBusy] = useState(false);
  const [storageProgress, setStorageProgress] = useState("");
  const [scanBusy, setScanBusy] = useState(false);
  const [scanProgress, setScanProgress] = useState("");
  const [githubInput, setGithubInput] = useState("");
  const [githubReport, setGithubReport] = useState<GithubReport | null>(null);
  const [githubBusy, setGithubBusy] = useState(false);
  const [privacyEmail, setPrivacyEmail] = useState("");
  const [breach, setBreach] = useState<BreachResult>(null);
  const [privacyBusy, setPrivacyBusy] = useState(false);
  const [lastError, setLastError] = useState("");
  const [reportOpen, setReportOpen] = useState(false);
  const [reportDraft, setReportDraft] = useState("");
  const [reportBusy, setReportBusy] = useState(false);
  const [reportStatus, setReportStatus] = useState("");
  const [updateReady, setUpdateReady] = useState(false);
  const [updLog, setUpdLog] = useState("");
  const [kbHeight, setKbHeight] = useState(0);
  const listRef = useRef<FlatList>(null);

  const C = PALETTES[themeName] || PALETTES.purple;
  const styles = useMemo(() => createStyles(C), [themeName]);

  // Check, fetch, and offer restart for an OTA update. Retries with backoff so a
  // slow or flaky network (service data) doesn't leave the app stale until the
  // next launch, and re-runs on foreground for the same reason.
  const checkForUpdates = useCallback(async (attempt = 1) => {
    if (!Updates.isEnabled) return;
    try {
      const check = await Updates.checkForUpdateAsync();
      if (check.isAvailable) {
        const fetched = await Updates.fetchUpdateAsync();
        const fetchedId = (fetched.isNew && fetched.manifest?.id) || "";
        const seenId = (await AsyncStorage.getItem("lotus:seen_update")) || "";
        // Offer the restart banner once per update id. Native launch-wait
        // applies it on the next cold start regardless, so never re-prompt —
        // that prevents banner loops if a restart lands on embedded again.
        if (fetched.isNew && fetchedId && fetchedId !== seenId) {
          await AsyncStorage.setItem("lotus:seen_update", fetchedId);
          setUpdateReady(true);
        }
      }
    } catch {
      if (attempt < 4) setTimeout(() => checkForUpdates(attempt + 1), 8000 * attempt);
    }
  }, []);

  useEffect(() => {
    (async () => {
      setMsgs(await loadHistory());
      setIid(await installId());
      const k = await getKey();
      setKeyState(k);
      setKeyDraft(k);
      const t = (await getTheme()) as ThemeName;
      if (PALETTES[t]) setThemeName(t);
      setPerson(await getPersonality());
      setPrivacyStateLocal(await getPrivacyState());
      setSection(k ? "ask" : "settings");
    })();
    const kbShow = Keyboard.addListener("keyboardDidShow", (e) => setKbHeight(e.endCoordinates.height));
    const kbHide = Keyboard.addListener("keyboardDidHide", () => setKbHeight(0));
    const fg = AppState.addEventListener("change", (s) => {
      if (s === "active") checkForUpdates();
    });
    if (Updates.isEnabled) {
      Updates.readLogEntriesAsync(86400000)
        .then((entries) => {
          const tail = entries.slice(-8)
            .map((e: any) => `${e.code || ""}:${String(e.message || "").slice(0, 90)}`)
            .join(" | ");
          if (tail) setUpdLog(tail);
        })
        .catch(() => {});
      checkForUpdates();
    }
    return () => { kbShow.remove(); kbHide.remove(); fg.remove(); };
  }, [checkForUpdates]);

  const openLink = useCallback((url: string) => {
    Linking.openURL(url).catch(() => {});
  }, []);

  const diagnostics = useCallback(() => [
    `Lotus ${VERSION}`,
    `Platform: ${Platform.OS} ${Platform.Version ?? "unknown"}`,
    `Install: ${iid || "…"}`,
    `Section: ${section}`,
    `Update: ${Updates.isEmbeddedLaunch ? "embedded" : "ota:" + (Updates.updateId || "?")}`,
    `Runtime: ${Updates.runtimeVersion || "?"}`,
    Updates.isEmergencyLaunch ? `Emergency: ${Updates.emergencyLaunchReason || "?"}` : "",
    updLog ? `Updates log: ${updLog}` : "",
    lastError ? `Last error: ${lastError}` : "",
  ].filter(Boolean).join("\n"), [iid, lastError, section, updLog]);

  const feedbackMailto = useCallback(() => {
    const body = `${diagnostics()}\n\nWhat happened?\n\nScreenshot/video: attach before sending — tap the paperclip in Mail. Lotus cannot attach files directly.\n\n`;
    return `mailto:${SUPPORT_EMAIL}?subject=${encodeURIComponent(`Lotus Beta feedback (v${VERSION})`)}&body=${encodeURIComponent(body)}`;
  }, [diagnostics]);

  const sendReport = useCallback(async () => {
    if (reportBusy) return;
    const body = `${diagnostics()}\n\n---- pasted error/crash report ----\n${reportDraft.trim() || "(none pasted)"}`;
    // Fire in the background — the UI confirms immediately; the request can
    // take seconds on the mail relay and nobody should wait on it.
    setReportStatus("Queued — sending in the background.");
    setReportDraft("");
    setReportOpen(false);
    fetch(REPORT_ENDPOINT, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        Origin: "https://github.com",
        Referer: "https://github.com/iAvize/Lotus",
      },
      body: JSON.stringify({
        _subject: `Lotus Beta crash report (v${VERSION})`,
        _captcha: "false",
        message: body,
      }),
    }).then(async (res) => {
      const data = await res.json().catch(() => ({}));
      setReportStatus(res.ok && String(data.success) === "true"
        ? "Sent — the developer will review it as soon as possible."
        : "Couldn't send — try again, or use Copy diagnostics and email it via Feedback.");
    }).catch(() => {
      setReportStatus("Couldn't send — check your connection, or use Copy diagnostics and email it via Feedback.");
    });
  }, [reportBusy, reportDraft, diagnostics]);

  const copyDiagnostics = useCallback(async () => {
    try {
      await Clipboard.setStringAsync(diagnostics());
      Alert.alert("Copied", "Diagnostics copied — paste into feedback or report.");
    } catch {
      Alert.alert("Copy failed", "Could not copy diagnostics.");
    }
  }, [diagnostics]);

  const send = useCallback(async () => {
    const text = draft.trim();
    if (!text || thinking) return;
    if (!key) {
      setSection("settings");
      return;
    }
    const next: Msg[] = [...msgs, { role: "user", content: text }];
    setMsgs(next);
    setDraft("");
    setThinking(true);
    try {
      const reply = await generateReply(key, next, voicePrompt(person));
      const updated: Msg[] = [...next, { role: "assistant", content: reply }];
      setMsgs(updated);
      saveHistory(updated);
    } catch (e: any) {
      setLastError(`chat: ${e?.message || e}`);
      const updated: Msg[] = [...next, { role: "assistant", content: `I hit an error: ${e?.message || e}` }];
      setMsgs(updated);
      saveHistory(updated);
    } finally {
      setThinking(false);
      if (Platform.OS === "android") Keyboard.dismiss();
    }
  }, [draft, thinking, key, msgs, person]);

  const saveKey = useCallback(async () => {
    await setKey(keyDraft);
    const saved = keyDraft.trim();
    setKeyState(saved);
    if (saved) setSection("ask");
  }, [keyDraft]);

  const clearHistory = useCallback(() => {
    Alert.alert("Clear chat?", "Wipes the on-device conversation history.", [
      { text: "Cancel", style: "cancel" },
      { text: "Clear", style: "destructive", onPress: () => { setMsgs([]); saveHistory([]); } },
    ]);
  }, []);

  const chooseTheme = useCallback((t: ThemeName) => {
    setThemeName(t);
    setTheme(t).catch(() => {});
  }, []);

  const savePerson = useCallback(async () => {
    const next = { archetype: person.archetype || "neutral", notes: person.notes.slice(0, 800) };
    setPerson(next);
    await setPersonality(next);
  }, [person]);

  const resetPerson = useCallback(async () => {
    const next = { archetype: "neutral", notes: "" };
    setPerson(next);
    await setPersonality(next);
  }, []);

  const runFilesScan = useCallback(async (kind: "app" | "pick") => {
    setScanBusy(true);
    setScanProgress(kind === "app" ? "Scanning app storage…" : "Opening Files picker…");
    setScanReport(null);
    try {
      const report = kind === "app" ? await scanAppStorage(setScanProgress) : await pickAndScan(setScanProgress);
      setScanReport(report);
      if (!report) setScanProgress("No files selected.");
    } catch (e: any) {
      setLastError(`files scan: ${e?.message || e}`);
      setScanReport({ scanned: 0, skipped: 0, findings: [], quarantined: 0, errors: [e?.message || String(e)] });
    } finally {
      setScanBusy(false);
      setScanProgress("");
    }
  }, []);

  const runStorageAudit = useCallback(async (kind: "app" | "pick") => {
    setStorageBusy(true);
    setStorageProgress(kind === "app" ? "Measuring Lotus storage…" : "Opening Files picker…");
    setStorageReport(null);
    try {
      const report = kind === "app" ? await auditAppStorage(setStorageProgress) : await pickStorageAudit(setStorageProgress);
      setStorageReport(report);
      if (!report) setStorageProgress("No files selected.");
    } catch (e: any) {
      setLastError(`storage audit: ${e?.message || e}`);
      setStorageReport({ deviceTotal: undefined, deviceFree: undefined, roots: [], picked: [], largest: [], errors: [e?.message || String(e)], note: "Storage audit failed." });
    } finally {
      setStorageBusy(false);
      setStorageProgress("");
    }
  }, []);

  const openSystemSettings = useCallback((path: string) => {
    if (Platform.OS === "android") {
      Linking.openSettings().catch(() => Alert.alert("Open Settings", "Open Settings → Apps → Lotus Beta manually."));
      return;
    }
    Linking.openURL(`App-Prefs:${path}`).catch(() => {
      Linking.openURL("App-Prefs:").catch(() => Alert.alert("Open Settings", "Go to Settings → General → iPhone Storage manually."));
    });
  }, []);

  // Android hardware back returns to Ask first; from Ask it exits normally.
  useEffect(() => {
    if (Platform.OS !== "android") return;
    const sub = BackHandler.addEventListener("hardwareBackPress", () => {
      if (section !== "ask") {
        setSection("ask");
        return true;
      }
      return false;
    });
    return () => sub.remove();
  }, [section]);

  const runGithubScan = useCallback(async () => {
    if (!githubInput.trim() || githubBusy) return;
    setGithubBusy(true);
    setScanProgress("Scanning GitHub repo…");
    setGithubReport(null);
    try {
      setGithubReport(await scanGitHubRepo(githubInput, setScanProgress));
    } catch (e: any) {
      setLastError(`github scan: ${e?.message || e}`);
      setGithubReport({ scanned: 0, skipped: 0, findings: [], quarantined: 0, errors: [e?.message || String(e)] });
    } finally {
      setGithubBusy(false);
      setScanProgress("");
    }
  }, [githubInput, githubBusy]);

  const checkBreaches = useCallback(async () => {
    if (privacyBusy) return;
    setPrivacyBusy(true);
    setBreach(null);
    setBreach(await breachCheck(privacyEmail));
    setPrivacyBusy(false);
  }, [privacyEmail, privacyBusy]);

  const cycleBroker = useCallback(async (name: string) => {
    const next = { ...privacyState };
    next[name] = nextPrivacyStatus(next[name] || "not_started");
    setPrivacyStateLocal(next);
    await setPrivacyState(next);
  }, [privacyState]);

  const renderMsg = ({ item }: { item: Msg }) => (
    <View style={[styles.msg, item.role === "user" ? styles.user : styles.lotus]}>
      <Text style={styles.msgWho}>{item.role === "user" ? "You" : "Lotus"}</Text>
      <Text style={styles.msgText}>{item.content}</Text>
    </View>
  );

  const sevColor = (s: string) => (s === "high" ? "#f87171" : s === "medium" ? "#fbbf24" : "#38bdf8");
  const renderFinding = (f: Finding, i: number) => (
    <View key={`${f.path}-${i}`} style={styles.finding}>
      <Text style={[styles.findingKind, { color: sevColor(f.severity) }]}>{f.severity.toUpperCase()} · {f.kind}</Text>
      <Text style={styles.findingPath}>{f.path}</Text>
      <Text style={styles.findingDetail}>{f.detail}</Text>
    </View>
  );

  const reportSummary = (r: ScanReport | GithubReport | null) => {
    if (!r) return null;
    return (
      <View style={styles.reportBox}>
        <Text style={styles.reportText}>
          scanned {r.scanned} · skipped {r.skipped} · findings {r.findings.length} · quarantined {r.quarantined}
        </Text>
        {"repo" in r && r.repo ? <Text style={styles.reportText}>{r.repo}@{r.branch}{r.truncated ? " · tree truncated" : ""}</Text> : null}
        {r.note ? <Text style={styles.reportText}>{r.note}</Text> : null}
        {r.errors?.length ? <Text style={styles.reportText}>errors: {r.errors.join("; ")}</Text> : null}
      </View>
    );
  };

  const storageSummary = (r: StorageReport | null) => {
    if (!r) return null;
    return (
      <View style={styles.reportBox}>
        <Text style={styles.reportText}>device total {formatBytes(r.deviceTotal)} · free {formatBytes(r.deviceFree)}</Text>
        {r.roots.map((root) => <Text key={root.path} style={styles.reportText}>• {root.label}: {formatBytes(root.size)} · {root.files} files</Text>)}
        {!!r.picked.length && <Text style={styles.reportText}>picked items: {r.picked.length}</Text>}
        {r.picked.slice(0, 12).map((item, i) => <Text key={`${item.path}-${i}`} style={styles.reportText}>• {item.name}: {formatBytes(item.size)}</Text>)}
        {!!r.largest.length && <Text style={styles.reportText}>largest Lotus files</Text>}
        {r.largest.slice(0, 10).map((item, i) => <Text key={`${item.path}-${i}`} style={styles.reportText}>• {item.name}: {formatBytes(item.size)}</Text>)}
        {r.note ? <Text style={styles.reportText}>{r.note}</Text> : null}
        {r.errors.length ? <Text style={styles.reportText}>errors: {r.errors.join("; ")}</Text> : null}
      </View>
    );
  };

  const askInner = (
    <>
      <FlatList
        ref={listRef}
        style={styles.list}
        contentContainerStyle={{ padding: 12, paddingBottom: 8 }}
        data={msgs}
        keyExtractor={(_, i) => String(i)}
        renderItem={renderMsg}
        onContentSizeChange={() => listRef.current?.scrollToEnd({ animated: true })}
        ListEmptyComponent={<Text style={styles.empty}>Ask questions about security, code, or your systems.</Text>}
        ListFooterComponent={thinking ? <Text style={styles.thinking}>Lotus is typing…</Text> : undefined}
      />
      <View style={styles.composer}>
        <TextInput style={styles.composerInput} placeholder="Ask Lotus…" placeholderTextColor="#5b4a86" value={draft} onChangeText={setDraft} multiline editable={!thinking} onSubmitEditing={send} />
        <Pressable style={[styles.sendBtn, (thinking || !draft.trim()) && { opacity: 0.5 }]} onPress={send} disabled={thinking || !draft.trim()}>
          <Text style={styles.sendText}>➤</Text>
        </Pressable>
      </View>
      <Text style={styles.footSmall}>v{VERSION}</Text>
    </>
  );
  // Android 16 edge-to-edge no longer resizes the window for the keyboard, so
  // KeyboardAvoidingView can't see the inset — pad the panel by the reported
  // keyboard height instead. iOS keeps the avoiding view.
  const askPanel = Platform.OS === "android" ? (
    <View style={[styles.panel, { paddingBottom: kbHeight }]}>{askInner}</View>
  ) : (
    <KeyboardAvoidingView behavior="padding" keyboardVerticalOffset={90} style={styles.panel}>
      {askInner}
    </KeyboardAvoidingView>
  );

  const filesPanel = (
    <ScrollView style={styles.panel} contentContainerStyle={styles.pad}>
      <Text style={styles.section}>Files</Text>
      <Text style={styles.sub}>Scan app storage or pick files from the Files app. Suspicious app files are quarantined inside Lotus storage.</Text>
      <View style={styles.chips}>
        <Pressable style={[styles.btn, scanBusy && { opacity: 0.5 }]} onPress={() => runFilesScan("app")} disabled={scanBusy}>
          <Text style={styles.btnText}>Scan app storage</Text>
        </Pressable>
        <Pressable style={[styles.btn, styles.btnGhost, scanBusy && { opacity: 0.5 }]} onPress={() => runFilesScan("pick")} disabled={scanBusy}>
          <Text style={styles.btnGhostText}>Pick files to scan</Text>
        </Pressable>
      </View>
      {!!scanProgress && <Text style={styles.progress}>{scanProgress}</Text>}
      {reportSummary(scanReport)}
      {(scanReport?.findings || []).slice(0, 80).map(renderFinding)}

      <Text style={styles.section}>Storage audit</Text>
      <Text style={styles.sub}>Audit storage Lotus can see. Mobile OSes do not let apps list other apps or uninstall them.</Text>
      <View style={styles.chips}>
        <Pressable style={[styles.btn, styles.btnGhost, storageBusy && { opacity: 0.5 }]} onPress={() => runStorageAudit("app")} disabled={storageBusy}>
          <Text style={styles.btnGhostText}>Audit Lotus storage</Text>
        </Pressable>
        <Pressable style={[styles.btn, styles.btnGhost, storageBusy && { opacity: 0.5 }]} onPress={() => runStorageAudit("pick")} disabled={storageBusy}>
          <Text style={styles.btnGhostText}>Audit picked files</Text>
        </Pressable>
        <Pressable style={[styles.btn, styles.btnGhost]} onPress={() => openSystemSettings("General&path=STORAGE")}>
          <Text style={styles.btnGhostText}>{Platform.OS === "android" ? "App settings" : "iPhone Storage"}</Text>
        </Pressable>
        <Pressable style={[styles.btn, styles.btnGhost]} onPress={() => Platform.OS === "android" ? openLink("https://play.google.com") : openSystemSettings("STORE")}>
          <Text style={styles.btnGhostText}>{Platform.OS === "android" ? "Play Store" : "App Store"}</Text>
        </Pressable>
      </View>
      {!!storageProgress && <Text style={styles.progress}>{storageProgress}</Text>}
      {storageSummary(storageReport)}
      <Text style={styles.foot}>External storage appears only if the OS exposes it through the file picker.</Text>
    </ScrollView>
  );

  const privacyPanel = (
    <ScrollView style={styles.panel} contentContainerStyle={styles.pad}>
      <Text style={styles.section}>Privacy Sweep</Text>
      <Text style={styles.sub}>Check breach exposure, then track data-broker opt-outs. Statuses stay on this device.</Text>
      <TextInput style={styles.input} placeholder="you@example.com" placeholderTextColor="#5b4a86" value={privacyEmail} onChangeText={setPrivacyEmail} autoCapitalize="none" autoCorrect={false} keyboardType="email-address" />
      <Pressable style={[styles.btn, privacyBusy && { opacity: 0.5 }]} onPress={checkBreaches} disabled={privacyBusy}>
        <Text style={styles.btnText}>{privacyBusy ? "Checking…" : "Check breaches"}</Text>
      </Pressable>
      {breach ? (
        <View style={styles.reportBox}>
          {"error" in breach ? <Text style={styles.reportText}>error: {breach.error}</Text> : (
            <>
              <Text style={styles.reportText}>breaches: {breach.breaches.length} · pastes: {breach.pastes}</Text>
              {breach.breaches.slice(0, 12).map((b) => <Text key={b} style={styles.reportText}>• {b}</Text>)}
            </>
          )}
        </View>
      ) : null}
      <Text style={styles.section}>Data brokers</Text>
      {BROKERS.map((b) => {
        const status = privacyState[b.name] || "not_started";
        return (
          <View key={b.name} style={styles.brokerRow}>
            <View style={{ flex: 1 }}>
              <Text style={styles.brokerName}>{b.name}</Text>
              <Text style={styles.brokerStatus}>{status.replace("_", " ")}</Text>
            </View>
            <Pressable style={styles.statusBtn} onPress={() => cycleBroker(b.name)}>
              <Text style={styles.statusText}>cycle</Text>
            </Pressable>
            <Pressable style={styles.statusBtn} onPress={() => openLink(b.optout)}>
              <Text style={styles.statusText}>open</Text>
            </Pressable>
          </View>
        );
      })}
    </ScrollView>
  );

  const personalityPanel = (
    <ScrollView style={styles.panel} contentContainerStyle={styles.pad}>
      <Text style={styles.section}>Personality</Text>
      <Text style={styles.sub}>Voice preset for Ask Lotus. Security reports stay literal and professional.</Text>
      <View style={styles.archRow}>
        {Object.entries(ARCHETYPES).map(([id, a]) => (
          <Pressable key={id} style={[styles.archBtn, person.archetype === id && styles.archBtnActive]} onPress={() => setPerson({ ...person, archetype: id })}>
            <Text style={[styles.archText, person.archetype === id && styles.archTextActive]}>{a.label}</Text>
          </Pressable>
        ))}
      </View>
      <TextInput style={[styles.input, styles.noteInput]} placeholder="Style notes, e.g. terse, no slang, explain like I'm senior" placeholderTextColor="#5b4a86" value={person.notes} onChangeText={(notes) => setPerson({ ...person, notes })} multiline />
      <View style={styles.chips}>
        <Pressable style={styles.btn} onPress={savePerson}><Text style={styles.btnText}>Save personality</Text></Pressable>
        <Pressable style={[styles.btn, styles.btnGhost]} onPress={resetPerson}><Text style={styles.btnGhostText}>Reset</Text></Pressable>
      </View>
    </ScrollView>
  );

  const patchesPanel = (
    <ScrollView style={styles.panel} contentContainerStyle={styles.pad}>
      <Text style={styles.section}>Patch Notes</Text>
      {PATCH_NOTES.map((r) => (
        <View key={r.version} style={styles.patchCard}>
          <Text style={styles.patchVersion}>{r.version}</Text>
          <Text style={styles.patchDate}>{r.date}</Text>
          {r.notes.map((n, i) => <Text key={i} style={styles.patchNote}>• {n}</Text>)}
        </View>
      ))}
    </ScrollView>
  );

  const settingsPanel = (
    <ScrollView style={styles.panel} contentContainerStyle={styles.settingsScroll}>
      <Text style={styles.section}>Settings</Text>
      <Text style={styles.sub}>Gemini API key — stored only in this device's secure keychain.</Text>
      <TextInput style={styles.input} placeholder="AIza…" placeholderTextColor="#5b4a86" value={keyDraft} onChangeText={setKeyDraft} autoCapitalize="none" autoCorrect={false} secureTextEntry />
      <Pressable style={styles.btn} onPress={saveKey}><Text style={styles.btnText}>Save key</Text></Pressable>
      <Pressable style={[styles.btn, styles.btnGhost]} onPress={() => openLink(AI_STUDIO_URL)}><Text style={styles.btnGhostText}>Get a Gemini API key in AI Studio</Text></Pressable>

      <Text style={styles.section}>Theme</Text>
      <View style={styles.swatches}>
        {THEME_NAMES.map((t) => (
          <Pressable key={t} onPress={() => chooseTheme(t)} style={[styles.swatch, { backgroundColor: PALETTES[t].accent }, themeName === t && styles.swatchActive]} />
        ))}
      </View>

      <Text style={styles.section}>Support</Text>
      {!!lastError && <Text style={styles.reportText}>last error: {lastError}</Text>}
      <View style={styles.chips}>
        <Pressable style={[styles.btn, styles.btnGhost]} onPress={() => setReportOpen(!reportOpen)}><Text style={styles.btnGhostText}>Report error</Text></Pressable>
        <Pressable style={[styles.btn, styles.btnGhost]} onPress={() => openLink(feedbackMailto())}><Text style={styles.btnGhostText}>Feedback</Text></Pressable>
        <Pressable style={[styles.btn, styles.btnGhost]} onPress={copyDiagnostics}><Text style={styles.btnGhostText}>Copy diagnostics</Text></Pressable>
      </View>
      {reportOpen && (
        <View>
          <TextInput
            style={[styles.input, { minHeight: 90, textAlignVertical: "top" }]}
            placeholder="Paste the error code or crash report here"
            placeholderTextColor="#5b4a86"
            value={reportDraft}
            onChangeText={setReportDraft}
            multiline
            autoCapitalize="none"
            autoCorrect={false}
          />
          <View style={styles.chips}>
            <Pressable style={[styles.btn, reportBusy && { opacity: 0.5 }]} onPress={sendReport} disabled={reportBusy}>
              <Text style={styles.btnText}>{reportBusy ? "Sending…" : "Send report"}</Text>
            </Pressable>
            <Pressable style={[styles.btn, styles.btnGhost]} onPress={() => setReportOpen(false)}><Text style={styles.btnGhostText}>Cancel</Text></Pressable>
          </View>
        </View>
      )}
      {!!reportStatus && <Text style={styles.sub}>{reportStatus}</Text>}
      <Text style={styles.sub}>Report error sends straight to the developer — paste the error and tap Send, done in seconds. Feedback is for detailed notes; it opens Mail so you can attach screenshots/videos (optional).</Text>

      <Text style={styles.section}>GitHub scanner</Text>
      <Text style={styles.sub}>Read-only public repo scan for secrets and risky code patterns.</Text>
      <TextInput style={styles.input} placeholder="owner/repo or github.com URL" placeholderTextColor="#5b4a86" value={githubInput} onChangeText={setGithubInput} autoCapitalize="none" autoCorrect={false} />
      <Pressable style={[styles.btn, (githubBusy || !githubInput.trim()) && { opacity: 0.5 }]} onPress={runGithubScan} disabled={githubBusy || !githubInput.trim()}>
        <Text style={styles.btnText}>{githubBusy ? "Scanning…" : "Scan repo"}</Text>
      </Pressable>
      {reportSummary(githubReport)}
      {(githubReport?.findings || []).slice(0, 40).map(renderFinding)}

      <View style={styles.chips}>
        <Pressable style={[styles.btn, styles.btnGhost]} onPress={clearHistory}><Text style={styles.btnGhostText}>Clear chat history</Text></Pressable>
        {!!key && <Pressable style={[styles.btn, styles.btnGhost]} onPress={() => setSection("ask")}><Text style={styles.btnGhostText}>Back to chat</Text></Pressable>}
      </View>
      <Text style={styles.foot}>v{VERSION} · install {iid}</Text>
    </ScrollView>
  );

  return (
    <SafeAreaView style={[styles.root, Platform.OS === "android" && { paddingTop: StatusBar.currentHeight ?? 0 }]}>
      <StatusBar barStyle="light-content" />
      {updateReady && (
        <Pressable style={styles.updateBanner} onPress={() => Updates.reloadAsync()}>
          <Text style={styles.updateBannerText}>Update ready — tap to restart and apply</Text>
        </Pressable>
      )}
      <View style={styles.header}>
        <View>
          <Text style={styles.title}>◆ LOTUS</Text>
          <Text style={styles.sub}>cybersecurity ai · mobile beta</Text>
        </View>
        <Text style={styles.headInstall}>#{iid || "…"}</Text>
      </View>
      <View style={styles.body}>
        <View style={styles.rail}>
          {SECTIONS.map((s) => (
            <Pressable key={s.id} onPress={() => setSection(s.id)} style={[styles.orb, section === s.id && styles.orbActive]}>
              <Text style={[styles.orbIcon, section === s.id && styles.orbIconActive]}>{s.icon}</Text>
              <Text style={[styles.orbLabel, section === s.id && styles.orbLabelActive]}>{s.label}</Text>
            </Pressable>
          ))}
        </View>
        <View style={styles.content}>
          {section === "ask" && askPanel}
          {section === "files" && filesPanel}
          {section === "privacy" && privacyPanel}
          {section === "personality" && personalityPanel}
          {section === "patches" && patchesPanel}
          {section === "settings" && settingsPanel}
        </View>
      </View>
    </SafeAreaView>
  );
}

function createStyles(c: Palette) {
  return StyleSheet.create({
    root: { flex: 1, backgroundColor: c.bg },
    header: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: 14, paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: c.border, backgroundColor: "rgba(20, 12, 38, 0.9)" },
    title: { color: c.text, fontWeight: "800", fontSize: 17, letterSpacing: 3 },
    sub: { color: c.sub, fontSize: 11, marginBottom: 8 },
    headInstall: { color: c.sub, fontSize: 10 },
    body: { flex: 1, flexDirection: "row" },
    rail: { width: 72, alignItems: "center", paddingVertical: 10, borderRightWidth: 1, borderRightColor: c.border, backgroundColor: "rgba(16, 9, 30, 0.9)" },
    orb: { width: 48, height: 48, borderRadius: 24, alignItems: "center", justifyContent: "center", marginVertical: 5, backgroundColor: c.panel, borderWidth: 1, borderColor: c.border },
    orbActive: { borderColor: c.accent, backgroundColor: "rgba(139, 92, 246, 0.24)" },
    orbIcon: { color: c.sub, fontSize: 16, fontWeight: "800" },
    orbIconActive: { color: c.accentLight },
    orbLabel: { color: c.sub, fontSize: 7, marginTop: 1, fontWeight: "700" },
    orbLabelActive: { color: c.accentLight },
    content: { flex: 1 },
    panel: { flex: 1 },
    pad: { padding: 14, paddingBottom: 24 },
    settingsScroll: { padding: 18, paddingBottom: 28 },
    list: { flex: 1 },
    empty: { color: c.sub, textAlign: "center", marginTop: 60, fontSize: 13 },
    thinking: { color: c.sub, fontStyle: "italic", marginTop: 8 },
    msg: { marginVertical: 5, padding: 10, borderRadius: 10, maxWidth: "90%" },
    user: { alignSelf: "flex-end", backgroundColor: "#241243", borderWidth: 1, borderColor: "#55308f" },
    lotus: { alignSelf: "flex-start", backgroundColor: c.panel, borderWidth: 1, borderColor: c.border },
    msgWho: { color: c.accentLight, fontSize: 10, fontWeight: "700", marginBottom: 3 },
    msgText: { color: c.text, fontSize: 14, lineHeight: 20 },
    composer: { flexDirection: "row", alignItems: "flex-end", padding: 10, borderTopWidth: 1, borderTopColor: c.border, backgroundColor: "rgba(20, 12, 38, 0.95)" },
    composerInput: { flex: 1, color: c.text, backgroundColor: c.input, borderWidth: 1, borderColor: c.border, borderRadius: 10, paddingHorizontal: 12, paddingTop: 10, paddingBottom: 10, maxHeight: 120, fontSize: 14 },
    sendBtn: { marginLeft: 8, backgroundColor: c.accent, borderRadius: 10, paddingHorizontal: 16, paddingVertical: 11 },
    sendText: { color: "#fff", fontSize: 15, fontWeight: "700" },
    footSmall: { color: c.sub, fontSize: 10, textAlign: "center", paddingBottom: 6 },
    updateBanner: { backgroundColor: c.accent, paddingVertical: 10, paddingHorizontal: 14 },
    updateBannerText: { color: "#fff", fontWeight: "800", fontSize: 13, textAlign: "center" },
    foot: { color: c.sub, fontSize: 10, marginTop: 16 },
    section: { color: c.accentLight, fontSize: 15, fontWeight: "700", marginBottom: 6, marginTop: 8 },
    input: { color: c.text, backgroundColor: c.input, borderWidth: 1, borderColor: c.border, borderRadius: 10, paddingHorizontal: 12, paddingVertical: 11, fontSize: 14, marginBottom: 10 },
    noteInput: { minHeight: 84, textAlignVertical: "top" },
    btn: { backgroundColor: c.accent, borderRadius: 10, paddingHorizontal: 14, paddingVertical: 11, alignItems: "center", marginBottom: 10 },
    btnText: { color: "#fff", fontWeight: "800", fontSize: 13 },
    btnGhost: { backgroundColor: "transparent", borderWidth: 1, borderColor: c.border },
    btnGhostText: { color: c.text, fontWeight: "700", fontSize: 12 },
    chips: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginBottom: 10 },
    progress: { color: c.sub, fontStyle: "italic", marginBottom: 8 },
    reportBox: { borderWidth: 1, borderColor: c.border, borderRadius: 10, padding: 10, marginBottom: 10, backgroundColor: c.panel },
    reportText: { color: c.text, fontSize: 12, marginBottom: 3 },
    finding: { borderWidth: 1, borderColor: c.border, borderRadius: 8, padding: 8, marginBottom: 7, backgroundColor: c.panel },
    findingKind: { fontSize: 10, fontWeight: "800", marginBottom: 2 },
    findingPath: { color: c.text, fontSize: 12, fontWeight: "700" },
    findingDetail: { color: c.sub, fontSize: 11, marginTop: 2 },
    brokerRow: { flexDirection: "row", alignItems: "center", borderBottomWidth: 1, borderBottomColor: c.border, paddingVertical: 8 },
    brokerName: { color: c.text, fontSize: 13, fontWeight: "700" },
    brokerStatus: { color: c.sub, fontSize: 11, marginTop: 2 },
    statusBtn: { borderWidth: 1, borderColor: c.border, borderRadius: 8, paddingHorizontal: 8, paddingVertical: 6, marginLeft: 6 },
    statusText: { color: c.text, fontSize: 10, fontWeight: "800" },
    archRow: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginBottom: 10 },
    archBtn: { borderWidth: 1, borderColor: c.border, borderRadius: 16, paddingHorizontal: 12, paddingVertical: 8, backgroundColor: c.panel },
    archBtnActive: { borderColor: c.accent, backgroundColor: "rgba(139, 92, 246, 0.24)" },
    archText: { color: c.sub, fontSize: 11, fontWeight: "800" },
    archTextActive: { color: c.accentLight },
    patchCard: { borderWidth: 1, borderColor: c.border, borderRadius: 10, padding: 12, marginBottom: 10, backgroundColor: c.panel },
    patchVersion: { color: c.text, fontSize: 14, fontWeight: "800" },
    patchDate: { color: c.sub, fontSize: 11, marginBottom: 6 },
    patchNote: { color: c.text, fontSize: 12, lineHeight: 18, marginBottom: 3 },
    swatches: { flexDirection: "row", gap: 10, marginBottom: 12 },
    swatch: { width: 34, height: 34, borderRadius: 17, borderWidth: 1, borderColor: c.border },
    swatchActive: { borderColor: c.text, borderWidth: 3 },
  });
}
