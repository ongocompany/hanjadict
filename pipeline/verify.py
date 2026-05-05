#!/usr/bin/env python3
"""hanjadict.db 종합 검증 — 실제 검색 시나리오 재현."""

from __future__ import annotations

import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "resources" / "hanjadict.db"


def header(s):
    print(f"\n{'─'*70}\n{s}\n{'─'*70}")


def main():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    header("[메타] DB 구축 시각")
    for k, v in cur.execute("SELECT key, value FROM meta ORDER BY key"):
        print(f"  {k}: {v}")

    header("[1] 한자 1자 — 國")
    row = cur.execute("""
        SELECT char, reading, meaning, radical, stroke_count, level_label,
               long_sound, pinyin, pinyin_extra, simplified, traditional, en_def
        FROM characters WHERE char='國'
    """).fetchone()
    cols = ["한자","음","훈","부수","총획","급수","장음","병음","다음발음","간체","번체","영문"]
    for c, v in zip(cols, row):
        print(f"  {c:<6} {v}")

    n_words = cur.execute(
        "SELECT COUNT(DISTINCT word_id) FROM char_words WHERE char='國'"
    ).fetchone()[0]
    print(f"  → 國이 들어간 stdict 단어: {n_words:,}개")

    header("[2] 한자 → 사용 단어 (民, 상위 5건)")
    for row in cur.execute("""
        SELECT w.word, w.hanja, substr(s.definition,1,60)
        FROM char_words cw
        JOIN words w ON w.id = cw.word_id
        LEFT JOIN senses s ON s.word_id = w.id AND s.sense_no = 1
        WHERE cw.char = '民' AND length(w.hanja) <= 4
        ORDER BY length(w.hanja), w.id
        LIMIT 5
    """):
        print(f"  {row[0]:<10} {row[1]:<6}  {row[2]}")

    header("[3] 한국어 단어 검색 — 민주주의")
    rows = cur.execute("""
        SELECT w.word, w.hanja, w.word_type,
               (SELECT GROUP_CONCAT(s.definition, ' / ')
                FROM senses s WHERE s.word_id = w.id)
        FROM words w
        WHERE w.word_clean = '민주주의'
        ORDER BY w.homonym_no
    """).fetchall()
    for r in rows[:3]:
        print(f"  {r[0]} | {r[1]} | {r[2]}")
        print(f"    → {(r[3] or '')[:90]}")

    header("[4] FTS5 — 한자 검색 '國民' (한자 단어)")
    for row in cur.execute("""
        SELECT w.word, w.hanja, substr(s.definition,1,60)
        FROM fts_words ftw
        JOIN words w ON w.id = ftw.word_id
        LEFT JOIN senses s ON s.word_id = w.id AND s.sense_no = 1
        WHERE fts_words MATCH ?
        LIMIT 5
    """, ('"國民"',)):
        print(f"  {row[0]:<14} {row[1]:<10} {row[2]}")

    header("[5] FTS5 — 병음 검색 'guó'")
    for row in cur.execute("""
        SELECT char, reading, meaning, pinyin
        FROM fts_chars WHERE fts_chars MATCH ? LIMIT 5
    """, ("guó",)):
        print(f"  {row[0]} {row[1]} {row[2]} ({row[3]})")

    header("[6] 동음이의 한자 — 음 '간' (어문회 한자만)")
    for row in cur.execute("""
        SELECT char, meaning, level_label, pinyin
        FROM characters WHERE reading='간'
        ORDER BY level_code, char LIMIT 8
    """):
        print(f"  {row[0]} {row[1]:<14} [{row[2]}] {row[3] or ''}")

    header("[7] DB 크기 / 행 수")
    for tbl in ("characters","words","senses","char_words","fts_chars","fts_words"):
        n = cur.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        print(f"  {tbl:<14} {n:>14,}")
    print(f"  파일       {DB.stat().st_size / 1024 / 1024:>14,.1f} MB")

    conn.close()


if __name__ == "__main__":
    main()
