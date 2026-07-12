mod config;
mod firewall;

use config::{save_config, Config};
use firewall::{start_firewall, update_subnets_cache, STATE};
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

pub fn update_window_icon(app: &AppHandle) {
    use tauri::Manager;
    use tauri::image::Image;
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
    }
    if sound_enabled {
        let sound_name = if is_locked { "lock" } else { "unlock" };
        let _ = app.emit("play-sound", sound_name);
    }
    let _ = app.emit("status-changed", ());
    update_window_icon(app);
}

#[tauri::command]
fn start_session(session_type: String, app: AppHandle) -> serde_json::Value {
    {
        let mut state = STATE.write();
        state.active_session = session_type;
        if state.active_session == "Lock" {
            state.is_locked = true;
        }
    }
    start_firewall(app.clone());
    let _ = app.emit("status-changed", ());
    update_window_icon(&app);
    get_status()
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
    serde_json::json!({
        "whitelist": state.whitelist.iter().cloned().collect::<Vec<String>>(),
        "blacklist": state.blacklist.iter().cloned().collect::<Vec<String>>(),
    })
}

#[tauri::command]
fn add_to_list(list_type: String, ip: String, app: AppHandle) -> Result<serde_json::Value, String> {
    // Basic IP validation
    if ip.trim().is_empty() {
        return Err("IP address cannot be empty".to_string());
    }

    {
        let mut state = STATE.write();
        if list_type == "whitelist" {
            // Check if relay (dynamic_blacklist)
            let is_relay = state.is_ip_relay(&ip);
            if is_relay {
                return Err("RELAY_PROTECTION".to_string());
            }

            state.whitelist.insert(ip.clone());
            state.config.whitelist.insert(ip, "".to_string());
        } else {
            state.blacklist.insert(ip.clone());
            state.config.blacklist.insert(ip, "".to_string());
        }
        let _ = save_config(&state.config);
    }

    update_subnets_cache();
    let _ = app.emit("lists-changed", ());
    Ok(get_lists())
}

#[tauri::command]
fn delete_from_list(list_type: String, ip: String, app: AppHandle) -> serde_json::Value {
    {
        let mut state = STATE.write();
        if list_type == "whitelist" {
            state.whitelist.remove(&ip);
            state.config.whitelist.remove(&ip);
        } else {
            state.blacklist.remove(&ip);
            state.config.blacklist.remove(&ip);
        }
        let _ = save_config(&state.config);
    }

    update_subnets_cache();
    let _ = app.emit("lists-changed", ());
    get_lists()
}

#[tauri::command]
fn clear_list(list_type: String, app: AppHandle) -> serde_json::Value {
    {
        let mut state = STATE.write();
        if list_type == "whitelist" {
            state.whitelist.clear();
            state.config.whitelist.clear();
        } else {
            state.blacklist.clear();
            state.config.blacklist.clear();
        }
        let _ = save_config(&state.config);
    }

    update_subnets_cache();
    let _ = app.emit("lists-changed", ());
    get_lists()
}

#[tauri::command]
fn get_settings() -> Config {
    STATE.read().config.clone()
}

#[tauri::command]
fn save_settings(mut config: Config) -> Result<(), String> {
    {
        let mut state = STATE.write();
        config.window_width = state.config.window_width;
        config.window_height = state.config.window_height;
        config.window_x = state.config.window_x;
        config.window_y = state.config.window_y;
        config.zoom_factor = state.config.zoom_factor;
        
        state.config = config.clone();
        let _ = save_config(&config);
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

#[tauri::command]
fn read_log_file(filename: String) -> Result<Vec<firewall::LogEntry>, String> {
    let logs_dir = if let Ok(exe_path) = std::env::current_exe() {
        if let Some(parent) = exe_path.parent() {
            parent.join("logs")
        } else {
            std::path::PathBuf::from("logs")
        }
    } else {
        std::path::PathBuf::from("logs")
    };
    let file_path = logs_dir.join(filename);
    if !file_path.exists() {
        return Err("File not found".to_string());
    }

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
    let logs_dir = if let Ok(exe_path) = std::env::current_exe() {
        if let Some(parent) = exe_path.parent() {
            parent.join("logs")
        } else {
            std::path::PathBuf::from("logs")
        }
    } else {
        std::path::PathBuf::from("logs")
    };
    let file_path = logs_dir.join(filename);
    if !file_path.exists() {
        return Err("File not found".to_string());
    }

    std::process::Command::new("notepad.exe")
        .arg(file_path)
        .spawn()
        .map_err(|e| e.to_string())?;
    Ok(())
}

fn start_hotkey_listener(app_handle: AppHandle) {
    std::thread::spawn(move || {
        use windows_sys::Win32::UI::Input::KeyboardAndMouse::RegisterHotKey;
        use windows_sys::Win32::UI::WindowsAndMessaging::{GetMessageW, MSG, WM_HOTKEY};

        let hotkey_vk = 0x78; // F9
        let hotkey_id = 1;

        unsafe {
            let res = RegisterHotKey(0, hotkey_id, 0, hotkey_vk);
            if res == 0 {
                eprintln!("Failed to register F9 hotkey");
            }
        }

        let mut msg: MSG = unsafe { std::mem::zeroed() };
        unsafe {
            while GetMessageW(&mut msg, 0, 0, 0) != 0 {
                if msg.message == WM_HOTKEY {
                    if msg.wParam == hotkey_id as usize {
                        toggle_lock_logic(&app_handle);
                    }
                }
            }
        }
    });
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .setup(|app| {
            let handle = app.handle().clone();

            // Extract WinDivert binaries from packaged resources if they don't exist next to the executable
            use tauri::Manager;
            use tauri::path::BaseDirectory;
            use std::fs;

            if let Ok(exe_path) = std::env::current_exe() {
                if let Some(exe_dir) = exe_path.parent() {
                    let dll_res = app.path().resolve("WinDivert.dll", BaseDirectory::Resource);
                    let sys_res = app.path().resolve("WinDivert64.sys", BaseDirectory::Resource);

                    if let Ok(dll_path) = dll_res {
                        firewall::log_system_message(&format!("SYSTEM: Resolved dll resource path to {:?}", dll_path));
                        let dest = exe_dir.join("WinDivert.dll");
                        if dll_path.exists() {
                            let _ = fs::remove_file(&dest);
                            let _ = fs::copy(&dll_path, &dest);
                        } else {
                            firewall::log_system_message("SYSTEM WARNING: Resolved dll resource file does not exist!");
                        }
                    }
                    if let Ok(sys_path) = sys_res {
                        firewall::log_system_message(&format!("SYSTEM: Resolved sys resource path to {:?}", sys_path));
                        let dest = exe_dir.join("WinDivert64.sys");
                        if sys_path.exists() {
                            let _ = fs::remove_file(&dest);
                            let _ = fs::copy(&sys_path, &dest);
                        } else {
                            firewall::log_system_message("SYSTEM WARNING: Resolved sys resource file does not exist!");
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
                    let _ = window.set_size(tauri::Size::Physical(tauri::PhysicalSize { width: w_val, height: h_val }));
                }
                if let (Some(x_val), Some(y_val)) = (config.window_x, config.window_y) {
                    let _ = window.set_position(tauri::Position::Physical(tauri::PhysicalPosition { x: x_val, y: y_val }));
                }

                let w_clone = window.clone();
                window.on_window_event(move |event| {
                    match event {
                        tauri::WindowEvent::Resized(_) => {
                            if !w_clone.is_minimized().unwrap_or(false) && !w_clone.is_maximized().unwrap_or(false) {
                                if let Ok(outer_size) = w_clone.outer_size() {
                                    let mut state = STATE.write();
                                    state.config.window_width = Some(outer_size.width);
                                    state.config.window_height = Some(outer_size.height);
                                    let _ = save_config(&state.config);
                                }
                            }
                        }
                        tauri::WindowEvent::Moved(pos) => {
                            if !w_clone.is_minimized().unwrap_or(false) && !w_clone.is_maximized().unwrap_or(false) {
                                let mut state = STATE.write();
                                state.config.window_x = Some(pos.x);
                                state.config.window_y = Some(pos.y);
                                let _ = save_config(&state.config);
                            }
                        }
                        tauri::WindowEvent::CloseRequested { .. } => {
                            let state = STATE.read();
                            let _ = save_config(&state.config);
                            firewall::stop_firewall_worker();
                        }
                        _ => {}
                    }
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
                firewall::stop_firewall_worker();
            }
        });
}
