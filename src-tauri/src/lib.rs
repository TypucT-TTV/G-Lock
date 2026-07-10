mod config;
mod firewall;

use config::{save_config, Config};
use firewall::{play_beep, start_firewall, update_subnets_cache, STATE};
use tauri::{AppHandle, Emitter};

#[tauri::command]
fn get_status() -> serde_json::Value {
    let state = STATE.read();
    serde_json::json!({
        "active_session": state.active_session,
        "is_locked": state.is_locked,
        "is_running": state.is_running,
    })
}

#[tauri::command]
fn toggle_lock(app: AppHandle) -> serde_json::Value {
    toggle_lock_logic(&app);
    get_status()
}

fn toggle_lock_logic(app: &AppHandle) {
    let mut sound_to_play = None;
    {
        let mut state = STATE.write();
        state.is_locked = !state.is_locked;
        if state.config.sound_enabled {
            if state.is_locked {
                sound_to_play = Some((state.config.sound_lock_freq, state.config.sound_lock_dur));
            } else {
                sound_to_play = Some((state.config.sound_unlock_freq, state.config.sound_unlock_dur));
            }
        }
    }
    if let Some((freq, dur)) = sound_to_play {
        play_beep(freq, dur);
    }
    let _ = app.emit("status-changed", ());
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
fn save_settings(config: Config) -> Result<(), String> {
    {
        let mut state = STATE.write();
        state.config = config.clone();
        let _ = save_config(&config);
    }
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
                        let dest = exe_dir.join("WinDivert.dll");
                        if !dest.exists() && dll_path.exists() {
                            let _ = fs::copy(&dll_path, &dest);
                        }
                    }
                    if let Ok(sys_path) = sys_res {
                        let dest = exe_dir.join("WinDivert64.sys");
                        if !dest.exists() && sys_path.exists() {
                            let _ = fs::copy(&sys_path, &dest);
                        }
                    }
                }
            }

            start_hotkey_listener(handle.clone());
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
            save_settings
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
