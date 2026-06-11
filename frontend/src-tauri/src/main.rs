// Prevents additional console window on Windows in release mode
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    tauri::Builder::default()
        .setup(|_app| {
            // 啟動時自動執行 docker compose（後台服務）
            std::process::Command::new("cmd")
                .args(["/C", "docker compose up -d"])
                .current_dir(
                    std::env::current_dir()
                        .unwrap()
                        .parent()
                        .unwrap()
                        .to_path_buf(),
                )
                .spawn()
                .ok();
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
