import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  Alert,
  FlatList,
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
import { generateReply } from "./gemini";
import { Msg, getKey, installId, loadHistory, saveHistory, setKey } from "./store";

const C = {
  bg: "#080512",
  panel: "rgba(23, 13, 43, 0.92)",
  border: "#4c2a7d",
  accent: "#8b5cf6",
  accentLight: "#a78bfa",
  text: "#e9d5ff",
  sub: "#a78bfa",
  input: "#130b24",
};

const VERSION = "0.1.0-beta.2";
const AI_STUDIO_URL = "https://aistudio.google.com/apikey";

type Section = "ask" | "logs" | "settings";

const SECTIONS: { id: Section; icon: string; label: string }[] = [
  { id: "ask", icon: "✦", label: "Ask" },
  { id: "logs", icon: "≡", label: "Logs" },
  { id: "settings", icon: "⚙", label: "Setup" },
];

export default function App() {
  const [section, setSection] = useState<Section>("ask");
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [draft, setDraft] = useState("");
  const [thinking, setThinking] = useState(false);
  const [key, setKeyState] = useState("");
  const [keyDraft, setKeyDraft] = useState("");
  const [iid, setIid] = useState("");
  const listRef = useRef<FlatList>(null);

  useEffect(() => {
    (async () => {
      setMsgs(await loadHistory());
      setIid(await installId());
      const k = await getKey();
      setKeyState(k);
      setKeyDraft(k);
      setSection(k ? "ask" : "settings");
    })();
  }, []);

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
      const reply = await generateReply(key, next);
      const updated: Msg[] = [...next, { role: "assistant", content: reply }];
      setMsgs(updated);
      saveHistory(updated);
    } catch (e: any) {
      const updated: Msg[] = [
        ...next,
        { role: "assistant", content: `I hit an error: ${e?.message || e}` },
      ];
      setMsgs(updated);
      saveHistory(updated);
    } finally {
      setThinking(false);
    }
  }, [draft, thinking, key, msgs]);

  const saveKey = useCallback(async () => {
    await setKey(keyDraft);
    const saved = keyDraft.trim();
    setKeyState(saved);
    if (saved) setSection("ask");
  }, [keyDraft]);

  const clearHistory = useCallback(() => {
    Alert.alert("Clear chat?", "Wipes the on-device conversation history.", [
      { text: "Cancel", style: "cancel" },
      {
        text: "Clear",
        style: "destructive",
        onPress: () => {
          setMsgs([]);
          saveHistory([]);
        },
      },
    ]);
  }, []);

  const openAIStudio = useCallback(() => {
    Linking.openURL(AI_STUDIO_URL).catch(() => {});
  }, []);

  const renderMsg = ({ item }: { item: Msg }) => (
    <View style={[styles.msg, item.role === "user" ? styles.user : styles.lotus]}>
      <Text style={styles.msgWho}>{item.role === "user" ? "You" : "Lotus"}</Text>
      <Text style={styles.msgText}>{item.content}</Text>
    </View>
  );

  const askPanel = (
    <KeyboardAvoidingView
      behavior={Platform.OS === "ios" ? "padding" : undefined}
      keyboardVerticalOffset={Platform.OS === "ios" ? 90 : 0}
      style={styles.panel}
    >
      <FlatList
        ref={listRef}
        style={styles.list}
        contentContainerStyle={{ padding: 12, paddingBottom: 8 }}
        data={msgs}
        keyExtractor={(_, i) => String(i)}
        renderItem={renderMsg}
        onContentSizeChange={() => listRef.current?.scrollToEnd({ animated: true })}
        ListEmptyComponent={
          <Text style={styles.empty}>
            Ask questions about security, code, or your systems.
          </Text>
        }
        ListFooterComponent={
          thinking ? <Text style={styles.thinking}>Lotus is typing…</Text> : undefined
        }
      />
      <View style={styles.composer}>
        <TextInput
          style={styles.composerInput}
          placeholder="Ask Lotus…"
          placeholderTextColor="#5b4a86"
          value={draft}
          onChangeText={setDraft}
          multiline
          editable={!thinking}
          onSubmitEditing={send}
        />
        <Pressable
          style={[styles.sendBtn, (thinking || !draft.trim()) && { opacity: 0.5 }]}
          onPress={send}
          disabled={thinking || !draft.trim()}
        >
          <Text style={styles.sendText}>➤</Text>
        </Pressable>
      </View>
      <Text style={styles.footSmall}>v{VERSION}</Text>
    </KeyboardAvoidingView>
  );

  const logsPanel = (
    <View style={styles.panel}>
      <FlatList
        style={styles.list}
        contentContainerStyle={{ padding: 12, paddingBottom: 18 }}
        data={msgs}
        keyExtractor={(_, i) => String(i)}
        renderItem={renderMsg}
        ListHeaderComponent={
          <View style={styles.logsHead}>
            <Text style={styles.section}>Logs / Memory</Text>
            <Text style={styles.sub}>
              On-device chat history · {msgs.length} message{msgs.length === 1 ? "" : "s"}
            </Text>
            <Pressable style={[styles.btn, styles.btnGhost, styles.logsClear]} onPress={clearHistory}>
              <Text style={styles.btnGhostText}>Clear history</Text>
            </Pressable>
          </View>
        }
        ListEmptyComponent={<Text style={styles.empty}>No messages yet.</Text>}
        ListFooterComponent={<Text style={styles.foot}>v{VERSION} · install {iid}</Text>}
      />
    </View>
  );

  const settingsPanel = (
    <ScrollView style={styles.panel} contentContainerStyle={styles.settingsScroll}>
      <Text style={styles.section}>Settings</Text>
      <Text style={styles.sub}>
        Gemini API key — stored only in this device's secure keychain.
      </Text>
      <TextInput
        style={styles.input}
        placeholder="AIza…"
        placeholderTextColor="#5b4a86"
        value={keyDraft}
        onChangeText={setKeyDraft}
        autoCapitalize="none"
        autoCorrect={false}
        secureTextEntry
      />
      <Pressable style={styles.btn} onPress={saveKey}>
        <Text style={styles.btnText}>Save key</Text>
      </Pressable>
      <Pressable style={[styles.btn, styles.btnGhost]} onPress={openAIStudio}>
        <Text style={styles.btnGhostText}>Get a Gemini API key in AI Studio</Text>
      </Pressable>
      <Pressable style={[styles.btn, styles.btnGhost]} onPress={clearHistory}>
        <Text style={styles.btnGhostText}>Clear chat history</Text>
      </Pressable>
      {!!key && (
        <Pressable style={[styles.btn, styles.btnGhost]} onPress={() => setSection("ask")}>
          <Text style={styles.btnGhostText}>Back to chat</Text>
        </Pressable>
      )}
      <Text style={styles.foot}>v{VERSION} · install {iid}</Text>
    </ScrollView>
  );

  return (
    <SafeAreaView style={styles.root}>
      <StatusBar barStyle="light-content" />
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
            <Pressable
              key={s.id}
              onPress={() => setSection(s.id)}
              style={[styles.orb, section === s.id && styles.orbActive]}
            >
              <Text style={[styles.orbIcon, section === s.id && styles.orbIconActive]}>
                {s.icon}
              </Text>
              <Text style={[styles.orbLabel, section === s.id && styles.orbLabelActive]}>
                {s.label}
              </Text>
            </Pressable>
          ))}
        </View>

        <View style={styles.content}>
          {section === "ask" && askPanel}
          {section === "logs" && logsPanel}
          {section === "settings" && settingsPanel}
        </View>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: C.bg },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: C.border,
    backgroundColor: "rgba(20, 12, 38, 0.9)",
  },
  title: { color: C.text, fontWeight: "800", fontSize: 17, letterSpacing: 3 },
  sub: { color: C.sub, fontSize: 11 },
  headInstall: { color: C.sub, fontSize: 10 },
  body: { flex: 1, flexDirection: "row" },
  rail: {
    width: 66,
    alignItems: "center",
    paddingVertical: 12,
    borderRightWidth: 1,
    borderRightColor: C.border,
    backgroundColor: "rgba(16, 9, 30, 0.9)",
  },
  orb: {
    width: 52,
    height: 52,
    borderRadius: 26,
    alignItems: "center",
    justifyContent: "center",
    marginVertical: 7,
    backgroundColor: C.panel,
    borderWidth: 1,
    borderColor: C.border,
  },
  orbActive: {
    borderColor: C.accent,
    backgroundColor: "rgba(139, 92, 246, 0.24)",
  },
  orbIcon: { color: C.sub, fontSize: 18, fontWeight: "800" },
  orbIconActive: { color: C.accentLight },
  orbLabel: { color: C.sub, fontSize: 8, marginTop: 2, fontWeight: "700" },
  orbLabelActive: { color: C.accentLight },
  content: { flex: 1 },
  panel: { flex: 1 },
  list: { flex: 1 },
  empty: { color: C.sub, textAlign: "center", marginTop: 60, fontSize: 13 },
  thinking: { color: C.sub, fontStyle: "italic", marginTop: 8 },
  msg: { marginVertical: 5, padding: 10, borderRadius: 10, maxWidth: "90%" },
  user: {
    alignSelf: "flex-end",
    backgroundColor: "#241243",
    borderWidth: 1,
    borderColor: "#55308f",
  },
  lotus: {
    alignSelf: "flex-start",
    backgroundColor: C.panel,
    borderWidth: 1,
    borderColor: C.border,
  },
  msgWho: { color: C.accentLight, fontSize: 10, fontWeight: "700", marginBottom: 3 },
  msgText: { color: C.text, fontSize: 14, lineHeight: 20 },
  composer: {
    flexDirection: "row",
    alignItems: "flex-end",
    padding: 10,
    borderTopWidth: 1,
    borderTopColor: C.border,
    backgroundColor: "rgba(20, 12, 38, 0.95)",
  },
  composerInput: {
    flex: 1,
    color: C.text,
    backgroundColor: C.input,
    borderWidth: 1,
    borderColor: C.border,
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingTop: 10,
    paddingBottom: 10,
    maxHeight: 120,
    fontSize: 14,
  },
  sendBtn: {
    marginLeft: 8,
    backgroundColor: C.accent,
    borderRadius: 10,
    paddingHorizontal: 16,
    paddingVertical: 11,
  },
  sendText: { color: "#fff", fontSize: 15, fontWeight: "700" },
  footSmall: { color: C.sub, fontSize: 10, textAlign: "center", paddingBottom: 6 },
  section: { color: C.accentLight, fontSize: 15, fontWeight: "700", marginBottom: 6 },
  logsHead: { marginBottom: 12 },
  logsClear: { alignSelf: "flex-start", marginTop: 8 },
  settingsScroll: { padding: 18, paddingBottom: 28 },
  input: {
    color: C.text,
    backgroundColor: C.input,
    borderWidth: 1,
    borderColor: C.border,
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 11,
    fontSize: 14,
    marginBottom: 10,
  },
  btn: {
    backgroundColor: C.accent,
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 11,
    alignItems: "center",
    marginBottom: 10,
  },
  btnText: { color: "#fff", fontWeight: "800", fontSize: 13 },
  btnGhost: {
    backgroundColor: "transparent",
    borderWidth: 1,
    borderColor: C.border,
  },
  btnGhostText: { color: C.text, fontWeight: "700", fontSize: 12 },
  foot: { color: C.sub, fontSize: 10, marginTop: 18 },
});
