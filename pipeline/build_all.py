#!/usr/bin/env python3
"""hanjadict 데이터 파이프라인 풀 빌드.

순차 실행:
  01_build_characters.py  → 어문회 5,978자
  02_enrich_unihan.py     → 병음/간체/번체/영문
  03_parse_nikl.py        → 표준국어대사전 (44만 단어)
  04_build_fts.py         → FTS5 통합 인덱스

총 소요: 약 30~60초 (Unihan 다운로드 첫 실행 시 +α).
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
STEPS = [
    "01_build_characters.py",
    "02_enrich_unihan.py",
    "03_parse_nikl.py",
    "04_build_fts.py",
]


def main():
    extra_args = sys.argv[1:]
    if "--reset" in extra_args:
        reset = True
        extra_args.remove("--reset")
    else:
        reset = False

    total_t = time.time()
    for step in STEPS:
        path = HERE / step
        print(f"\n{'='*60}\n▶ {step}\n{'='*60}")
        cmd = [sys.executable, str(path)]
        # 03_parse_nikl만 --reset 받음 (다른 스크립트는 idempotent하거나 처음부터 빌드)
        if reset and step == "03_parse_nikl.py":
            cmd.append("--reset")
        if step == "01_build_characters.py" and reset:
            cmd.append("--reset")
        cmd.extend(extra_args)
        t = time.time()
        r = subprocess.run(cmd)
        if r.returncode != 0:
            sys.exit(f"\n실패: {step} (exit {r.returncode})")
        print(f"\n[{step} 완료, {time.time()-t:.1f}s]")

    # Tauri 번들에서 DB를 찾을 수 있도록 src-tauri/resources/ 셋업.
    # macOS/Linux에선 심볼릭 링크, Windows에선 실제 복사 (link 권한 회피).
    import shutil, sys as _sys
    repo = HERE.parent
    src_tauri_res = repo / "src-tauri" / "resources"
    src_tauri_res.mkdir(parents=True, exist_ok=True)
    target = src_tauri_res / "hanjadict.db"
    source = repo / "resources" / "hanjadict.db"
    if target.exists() or target.is_symlink():
        target.unlink()
    if _sys.platform == "win32":
        shutil.copy2(source, target)
        print(f"\n[setup] copied DB → {target}")
    else:
        target.symlink_to("../../resources/hanjadict.db")
        print(f"\n[setup] symlinked DB → {target}")

    print(f"\n{'='*60}\n✓ 전체 빌드 완료. 총 {time.time()-total_t:.1f}s.\n{'='*60}")


if __name__ == "__main__":
    main()
