import AsyncStorage from "@react-native-async-storage/async-storage";
import * as SecureStore from "expo-secure-store";

const KEY_HISTORY = "lotus.chat.history";
const KEY_INSTALL = "lotus.install_id";
const KEY_API = "lotus.gemini_key";
const KEY_THEME = "lotus.theme";
const KEY_PERSONALITY = "lotus.personality";
const KEY_PRIVACY = "lotus.privacy_brokers";

export type Msg = { role: "user" | "assistant"; content: string };
export type Personality = { archetype: string; notes: string };
export type PrivacyState = Record<string, string>;

export async function loadHistory(): Promise<Msg[]> {
  try {
    const raw = await AsyncStorage.getItem(KEY_HISTORY);
    return raw ? (JSON.parse(raw) as Msg[]) : [];
  } catch {
    return [];
  }
}

export async function saveHistory(msgs: Msg[]): Promise<void> {
  try {
    await AsyncStorage.setItem(KEY_HISTORY, JSON.stringify(msgs.slice(-200)));
  } catch {}
}

export async function getKey(): Promise<string> {
  return (await SecureStore.getItemAsync(KEY_API)) || "";
}

export async function setKey(key: string): Promise<void> {
  if (key.trim()) await SecureStore.setItemAsync(KEY_API, key.trim());
  else await SecureStore.deleteItemAsync(KEY_API);
}

export async function installId(): Promise<string> {
  let id = await AsyncStorage.getItem(KEY_INSTALL);
  if (!id) {
    id = Math.random().toString(16).slice(2, 14);
    await AsyncStorage.setItem(KEY_INSTALL, id);
  }
  return id;
}

export async function getTheme(): Promise<string> {
  return (await AsyncStorage.getItem(KEY_THEME)) || "purple";
}

export async function setTheme(theme: string): Promise<void> {
  await AsyncStorage.setItem(KEY_THEME, theme);
}

export async function getPersonality(): Promise<Personality> {
  try {
    const raw = await AsyncStorage.getItem(KEY_PERSONALITY);
    if (!raw) return { archetype: "neutral", notes: "" };
    const parsed = JSON.parse(raw);
    return {
      archetype: typeof parsed?.archetype === "string" ? parsed.archetype : "neutral",
      notes: typeof parsed?.notes === "string" ? parsed.notes : "",
    };
  } catch {
    return { archetype: "neutral", notes: "" };
  }
}

export async function setPersonality(personality: Personality): Promise<void> {
  await AsyncStorage.setItem(KEY_PERSONALITY, JSON.stringify(personality));
}

export async function getPrivacyState(): Promise<PrivacyState> {
  try {
    const raw = await AsyncStorage.getItem(KEY_PRIVACY);
    return raw ? (JSON.parse(raw) as PrivacyState) : {};
  } catch {
    return {};
  }
}

export async function setPrivacyState(state: PrivacyState): Promise<void> {
  await AsyncStorage.setItem(KEY_PRIVACY, JSON.stringify(state));
}
