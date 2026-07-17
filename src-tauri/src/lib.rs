mod config;
mod firewall;

use config::{save_config, Config};
use firewall::{start_firewall, update_subnets_cache, STATE};
use std::net::Ipv4Addr;
use tauri::{AppHandle, Emitter};

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
    Ok(())
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
        use windows_sys::Win32::UI::Input::KeyboardAndMouse::{RegisterHotKey, MOD_CONTROL};
        use windows_sys::Win32::UI::WindowsAndMessaging::{GetMessageW, MSG, WM_HOTKEY};

        let config = STATE.read().config.clone();
        let hotkey_id = 1_i32;
        let panic_hotkey_id = 2_i32;

        unsafe {
            let res = RegisterHotKey(0, hotkey_id, 0, config.hotkey_vk);
            if res == 0 {
                firewall::log_system_message("SYSTEM ERROR: Failed to register lock hotkey.");
            }
            let panic_modifiers = if config.panic_hotkey_ctrl {
                MOD_CONTROL
            } else {
                0
            };
            let res = RegisterHotKey(0, panic_hotkey_id, panic_modifiers, config.panic_hotkey_vk);
            if res == 0 {
                firewall::log_system_message("SYSTEM ERROR: Failed to register panic hotkey.");
            }
        }

        let mut msg: MSG = unsafe { std::mem::zeroed() };
        unsafe {
            while GetMessageW(&mut msg, 0, 0, 0) != 0 {
                if msg.message == WM_HOTKEY {
                    match msg.wParam as i32 {
                        id if id == hotkey_id => toggle_lock_logic(&app_handle),
                        id if id == panic_hotkey_id => panic_unlock_logic(&app_handle),
                        _ => {}
                    }
                }
            }
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
            list_log_files,
            read_log_file,
            open_log_file_in_notepad
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
}
