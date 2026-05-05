#!/usr/bin/env python3
"""FTS5 통합 검색 인덱스 구축.

- fts_chars: 한자 단자 검색 (한자/음/훈/병음/영문)
- fts_words: 한국어 단어 검색 (단어/한자/뜻풀이)
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = REPO_ROOT / "resources" / "hanjadict.db"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = ap.parse_args()

    if not args.db.exists():
        sys.exit(f"DB 없음: {args.db}")

    conn = sqlite3.connect(args.db)
    conn.execute("PRAGMA synchronous = OFF")
    conn.execute("PRAGMA cache_size = -200000")
    cur = conn.cursor()

    # FTS 가상 테이블 DROP/재생성 (스키마 변경 반영)
    cur.execute("DROP TABLE IF EXISTS fts_chars")
    cur.execute("DROP TABLE IF EXISTS fts_words")
    cur.executescript((REPO_ROOT / "pipeline" / "schema.sql").read_text(encoding="utf-8"))

    # 1) fts_chars 재구축
    print("[1/2] fts_chars 빌드…")
    t = time.time()
    cur.execute("DELETE FROM fts_chars")
    cur.execute("""
        INSERT INTO fts_chars(rowid, char, reading, meaning, pinyin, pinyin_plain, en_def)
        SELECT rowid, char, reading, meaning,
               COALESCE(pinyin,''),
               COALESCE(pinyin_plain,''),
               COALESCE(en_def,'')
        FROM characters
    """)
    n_chars = cur.execute("SELECT COUNT(*) FROM fts_chars").fetchone()[0]
    print(f"  → {n_chars:,} rows ({time.time()-t:.1f}s)")

    # 2) fts_words: 단어별 1 row, 모든 sense의 definition 합침
    print("[2/2] fts_words 빌드…")
    t = time.time()
    cur.execute("DELETE FROM fts_words")
    cur.execute("""
        INSERT INTO fts_words(word_clean, hanja, definition, word_id)
        SELECT w.word_clean,
               COALESCE(w.hanja,''),
               (SELECT GROUP_CONCAT(s.definition, ' | ')
                FROM senses s WHERE s.word_id = w.id),
               w.id
        FROM words w
    """)
    n_words = cur.execute("SELECT COUNT(*) FROM fts_words").fetchone()[0]
    print(f"  → {n_words:,} rows ({time.time()-t:.1f}s)")

    # FTS5 최적화 (인덱스 합침, 검색 속도 ↑)
    print("최적화 (optimize)…")
    t = time.time()
    cur.execute("INSERT INTO fts_chars(fts_chars) VALUES('optimize')")
    cur.execute("INSERT INTO fts_words(fts_words) VALUES('optimize')")
    print(f"  → {time.time()-t:.1f}s")

    cur.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('fts_built_at', datetime('now'))")
    conn.commit()
    cur.execute("VACUUM")
    conn.commit()

    # 검증 — 검색 테스트
    print("\n=== 검증: fts_chars ===")
    queries = ["민", "han", "guó", "edge"]
    for q in queries:
        rows = cur.execute(
            "SELECT char, reading, meaning, pinyin "
            "FROM fts_chars WHERE fts_chars MATCH ? LIMIT 3",
            (q,),
        ).fetchall()
        print(f"  '{q}' → {len(rows)} 결과: {rows[:2]}")

    print("\n=== 검증: fts_words ===")
    for q in ["민주주의", "國民", "edge"]:
        rows = cur.execute(
            "SELECT w.word, w.hanja, substr(s.definition,1,50) "
            "FROM fts_words ftw "
            "JOIN words w ON w.id = ftw.word_id "
            "LEFT JOIN senses s ON s.word_id = w.id AND s.sense_no = 1 "
            "WHERE fts_words MATCH ? LIMIT 3",
            (q,),
        ).fetchall()
        print(f"  '{q}' → {len(rows)} 결과:")
        for r in rows:
            print(f"      {r}")

    print("\n=== DB 통계 ===")
    for tbl in ("characters", "words", "senses", "char_words", "fts_chars", "fts_words"):
        n = cur.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        print(f"  {tbl:<12} {n:>12,}")

    size = args.db.stat().st_size
    print(f"\nDB 파일 크기: {size:,} bytes ({size / 1024 / 1024:.1f} MB)")
    conn.close()


if __name__ == "__main__":
    main()
