import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  Alert,
  FlatList,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  SafeAreaView,
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

export default function App() {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [draft, setDraft] = useState("");
  const [thinking, setThinking] = useState(false);
  const [key, setKeyState] = useState("");
  const [showSettings, setShowSettings] = useState(false);
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
      if (!k) setShowSettings(true);
    })();
  }, []);

  const send = useCallback(async () => {
    const text = draft.trim();
    if (!text || thinking) return;
    if (!key) {
      setShowSettings(true);
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
    setKeyState(keyDraft.trim());
    setShowSettings(false);
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

  const renderMsg = ({ item }: { item: Msg }) => (
    <View style={[styles.msg, item.role === "user" ? styles.user : styles.lotus]}>
      <Text style={styles.msgWho}>{item.role === "user" ? "You" : "Lotus"}</Text>
      <Text style={styles.msgText}>{item.content}</Text>
    </View>
  );

  const version = "0.1.0-beta.1";

  if (showSettings) {
    return (
      <SafeAreaView style={styles.root}>
        <StatusBar barStyle="light-content" />
        <View style={styles.header}>
          <Text style={styles.title}>◆ LOTUS</Text>
        </View>
        <View style={styles.settings}>
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
          <Pressable style={[styles.btn, styles.btnGhost]} onPress={clearHistory}>
            <Text style={styles.btnGhostText}>Clear chat history</Text>
          </Pressable>
          {!!key && (
            <Pressable
              style={[styles.btn, styles.btnGhost]}
              onPress={() => setShowSettings(false)}
            >
              <Text style={styles.btnGhostText}>Back to chat</Text>
            </Pressable>
          )}
          <View style={{ flex: 1 }} />
          <Text style={styles.foot}>v{version} · install {iid}</Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.root}>
      <StatusBar barStyle="light-content" />
      <View style={styles.header}>
        <View>
          <Text style={styles.title}>◆ LOTUS</Text>
          <Text style={styles.sub}>cybersecurity ai · mobile beta</Text>
        </View>
        <Pressable onPress={() => setShowSettings(true)} style={styles.gear}>
          <Text style={styles.gearText}>⚙</Text>
        </Pressable>
      </View>

      <FlatList
        ref={listRef}
        style={styles.list}
        contentContainerStyle={{ padding: 14, paddingBottom: 8 }}
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

      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : undefined}
        keyboardVerticalOffset={Platform.OS === "ios" ? 90 : 0}
      >
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
        <Text style={styles.footSmall}>v{version}</Text>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: C.bg },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: C.border,
    backgroundColor: "rgba(20, 12, 38, 0.9)",
  },
  title: { color: C.text, fontWeight: "800", fontSize: 18, letterSpacing: 3 },
  sub: { color: C.sub, fontSize: 11 },
  section: { color: C.accentLight, fontSize: 15, fontWeight: "700", marginBottom: 8 },
  gear: { padding: 6 },
  gearText: { color: C.accentLight, fontSize: 20 },
  list: { flex: 1 },
  empty: { color: C.sub, textAlign: "center", marginTop: 60, fontSize: 13 },
  thinking: { color: C.sub, fontStyle: "italic", marginTop: 8 },
  msg: { marginVertical: 5, padding: 10, borderRadius: 10, maxWidth: "88%" },
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
  settings: { padding: 20 },
  input: {
    color: C.text,
    backgroundColor: C.input,
    borderWidth: 1,
    borderColor: C.border,
    borderRadius: 10,
    padding: 12,
    marginTop: 10,
    fontSize: 14,
  },
  btn: {
    backgroundColor: C.accent,
    borderRadius: 10,
    padding: 13,
    alignItems: "center",
    marginTop: 14,
  },
  btnText: { color: "#fff", fontWeight: "700" },
  btnGhost: {
    backgroundColor: "transparent",
    borderWidth: 1,
    borderColor: C.border,
  },
  btnGhostText: { color: C.sub, fontWeight: "600" },
  foot: { color: "#5b4a86", fontSize: 11, textAlign: "center", paddingVertical: 14 },
  footSmall: { color: "#5b4a86", fontSize: 10, textAlign: "right", paddingRight: 12, paddingBottom: 6 },
});
