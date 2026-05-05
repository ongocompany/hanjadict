import type { CharEntry, WordEntry } from "../types";
import type { Selection } from "../App";

interface Props {
  words: WordEntry[];
  chars: CharEntry[];
  selection: Selection | null;
  onSelect: (s: Selection) => void;
}

export function ResultList({ words, chars, selection, onSelect }: Props) {
  const empty = words.length === 0 && chars.length === 0;

  return (
    <div className="result-list">
      {empty && <div className="result-list__empty">검색어를 입력하세요</div>}

      {words.length > 0 && (
        <section className="result-list__section">
          <h3 className="result-list__heading">단어 ({words.length})</h3>
          {words.map((w) => {
            const active = selection?.kind === "word" && selection.data.id === w.id;
            return (
              <button
                key={w.id}
                type="button"
                className={`result-row ${active ? "result-row--active" : ""}`}
                onClick={() => onSelect({ kind: "word", data: w })}
              >
                <div className="result-row__main">
                  <span className="result-row__word">
                    {w.word_clean}
                    {w.homonym_no != null && (
                      <sup className="result-row__homonym">{w.homonym_no}</sup>
                    )}
                  </span>
                  {w.hanja && <span className="result-row__hanja">{w.hanja}</span>}
                </div>
                <div className="result-row__sub">
                  {w.senses[0]?.definition.slice(0, 42)}
                  {w.senses[0] && w.senses[0].definition.length > 42 ? "…" : ""}
                </div>
              </button>
            );
          })}
        </section>
      )}

      {chars.length > 0 && (
        <section className="result-list__section">
          <h3 className="result-list__heading">한자 ({chars.length})</h3>
          {chars.map((c) => {
            const active = selection?.kind === "char" && selection.data.char === c.char;
            return (
              <button
                key={c.char}
                type="button"
                className={`result-row ${active ? "result-row--active" : ""}`}
                onClick={() => onSelect({ kind: "char", data: c })}
              >
                <div className="result-row__main">
                  <span className="result-row__char">{c.char}</span>
                  <span className="result-row__reading">[{c.reading}]</span>
                  <span className="result-row__meaning">{c.meaning}</span>
                </div>
                <div className="result-row__sub">
                  {c.level_label} · {c.pinyin}
                  {c.simplified && ` · ${c.simplified}`}
                </div>
              </button>
            );
          })}
        </section>
      )}
    </div>
  );
}
