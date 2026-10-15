use std::path::PathBuf;
use std::process::{Child, Command};
use std::sync::Mutex;
use tauri::{AppHandle, Manager};

#[cfg(windows)]
use std::os::windows::process::CommandExt;

#[cfg(windows)]
use std::os::windows::io::AsRawHandle;

#[cfg(windows)]
use windows::Win32::System::JobObjects::{
    AssignProcessToJobObject, CreateJobObjectW, SetInformationJobObject,
    JobObjectExtendedLimitInformation, JOBOBJECT_EXTENDED_LIMIT_INFORMATION,
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
};

#[cfg(windows)]
use windows::Win32::Foundation::HANDLE;

#[cfg(windows)]
const CREATE_NO_WINDOW: u32 = 0x0800_0000;

static BACKEND_PROCESS: Mutex<Option<Child>> = Mutex::new(None);

#[cfg(windows)]
static JOB_OBJECT: Mutex<Option<isize>> = Mutex::new(None);

#[cfg(windows)]
fn assign_to_job(child: &Child) {
    unsafe {
        if let Ok(job_handle) = CreateJobObjectW(None, None) {
            let mut info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION::default();
            info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
            let res = SetInformationJobObject(
                job_handle,
                JobObjectExtendedLimitInformation,
                &info as *const _ as *const _,
                std::mem::size_of::<JOBOBJECT_EXTENDED_LIMIT_INFORMATION>() as u32,
            );
            if res.is_ok() {
                let process_handle = HANDLE(child.as_raw_handle() as _);
                let _ = AssignProcessToJobObject(job_handle, process_handle);
                let mut lock = JOB_OBJECT.lock().unwrap();
                *lock = Some(job_handle.0 as isize);
                crate::log::line("Assigned Caf backend process to Windows Job Object (KILL_ON_JOB_CLOSE).");
            }
        }
    }
}

pub fn start(app: &AppHandle) {
    if is_backend_alive() {
        crate::log::line("Caf voice backend already running on port 8000; skipping spawn.");
        return;
    }

    let exe_path = find_backend_exe(app);
    let mut child = None;
    let parent_pid = std::process::id().to_string();

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
        cmd.env("PYTHONUNBUFFERED", "1");
        cmd.env("COUCOU_PARENT_PID", &parent_pid);

        #[cfg(windows)]
        cmd.creation_flags(CREATE_NO_WINDOW);

        if let Ok(c) = cmd.spawn() {
            #[cfg(windows)]
            assign_to_job(&c);
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
        cmd.env("COUCOU_PARENT_PID", &parent_pid);
        #[cfg(windows)]
        cmd.creation_flags(CREATE_NO_WINDOW);

        if let Ok(c) = cmd.spawn() {
            #[cfg(windows)]
            assign_to_job(&c);
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
    // 1. Enviar solicitud de cierre elegante por HTTP usando TcpStream nativo
    if let Ok(mut stream) = std::net::TcpStream::connect("127.0.0.1:8000") {
        let _ = stream.set_write_timeout(Some(std::time::Duration::from_millis(500)));
        let _ = stream.set_read_timeout(Some(std::time::Duration::from_millis(500)));
        let req = "POST /shutdown HTTP/1.1\r\nHost: 127.0.0.1:8000\r\nContent-Length: 0\r\nConnection: close\r\n\r\n";
        use std::io::Write;
        let _ = stream.write_all(req.as_bytes());
        std::thread::sleep(std::time::Duration::from_millis(150));
    }

    // 2. Terminar proceso hijo si todavía está corriendo
    let mut lock = BACKEND_PROCESS.lock().unwrap();
    if let Some(mut child) = lock.take() {
        crate::log::line("Stopping Caf voice backend...");
        let _ = child.kill();
        let _ = child.wait();
    }

    #[cfg(windows)]
    {
        let mut job_lock = JOB_OBJECT.lock().unwrap();
        if let Some(raw) = job_lock.take() {
            unsafe {
                let _ = windows::Win32::Foundation::CloseHandle(HANDLE(raw as *mut _));
            }
        }
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
