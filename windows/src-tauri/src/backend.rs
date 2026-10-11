use std::path::PathBuf;
use std::process::{Child, Command};
use std::sync::Mutex;
use tauri::{AppHandle, Manager};

#[cfg(windows)]
use std::os::windows::process::CommandExt;

#[cfg(windows)]
const CREATE_NO_WINDOW: u32 = 0x0800_0000;

static BACKEND_PROCESS: Mutex<Option<Child>> = Mutex::new(None);

pub fn start(app: &AppHandle) {
    if is_backend_alive() {
        crate::log::line("Caf voice backend already running on port 8000; skipping spawn.");
        return;
    }

    let exe_path = find_backend_exe(app);
    let mut child = None;

    if let Some(ref path) = exe_path {
        crate::log::line(format!("Starting Caf voice backend from: {}", path.display()));
        let mut cmd = Command::new(path);
        if let Some(parent) = path.parent() {
            cmd.current_dir(parent);
            let log_path = parent.join("coucou-backend.log");
            if let Ok(f) = std::fs::OpenOptions::new().create(true).append(true).open(&log_path) {
                if let Ok(f_err) = f.try_clone() {
                    cmd.stdout(f);
                    cmd.stderr(f_err);
                }
            }
        }

        if let Some(key) = crate::secrets::get("caf-api-key").or_else(|| crate::secrets::get("google-api-key")) {
            cmd.env("GEMINI_API_KEY", key);
        }

        #[cfg(windows)]
        cmd.creation_flags(CREATE_NO_WINDOW);

        if let Ok(c) = cmd.spawn() {
            child = Some(c);
        } else {
            crate::log::line("Failed to spawn coucou-backend executable, attempting fallback to python...");
        }
    }

    if child.is_none() {
        crate::log::line("Attempting to start backend via python...");
        let mut cmd = Command::new("python");
        cmd.args(["-m", "uvicorn", "server:app", "--host", "127.0.0.1", "--port", "8000"]);
        if let Some(key) = crate::secrets::get("caf-api-key").or_else(|| crate::secrets::get("google-api-key")) {
            cmd.env("GEMINI_API_KEY", key);
        }
        #[cfg(windows)]
        cmd.creation_flags(CREATE_NO_WINDOW);

        if let Ok(c) = cmd.spawn() {
            child = Some(c);
        }
    }

    if let Some(c) = child {
        let mut lock = BACKEND_PROCESS.lock().unwrap();
        *lock = Some(c);
        crate::log::line("Caf voice backend process started.");
    } else {
        crate::log::line("Warning: Could not start Caf voice backend.");
    }
}

pub fn stop() {
    let mut lock = BACKEND_PROCESS.lock().unwrap();
    if let Some(mut child) = lock.take() {
        crate::log::line("Stopping Caf voice backend...");
        let _ = child.kill();
        let _ = child.wait();
    }
}

fn is_backend_alive() -> bool {
    std::net::TcpStream::connect("127.0.0.1:8000").is_ok()
}

fn find_backend_exe(app: &AppHandle) -> Option<PathBuf> {
    let mut candidates: Vec<PathBuf> = Vec::new();

    // 1. Installed / bundled resource:
    if let Ok(p) = app.path().resolve("coucou-backend.exe", tauri::path::BaseDirectory::Resource) {
        candidates.push(p);
    }
    if let Ok(p) = app.path().resolve("binaries/coucou-backend-x86_64-pc-windows-msvc.exe", tauri::path::BaseDirectory::Resource) {
        candidates.push(p);
    }
    if let Ok(p) = app.path().resolve("coucou-backend-x86_64-pc-windows-msvc.exe", tauri::path::BaseDirectory::Resource) {
        candidates.push(p);
    }

    // 2. Next to the main executable (Coucou.exe):
    if let Ok(exe) = std::env::current_exe() {
        if let Some(parent) = exe.parent() {
            candidates.push(parent.join("coucou-backend.exe"));
            candidates.push(parent.join("coucou-backend-x86_64-pc-windows-msvc.exe"));
            candidates.push(parent.join("binaries/coucou-backend-x86_64-pc-windows-msvc.exe"));
            candidates.push(parent.join("../../../src-tauri/binaries/coucou-backend-x86_64-pc-windows-msvc.exe"));
        }
    }

    // 3. Current working directory / dev path:
    candidates.push(PathBuf::from("windows/src-tauri/binaries/coucou-backend-x86_64-pc-windows-msvc.exe"));
    candidates.push(PathBuf::from("src-tauri/binaries/coucou-backend-x86_64-pc-windows-msvc.exe"));
    candidates.push(PathBuf::from("binaries/coucou-backend-x86_64-pc-windows-msvc.exe"));

    candidates.into_iter().find(|p| p.exists())
}
