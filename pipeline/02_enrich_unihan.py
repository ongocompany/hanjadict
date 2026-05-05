#!/usr/bin/env python3
"""Unihan Database 다운로드 + 파싱 → characters 테이블 보강.

추출 필드:
- kMandarin            → pinyin       (만다린 표준 발음)
- kHanyuPinyin         → pinyin_extra (한어대자전 다음 발음, JSON 배열)
- kSimplifiedVariant   → simplified
- kTraditionalVariant  → traditional
- kDefinition          → en_def       (영문 뜻)
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import urllib.request
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = REPO_ROOT / "pipeline" / "cache"
DEFAULT_DB = REPO_ROOT / "resources" / "hanjadict.db"
UNIHAN_URL = "https://www.unicode.org/Public/UCD/latest/ucd/Unihan.zip"
UNIHAN_ZIP = CACHE_DIR / "Unihan.zip"

WANTED = {
    "kMandarin",
    "kHanyuPinyin",
    "kSimplifiedVariant",
    "kTraditionalVariant",
    "kDefinition",
}

# kHanyuPinyin 형식: '10001.020:dāng,dàng' — 콜론 뒤 발음들만 추출
HANYU_RE = re.compile(r":([^\s,]+(?:,[^\s,]+)*)")


def codepoint_to_char(cp: str) -> str:
    """U+6F22 → '漢'"""
    return chr(int(cp.removeprefix("U+"), 16))


def variant_field_to_chars(value: str) -> str:
    """'U+6C49 U+6C49<kHanyuDaZidian:T' → '汉'"""
    out = []
    for tok in value.split():
        cp = tok.split("<", 1)[0]  # 어노테이션 (<kSource:...) 떼기
        if cp.startswith("U+"):
            try:
                out.append(codepoint_to_char(cp))
            except ValueError:
                pass
    return "".join(dict.fromkeys(out))  # 중복 제거, 순서 유지


def download_unihan(force: bool = False) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if UNIHAN_ZIP.exists() and not force:
        print(f"캐시 사용: {UNIHAN_ZIP} ({UNIHAN_ZIP.stat().st_size:,} bytes)")
        return UNIHAN_ZIP
    print(f"다운로드: {UNIHAN_URL}")
    urllib.request.urlretrieve(UNIHAN_URL, UNIHAN_ZIP)
    print(f"  → {UNIHAN_ZIP} ({UNIHAN_ZIP.stat().st_size:,} bytes)")
    return UNIHAN_ZIP


def parse_unihan(zip_path: Path, target_chars: set[str]) -> dict[str, dict]:
    """대상 한자에 대해서만 필드 추출. {char: {field: value}}"""
    target_cps = {f"U+{ord(c):04X}": c for c in target_chars}
    out: dict[str, dict] = {}

    with zipfile.ZipFile(zip_path) as zf:
        names = [n for n in zf.namelist() if n.endswith(".txt")]
        print(f"Unihan zip 내 .txt: {names}")
        for name in names:
            with zf.open(name) as f:
                for raw in f:
                    line = raw.decode("utf-8", errors="replace")
                    if not line or line.startswith("#"):
                        continue
                    parts = line.rstrip("\n").split("\t")
                    if len(parts) < 3:
                        continue
                    cp, field, value = parts[0], parts[1], parts[2]
                    if field not in WANTED:
                        continue
                    if cp not in target_cps:
                        continue
                    char = target_cps[cp]
                    out.setdefault(char, {})[field] = value

    return out


_TONE_MAP = str.maketrans(
    "āáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜüĀÁǍÀĒÉĚÈĪÍǏÌŌÓǑÒŪÚǓÙǕǗǙǛÜ",
    "aaaaeeeeiiiioooouuuuuuuuuAAAAEEEEIIIIOOOOUUUUUUUUU",
)


def strip_tones(pinyin: str) -> str:
    return pinyin.translate(_TONE_MAP)


def transform(fields: dict) -> dict:
    """Unihan 원시 필드 → DB 컬럼 값."""
    result = {}

    # pinyin: kMandarin은 보통 단일값. 첫 토큰만.
    if "kMandarin" in fields:
        py = fields["kMandarin"].split()[0]
        result["pinyin"] = py
        result["pinyin_plain"] = strip_tones(py)

    # pinyin_extra: kHanyuPinyin에서 발음만 추출, 중복 제거
    if "kHanyuPinyin" in fields:
        readings = []
        for m in HANYU_RE.finditer(fields["kHanyuPinyin"]):
            for r in m.group(1).split(","):
                if r and r not in readings:
                    readings.append(r)
        if readings:
            result["pinyin_extra"] = json.dumps(readings, ensure_ascii=False)

    if "kSimplifiedVariant" in fields:
        s = variant_field_to_chars(fields["kSimplifiedVariant"])
        if s:
            result["simplified"] = s
    if "kTraditionalVariant" in fields:
        t = variant_field_to_chars(fields["kTraditionalVariant"])
        if t:
            result["traditional"] = t

    if "kDefinition" in fields:
        # 영문 뜻은 그대로 (세미콜론으로 의미 구분)
        result["en_def"] = fields["kDefinition"].strip()

    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--force-download", action="store_true")
    args = ap.parse_args()

    if not args.db.exists():
        sys.exit(f"DB 없음 — 먼저 01_build_characters.py 실행: {args.db}")

    zip_path = download_unihan(force=args.force_download)

    conn = sqlite3.connect(args.db)
    cur = conn.cursor()
    target = {row[0] for row in cur.execute("SELECT char FROM characters")}
    print(f"대상 한자: {len(target):,}자")

    raw = parse_unihan(zip_path, target)
    print(f"Unihan 매칭: {len(raw):,}자")

    counters = {"pinyin": 0, "pinyin_plain": 0, "pinyin_extra": 0, "simplified": 0,
                "traditional": 0, "en_def": 0}
    for char, fields in raw.items():
        cols = transform(fields)
        if not cols:
            continue
        sets = ", ".join(f"{k}=?" for k in cols)
        cur.execute(f"UPDATE characters SET {sets} WHERE char=?",
                    (*cols.values(), char))
        for k in cols:
            counters[k] += 1

    cur.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('unihan_built_at', datetime('now'))")
    conn.commit()

    print("\n보강 결과:")
    for k, v in counters.items():
        print(f"  {k:<14} {v:>5,}자")

    print("\n샘플 (감사 검증):")
    for row in cur.execute("""
        SELECT char, reading, pinyin, pinyin_extra, simplified, traditional, substr(en_def,1,40)
        FROM characters
        WHERE char IN ('漢','國','學','韓','中','東','龍','龜','體')
        ORDER BY char
    """):
        print(" ", row)

    conn.close()


if __name__ == "__main__":
    main()
