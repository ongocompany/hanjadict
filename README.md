# hanjadict

맥/윈도우용 오프라인 한자 사전. 한국어문회 5,978자 + 표준국어대사전 한자어 + Unihan(병음·간체·번체) 통합. Tauri 2 + SQLite FTS5.

> 비상업·무료. 진우형 + 중어중문과 학생용.

## 구조

```
hanjadict/
├── pipeline/         # 데이터 파이프라인 (Python, 일회성)
│   ├── schema.sql           # SQLite 스키마
│   ├── 01_build_characters.py  # 어문회 5,978자 → characters
│   ├── 02_enrich_unihan.py     # Unihan → 병음/간체/번체
│   ├── 03_parse_nikl.py        # 표준국어대사전 → words/senses/char_words
│   ├── 04_build_fts.py         # FTS5 인덱스
│   └── build_all.py            # 전부 순차 실행
├── resources/        # 빌드 산출물 (Tauri 번들에 임베드)
│   └── hanjadict.db
├── src-tauri/        # Rust 백엔드 (DB 쿼리, 글로벌 단축키)
└── src/              # React + Vite UI
```

## 데이터 출처

| 자원 | 라이선스 | 위치 |
|---|---|---|
| 한국어문회 배정한자 5,978자 (xls) | 공개 자료 | `../hanjahanja/docs/reference/` |
| 표준국어대사전 / 우리말샘 / 한국어기초사전 (NIKL) | CC BY-SA 2.0 KR | `../hanjahanja/korean-dict-nikl/` |
| Unihan Database | Unicode (BSD-style) | 빌드 시 자동 다운로드 |

## 빌드

```bash
# 1. 의존성 (Node + Python)
pnpm install
pip3 install xlrd Pillow

# 2. 데이터 파이프라인 (한 번만, ~30초 + Unihan 다운로드 첫 실행 시 +α)
python3 pipeline/build_all.py
# → resources/hanjadict.db 생성 + src-tauri/resources/ 자동 셋업

# 3. 개발
pnpm tauri:dev

# 4. 릴리즈 빌드
pnpm tauri:build   # macOS: dmg / Windows: msi
```

빌드 산출물:
- macOS: `src-tauri/target/release/bundle/dmg/한자사전_*.dmg`
- Windows: `src-tauri/target/release/bundle/msi/한자사전_*.msi`

## v1 범위

- 한자 단자 카드: 음, 훈, 부수, 획수, 급수, 장음, 병음, 간체/번체, 영문 뜻
- 한자 → 단어 역검색 (예: `民` 클릭 → 民主, 民族, 國民...)
- 한국어 단어 검색 → 한자 표기 + 뜻풀이
- 통합 검색바 (한자/한글음/한국어 단어 자동 분기)
- 글로벌 단축키 호출

## v2 (미정)

- 만다린 TTS (보통화 발음 재생)
- 부수 + 획수 검색
- 필기 인식

## 라이선스

코드: MIT. 데이터는 각 출처 라이선스 따름.
