//! SQLite 백엔드 — characters / words / senses / char_words / FTS5.

use rusqlite::{params, Connection, OpenFlags, OptionalExtension, Row};
use serde::Serialize;
use std::path::Path;
use std::sync::Mutex;

#[derive(thiserror::Error, Debug)]
pub enum DbError {
    #[error("SQLite: {0}")]
    Sqlite(#[from] rusqlite::Error),
    #[error("JSON: {0}")]
    Json(#[from] serde_json::Error),
}

pub type DbResult<T> = Result<T, DbError>;

#[derive(Debug, Serialize, Clone)]
pub struct CharEntry {
    pub char: String,
    pub reading: String,
    pub meaning: String,
    pub radical: Option<String>,
    pub radical_strokes: Option<i64>,
    pub stroke_count: Option<i64>,
    pub level_code: i64,
    pub level_label: String,
    pub long_sound: bool,
    pub pinyin: Option<String>,
    pub pinyin_extra: Option<Vec<String>>,
    pub simplified: Option<String>,
    pub traditional: Option<String>,
    pub en_def: Option<String>,
    pub word_count: Option<i64>,
}

#[derive(Debug, Serialize, Clone)]
pub struct Sense {
    pub sense_no: Option<i64>,
    pub definition: String,
    pub category: Option<String>,
}

#[derive(Debug, Serialize, Clone)]
pub struct WordEntry {
    pub id: i64,
    pub word: String,
    pub word_clean: String,
    pub homonym_no: Option<i64>,
    pub is_affix: bool,
    pub hanja: Option<String>,
    pub word_type: Option<String>,
    pub pos: Option<String>,
    pub pronunciation: Option<String>,
    pub senses: Vec<Sense>,
}

#[derive(Debug, Serialize)]
pub struct SearchResults {
    pub chars: Vec<CharEntry>,
    pub words: Vec<WordEntry>,
}

pub struct Database {
    conn: Mutex<Connection>,
}

impl Database {
    pub fn open(path: &Path) -> DbResult<Self> {
        let conn = Connection::open_with_flags(
            path,
            OpenFlags::SQLITE_OPEN_READ_ONLY | OpenFlags::SQLITE_OPEN_NO_MUTEX,
        )?;
        conn.pragma_update(None, "query_only", true)?;
        Ok(Self { conn: Mutex::new(conn) })
    }

    fn map_char(row: &Row<'_>) -> rusqlite::Result<CharEntry> {
        let pinyin_extra_raw: Option<String> = row.get("pinyin_extra")?;
        let pinyin_extra = pinyin_extra_raw
            .and_then(|s| serde_json::from_str::<Vec<String>>(&s).ok());
        Ok(CharEntry {
            char: row.get("char")?,
            reading: row.get("reading")?,
            meaning: row.get("meaning")?,
            radical: row.get("radical")?,
            radical_strokes: row.get("radical_strokes")?,
            stroke_count: row.get("stroke_count")?,
            level_code: row.get("level_code")?,
            level_label: row.get("level_label")?,
            long_sound: row.get::<_, i64>("long_sound")? != 0,
            pinyin: row.get("pinyin")?,
            pinyin_extra,
            simplified: row.get("simplified")?,
            traditional: row.get("traditional")?,
            en_def: row.get("en_def")?,
            word_count: None,
        })
    }

    pub fn get_char(&self, ch: &str) -> DbResult<Option<CharEntry>> {
        let conn = self.conn.lock().unwrap();
        let mut entry: Option<CharEntry> = conn
            .query_row(
                "SELECT * FROM characters WHERE char = ?1",
                params![ch],
                Self::map_char,
            )
            .optional()?;
        if let Some(ref mut e) = entry {
            e.word_count = Some(conn.query_row(
                "SELECT COUNT(DISTINCT word_id) FROM char_words WHERE char = ?1",
                params![ch],
                |r| r.get::<_, i64>(0),
            )?);
        }
        Ok(entry)
    }

    fn map_word_meta(row: &Row<'_>) -> rusqlite::Result<WordEntry> {
        Ok(WordEntry {
            id: row.get("id")?,
            word: row.get("word")?,
            word_clean: row.get("word_clean")?,
            homonym_no: row.get("homonym_no")?,
            is_affix: row.get::<_, i64>("is_affix")? != 0,
            hanja: row.get("hanja")?,
            word_type: row.get("word_type")?,
            pos: row.get("pos")?,
            pronunciation: row.get("pronunciation")?,
            senses: vec![],
        })
    }

    fn fill_senses(conn: &Connection, w: &mut WordEntry) -> rusqlite::Result<()> {
        let mut stmt = conn.prepare_cached(
            "SELECT sense_no, definition, category FROM senses
             WHERE word_id = ?1 ORDER BY sense_no",
        )?;
        let rows = stmt.query_map(params![w.id], |r| {
            Ok(Sense {
                sense_no: r.get(0)?,
                definition: r.get(1)?,
                category: r.get(2)?,
            })
        })?;
        for s in rows { w.senses.push(s?); }
        Ok(())
    }

    pub fn get_word(&self, id: i64) -> DbResult<Option<WordEntry>> {
        let conn = self.conn.lock().unwrap();
        let mut w: Option<WordEntry> = conn
            .query_row(
                "SELECT * FROM words WHERE id = ?1",
                params![id],
                Self::map_word_meta,
            )
            .optional()?;
        if let Some(ref mut entry) = w {
            Self::fill_senses(&conn, entry)?;
        }
        Ok(w)
    }

    /// 한자 → 그 한자가 들어간 단어 (짧은 한자어 우선).
    pub fn words_by_char(&self, ch: &str, limit: i64) -> DbResult<Vec<WordEntry>> {
        let conn = self.conn.lock().unwrap();
        let mut stmt = conn.prepare_cached(
            "SELECT w.* FROM char_words cw
             JOIN words w ON w.id = cw.word_id
             WHERE cw.char = ?1 AND w.is_affix = 0 AND w.hanja IS NOT NULL
             GROUP BY w.id
             ORDER BY length(w.hanja), cw.position, w.id
             LIMIT ?2",
        )?;
        let rows = stmt.query_map(params![ch, limit], Self::map_word_meta)?;
        let mut out: Vec<WordEntry> = rows.collect::<rusqlite::Result<_>>()?;
        for w in &mut out { Self::fill_senses(&conn, w)?; }
        Ok(out)
    }

    /// 통합 검색.
    /// - 한자 1자 → 단자 카드 + 단어 후보
    /// - 한자 여러 자 → fts_words.hanja 매칭
    /// - 한글 → fts_chars.reading + fts_words.word_clean
    /// - ASCII (병음/영문) → fts_chars.pinyin + fts_chars.en_def
    pub fn search(&self, q: &str, limit: i64) -> DbResult<SearchResults> {
        let q = q.trim();
        if q.is_empty() {
            return Ok(SearchResults { chars: vec![], words: vec![] });
        }
        let conn = self.conn.lock().unwrap();

        let has_hanja = q.chars().any(is_hanja);
        let has_hangul = q.chars().any(is_hangul);
        // Latin / 병음 (Latin-1 Sup, Latin Ext, combining diacritics 포함 — "guó" "guo" 둘 다)
        let is_latin = q.chars().all(is_latin_or_ws);

        let mut chars: Vec<CharEntry> = Vec::new();
        let mut words: Vec<WordEntry> = Vec::new();

        // ── chars ──
        if has_hanja {
            // query에 들어있는 각 한자의 단자 정보
            let mut stmt = conn.prepare_cached("SELECT * FROM characters WHERE char = ?1")?;
            for c in q.chars().filter(|c| is_hanja(*c)) {
                let s = c.to_string();
                if let Some(e) = stmt
                    .query_row(params![s], Self::map_char)
                    .optional()?
                {
                    chars.push(e);
                }
            }
        } else if has_hangul {
            // 한글 음 정확 매칭
            let mut stmt = conn.prepare_cached(
                "SELECT * FROM characters WHERE reading = ?1 ORDER BY level_code, char LIMIT ?2",
            )?;
            let rows = stmt.query_map(params![q, limit], Self::map_char)?;
            chars = rows.collect::<rusqlite::Result<_>>()?;
        } else if is_latin {
            // 병음/영문 — FTS5
            let pattern = sanitize_fts(q);
            let mut stmt = conn.prepare_cached(
                "SELECT c.* FROM fts_chars f
                 JOIN characters c ON c.rowid = f.rowid
                 WHERE fts_chars MATCH ?1
                 LIMIT ?2",
            )?;
            let rows = stmt.query_map(params![pattern, limit], Self::map_char)?;
            chars = rows.collect::<rusqlite::Result<_>>()?;
        }

        // ── words ──
        if has_hanja && q.chars().count() >= 1 {
            // 한자 표기 정확 일치 우선, 그 다음 부분 매칭
            let mut stmt = conn.prepare_cached(
                "SELECT * FROM words WHERE hanja = ?1 ORDER BY homonym_no LIMIT ?2",
            )?;
            let rows = stmt.query_map(params![q, limit], Self::map_word_meta)?;
            words = rows.collect::<rusqlite::Result<_>>()?;

            // 부족하면 FTS5로 보완
            if (words.len() as i64) < limit && q.chars().count() >= 2 {
                let pattern = format!("\"{}\"", q);
                let mut stmt = conn.prepare_cached(
                    "SELECT w.* FROM fts_words f
                     JOIN words w ON w.id = f.word_id
                     WHERE fts_words MATCH ?1 AND w.hanja IS NOT NULL
                     LIMIT ?2",
                )?;
                let extra_limit = limit - words.len() as i64;
                let rows = stmt.query_map(params![pattern, extra_limit], Self::map_word_meta)?;
                let seen: std::collections::HashSet<i64> = words.iter().map(|w| w.id).collect();
                for w in rows.collect::<rusqlite::Result<Vec<_>>>()? {
                    if !seen.contains(&w.id) { words.push(w); }
                }
            }
        } else if has_hangul {
            // 한글 단어: 정확 매칭 → prefix
            let mut stmt = conn.prepare_cached(
                "SELECT * FROM words WHERE word_clean = ?1 ORDER BY homonym_no LIMIT ?2",
            )?;
            let rows = stmt.query_map(params![q, limit], Self::map_word_meta)?;
            words = rows.collect::<rusqlite::Result<_>>()?;

            if (words.len() as i64) < limit {
                let prefix = format!("{}%", q);
                let mut stmt = conn.prepare_cached(
                    "SELECT * FROM words WHERE word_clean LIKE ?1 AND word_clean != ?2
                     ORDER BY length(word_clean), word_clean LIMIT ?3",
                )?;
                let extra = limit - words.len() as i64;
                let rows = stmt.query_map(params![prefix, q, extra], Self::map_word_meta)?;
                for w in rows.collect::<rusqlite::Result<Vec<_>>>()? {
                    words.push(w);
                }
            }
        }

        for w in &mut words { Self::fill_senses(&conn, w)?; }

        Ok(SearchResults { chars, words })
    }
}

fn is_hanja(c: char) -> bool {
    let cp = c as u32;
    (0x3400..=0x9FFF).contains(&cp)
        || (0xF900..=0xFAFF).contains(&cp)
        || (0x20000..=0x2FFFF).contains(&cp)
}

fn is_hangul(c: char) -> bool {
    let cp = c as u32;
    (0xAC00..=0xD7A3).contains(&cp) || (0x1100..=0x11FF).contains(&cp)
}

fn is_latin_or_ws(c: char) -> bool {
    let cp = c as u32;
    c.is_ascii_alphanumeric()
        || c.is_ascii_whitespace()
        || c == '-' || c == '\''
        || (0x00C0..=0x024F).contains(&cp)  // Latin-1 Sup + Ext-A + Ext-B (병음 성조 부호 포함)
        || (0x1E00..=0x1EFF).contains(&cp)  // Latin Ext Additional
        || (0x0300..=0x036F).contains(&cp)  // Combining diacritical marks
}

fn sanitize_fts(q: &str) -> String {
    // FTS5 특수문자 (큰따옴표, 별표 등) 이스케이프 — 토큰만 추출해 따옴표로 감싸기
    let cleaned: String = q
        .chars()
        .map(|c| if c.is_alphanumeric() || c == '\u{0304}' || c == '\u{0301}' || c == '\u{0300}' || c == '\u{030c}' { c } else { ' ' })
        .collect();
    let toks: Vec<String> = cleaned
        .split_whitespace()
        .map(|t| format!("\"{}\"", t))
        .collect();
    toks.join(" ")
}
