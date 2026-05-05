// API 클라이언트 — Tauri 환경에서는 invoke, 브라우저(vite dev)에선 mock 데이터.

import type { CharEntry, WordEntry } from "../types";
import { MOCK_CHARS, MOCK_WORDS } from "../data/mock";

export interface SearchResults {
  chars: CharEntry[];
  words: WordEntry[];
}

const isTauri =
  typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;

async function tauriInvoke<T>(cmd: string, args: Record<string, unknown>): Promise<T> {
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke<T>(cmd, args);
}

// ─── Tauri 명령 래퍼 ─────────────────────────────────────────
export async function search(query: string, limit = 50): Promise<SearchResults> {
  if (isTauri) return tauriInvoke<SearchResults>("search", { query, limit });
  return mockSearch(query, limit);
}

export async function getChar(ch: string): Promise<CharEntry | null> {
  if (isTauri) return tauriInvoke<CharEntry | null>("get_char", { ch });
  return MOCK_CHARS[ch] ?? null;
}

export async function getWord(id: number): Promise<WordEntry | null> {
  if (isTauri) return tauriInvoke<WordEntry | null>("get_word", { id });
  return MOCK_WORDS.find((w) => w.id === id) ?? null;
}

export async function wordsByChar(ch: string, limit = 30): Promise<WordEntry[]> {
  if (isTauri) return tauriInvoke<WordEntry[]>("words_by_char", { ch, limit });
  return MOCK_WORDS.filter((w) => w.hanja?.includes(ch)).slice(0, limit);
}

// ─── Mock 검색 (브라우저 dev용) ───────────────────────────────
function mockSearch(query: string, _limit: number): SearchResults {
  const q = query.trim();
  if (!q) return { chars: [], words: [] };

  const isHanja = (c: string) => {
    const cp = c.codePointAt(0)!;
    return (
      (cp >= 0x3400 && cp <= 0x9fff) ||
      (cp >= 0xf900 && cp <= 0xfaff) ||
      (cp >= 0x20000 && cp <= 0x2ffff)
    );
  };
  const hasHanja = Array.from(q).some(isHanja);

  let chars: CharEntry[] = [];
  let words: WordEntry[] = [];

  if (hasHanja) {
    chars = Array.from(q)
      .filter(isHanja)
      .map((c) => MOCK_CHARS[c])
      .filter(Boolean);
    words = MOCK_WORDS.filter((w) => w.hanja === q || w.hanja?.includes(q));
  } else {
    chars = Object.values(MOCK_CHARS).filter(
      (c) => c.reading === q || c.pinyin?.startsWith(q),
    );
    words = MOCK_WORDS.filter(
      (w) => w.word_clean === q || w.word_clean.startsWith(q),
    );
  }
  return { chars, words };
}
