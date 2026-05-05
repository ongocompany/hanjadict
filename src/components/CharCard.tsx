import { useEffect, useState } from "react";
import type { CharEntry, WordEntry } from "../types";
import { wordsByChar } from "../lib/api";

interface Props {
  entry: CharEntry;
  onCharClick?: (ch: string) => void;
}

export function CharCard({ entry, onCharClick }: Props) {
  const [words, setWords] = useState<WordEntry[]>([]);

  useEffect(() => {
    let cancelled = false;
    wordsByChar(entry.char, 12).then((ws) => {
      if (!cancelled) setWords(ws);
    });
    return () => {
      cancelled = true;
    };
  }, [entry.char]);

  return (
    <article className="char-card">
      <div className="char-card__hero">
        <div className="char-card__big">{entry.char}</div>
        <div className="char-card__hero-meta">
          <div className="char-card__reading">
            {entry.reading}
            {entry.long_sound && <span className="char-card__long">ː</span>}
          </div>
          <div className="char-card__meaning">{entry.meaning}</div>
          <div className="char-card__badges">
            <span className="badge badge--level">{entry.level_label}</span>
            {entry.radical && (
              <span className="badge">
                부수 <strong>{entry.radical}</strong>
                {entry.radical_strokes != null && ` (${entry.radical_strokes}획)`}
              </span>
            )}
            {entry.stroke_count != null && (
              <span className="badge">총 {entry.stroke_count}획</span>
            )}
          </div>
        </div>
      </div>

      {(entry.pinyin || entry.simplified || entry.traditional) && (
        <section className="char-card__section">
          <h4>중국어</h4>
          <dl className="kv">
            {entry.pinyin && (
              <>
                <dt>병음</dt>
                <dd className="pinyin">
                  {entry.pinyin}
                  {entry.pinyin_extra && entry.pinyin_extra.length > 1 && (
                    <span className="pinyin-extra">
                      {" "}
                      / {entry.pinyin_extra.filter((p) => p !== entry.pinyin).join(", ")}
                    </span>
                  )}
                </dd>
              </>
            )}
            {entry.simplified && (
              <>
                <dt>간체</dt>
                <dd className="hanja-inline" data-region="sc">{entry.simplified}</dd>
              </>
            )}
            {entry.traditional && (
              <>
                <dt>번체</dt>
                <dd className="hanja-inline" data-region="tc">{entry.traditional}</dd>
              </>
            )}
          </dl>
        </section>
      )}

      {entry.en_def && (
        <section className="char-card__section">
          <h4>영문</h4>
          <p className="en-def">{entry.en_def}</p>
        </section>
      )}

      <section className="char-card__section">
        <h4>
          이 한자가 들어간 단어
          {entry.word_count != null && (
            <span className="muted"> ({entry.word_count.toLocaleString()})</span>
          )}
        </h4>
        {words.length > 0 ? (
          <ul className="word-pill-list">
            {words.map((w) => (
              <li
                key={w.id}
                className="word-pill"
                onClick={() => w.hanja && onCharClick?.(w.hanja)}
              >
                <strong>{w.hanja}</strong> {w.word_clean}
              </li>
            ))}
            {entry.word_count != null && entry.word_count > words.length && (
              <li className="word-pill word-pill--more">
                +{(entry.word_count - words.length).toLocaleString()}개 더
              </li>
            )}
          </ul>
        ) : (
          <p className="muted">불러오는 중…</p>
        )}
      </section>
    </article>
  );
}
