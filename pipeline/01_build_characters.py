#!/usr/bin/env python3
"""한국어문회 배정한자 5,978자 xls → SQLite characters 테이블."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

import xlrd

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_XLS = (
    REPO_ROOT.parent / "hanjahanja" / "docs" / "reference"
    / "한국어문회 배정한자(5978자) 정리.xls"
)
DEFAULT_DB = REPO_ROOT / "resources" / "hanjadict.db"
SCHEMA = REPO_ROOT / "pipeline" / "schema.sql"

LEVEL_LABEL = {
    0: "특급", 2: "특급Ⅱ",
    10: "1급", 12: "2급(인명지명)",
    20: "2급", 30: "3급", 32: "3급Ⅱ",
    40: "4급", 42: "4급Ⅱ",
    50: "5급", 52: "5급Ⅱ",
    60: "6급", 62: "6급Ⅱ",
    70: "7급", 72: "7급Ⅱ",
    80: "8급",
}


def parse_int(v) -> int | None:
    if v in ("", None):
        return None
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def load_rows(xls_path: Path):
    book = xlrd.open_workbook(str(xls_path))
    sheet = book.sheet_by_name("한국어문회 급수별 배정한자 전체목록(5,978자)")
    # 헤더는 3번째 행: ['순번','급수','한자','표제훈음','표제훈','표제음','부수','획수','총획','음표']
    header_row = 2
    cols = [sheet.cell_value(header_row, c) for c in range(sheet.ncols)]
    idx = {name: cols.index(name) for name in cols if name}
    for r in range(header_row + 1, sheet.nrows):
        row = [sheet.cell_value(r, c) for c in range(sheet.ncols)]
        if not row[idx["한자"]]:
            continue
        yield {
            "char": row[idx["한자"]].strip(),
            "level_code": parse_int(row[idx["급수"]]),
            "title": str(row[idx["표제훈음"]]).strip(),
            "meaning": str(row[idx["표제훈"]]).strip(),
            "reading": str(row[idx["표제음"]]).strip(),
            "radical": str(row[idx["부수"]]).strip() or None,
            "rad_strokes": parse_int(row[idx["획수"]]),
            "stroke_count": parse_int(row[idx["총획"]]),
            "long_sound": 1 if ":" in str(row[idx["음표"]]) else 0,
        }


def init_db(db_path: Path):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    return conn


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--xls", type=Path, default=DEFAULT_XLS)
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--reset", action="store_true",
                    help="기존 characters 데이터 비우고 다시 적재")
    args = ap.parse_args()

    if not args.xls.exists():
        sys.exit(f"xls 없음: {args.xls}")

    conn = init_db(args.db)
    cur = conn.cursor()
    if args.reset:
        cur.execute("DELETE FROM characters")

    rows = list(load_rows(args.xls))
    print(f"읽은 행: {len(rows):,}")

    inserted = 0
    skipped = 0
    seen = set()
    for r in rows:
        if r["char"] in seen:
            skipped += 1
            continue
        seen.add(r["char"])
        level_code = r["level_code"] or 0
        cur.execute(
            """
            INSERT OR REPLACE INTO characters
              (char, reading, meaning, radical, radical_strokes, stroke_count,
               level_code, level_label, long_sound)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                r["char"], r["reading"], r["meaning"],
                r["radical"], r["rad_strokes"], r["stroke_count"],
                level_code, LEVEL_LABEL.get(level_code, f"코드{level_code}"),
                r["long_sound"],
            ),
        )
        inserted += 1

    cur.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('chars_built_at', datetime('now'))")
    conn.commit()
    print(f"적재: {inserted:,}자, 중복 스킵: {skipped}")

    # 검증
    n = cur.execute("SELECT COUNT(*) FROM characters").fetchone()[0]
    print(f"DB characters 총: {n:,}")
    print("\n급수별 분포:")
    for lvl, label, c in cur.execute(
        "SELECT level_code, level_label, COUNT(*) FROM characters "
        "GROUP BY level_code ORDER BY level_code"
    ):
        print(f"  {lvl:>3} {label:<12} {c:>5,}자")

    print("\n샘플 5건:")
    for row in cur.execute(
        "SELECT char, reading, meaning, radical, stroke_count, level_label, long_sound "
        "FROM characters LIMIT 5"
    ):
        print(" ", row)

    conn.close()


if __name__ == "__main__":
    main()
