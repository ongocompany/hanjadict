import { useEffect, useState } from "react";
import { CharCard } from "./components/CharCard";
import { WordCard } from "./components/WordCard";
import { SearchBar } from "./components/SearchBar";
import { ResultList } from "./components/ResultList";
import { search, type SearchResults } from "./lib/api";
import type { CharEntry, WordEntry } from "./types";

export type Selection =
  | { kind: "char"; data: CharEntry }
  | { kind: "word"; data: WordEntry };

export function App() {
  const [query, setQuery] = useState("國民");
  const [results, setResults] = useState<SearchResults>({ chars: [], words: [] });
  const [selection, setSelection] = useState<Selection | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    const t = setTimeout(async () => {
      try {
        const r = await search(query, 50);
        if (cancelled) return;
        setResults(r);
        // 자동 선택 — words가 있으면 첫 단어, 없으면 첫 한자
        if (r.words.length > 0) {
          setSelection({ kind: "word", data: r.words[0] });
        } else if (r.chars.length > 0) {
          setSelection({ kind: "char", data: r.chars[0] });
        } else {
          setSelection(null);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }, 80); // 디바운스
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
  }, [query]);

  return (
    <div className="app">
      <aside className="sidebar">
        <SearchBar value={query} onChange={setQuery} loading={loading} />
        <ResultList
          words={results.words}
          chars={results.chars}
          selection={selection}
          onSelect={setSelection}
        />
      </aside>
      <main className="main">
        {selection?.kind === "char" && (
          <CharCard entry={selection.data} onCharClick={(c) => setQuery(c)} />
        )}
        {selection?.kind === "word" && (
          <WordCard entry={selection.data} onCharClick={(c) => setQuery(c)} />
        )}
        {!selection && (
          <div className="empty-state">
            <div className="empty-state__hanja">字</div>
            <p>한자, 한글 음, 한국어 단어, 또는 병음을 입력하세요</p>
            <div className="empty-state__hint">
              <code>國民</code> · <code>국</code> · <code>민주주의</code> · <code>guó</code>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
