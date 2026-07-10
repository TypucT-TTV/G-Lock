use once_cell::sync::Lazy;
use parking_lot::RwLock;
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet};
use std::net::Ipv4Addr;
use std::sync::Arc;
use std::time::{Duration, Instant};
use tauri::{AppHandle, Emitter};
use windivert::prelude::*;

// Heartbeat payload sizes that should never be blocked
const HEARTBEAT_SIZES: [usize; 3] = [12, 18, 63];
// Matchmaking payload sizes that are blocked during Locked sessions
const MATCHMAKING_SIZES: [usize; 4] = [191, 207, 223, 239];

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LogEntry {
    pub timestamp: String,
    pub ip: String,
    pub action: String,
    pub size: usize,
    pub reason: String,
}

pub struct FirewallState {
    pub active_session: String, // "Open", "Solo", "Whitelist", "Blacklist", "Lock"
    pub is_locked: bool,
    pub is_running: bool,
    pub whitelist: HashSet<String>,
    pub blacklist: HashSet<String>,
    pub dynamic_blacklist: Vec<ipnet::Ipv4Net>,
    pub config: crate::config::Config,
}

impl FirewallState {
    pub fn is_ip_whitelisted(&self, ip: &str) -> bool {
        if self.whitelist.contains(ip) {
            return true;
        }
        if let Ok(ip_addr) = ip.parse::<Ipv4Addr>() {
            for net in self.whitelist_subnets() {
                if net.contains(&ip_addr) {
                    return true;
                }
            }
        }
        false
    }

    pub fn is_ip_blacklisted(&self, ip: &str) -> bool {
        if self.blacklist.contains(ip) {
            return true;
        }
        if let Ok(ip_addr) = ip.parse::<Ipv4Addr>() {
            for net in self.blacklist_subnets() {
                if net.contains(&ip_addr) {
                    return true;
                }
            }
        }
        false
    }

    pub fn is_ip_relay(&self, ip: &str) -> bool {
        if let Ok(ip_addr) = ip.parse::<Ipv4Addr>() {
            for net in &self.dynamic_blacklist {
                if net.contains(&ip_addr) {
                    return true;
                }
            }
        }
        false
    }
}

// Pre-parsed subnet lists for fast lookup
struct ParsedSubnets {
    whitelist_subnets: Vec<ipnet::Ipv4Net>,
    blacklist_subnets: Vec<ipnet::Ipv4Net>,
}

static SUBNETS: Lazy<RwLock<ParsedSubnets>> = Lazy::new(|| {
    RwLock::new(ParsedSubnets {
        whitelist_subnets: Vec::new(),
        blacklist_subnets: Vec::new(),
    })
});

pub static STATE: Lazy<Arc<RwLock<FirewallState>>> = Lazy::new(|| {
    let config = crate::config::load_config();
    let whitelist: HashSet<String> = config.whitelist.keys().cloned().collect();
    let blacklist: HashSet<String> = config.blacklist.keys().cloned().collect();

    let mut wl_subnets = Vec::new();
    let mut bl_subnets = Vec::new();

    for ip in &whitelist {
        if ip.contains('/') {
            if let Ok(net) = ip.parse::<ipnet::Ipv4Net>() {
                wl_subnets.push(net);
            }
        }
    }
    for ip in &blacklist {
        if ip.contains('/') {
            if let Ok(net) = ip.parse::<ipnet::Ipv4Net>() {
                bl_subnets.push(net);
            }
        }
    }

    {
        let mut sub = SUBNETS.write();
        sub.whitelist_subnets = wl_subnets;
        sub.blacklist_subnets = bl_subnets;
    }

    Arc::new(RwLock::new(FirewallState {
        active_session: "Open".to_string(),
        is_locked: false,
        is_running: false,
        whitelist,
        blacklist,
        dynamic_blacklist: Vec::new(),
        config,
    }))
});

impl FirewallState {
    fn whitelist_subnets(&self) -> Vec<ipnet::Ipv4Net> {
        SUBNETS.read().whitelist_subnets.clone()
    }
    fn blacklist_subnets(&self) -> Vec<ipnet::Ipv4Net> {
        SUBNETS.read().blacklist_subnets.clone()
    }
}

// Global thread control
static STOP_FLAG: Lazy<Arc<RwLock<bool>>> = Lazy::new(|| Arc::new(RwLock::new(false)));

pub fn load_dynamic_blacklist() {
    let mut ranges = Vec::new();

    // 1. T2 Hardcoded prefixes
    let t2_prefixes = [
        "185.56.64.0/24", "185.56.64.0/22", "185.56.65.0/24", "185.56.66.0/24", "185.56.67.0/24",
        "104.255.104.0/24", "104.255.104.0/22", "104.255.105.0/24", "104.255.106.0/24", "104.255.107.0/24",
        "192.81.240.0/24", "192.81.240.0/22", "192.81.241.0/24", "192.81.242.0/24", "192.81.243.0/24",
        "192.81.244.0/24", "192.81.244.0/22", "192.81.245.0/24", "192.81.246.0/24", "192.81.247.0/24",
        "198.133.210.0/24"
    ];
    for p in &t2_prefixes {
        if let Ok(net) = p.parse::<ipnet::Ipv4Net>() {
            ranges.push(net);
        }
    }

    // 2. Load Azure Cloud from db.json if present
    if std::path::Path::new("db.json").exists() {
        if let Ok(content) = std::fs::read_to_string("db.json") {
            if let Ok(val) = serde_json::from_str::<serde_json::Value>(&content) {
                if let Some(values) = val.get("values").and_then(|v| v.as_array()) {
                    for cat in values {
                        if cat.get("name").and_then(|n| n.as_str()) == Some("AzureCloud") {
                            if let Some(prefixes) = cat.get("properties").and_then(|p| p.get("addressPrefixes")).and_then(|a| a.as_array()) {
                                for p in prefixes {
                                    if let Some(prefix_str) = p.as_str() {
                                        if let Ok(net) = prefix_str.parse::<ipnet::Ipv4Net>() {
                                            ranges.push(net);
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    STATE.write().dynamic_blacklist = ranges;
}

pub fn update_subnets_cache() {
    let state = STATE.read();
    let mut wl_subnets = Vec::new();
    let mut bl_subnets = Vec::new();

    for ip in &state.whitelist {
        if ip.contains('/') {
            if let Ok(net) = ip.parse::<ipnet::Ipv4Net>() {
                wl_subnets.push(net);
            }
        }
    }
    for ip in &state.blacklist {
        if ip.contains('/') {
            if let Ok(net) = ip.parse::<ipnet::Ipv4Net>() {
                bl_subnets.push(net);
            }
        }
    }

    let mut sub = SUBNETS.write();
    sub.whitelist_subnets = wl_subnets;
    sub.blacklist_subnets = bl_subnets;
}

fn is_lan_ip(ip: &str) -> bool {
    if let Ok(ip_addr) = ip.parse::<Ipv4Addr>() {
        let octets = ip_addr.octets();
        return octets[0] == 10
            || (octets[0] == 172 && octets[1] >= 16 && octets[1] <= 31)
            || (octets[0] == 192 && octets[1] == 168)
            || octets[0] == 127;
    }
    false
}

struct ParsedPacket {
    src_ip: String,
    payload_len: usize,
}

fn parse_ipv4_udp(data: &[u8]) -> Option<ParsedPacket> {
    if data.len() < 20 {
        return None;
    }
    let version = data[0] >> 4;
    if version != 4 {
        return None;
    }
    let ihl = (data[0] & 0x0F) as usize * 4;
    if data.len() < ihl + 8 {
        return None;
    }
    let protocol = data[9];
    if protocol != 17 {
        return None;
    }
    let src_ip = format!("{}.{}.{}.{}", data[12], data[13], data[14], data[15]);
    let payload_len = data.len() - (ihl + 8);
    Some(ParsedPacket { src_ip, payload_len })
}

#[derive(Default)]
struct RateStats {
    window_start: Option<Instant>,
    count: usize,
    suspicious_count: usize,
}

pub fn play_beep(freq: u32, duration: u32) {
    #[cfg(target_os = "windows")]
    unsafe {
        windows_sys::Win32::System::Diagnostics::Debug::Beep(freq, duration);
    }
}

pub fn start_firewall(app: AppHandle) {
    let running = STATE.read().is_running;
    if running {
        return;
    }
    STATE.write().is_running = true;
    *STOP_FLAG.write() = false;

    // Load initial dynamic blacklist
    load_dynamic_blacklist();

    std::thread::spawn(move || {
        let filter = "udp.DstPort == 6672 and udp.PayloadLength > 0 and ip";
        
        let w: WinDivert<windivert::layer::NetworkLayer> = match WinDivert::network(filter, 0, WinDivertFlags::default()) {
            Ok(handle) => handle,
            Err(e) => {
                eprintln!("Failed to open WinDivert handle: {:?}", e);
                STATE.write().is_running = false;
                return;
            }
        };

        let session_start = Instant::now();
        let mut rates: HashMap<String, RateStats> = HashMap::new();
        let mut temp_blacklist: HashMap<String, Instant> = HashMap::new();
        let mut measured_max_pps = 0;
        let mut adaptive_calibrated = false;
        let mut current_threshold = STATE.read().config.ips_fallback_threshold as usize;

        let mut last_log_time: HashMap<String, Instant> = HashMap::new();
        let mut buf = [0u8; 65535];

        while !*STOP_FLAG.read() {
            let packet = match w.recv(Some(&mut buf)) {
                Ok(p) => p,
                Err(_) => continue,
            };

            let parsed = match parse_ipv4_udp(&packet.data) {
                Some(p) => p,
                None => {
                    let _ = w.send(&packet);
                    continue;
                }
            };

            let ip_src = parsed.src_ip;
            let payload_len = parsed.payload_len;
            let now = Instant::now();

            let state = STATE.read();
            let is_service = HEARTBEAT_SIZES.contains(&payload_len) || MATCHMAKING_SIZES.contains(&payload_len);
            let is_friend = state.is_ip_whitelisted(&ip_src);
            let is_lan = is_lan_ip(&ip_src);
            let is_relay = state.is_ip_relay(&ip_src);
            let is_suspicious = !is_service && !is_friend && !is_lan;

            // Handle temporary ban
            let mut is_banned = false;
            if state.config.ips_enabled {
                if let Some(&ban_until) = temp_blacklist.get(&ip_src) {
                    if now < ban_until {
                        is_banned = true;
                    } else {
                        temp_blacklist.remove(&ip_src);
                    }
                }
            }

            // Decide allow/block
            let mut decision = true;
            let mut reason = "Allow".to_string();

            if is_banned {
                decision = false;
                reason = "Blocked - Flood Protection".to_string();
            } else if state.is_ip_blacklisted(&ip_src) {
                decision = false;
                reason = "Blocked - Blacklist".to_string();
            } else {
                match state.active_session.as_str() {
                    "Solo" => {
                        if !is_friend && !is_lan {
                            decision = false;
                            reason = "Blocked - Solo Session".to_string();
                        }
                    }
                    "Whitelist" => {
                        if !is_friend && !is_lan {
                            decision = false;
                            reason = "Blocked - Whitelist Only".to_string();
                        }
                    }
                    _ => {
                        if state.is_locked {
                            if MATCHMAKING_SIZES.contains(&payload_len) {
                                decision = false;
                                reason = "Blocked - Locked Session".to_string();
                            } else if is_relay {
                                decision = false;
                                reason = "Blocked - Relay (Locked)".to_string();
                            }
                        }
                    }
                }
            }

            // Always allow Heartbeats
            if HEARTBEAT_SIZES.contains(&payload_len) {
                decision = true;
                reason = "Service/Heartbeat".to_string();
            }

            // Update Rate Stats
            let stats = rates.entry(ip_src.clone()).or_insert_with(|| RateStats {
                window_start: Some(now),
                ..Default::default()
            });

            stats.count += 1;
            if is_suspicious {
                stats.suspicious_count += 1;
            }

            if let Some(win_start) = stats.window_start {
                if now.duration_since(win_start) >= Duration::from_secs(1) {
                    let pps = stats.suspicious_count;
                    stats.window_start = Some(now);
                    stats.count = 0;
                    stats.suspicious_count = 0;

                    // Calibrate adaptive IPS
                    if !adaptive_calibrated {
                        let elapsed = now.duration_since(session_start);
                        if elapsed < Duration::from_secs(state.config.ips_adaptive_measurement_seconds as u64) {
                            if !is_friend && !is_lan {
                                measured_max_pps = measured_max_pps.max(pps);
                            }
                        } else {
                            if measured_max_pps > 0 {
                                current_threshold = measured_max_pps.max(5) * state.config.ips_adaptive_multiplier as usize;
                            } else {
                                current_threshold = state.config.ips_fallback_threshold as usize;
                            }
                            adaptive_calibrated = true;
                        }
                    }

                    // Check for Attack & Ban
                    if state.config.ips_enabled && !is_friend && !is_lan && !is_relay && pps >= current_threshold {
                        temp_blacklist.insert(ip_src.clone(), now + Duration::from_secs(state.config.ips_ban_duration as u64));
                    }

                    // Trigger Auto-Lock or Alarm
                    if state.config.ips_enabled && pps >= current_threshold {
                        if state.config.sound_enabled {
                            play_beep(state.config.sound_lock_freq, state.config.sound_lock_dur);
                        }
                        if state.config.auto_lock_on_attack && !state.is_locked {
                            drop(state);
                            {
                                let mut state_write = STATE.write();
                                state_write.is_locked = true;
                                if state_write.config.sound_enabled {
                                    play_beep(state_write.config.sound_lock_freq, state_write.config.sound_lock_dur);
                                }
                            }
                            let _ = app.emit("status-changed", ());
                            crate::update_window_icon(&app);
                            // Re-acquire read lock
                            // Since we drop and lock is now completed, we just recreate local reference
                        }
                    }
                }
            }

            // Emit to log if it's a matchmaking request or blocked/yellow highlighted friend, with cooldown
            let should_log = !decision || is_friend || is_relay || MATCHMAKING_SIZES.contains(&payload_len);
            if should_log {
                let throttle = last_log_time.get(&ip_src);
                if throttle.is_none() || now.duration_since(*throttle.unwrap()) >= Duration::from_secs(15) {
                    last_log_time.insert(ip_src.clone(), now);

                    let timestamp = chrono::Local::now().format("%Y-%m-%d %H:%M:%S").to_string();
                    let action = if decision { "ALLOW".to_string() } else { "BLOCK".to_string() };
                    let log = LogEntry {
                        timestamp,
                        ip: ip_src.clone(),
                        action,
                        size: payload_len,
                        reason: reason.clone(),
                    };
                    let _ = app.emit("connection-log", log);
                }
            }

            if decision {
                let _ = w.send(&packet);
            }
        }

        STATE.write().is_running = false;
    });
}

#[allow(dead_code)]
pub fn stop_firewall_worker() {
    *STOP_FLAG.write() = true;
}
