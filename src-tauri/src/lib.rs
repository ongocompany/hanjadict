//! hanjadict — Tauri 2 앱 진입점.

mod db;

use db::{CharEntry, Database, SearchResults, WordEntry};
use std::path::PathBuf;
use std::sync::Arc;
use tauri::Manager;

struct AppState {
    db: Arc<Database>,
}

fn db_path(handle: &tauri::AppHandle) -> Result<PathBuf, String> {
    // 후보 경로 모두 시도. 첫 번째 발견 시 사용.
    let mut tried: Vec<String> = Vec::new();
    let resource_keys = ["resources/hanjadict.db", "_up_/resources/hanjadict.db"];
    for key in resource_keys {
        match handle
            .path()
            .resolve(key, tauri::path::BaseDirectory::Resource)
        {
            Ok(p) => {
                tried.push(p.display().to_string());
                if p.exists() {
                    return Ok(p);
                }
            }
            Err(e) => tried.push(format!("(resolve {key} 실패: {e})")),
        }
    }
    // Dev fallback — cwd 기준
    if let Ok(cwd) = std::env::current_dir() {
        for cand in [
            cwd.join("resources/hanjadict.db"),
            cwd.join("../resources/hanjadict.db"),
        ] {
            tried.push(cand.display().to_string());
            if cand.exists() {
                return cand
                    .canonicalize()
                    .map_err(|e| format!("DB 경로 정규화 실패: {e}"));
            }
        }
    }
    Err(format!(
        "DB 파일을 찾을 수 없음. 시도한 경로:\n  {}",
        tried.join("\n  ")
    ))
}

#[tauri::command]
fn search(state: tauri::State<'_, AppState>, query: String, limit: Option<i64>) -> Result<SearchResults, String> {
    state
        .db
        .search(&query, limit.unwrap_or(50))
        .map_err(|e| e.to_string())
}

#[tauri::command]
fn get_char(state: tauri::State<'_, AppState>, ch: String) -> Result<Option<CharEntry>, String> {
    state.db.get_char(&ch).map_err(|e| e.to_string())
}

#[tauri::command]
fn get_word(state: tauri::State<'_, AppState>, id: i64) -> Result<Option<WordEntry>, String> {
    state.db.get_word(id).map_err(|e| e.to_string())
}

#[tauri::command]
fn words_by_char(
    state: tauri::State<'_, AppState>,
    ch: String,
    limit: Option<i64>,
) -> Result<Vec<WordEntry>, String> {
    state
        .db
        .words_by_char(&ch, limit.unwrap_or(30))
        .map_err(|e| e.to_string())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .setup(|app| {
            let path = db_path(&app.handle()).map_err(|e| std::io::Error::new(std::io::ErrorKind::NotFound, e))?;
            eprintln!("[hanjadict] DB: {}", path.display());
            let db = Database::open(&path)
                .map_err(|e| std::io::Error::new(std::io::ErrorKind::Other, e.to_string()))?;
            app.manage(AppState { db: Arc::new(db) });
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            search,
            get_char,
            get_word,
            words_by_char,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
