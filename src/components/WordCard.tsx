import { useEffect, useState } from "react";
import type { CharEntry, WordEntry } from "../types";
import { getChar } from "../lib/api";

interface Props {
  entry: WordEntry;
  onCharClick?: (ch: string) => void;
}

export function WordCard({ entry, onCharClick }: Props) {
  const hanjaChars = entry.hanja ? Array.from(entry.hanja) : [];
  const [charInfos, setCharInfos] = useState<Record<string, CharEntry | null>>({});

  useEffect(() => {
    let cancelled = false;
    Promise.all(hanjaChars.map((c) => getChar(c).then((info) => [c, info] as const))).then(
      (entries) => {
        if (cancelled) return;
        setCharInfos(Object.fromEntries(entries));
      },
    );
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [entry.hanja]);

  return (
    <article className="word-card">
      <header className="word-card__head">
        <div className="word-card__title-row">
          {entry.hanja && <span className="word-card__hanja-big">{entry.hanja}</span>}
          <span className="word-card__word-big">
            {entry.word_clean}
            {entry.homonym_no != null && (
              <sup className="word-card__homonym">{entry.homonym_no}</sup>
            )}
          </span>
        </div>
        <div className="word-card__meta">
          {entry.word_type && <span className="badge">{entry.word_type}</span>}
          {entry.pos && <span className="badge">{entry.pos}</span>}
          {entry.pronunciation && (
            <span className="badge">[{entry.pronunciation}]</span>
          )}
        </div>
      </header>

      {entry.hanja && hanjaChars.length > 0 && (
        <section className="word-card__section">
          <h4>한자 분해</h4>
          <div className="char-breakdown">
            {hanjaChars.map((h, i) => {
              const info = charInfos[h];
              return (
                <button
                  key={`${h}-${i}`}
                  type="button"
                  className="char-chip"
                  onClick={() => onCharClick?.(h)}
                >
                  <div className="char-chip__char">{h}</div>
                  {info ? (
                    <>
                      <div className="char-chip__reading">[{info.reading}]</div>
                      <div className="char-chip__meaning">{info.meaning}</div>
                    </>
                  ) : (
                    <div className="char-chip__reading muted">…</div>
                  )}
                </button>
              );
            })}
          </div>
        </section>
      )}

      <section className="word-card__section">
        <h4>뜻풀이</h4>
        <ol className="senses">
          {entry.senses.map((s, i) => (
            <li key={s.sense_no ?? i} className="sense">
              {s.category && <span className="sense__cat">[{s.category}]</span>}
              <span className="sense__def">{s.definition}</span>
            </li>
          ))}
        </ol>
      </section>
    </article>
  );
}
