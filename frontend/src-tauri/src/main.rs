// Prevents additional console window on Windows in release mode
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::path::PathBuf;

const PROJECT: &str = r"C:\Users\ERIC\projects\taiwan-stock-radar";

fn main() {
    tauri::Builder::default()
        .setup(|app| {
            // Resolve AppData path for SQLite DB
            use tauri::Manager;
            let db_path: PathBuf = app
                .path()
                .app_data_dir()
                .map(|p| p.join("stockradar.db"))
                .unwrap_or_else(|_| PathBuf::from(format!(r"{}\backend\data\stockradar.db", PROJECT)));

            let db_path_str = db_path.to_string_lossy().to_string();

            // 1. Start Redis via Docker (SQLite is embedded, no postgres needed)
            std::process::Command::new("cmd")
                .args(["/C", "docker-compose", "up", "redis", "-d"])
                .current_dir(PROJECT)
                .spawn()
                .ok();

            // 2. Start FastAPI with DB_PATH injected
            std::process::Command::new("powershell")
                .args([
                    "-NoProfile",
                    "-WindowStyle", "Minimized",
                    "-Command",
                    &format!(
                        "$env:DB_PATH='{}'; cd '{}\\backend'; .venv\\Scripts\\python.exe -m uvicorn main:app --port 8000",
                        db_path_str, PROJECT
                    ),
                ])
                .spawn()
                .ok();

            // 3. Start Next.js dev server on host (port 3002)
            std::process::Command::new("powershell")
                .args([
                    "-NoProfile",
                    "-WindowStyle", "Minimized",
                    "-Command",
                    &format!(
                        "cd '{}\\frontend'; npm run dev -- --hostname 127.0.0.1 -p 3002",
                        PROJECT
                    ),
                ])
                .spawn()
                .ok();

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
