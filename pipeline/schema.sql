-- hanjadict SQLite schema
-- 한자 단자 + 한국어 단어 + 한자 역인덱스 + FTS5

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

-- ─────────────────────────────────────────────────────────
-- 1. 한자 단자 (어문회 5,978자, Unihan 보강)
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS characters (
    char         TEXT PRIMARY KEY,        -- 한자 (1자)
    reading      TEXT NOT NULL,           -- 한국어 음 (가, 각, ...)
    meaning      TEXT NOT NULL,           -- 한국어 훈 (가나무, 가할, ...)
    radical      TEXT,                    -- 부수 (木, 口 ...)
    radical_strokes INTEGER,              -- 부수 획수 (xls의 '획수' 컬럼)
    stroke_count INTEGER,                 -- 총획수 (xls의 '총획' 컬럼)
    level_code   INTEGER NOT NULL,        -- 급수 코드 (00=특급, 02=특급Ⅱ, 10=1급, ..., 80=8급)
    level_label  TEXT NOT NULL,           -- 급수 라벨 (특급, 특급Ⅱ, 1급, ..., 8급)
    long_sound   INTEGER NOT NULL DEFAULT 0,  -- 장음 (xls 음표 ':')
    -- Unihan 보강
    pinyin       TEXT,                    -- kMandarin (만다린 표준 발음, 성조 포함)
    pinyin_plain TEXT,                    -- 성조 제거된 병음 (검색용: "guó" → "guo")
    pinyin_extra TEXT,                    -- kHanyuPinyin (다음 발음, JSON 배열)
    simplified   TEXT,                    -- kSimplifiedVariant
    traditional  TEXT,                    -- kTraditionalVariant
    en_def       TEXT                     -- kDefinition (영문 뜻, 보너스)
);

CREATE INDEX IF NOT EXISTS idx_chars_reading ON characters(reading);
CREATE INDEX IF NOT EXISTS idx_chars_radical ON characters(radical);
CREATE INDEX IF NOT EXISTS idx_chars_level ON characters(level_code);

-- ─────────────────────────────────────────────────────────
-- 2. 한국어 단어 (NIKL stdict/krdict/opendict)
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS words (
    id           INTEGER PRIMARY KEY,
    word         TEXT NOT NULL,           -- 표제어 (한글, 동음번호 포함: '가01')
    word_clean   TEXT NOT NULL,           -- 검색용 (동음번호·하이픈 제거: '가')
    homonym_no   INTEGER,                 -- 동음 번호 (가01의 01)
    is_affix     INTEGER NOT NULL DEFAULT 0, -- 접두사/접미사 여부 ('-가12' 같은)
    hanja        TEXT,                    -- 한자 표기 (한자어인 경우)
    word_type    TEXT,                    -- 한자어/고유어/혼종어/외래어
    pos          TEXT,                    -- 품사 (명사, 동사, ...)
    pronunciation TEXT,                   -- 발음
    source       TEXT NOT NULL            -- stdict / krdict / opendict
);

CREATE INDEX IF NOT EXISTS idx_words_clean ON words(word_clean);
CREATE INDEX IF NOT EXISTS idx_words_hanja ON words(hanja);
CREATE INDEX IF NOT EXISTS idx_words_type ON words(word_type);

-- ─────────────────────────────────────────────────────────
-- 3. 의미 (한 단어에 여러 sense)
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS senses (
    id           INTEGER PRIMARY KEY,
    word_id      INTEGER NOT NULL REFERENCES words(id) ON DELETE CASCADE,
    sense_no     INTEGER,                 -- 의미 번호
    definition   TEXT NOT NULL,
    category     TEXT                     -- 분야 (음악, 의학, ...)
);

CREATE INDEX IF NOT EXISTS idx_senses_word ON senses(word_id);

-- ─────────────────────────────────────────────────────────
-- 4. 한자 → 단어 역인덱스 (民 → 民主, 民族, 國民 ...)
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS char_words (
    char         TEXT NOT NULL,
    word_id      INTEGER NOT NULL REFERENCES words(id) ON DELETE CASCADE,
    position     INTEGER NOT NULL,        -- 단어 내 한자 위치 (0-based)
    PRIMARY KEY (char, word_id, position)
);

CREATE INDEX IF NOT EXISTS idx_cw_char ON char_words(char);

-- ─────────────────────────────────────────────────────────
-- 5. FTS5 통합 인덱스
-- ─────────────────────────────────────────────────────────

-- 한자 단자 검색 (한자/음/훈/병음/영문)
-- pinyin_plain은 성조 무관 검색용. tokenize는 remove_diacritics=2로 양쪽 모두 정규화.
CREATE VIRTUAL TABLE IF NOT EXISTS fts_chars USING fts5(
    char UNINDEXED,
    reading,
    meaning,
    pinyin,
    pinyin_plain,
    en_def,
    tokenize='unicode61 remove_diacritics 2'
);

-- 한국어 단어 검색 (단어/한자/뜻풀이) — hanja도 indexed (한자 단어 직접 검색)
CREATE VIRTUAL TABLE IF NOT EXISTS fts_words USING fts5(
    word_clean,
    hanja,
    definition,
    word_id UNINDEXED,
    tokenize='unicode61 remove_diacritics 0'
);

-- ─────────────────────────────────────────────────────────
-- 메타데이터
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
