mod config;
mod firewall;

use config::{save_config, Config};
use firewall::{start_firewall, update_subnets_cache, STATE};
use serde::{Deserialize, Serialize};
use std::net::Ipv4Addr;
use std::sync::atomic::{AtomicU32, Ordering};
use tauri::{AppHandle, Emitter};

const GITHUB_LATEST_RELEASE_API: &str =
    "https://api.github.com/repos/TypucT-TTV/G-Lock/releases/latest";
const GITHUB_RELEASES_URL: &str = "https://github.com/TypucT-TTV/G-Lock/releases/latest";
const HOTKEY_RELOAD_MESSAGE: u32 = windows_sys::Win32::UI::WindowsAndMessaging::WM_APP + 1;
static HOTKEY_THREAD_ID: AtomicU32 = AtomicU32::new(0);

#[derive(Debug, Deserialize)]
struct GitHubAsset {
    name: String,
    browser_download_url: String,
}

#[derive(Debug, Deserialize)]
struct GitHubRelease {
    tag_name: String,
    html_url: String,
    assets: Vec<GitHubAsset>,
}

#[derive(Debug, Serialize)]
struct UpdateCheck {
    current_version: String,
    latest_version: Option<String>,
    update_available: bool,
    release_url: String,
    download_url: Option<String>,
    error: Option<String>,
}

fn version_triplet(version: &str) -> Option<(u64, u64, u64)> {
    let normalized = version
        .trim()
        .trim_start_matches(['v', 'V'])
        .split('-')
        .next()?;
    let mut parts = normalized.split('.');
    let major = parts.next()?.parse().ok()?;
    let minor = parts.next()?.parse().ok()?;
    let patch = parts.next()?.parse().ok()?;
    Some((major, minor, patch))
}

fn is_newer_version(latest: &str, current: &str) -> bool {
    matches!(
        (version_triplet(latest), version_triplet(current)),
        (Some(latest), Some(current)) if latest > current
    )
}

fn preferred_download_url(assets: &[GitHubAsset]) -> Option<String> {
    assets
        .iter()
        .find(|asset| asset.name.to_ascii_lowercase().ends_with("_x64-setup.exe"))
        .or_else(|| {
            assets
                .iter()
                .find(|asset| asset.name.to_ascii_lowercase().ends_with(".msi"))
        })
        .or_else(|| {
            assets
                .iter()
                .find(|asset| asset.name.to_ascii_lowercase().ends_with(".exe"))
        })
        .map(|asset| asset.browser_download_url.clone())
}

#[tauri::command]
async fn check_for_updates() -> UpdateCheck {
    let current_version = env!("CARGO_PKG_VERSION").to_string();
    let fallback = |error: String| UpdateCheck {
        current_version: current_version.clone(),
        latest_version: None,
        update_available: false,
        release_url: GITHUB_RELEASES_URL.to_string(),
        download_url: None,
        error: Some(error),
    };

    let client = match reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(6))
        .user_agent(format!("G-Lock/{current_version}"))
        .build()
    {
        Ok(client) => client,
        Err(error) => return fallback(error.to_string()),
    };

    let response = match client
        .get(GITHUB_LATEST_RELEASE_API)
        .header("Accept", "application/vnd.github+json")
        .send()
        .await
    {
        Ok(response) => response,
        Err(error) => return fallback(error.to_string()),
    };

    let release = match response.error_for_status() {
        Ok(response) => match response.json::<GitHubRelease>().await {
            Ok(release) => release,
            Err(error) => return fallback(error.to_string()),
        },
        Err(error) => return fallback(error.to_string()),
    };

    UpdateCheck {
        current_version: current_version.clone(),
        latest_version: Some(release.tag_name.clone()),
        update_available: is_newer_version(&release.tag_name, &current_version),
        release_url: release.html_url,
        download_url: preferred_download_url(&release.assets),
        error: None,
    }
}

#[tauri::command]
fn get_status() -> serde_json::Value {
    let state = STATE.read();
    serde_json::json!({
        "active_session": state.active_session,
        "is_locked": state.is_locked,
        "is_running": state.is_running,
        "driver_error": state.driver_error.clone(),
    })
}

#[tauri::command]
fn toggle_lock(app: AppHandle) -> serde_json::Value {
    toggle_lock_logic(&app);
    get_status()
}

fn toggled_session_mode(is_locked: bool) -> String {
    if is_locked {
        "Lock".to_string()
    } else {
        "Open".to_string()
    }
}

pub fn update_window_icon(app: &AppHandle) {
    use tauri::image::Image;
    use tauri::Manager;
    if let Some(window) = app.get_webview_window("main") {
        let is_locked = STATE.read().is_locked;
        let icon_bytes = if is_locked {
            include_bytes!("../icons/icon_locked.png").as_slice()
        } else {
            include_bytes!("../icons/icon_open.png").as_slice()
        };
        if let Ok(icon) = Image::from_bytes(icon_bytes) {
            let _ = window.set_icon(icon);
        }
    }
}

fn toggle_lock_logic(app: &AppHandle) {
    let is_locked;
    let sound_enabled;
    {
        let mut state = STATE.write();
        if state.driver_error.is_some() {
            return;
        }
        state.is_locked = !state.is_locked;
        is_locked = state.is_locked;
        sound_enabled = state.config.sound_enabled;

        state.active_session = toggled_session_mode(is_locked);
    }

    if sound_enabled {
        let sound_name = if is_locked { "lock" } else { "unlock" };
        let _ = app.emit("play-sound", sound_name);
    }
    let _ = app.emit("status-changed", ());
    update_window_icon(app);
}

#[tauri::command]
fn start_session(session_type: String, app: AppHandle) -> Result<serde_json::Value, String> {
    if !is_supported_session(&session_type) {
        return Err("Unsupported session type".to_string());
    }
    {
        let mut state = STATE.write();
        state.is_locked = session_type == "Lock";
        state.active_session = session_type;
    }
    start_firewall(app.clone());
    let _ = app.emit("status-changed", ());
    update_window_icon(&app);
    Ok(get_status())
}

fn is_supported_session(value: &str) -> bool {
    matches!(value, "Open" | "Lock")
}

#[tauri::command]
fn stop_session(app: AppHandle) -> serde_json::Value {
    {
        let mut state = STATE.write();
        state.active_session = "Open".to_string();
        state.is_locked = false;
    }
    let _ = app.emit("status-changed", ());
    update_window_icon(&app);
    get_status()
}

#[tauri::command]
fn get_lists() -> serde_json::Value {
    let state = STATE.read();
    let mut blacklist = state.blacklist.iter().cloned().collect::<Vec<String>>();
    blacklist.sort();
    serde_json::json!({
        "blacklist": blacklist,
    })
}

fn ensure_blacklist(value: &str) -> Result<(), String> {
    if value == "blacklist" {
        Ok(())
    } else {
        Err("Only the advanced IP blocklist is supported".to_string())
    }
}

fn normalize_ip_rule(value: &str) -> Result<String, String> {
    let value = value.trim();
    if let Ok(ip) = value.parse::<Ipv4Addr>() {
        return Ok(ip.to_string());
    }
    if let Ok(network) = value.parse::<ipnet::Ipv4Net>() {
        return Ok(network.trunc().to_string());
    }
    Err("Enter a valid IPv4 address or IPv4 CIDR network".to_string())
}

#[tauri::command]
fn add_to_list(list_type: String, ip: String, app: AppHandle) -> Result<serde_json::Value, String> {
    ensure_blacklist(&list_type)?;
    let ip = normalize_ip_rule(&ip)?;

    {
        let mut state = STATE.write();
        let mut next_config = state.config.clone();
        let mut next_blacklist = state.blacklist.clone();
        next_blacklist.insert(ip.clone());
        next_config.blacklist.insert(ip, "".to_string());
        save_config(&next_config).map_err(|e| e.to_string())?;
        state.config = next_config;
        state.blacklist = next_blacklist;
    }

    update_subnets_cache();
    let _ = app.emit("lists-changed", ());
    Ok(get_lists())
}

#[tauri::command]
fn delete_from_list(
    list_type: String,
    ip: String,
    app: AppHandle,
) -> Result<serde_json::Value, String> {
    ensure_blacklist(&list_type)?;
    let ip = normalize_ip_rule(&ip)?;
    {
        let mut state = STATE.write();
        let mut next_config = state.config.clone();
        let mut next_blacklist = state.blacklist.clone();
        next_blacklist.remove(&ip);
        next_config.blacklist.remove(&ip);
        save_config(&next_config).map_err(|e| e.to_string())?;
        state.config = next_config;
        state.blacklist = next_blacklist;
    }

    update_subnets_cache();
    let _ = app.emit("lists-changed", ());
    Ok(get_lists())
}

#[tauri::command]
fn clear_list(list_type: String, app: AppHandle) -> Result<serde_json::Value, String> {
    ensure_blacklist(&list_type)?;
    {
        let mut state = STATE.write();
        let mut next_config = state.config.clone();
        next_config.blacklist.clear();
        save_config(&next_config).map_err(|e| e.to_string())?;
        state.config = next_config;
        state.blacklist.clear();
    }

    update_subnets_cache();
    let _ = app.emit("lists-changed", ());
    Ok(get_lists())
}

#[tauri::command]
fn get_settings() -> Config {
    STATE.read().config.clone()
}

#[tauri::command]
fn save_settings(mut config: Config) -> Result<(), String> {
    config.validate()?;
    {
        let mut state = STATE.write();
        config.blacklist = state.config.blacklist.clone();
        config.window_width = state.config.window_width;
        config.window_height = state.config.window_height;
        config.window_x = state.config.window_x;
        config.window_y = state.config.window_y;
        save_config(&config).map_err(|e| e.to_string())?;
        state.config = config.clone();
    }
    notify_hotkey_listener();
    Ok(())
}

fn notify_hotkey_listener() {
    let thread_id = HOTKEY_THREAD_ID.load(Ordering::Acquire);
    if thread_id == 0 {
        return;
    }

    unsafe {
        windows_sys::Win32::UI::WindowsAndMessaging::PostThreadMessageW(
            thread_id,
            HOTKEY_RELOAD_MESSAGE,
            0,
            0,
        );
    }
}

#[tauri::command]
fn list_log_files() -> Result<Vec<String>, String> {
    let mut files = Vec::new();
    let logs_dir = if let Ok(exe_path) = std::env::current_exe() {
        if let Some(parent) = exe_path.parent() {
            parent.join("logs")
        } else {
            std::path::PathBuf::from("logs")
        }
    } else {
        std::path::PathBuf::from("logs")
    };

    if logs_dir.exists() {
        if let Ok(entries) = std::fs::read_dir(logs_dir) {
            for entry in entries.flatten() {
                if let Some(name) = entry.file_name().to_str() {
                    if name.starts_with("connections_") && name.ends_with(".log") {
                        files.push(name.to_string());
                    }
                }
            }
        }
    }
    files.sort_by(|a, b| b.cmp(a)); // Newest first
    Ok(files)
}

fn resolve_log_file(filename: &str) -> Result<std::path::PathBuf, String> {
    let path = std::path::Path::new(filename);
    let date = filename
        .strip_prefix("connections_")
        .and_then(|value| value.strip_suffix(".log"));
    let valid_date = date.is_some_and(|value| {
        value.len() == 10
            && value.bytes().enumerate().all(|(index, byte)| match index {
                4 | 7 => byte == b'-',
                _ => byte.is_ascii_digit(),
            })
    });
    let is_plain_filename = path.components().count() == 1 && valid_date;
    if !is_plain_filename {
        return Err("Invalid log filename".to_string());
    }

    let logs_dir = if let Ok(exe_path) = std::env::current_exe() {
        exe_path
            .parent()
            .map(|parent| parent.join("logs"))
            .unwrap_or_else(|| std::path::PathBuf::from("logs"))
    } else {
        std::path::PathBuf::from("logs")
    };
    let file_path = logs_dir.join(filename);
    if !file_path.is_file() {
        return Err("File not found".to_string());
    }
    Ok(file_path)
}

#[tauri::command]
fn read_log_file(filename: String) -> Result<Vec<firewall::LogEntry>, String> {
    let file_path = resolve_log_file(&filename)?;

    let content = std::fs::read_to_string(file_path).map_err(|e| e.to_string())?;
    let mut entries = Vec::new();
    for line in content.lines() {
        if let Ok(entry) = serde_json::from_str::<firewall::LogEntry>(line) {
            entries.push(entry);
        }
    }
    Ok(entries)
}

#[tauri::command]
fn open_log_file_in_notepad(filename: String) -> Result<(), String> {
    let file_path = resolve_log_file(&filename)?;

    std::process::Command::new("notepad.exe")
        .arg(file_path)
        .spawn()
        .map_err(|e| e.to_string())?;
    Ok(())
}

#[tauri::command]
fn open_url(url: String) -> Result<(), String> {
    if url.starts_with("https://") || url.starts_with("http://") {
        #[cfg(target_os = "windows")]
        {
            std::process::Command::new("cmd")
                .args(["/C", "start", "", &url])
                .spawn()
                .map_err(|e| e.to_string())?;
        }
        Ok(())
    } else {
        Err("Invalid URL protocol".to_string())
    }
}

fn panic_unlock_logic(app: &AppHandle) {
    let sound_enabled = {
        let mut state = STATE.write();
        state.active_session = "Open".to_string();
        state.is_locked = false;
        state.config.sound_enabled
    };
    if sound_enabled {
        let _ = app.emit("play-sound", "unlock");
    }
    let _ = app.emit("status-changed", ());
    update_window_icon(app);
}

fn start_hotkey_listener(app_handle: AppHandle) {
    std::thread::spawn(move || {
        use windows_sys::Win32::System::Threading::GetCurrentThreadId;
        use windows_sys::Win32::UI::Input::KeyboardAndMouse::{
            RegisterHotKey, UnregisterHotKey, MOD_ALT, MOD_CONTROL, MOD_NOREPEAT, MOD_SHIFT,
        };
        use windows_sys::Win32::UI::WindowsAndMessaging::{
            GetMessageW, PeekMessageW, MSG, PM_NOREMOVE, WM_HOTKEY,
        };

        let hotkey_id = 1_i32;
        let panic_hotkey_id = 2_i32;
        let mut msg: MSG = unsafe { std::mem::zeroed() };

        unsafe {
            // Force creation of this thread's message queue before publishing its ID.
            PeekMessageW(&mut msg, 0, 0, 0, PM_NOREMOVE);
            HOTKEY_THREAD_ID.store(GetCurrentThreadId(), Ordering::Release);

            let register_hotkeys = |config: &Config| {
                let mut lock_modifiers = MOD_NOREPEAT;
                if config.hotkey_ctrl {
                    lock_modifiers |= MOD_CONTROL;
                }
                if config.hotkey_alt {
                    lock_modifiers |= MOD_ALT;
                }
                if config.hotkey_shift {
                    lock_modifiers |= MOD_SHIFT;
                }
                let lock_result = RegisterHotKey(0, hotkey_id, lock_modifiers, config.hotkey_vk);
                if lock_result == 0 {
                    firewall::log_system_message("SYSTEM ERROR: Failed to register lock hotkey.");
                }

                let panic_modifiers = if config.panic_hotkey_ctrl {
                    MOD_CONTROL | MOD_NOREPEAT
                } else {
                    MOD_NOREPEAT
                };
                let panic_result =
                    RegisterHotKey(0, panic_hotkey_id, panic_modifiers, config.panic_hotkey_vk);
                if panic_result == 0 {
                    firewall::log_system_message("SYSTEM ERROR: Failed to register panic hotkey.");
                }
            };

            register_hotkeys(&STATE.read().config.clone());

            while GetMessageW(&mut msg, 0, 0, 0) != 0 {
                if msg.message == HOTKEY_RELOAD_MESSAGE {
                    UnregisterHotKey(0, hotkey_id);
                    UnregisterHotKey(0, panic_hotkey_id);
                    register_hotkeys(&STATE.read().config.clone());
                } else if msg.message == WM_HOTKEY {
                    match msg.wParam as i32 {
                        id if id == hotkey_id => toggle_lock_logic(&app_handle),
                        id if id == panic_hotkey_id => panic_unlock_logic(&app_handle),
                        _ => {}
                    }
                }
            }

            UnregisterHotKey(0, hotkey_id);
            UnregisterHotKey(0, panic_hotkey_id);
            HOTKEY_THREAD_ID.store(0, Ordering::Release);
        }
    });
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .setup(|app| {
            let handle = app.handle().clone();

            // Extract WinDivert binaries from packaged resources if they don't exist next to the executable
            use tauri::path::BaseDirectory;
            use tauri::Manager;

            if let Ok(exe_path) = std::env::current_exe() {
                if let Some(exe_dir) = exe_path.parent() {
                    let dll_res = app.path().resolve("WinDivert.dll", BaseDirectory::Resource);
                    let sys_res = app
                        .path()
                        .resolve("WinDivert64.sys", BaseDirectory::Resource);

                    if let Ok(dll_path) = dll_res {
                        firewall::log_system_message(&format!(
                            "SYSTEM: Resolved dll resource path to {:?}",
                            dll_path
                        ));
                        let dest = exe_dir.join("WinDivert.dll");
                        let same_file = matches!(
                            (dll_path.canonicalize(), dest.canonicalize()),
                            (Ok(source), Ok(destination)) if source == destination
                        );
                        if !same_file && !dest.exists() && dll_path.exists() {
                            if let Err(error) = std::fs::copy(&dll_path, &dest) {
                                firewall::log_system_message(&format!(
                                    "SYSTEM ERROR: Failed to install WinDivert.dll: {}",
                                    error
                                ));
                            }
                        } else if !dll_path.exists() {
                            firewall::log_system_message(
                                "SYSTEM WARNING: Resolved dll resource file does not exist!",
                            );
                        }
                    }
                    if let Ok(sys_path) = sys_res {
                        firewall::log_system_message(&format!(
                            "SYSTEM: Resolved sys resource path to {:?}",
                            sys_path
                        ));
                        let dest = exe_dir.join("WinDivert64.sys");
                        let same_file = matches!(
                            (sys_path.canonicalize(), dest.canonicalize()),
                            (Ok(source), Ok(destination)) if source == destination
                        );
                        if !same_file && !dest.exists() && sys_path.exists() {
                            if let Err(error) = std::fs::copy(&sys_path, &dest) {
                                firewall::log_system_message(&format!(
                                    "SYSTEM ERROR: Failed to install WinDivert64.sys: {}",
                                    error
                                ));
                            }
                        } else if !sys_path.exists() {
                            firewall::log_system_message(
                                "SYSTEM WARNING: Resolved sys resource file does not exist!",
                            );
                        }
                    }
                }
            }

            start_hotkey_listener(handle.clone());
            // Set initial window icon
            update_window_icon(&handle);

            // Restore window size and position, and register save-on-close event
            if let Some(window) = app.get_webview_window("main") {
                let config = STATE.read().config.clone();
                if let (Some(w_val), Some(h_val)) = (config.window_width, config.window_height) {
                    let _ = window.set_size(tauri::Size::Physical(tauri::PhysicalSize {
                        width: w_val,
                        height: h_val,
                    }));
                }
                if let (Some(x_val), Some(y_val)) = (config.window_x, config.window_y) {
                    let _ =
                        window.set_position(tauri::Position::Physical(tauri::PhysicalPosition {
                            x: x_val,
                            y: y_val,
                        }));
                }

                let w_clone = window.clone();
                window.on_window_event(move |event| match event {
                    tauri::WindowEvent::Resized(_) => {
                        if !w_clone.is_minimized().unwrap_or(false)
                            && !w_clone.is_maximized().unwrap_or(false)
                        {
                            if let Ok(outer_size) = w_clone.outer_size() {
                                let mut state = STATE.write();
                                state.config.window_width = Some(outer_size.width);
                                state.config.window_height = Some(outer_size.height);
                                if let Err(error) = save_config(&state.config) {
                                    firewall::log_system_message(&format!(
                                        "SYSTEM ERROR: Failed to save window size: {}",
                                        error
                                    ));
                                }
                            }
                        }
                    }
                    tauri::WindowEvent::Moved(pos) => {
                        if !w_clone.is_minimized().unwrap_or(false)
                            && !w_clone.is_maximized().unwrap_or(false)
                        {
                            let mut state = STATE.write();
                            state.config.window_x = Some(pos.x);
                            state.config.window_y = Some(pos.y);
                            if let Err(error) = save_config(&state.config) {
                                firewall::log_system_message(&format!(
                                    "SYSTEM ERROR: Failed to save window position: {}",
                                    error
                                ));
                            }
                        }
                    }
                    tauri::WindowEvent::CloseRequested { .. } => {
                        let state = STATE.read();
                        if let Err(error) = save_config(&state.config) {
                            firewall::log_system_message(&format!(
                                "SYSTEM ERROR: Failed to save configuration on close: {}",
                                error
                            ));
                        }
                        firewall::shutdown_firewall();
                    }
                    _ => {}
                });
            }

            // Start default open session
            start_firewall(handle);
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            get_status,
            toggle_lock,
            start_session,
            stop_session,
            get_lists,
            add_to_list,
            delete_from_list,
            clear_list,
            get_settings,
            save_settings,
            check_for_updates,
            list_log_files,
            read_log_file,
            open_log_file_in_notepad,
            open_url
        ])
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|_app_handle, event| {
            if let tauri::RunEvent::Exit = event {
                firewall::shutdown_firewall();
            }
        });
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ip_rules_are_validated_and_normalized() {
        assert_eq!(normalize_ip_rule(" 203.0.113.8 ").unwrap(), "203.0.113.8");
        assert_eq!(
            normalize_ip_rule("192.168.1.99/24").unwrap(),
            "192.168.1.0/24"
        );
        assert!(normalize_ip_rule("not-an-ip").is_err());
        assert!(normalize_ip_rule("2001:db8::1").is_err());
    }

    #[test]
    fn log_paths_reject_traversal_and_alternate_streams() {
        assert!(resolve_log_file("../connections_2026-07-15.log").is_err());
        assert!(resolve_log_file("connections_2026-07-15.log:secret").is_err());
        assert!(resolve_log_file("data.json").is_err());
    }

    #[test]
    fn lock_toggle_has_only_open_and_locked_states() {
        assert_eq!(toggled_session_mode(true), "Lock");
        assert_eq!(toggled_session_mode(false), "Open");
    }

    #[test]
    fn experimental_sessions_and_lists_are_rejected() {
        assert!(is_supported_session("Open"));
        assert!(is_supported_session("Lock"));
        assert!(!is_supported_session("Solo"));
        assert!(!is_supported_session("Whitelist"));
        assert!(ensure_blacklist("blacklist").is_ok());
        assert!(ensure_blacklist("whitelist").is_err());
    }

    #[test]
    fn release_versions_are_compared_semantically() {
        assert!(is_newer_version("v2.0.45", "2.0.44"));
        assert!(is_newer_version("v2.1.0", "2.0.99"));
        assert!(!is_newer_version("v2.0.44", "2.0.44"));
        assert!(!is_newer_version("v2.0.43", "2.0.44"));
        assert!(!is_newer_version("unexpected", "2.0.44"));
    }

    #[test]
    fn installer_asset_is_preferred_for_updates() {
        let assets = vec![
            GitHubAsset {
                name: "G-Lock_2.0.45_x64_en-US.msi".to_string(),
                browser_download_url: "https://example.test/app.msi".to_string(),
            },
            GitHubAsset {
                name: "G-Lock_2.0.45_x64-setup.exe".to_string(),
                browser_download_url: "https://example.test/setup.exe".to_string(),
            },
        ];

        assert_eq!(
            preferred_download_url(&assets).as_deref(),
            Some("https://example.test/setup.exe")
        );
    }
}
