use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fs::File;
use std::io::{Read, Write};
use std::path::Path;

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct Config {
    pub blacklist: HashMap<String, String>,
    pub whitelist: HashMap<String, String>,
    pub language: String,
    pub hotkey_vk: u32,
    pub hotkey_name: String,
    pub sound_enabled: bool,
    pub sound_lock_freq: u32,
    pub sound_lock_dur: u32,
    pub sound_lock_vol: u32,
    pub sound_unlock_freq: u32,
    pub sound_unlock_dur: u32,
    pub sound_unlock_vol: u32,
    pub zoom_factor: f64,
    pub verbose_logging_enabled: bool,
    pub verbose_flood_threshold: u32,
    pub ips_enabled: bool,
    pub ips_pps_threshold: u32,
    pub ips_ban_duration: u32,
    pub auto_lock_on_attack: bool,
    pub panic_hotkey_vk: u32,
    pub panic_hotkey_ctrl: bool,
    pub panic_hotkey_name: String,
    pub ips_adaptive_multiplier: u32,
    pub ips_adaptive_measurement_seconds: u32,
    pub ips_fallback_threshold: u32,
    #[serde(alias = "window_w")]
    pub window_width: Option<u32>,
    #[serde(alias = "window_h")]
    pub window_height: Option<u32>,
    pub window_x: Option<i32>,
    pub window_y: Option<i32>,
}

impl Default for Config {
    fn default() -> Self {
        Config {
            blacklist: HashMap::new(),
            whitelist: HashMap::new(),
            language: "ru".to_string(),
            hotkey_vk: 0x78, // VK_F9
            hotkey_name: "F9".to_string(),
            sound_enabled: true,
            sound_lock_freq: 900,
            sound_lock_dur: 200,
            sound_lock_vol: 80,
            sound_unlock_freq: 400,
            sound_unlock_dur: 200,
            sound_unlock_vol: 80,
            zoom_factor: 1.0,
            verbose_logging_enabled: true,
            verbose_flood_threshold: 50,
            ips_enabled: true,
            ips_pps_threshold: 150,
            ips_ban_duration: 60,
            auto_lock_on_attack: false,
            panic_hotkey_vk: 0x78, // VK_F9
            panic_hotkey_ctrl: true,
            panic_hotkey_name: "Ctrl+F9".to_string(),
            ips_adaptive_multiplier: 5,
            ips_adaptive_measurement_seconds: 45,
            ips_fallback_threshold: 250,
            window_width: None,
            window_height: None,
            window_x: None,
            window_y: None,
        }
    }
}

pub fn get_config_path() -> &'static Path {
    Path::new("data.json")
}

pub fn load_config() -> Config {
    let path = get_config_path();
    if !path.exists() {
        let default_cfg = Config::default();
        let _ = save_config(&default_cfg);
        return default_cfg;
    }

    match File::open(path) {
        Ok(mut file) => {
            let mut content = String::new();
            if file.read_to_string(&mut content).is_ok() {
                if let Ok(config) = serde_json::from_str::<Config>(&content) {
                    return config;
                }
                // Attempt partial migration or fallback
                if let Ok(val) = serde_json::from_str::<serde_json::Value>(&content) {
                    let mut cfg = Config::default();
                    if let Some(bl) = val.get("blacklist").and_then(|v| serde_json::from_value(v.clone()).ok()) {
                        cfg.blacklist = bl;
                    }
                    if let Some(wl) = val.get("whitelist").and_then(|v| serde_json::from_value(v.clone()).ok()) {
                        cfg.whitelist = wl;
                    }
                    if let Some(lang) = val.get("language").and_then(|v| v.as_str()) {
                        cfg.language = lang.to_string();
                    }
                    if let Some(val) = val.get("sound_enabled").and_then(|v| v.as_bool()) {
                        cfg.sound_enabled = val;
                    }
                    if let Some(val) = val.get("auto_lock_on_attack").and_then(|v| v.as_bool()) {
                        cfg.auto_lock_on_attack = val;
                    }
                    if let Some(val) = val.get("ips_adaptive_multiplier").and_then(|v| v.as_u64()) {
                        cfg.ips_adaptive_multiplier = val as u32;
                    }
                    if let Some(val) = val.get("ips_adaptive_measurement_seconds").and_then(|v| v.as_u64()) {
                        cfg.ips_adaptive_measurement_seconds = val as u32;
                    }
                    if let Some(val) = val.get("ips_fallback_threshold").and_then(|v| v.as_u64()) {
                        cfg.ips_fallback_threshold = val as u32;
                    }
                    if let Some(val) = val.get("window_width").and_then(|v| v.as_u64()) {
                        cfg.window_width = Some(val as u32);
                    }
                    if let Some(val) = val.get("window_height").and_then(|v| v.as_u64()) {
                        cfg.window_height = Some(val as u32);
                    }
                    if let Some(val) = val.get("window_x").and_then(|v| v.as_i64()) {
                        cfg.window_x = Some(val as i32);
                    }
                    if let Some(val) = val.get("window_y").and_then(|v| v.as_i64()) {
                        cfg.window_y = Some(val as i32);
                    }
                    let _ = save_config(&cfg);
                    return cfg;
                }
            }
            Config::default()
        }
        Err(_) => Config::default(),
    }
}

pub fn save_config(config: &Config) -> std::io::Result<()> {
    let path = get_config_path();
    let content = serde_json::to_string_pretty(config)?;
    let mut file = File::create(path)?;
    file.write_all(content.as_bytes())?;
    Ok(())
}
