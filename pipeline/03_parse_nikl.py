#!/usr/bin/env python3
"""표준국어대사전(stdict) XML → words / senses / char_words 테이블.

stdict 89개 파일, 약 44만 항목을 streaming(iterparse)으로 처리.
한자어/혼종어는 origin 필드에 한자가 박혀있어 char_words 역인덱스 생성.
"""

from __future__ import annotations

import argparse
import re
import sqlite3
import sys
import time
from pathlib import Path
from xml.etree import ElementTree as ET

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = REPO_ROOT / "resources" / "hanjadict.db"
DEFAULT_STDICT = REPO_ROOT.parent / "hanjahanja" / "korean-dict-nikl" / "stdict"

# CJK 통합 한자 범위 (BMP + Extension A + Compat + Plane 2)
def is_hanja(c: str) -> bool:
    cp = ord(c)
    return (
        0x3400 <= cp <= 0x9FFF or
        0xF900 <= cp <= 0xFAFF or
        0x20000 <= cp <= 0x2FFFF
    )


def extract_hanja(s: str | None) -> str | None:
    if not s:
        return None
    out = "".join(c for c in s if is_hanja(c))
    return out or None


# 표제어 끝 1~2자리 숫자가 동음 번호 (예: '가01', '학생02')
HOMONYM_RE = re.compile(r"^(.+?)(\d{1,2})$")


def normalize_word(word: str) -> tuple[str, int | None, int]:
    """word → (word_clean, homonym_no, is_affix)"""
    m = HOMONYM_RE.match(word)
    if m and not word[0].isdigit() and len(m.group(1)) >= 1:
        clean, homonym = m.group(1), int(m.group(2))
    else:
        clean, homonym = word, None
    is_affix = 1 if (clean.startswith("-") or clean.endswith("-")) else 0
    # stdict 복합어 구분자(^), 가운뎃점(·), 하이픈, 공백 모두 제거 → 검색 정규화
    for ch in ("-", "^", "·", " "):
        clean = clean.replace(ch, "")
    return clean, homonym, is_affix


# definition 안의 내부 마크업 정리: <each_sense_no>...</each_sense_no> 등
SENSE_NO_RE = re.compile(r"<each_sense_no>[^<]*</each_sense_no>")


def clean_definition(text: str) -> str:
    return SENSE_NO_RE.sub("", text).strip()


def iter_items(xml_path: Path):
    """item 요소를 streaming으로 yield. 각 항목 처리 후 clear."""
    for event, elem in ET.iterparse(xml_path, events=("end",)):
        if elem.tag == "item":
            yield elem
            elem.clear()


def process_item(elem) -> tuple[dict, list[dict]] | None:
    wi = elem.find("word_info")
    if wi is None:
        return None
    word = (wi.findtext("word") or "").strip()
    if not word:
        return None

    word_clean, homonym, is_affix = normalize_word(word)
    word_type = wi.findtext("word_type") or None
    pos = wi.findtext("pos_info/pos") or None
    pron = wi.findtext("pronunciation_info/pronunciation") or None

    # 한자 표기는 original_language_info/original_language (language_type='한자')에 있음.
    # 한자 외 어원(범어/중/일 등도 한자형이지만 한국 어문회 도메인에선 한자만 추출).
    hanja_parts = []
    for oli in wi.findall("original_language_info"):
        ltype = oli.findtext("language_type") or ""
        if "한자" not in ltype:
            continue
        ol = oli.findtext("original_language") or ""
        h = extract_hanja(ol)
        if h:
            hanja_parts.append(h)
    hanja = "".join(hanja_parts) or None

    senses = []
    for s_idx, sense in enumerate(wi.findall("pos_info/comm_pattern_info/sense_info"), start=1):
        defi = sense.findtext("definition") or ""
        defi = clean_definition(defi)
        if not defi:
            continue
        cat = sense.findtext("cat_info/cat")
        if cat == "없음":
            cat = None
        senses.append({
            "sense_no": s_idx,
            "definition": defi,
            "category": cat,
        })

    if not senses:
        return None

    word_row = {
        "word": word,
        "word_clean": word_clean,
        "homonym_no": homonym,
        "is_affix": is_affix,
        "hanja": hanja,
        "word_type": word_type,
        "pos": pos,
        "pronunciation": pron,
        "source": "stdict",
    }
    return word_row, senses


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--stdict", type=Path, default=DEFAULT_STDICT)
    ap.add_argument("--limit-files", type=int, default=0,
                    help="0=전부, n>0이면 처음 n개 파일만 (디버그)")
    ap.add_argument("--reset", action="store_true",
                    help="기존 stdict 데이터 비우고 재적재")
    args = ap.parse_args()

    if not args.db.exists():
        sys.exit(f"DB 없음: {args.db}")
    files = sorted(args.stdict.glob("*.xml"))
    if args.limit_files:
        files = files[:args.limit_files]
    if not files:
        sys.exit(f"stdict 파일 없음: {args.stdict}")
    print(f"파일 {len(files)}개 처리 시작")

    conn = sqlite3.connect(args.db)
    conn.execute("PRAGMA synchronous = OFF")
    conn.execute("PRAGMA cache_size = -200000")  # 200MB
    cur = conn.cursor()

    if args.reset:
        cur.execute("DELETE FROM char_words WHERE word_id IN (SELECT id FROM words WHERE source='stdict')")
        cur.execute("DELETE FROM senses WHERE word_id IN (SELECT id FROM words WHERE source='stdict')")
        cur.execute("DELETE FROM words WHERE source='stdict'")
        conn.commit()

    n_words = n_senses = n_charlinks = 0
    t0 = time.time()
    for fi, xml_path in enumerate(files, start=1):
        words_buf, senses_buf, char_buf = [], [], []
        for elem in iter_items(xml_path):
            r = process_item(elem)
            if r is None:
                continue
            word_row, senses = r
            words_buf.append(word_row)
            # senses는 word_id가 아직 없어서 임시로 인덱스 매칭
            senses_buf.append(senses)

        # 일괄 INSERT (단일 트랜잭션)
        cur.execute("BEGIN")
        for w, s_list in zip(words_buf, senses_buf):
            cur.execute(
                """
                INSERT INTO words(word, word_clean, homonym_no, is_affix, hanja,
                                  word_type, pos, pronunciation, source)
                VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (w["word"], w["word_clean"], w["homonym_no"], w["is_affix"],
                 w["hanja"], w["word_type"], w["pos"], w["pronunciation"], w["source"]),
            )
            wid = cur.lastrowid
            for s in s_list:
                cur.execute(
                    "INSERT INTO senses(word_id, sense_no, definition, category) VALUES (?,?,?,?)",
                    (wid, s["sense_no"], s["definition"], s["category"]),
                )
                n_senses += 1
            if w["hanja"]:
                for pos_idx, c in enumerate(w["hanja"]):
                    cur.execute(
                        "INSERT OR IGNORE INTO char_words(char, word_id, position) VALUES (?,?,?)",
                        (c, wid, pos_idx),
                    )
                    n_charlinks += 1
            n_words += 1
        conn.commit()

        if fi % 5 == 0 or fi == len(files):
            elapsed = time.time() - t0
            rate = n_words / elapsed if elapsed else 0
            print(f"  [{fi}/{len(files)}] {xml_path.name} | 누적 단어 {n_words:,} | "
                  f"{rate:,.0f} words/s | {elapsed:.1f}s")

    cur.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('nikl_built_at', datetime('now'))")
    conn.commit()

    print(f"\n총 {n_words:,} 단어, {n_senses:,} 의미, {n_charlinks:,} 한자-단어 링크")

    print("\n워드 타입 분포:")
    for row in cur.execute(
        "SELECT word_type, COUNT(*) FROM words WHERE source='stdict' GROUP BY word_type ORDER BY 2 DESC"
    ):
        print(f"  {str(row[0] or 'NULL'):<10} {row[1]:>7,}")

    print("\nhanja 보유 단어:",
          cur.execute("SELECT COUNT(*) FROM words WHERE source='stdict' AND hanja IS NOT NULL").fetchone()[0])

    print("\n샘플 — 한자 民 가 들어간 단어 5개:")
    for row in cur.execute("""
        SELECT w.word, w.hanja, substr(s.definition,1,50)
        FROM char_words cw
        JOIN words w ON w.id = cw.word_id
        JOIN senses s ON s.word_id = w.id AND s.sense_no = 1
        WHERE cw.char = '民'
        LIMIT 5
    """):
        print(" ", row)

    conn.close()


if __name__ == "__main__":
    main()
