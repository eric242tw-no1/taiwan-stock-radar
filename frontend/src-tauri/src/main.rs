// Prevents additional console window on Windows in release mode
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::net::TcpStream;
use std::time::Duration;

const PROJECT: &str = r"C:\Users\ERIC\projects\taiwan-stock-radar";

/// 埠已有服務在聽 → 該服務已由 bat 或前次啟動帶起，不重複 spawn
fn port_in_use(port: u16) -> bool {
    TcpStream::connect_timeout(
        &format!("127.0.0.1:{port}").parse().unwrap(),
        Duration::from_millis(300),
    )
    .is_ok()
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .setup(|_app| {
            // 1. Start FastAPI backend (host venv; DB 用 db.py 預設 backend\data\stockradar.db)
            if !port_in_use(8000) {
                std::process::Command::new("powershell")
                    .args([
                        "-NoProfile",
                        "-WindowStyle",
                        "Minimized",
                        "-Command",
                        &format!(
                            "cd '{}\\backend'; .venv\\Scripts\\python.exe -m uvicorn main:app --port 8000",
                            PROJECT
                        ),
                    ])
                    .spawn()
                    .ok();
            }

            // 2. Start Next.js dev server on host (port 3002)
            if !port_in_use(3002) {
                std::process::Command::new("powershell")
                    .args([
                        "-NoProfile",
                        "-WindowStyle",
                        "Minimized",
                        "-Command",
                        &format!(
                            "cd '{}\\frontend'; npm run dev -- --hostname 127.0.0.1 -p 3002",
                            PROJECT
                        ),
                    ])
                    .spawn()
                    .ok();
            }

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
