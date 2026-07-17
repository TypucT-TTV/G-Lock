use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fs::{File, OpenOptions};
use std::io::{Read, Write};
use std::path::{Path, PathBuf};

#[derive(Debug, Serialize, Deserialize, Clone)]
#[serde(default)]
pub struct Config {
    pub blacklist: HashMap<String, String>,
    pub language: String,
    pub hotkey_vk: u32,
    pub hotkey_name: String,
    pub hotkey_ctrl: bool,
    pub hotkey_alt: bool,
    pub hotkey_shift: bool,
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
    pub ips_global_pps_ceiling: u32,
    #[serde(rename = "window_w")]
    pub window_width: Option<u32>,
    #[serde(rename = "window_h")]
    pub window_height: Option<u32>,
    pub window_x: Option<i32>,
    pub window_y: Option<i32>,
}

impl Default for Config {
    fn default() -> Self {
        Config {
            blacklist: HashMap::new(),
            language: "ru".to_string(),
            hotkey_vk: 0x78, // VK_F9
            hotkey_name: "F9".to_string(),
            hotkey_ctrl: false,
            hotkey_alt: false,
            hotkey_shift: false,
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
            ips_global_pps_ceiling: 2000,
            window_width: None,
            window_height: None,
            window_x: None,
            window_y: None,
        }
    }
}

impl Config {
    pub fn validate(&self) -> Result<(), String> {
        if !matches!(self.language.as_str(), "ru" | "en") {
            return Err("Unsupported language".to_string());
        }
        if self.hotkey_vk == 0 || self.panic_hotkey_vk == 0 {
            return Err("Hotkey virtual-key code cannot be zero".to_string());
        }
        if self.hotkey_vk == self.panic_hotkey_vk
            && self.hotkey_ctrl == self.panic_hotkey_ctrl
            && !self.hotkey_alt
            && !self.hotkey_shift
        {
            return Err("Main hotkey conflicts with the Ctrl+F9 fallback hotkey".to_string());
        }
        if self.sound_lock_vol > 100 || self.sound_unlock_vol > 100 {
            return Err("Sound volume must be between 0 and 100".to_string());
        }
        if self.sound_lock_dur == 0 || self.sound_unlock_dur == 0 {
            return Err("Sound duration must be greater than zero".to_string());
        }
        if !(0.5..=2.0).contains(&self.zoom_factor) {
            return Err("Zoom factor must be between 0.5 and 2.0".to_string());
        }
        if !(2..=15).contains(&self.ips_adaptive_multiplier) {
            return Err("IPS multiplier must be between 2 and 15".to_string());
        }
        if !(15..=120).contains(&self.ips_adaptive_measurement_seconds) {
            return Err("IPS measurement duration must be between 15 and 120 seconds".to_string());
        }
        if !(50..=10_000).contains(&self.ips_fallback_threshold) {
            return Err("IPS fallback threshold must be between 50 and 10000 PPS".to_string());
        }
        if !(100..=100_000).contains(&self.ips_global_pps_ceiling) {
            return Err("Global IPS ceiling must be between 100 and 100000 PPS".to_string());
        }
        Ok(())
    }
}

pub fn get_config_path() -> PathBuf {
    if let Some(local_app_data) = std::env::var_os("LOCALAPPDATA") {
        return PathBuf::from(local_app_data)
            .join("G-Lock")
            .join("data.json");
    }

    legacy_config_path()
}

fn legacy_config_path() -> PathBuf {
    if let Ok(exe_path) = std::env::current_exe() {
        if let Some(parent) = exe_path.parent() {
            return parent.join("data.json");
        }
    }
    PathBuf::from("data.json")
}

pub fn load_config() -> Config {
    let path = get_config_path();
    if !path.exists() {
        let legacy_path = legacy_config_path();
        if legacy_path != path && legacy_path.exists() {
            if let Some(config) = read_config(&legacy_path) {
                let _ = save_config(&config);
                return config;
            }
        }

        let default_cfg = Config::default();
        let _ = save_config(&default_cfg);
        return default_cfg;
    }

    read_config(&path).unwrap_or_default()
}

fn read_config(path: &Path) -> Option<Config> {
    match File::open(path) {
        Ok(mut file) => {
            let mut content = String::new();
            if file.read_to_string(&mut content).is_ok() {
                if let Ok(config) = serde_json::from_str::<Config>(&content) {
                    return Some(config);
                }
                // Attempt partial migration or fallback
                if let Ok(val) = serde_json::from_str::<serde_json::Value>(&content) {
                    let mut cfg = Config::default();
                    if let Some(bl) = val
                        .get("blacklist")
                        .and_then(|v| serde_json::from_value(v.clone()).ok())
                    {
                        cfg.blacklist = bl;
                    }
                    if let Some(lang) = val.get("language").and_then(|v| v.as_str()) {
                        cfg.language = lang.to_string();
                    }
                    if let Some(hotkey_vk) = val.get("hotkey_vk").and_then(|v| v.as_u64()) {
                        cfg.hotkey_vk = hotkey_vk as u32;
                    }
                    if let Some(hotkey_name) = val.get("hotkey_name").and_then(|v| v.as_str()) {
                        cfg.hotkey_name = hotkey_name.to_string();
                    }
                    if let Some(hotkey_ctrl) = val.get("hotkey_ctrl").and_then(|v| v.as_bool()) {
                        cfg.hotkey_ctrl = hotkey_ctrl;
                    }
                    if let Some(hotkey_alt) = val.get("hotkey_alt").and_then(|v| v.as_bool()) {
                        cfg.hotkey_alt = hotkey_alt;
                    }
                    if let Some(hotkey_shift) = val.get("hotkey_shift").and_then(|v| v.as_bool()) {
                        cfg.hotkey_shift = hotkey_shift;
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
                    if let Some(val) = val
                        .get("ips_adaptive_measurement_seconds")
                        .and_then(|v| v.as_u64())
                    {
                        cfg.ips_adaptive_measurement_seconds = val as u32;
                    }
                    if let Some(val) = val.get("ips_fallback_threshold").and_then(|v| v.as_u64()) {
                        cfg.ips_fallback_threshold = val as u32;
                    }
                    if let Some(val) = val.get("ips_global_pps_ceiling").and_then(|v| v.as_u64()) {
                        cfg.ips_global_pps_ceiling = val as u32;
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
                    return Some(cfg);
                }
            }
            None
        }
        Err(_) => None,
    }
}

pub fn save_config(config: &Config) -> std::io::Result<()> {
    let path = get_config_path();
    save_config_to_path(config, &path)
}

fn save_config_to_path(config: &Config, path: &Path) -> std::io::Result<()> {
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    let content = serde_json::to_string_pretty(config)?;
    let temp_path = path.with_extension("json.tmp");
    let mut file = OpenOptions::new()
        .create(true)
        .truncate(true)
        .write(true)
        .open(&temp_path)?;
    file.write_all(content.as_bytes())?;
    file.sync_all()?;
    drop(file);
    replace_file(&temp_path, path)
}

#[cfg(target_os = "windows")]
fn replace_file(source: &Path, destination: &Path) -> std::io::Result<()> {
    use std::iter::once;
    use std::os::windows::ffi::OsStrExt;
    use windows_sys::Win32::Storage::FileSystem::{
        MoveFileExW, MOVEFILE_REPLACE_EXISTING, MOVEFILE_WRITE_THROUGH,
    };

    let source: Vec<u16> = source.as_os_str().encode_wide().chain(once(0)).collect();
    let destination: Vec<u16> = destination
        .as_os_str()
        .encode_wide()
        .chain(once(0))
        .collect();
    let result = unsafe {
        MoveFileExW(
            source.as_ptr(),
            destination.as_ptr(),
            MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH,
        )
    };
    if result == 0 {
        Err(std::io::Error::last_os_error())
    } else {
        Ok(())
    }
}

#[cfg(not(target_os = "windows"))]
fn replace_file(source: &Path, destination: &Path) -> std::io::Result<()> {
    std::fs::rename(source, destination)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn missing_fields_use_defaults() {
        let config: Config = serde_json::from_str(r#"{"language":"en"}"#).unwrap();
        assert_eq!(config.language, "en");
        assert_eq!(config.hotkey_vk, 0x78);
        assert_eq!(config.ips_global_pps_ceiling, 2000);
    }

    #[test]
    fn validation_rejects_invalid_values() {
        let config = Config {
            sound_lock_vol: 101,
            ..Config::default()
        };
        assert!(config.validate().is_err());

        let conflicting_hotkey = Config {
            hotkey_ctrl: true,
            ..Config::default()
        };
        assert!(conflicting_hotkey.validate().is_err());
    }

    #[test]
    fn settings_round_trip_preserves_user_choices() {
        let test_dir = std::env::temp_dir().join(format!(
            "g-lock-config-test-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        let path = test_dir.join("data.json");
        let mut config = Config {
            language: "en".to_string(),
            hotkey_vk: 0x74,
            hotkey_name: "Ctrl+Shift+F5".to_string(),
            hotkey_ctrl: true,
            hotkey_shift: true,
            sound_enabled: false,
            ips_enabled: false,
            ..Config::default()
        };
        config
            .blacklist
            .insert("203.0.113.8".to_string(), "manual".to_string());

        save_config_to_path(&config, &path).unwrap();
        let loaded = read_config(&path).unwrap();

        assert_eq!(loaded.language, "en");
        assert_eq!(loaded.hotkey_vk, 0x74);
        assert_eq!(loaded.hotkey_name, "Ctrl+Shift+F5");
        assert!(loaded.hotkey_ctrl);
        assert!(!loaded.hotkey_alt);
        assert!(loaded.hotkey_shift);
        assert!(!loaded.sound_enabled);
        assert!(!loaded.ips_enabled);
        assert_eq!(
            loaded.blacklist.get("203.0.113.8").map(String::as_str),
            Some("manual")
        );

        std::fs::remove_dir_all(test_dir).unwrap();
    }
}
