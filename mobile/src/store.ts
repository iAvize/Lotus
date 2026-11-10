/** Local persistence — chat history + install id. Key lives in
 *  expo-secure-store (iOS Keychain), history in AsyncStorage. */
import AsyncStorage from "@react-native-async-storage/async-storage";
import * as SecureStore from "expo-secure-store";

const KEY_HISTORY = "lotus.chat.history";
const KEY_INSTALL = "lotus.install_id";
const KEY_API = "lotus.gemini_key";

export type Msg = { role: "user" | "assistant"; content: string };

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
