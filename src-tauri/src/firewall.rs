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
    pub dynamic_blacklist_table: Vec<Vec<ipnet::Ipv4Net>>,
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
            let ip_u32 = u32::from(ip_addr);
            let key = (ip_u32 >> 16) as usize;
            if key < self.dynamic_blacklist_table.len() {
                for net in &self.dynamic_blacklist_table[key] {
                    if net.contains(&ip_addr) {
                        return true;
                    }
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
        dynamic_blacklist_table: vec![Vec::new(); 65536],
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

fn fetch_ripe_prefixes(asn: u32) -> Result<Vec<ipnet::Ipv4Net>, Box<dyn std::error::Error>> {
    let url = format!("https://stat.ripe.net/data/announced-prefixes/data.json?resource=AS{}", asn);
    let client = reqwest::blocking::Client::builder()
        .user_agent("G-Lock/1.0 (GTA5-Firewall; +https://github.com)")
        .timeout(Duration::from_secs(10))
        .build()?;
    let resp = client.get(&url).send()?;
    let val: serde_json::Value = resp.json()?;
    let mut prefixes = Vec::new();
    if let Some(data) = val.get("data") {
        if let Some(prefixes_array) = data.get("prefixes").and_then(|p| p.as_array()) {
            for entry in prefixes_array {
                if let Some(prefix_str) = entry.get("prefix").and_then(|p| p.as_str()) {
                    if let Ok(net) = prefix_str.parse::<ipnet::Ipv4Net>() {
                        prefixes.push(net);
                    }
                }
            }
        }
    }
    Ok(prefixes)
}

fn build_dynamic_blacklist_table(ranges: &[ipnet::Ipv4Net]) -> Vec<Vec<ipnet::Ipv4Net>> {
    let mut table = vec![Vec::new(); 65536];
    for &net in ranges {
        let prefix = net.prefix_len();
        if prefix >= 16 {
            let ip_u32 = u32::from(net.network());
            let key = (ip_u32 >> 16) as usize;
            if key < 65536 {
                table[key].push(net);
            }
        } else {
            let ip_u32 = u32::from(net.network());
            let mask = !((1 << (32 - prefix)) - 1);
            let start_ip = ip_u32 & mask;
            let num_ips = 1u64 << (32 - prefix);
            let end_ip = start_ip.saturating_add((num_ips - 1) as u32);
            
            let start_key = (start_ip >> 16) as usize;
            let end_key = (end_ip >> 16) as usize;
            
            for key in start_key..=end_key {
                if key < 65536 {
                    table[key].push(net);
                }
            }
        }
    }
    table
}

pub fn load_dynamic_blacklist(app: &AppHandle) {
    let mut ranges = Vec::new();
    log_system_message("SYSTEM: Starting load_dynamic_blacklist...");

    // 1. Fetch Take-Two EU and US prefixes dynamically from RIPE Stat
    for asn in &[202021, 46555] {
        match fetch_ripe_prefixes(*asn) {
            Ok(nets) => {
                log_system_message(&format!("SYSTEM: Fetched {} prefixes for AS{}", nets.len(), asn));
                ranges.extend(nets);
            }
            Err(e) => {
                log_system_message(&format!("SYSTEM ERROR: Failed to fetch prefixes for AS{}: {:?}", asn, e));
            }
        }
    }

    // 1.1. T2 Hardcoded prefixes
    let t2_prefixes = [
        "185.56.64.0/24", "185.56.64.0/22", "185.56.65.0/24", "185.56.66.0/24", "185.56.67.0/24",
        "104.255.104.0/24", "104.255.104.0/22", "104.255.105.0/24", "104.255.106.0/24", "104.255.107.0/24",
        "192.81.240.0/24", "192.81.240.0/22", "192.81.241.0/24", "192.81.242.0/24", "192.81.243.0/24",
        "192.81.244.0/24", "192.81.244.0/22", "192.81.245.0/24", "192.81.246.0/24", "192.81.247.0/24",
        "198.133.210.0/24"
    ];
    for p in &t2_prefixes {
        if let Ok(net) = p.parse::<ipnet::Ipv4Net>() {
            if !ranges.contains(&net) {
                ranges.push(net);
            }
        }
    }

    // 2. Load Azure Cloud from db.json if present
    use tauri::Manager;
    use tauri::path::BaseDirectory;
    let mut db_content = None;

    if let Ok(resource_path) = app.path().resolve("db.json", BaseDirectory::Resource) {
        log_system_message(&format!("SYSTEM: Resolved Tauri resource path to {:?}", resource_path));
        if resource_path.exists() {
            log_system_message("SYSTEM: Resource file exists, loading...");
            if let Ok(content) = std::fs::read_to_string(&resource_path) {
                db_content = Some(content);
            } else {
                log_system_message("SYSTEM ERROR: Failed to read resource db.json file.");
            }
        } else {
            log_system_message("SYSTEM: Resource path does not exist on disk.");
        }
    }

    if db_content.is_none() {
        if let Ok(exe_path) = std::env::current_exe() {
            if let Some(exe_dir) = exe_path.parent() {
                let path = exe_dir.join("db.json");
                log_system_message(&format!("SYSTEM: Resolved exe-adjacent path to {:?}", path));
                if path.exists() {
                    log_system_message("SYSTEM: Exe-adjacent file exists, loading...");
                    if let Ok(content) = std::fs::read_to_string(path) {
                        db_content = Some(content);
                    }
                } else {
                    log_system_message("SYSTEM: Exe-adjacent file does not exist.");
                }
            }
        }
    }

    if db_content.is_none() {
        let path = std::path::Path::new("db.json");
        log_system_message(&format!("SYSTEM: Resolved CWD relative path to {:?}", path));
        if path.exists() {
            log_system_message("SYSTEM: CWD relative file exists, loading...");
            if let Ok(content) = std::fs::read_to_string(path) {
                db_content = Some(content);
            }
        } else {
            log_system_message("SYSTEM: CWD relative file does not exist.");
        }
    }

    if let Some(content) = db_content {
        if let Ok(val) = serde_json::from_str::<serde_json::Value>(&content) {
            if let Some(values) = val.get("values").and_then(|v| v.as_array()) {
                let mut count = 0;
                for cat in values {
                    if cat.get("name").and_then(|n| n.as_str()) == Some("AzureCloud") {
                        if let Some(prefixes) = cat.get("properties").and_then(|p| p.get("addressPrefixes")).and_then(|a| a.as_array()) {
                            for p in prefixes {
                                if let Some(prefix_str) = p.as_str() {
                                    if let Ok(net) = prefix_str.parse::<ipnet::Ipv4Net>() {
                                        ranges.push(net);
                                        count += 1;
                                    }
                                }
                            }
                        }
                    }
                }
                log_system_message(&format!("SYSTEM: Successfully loaded {} Azure ranges from db.json.", count));
            }
        } else {
            log_system_message("SYSTEM ERROR: Failed to parse db.json as JSON.");
        }
    } else {
        log_system_message("SYSTEM WARNING: db.json could not be loaded from any source.");
    }

    log_system_message(&format!("SYSTEM: Total dynamic blacklist size: {} ranges.", ranges.len()));
    let table = build_dynamic_blacklist_table(&ranges);
    let mut state = STATE.write();
    state.dynamic_blacklist = ranges;
    state.dynamic_blacklist_table = table;
    log_system_message("SYSTEM: load_dynamic_blacklist finished successfully.");
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

#[repr(C)]
#[allow(non_snake_case)]
struct PROCESSENTRY32W {
    dwSize: u32,
    cntUsage: u32,
    th32ProcessID: u32,
    th32DefaultHeapID: usize,
    th32ModuleID: u32,
    cntThreads: u32,
    th32ParentProcessID: u32,
    pcPriClassBase: i32,
    dwFlags: u32,
    szExeFile: [u16; 260],
}

#[link(name = "kernel32")]
extern "system" {
    fn CreateToolhelp32Snapshot(dwFlags: u32, th32ProcessID: u32) -> isize;
    fn Process32FirstW(hSnapshot: isize, lppe: *mut PROCESSENTRY32W) -> i32;
    fn Process32NextW(hSnapshot: isize, lppe: *mut PROCESSENTRY32W) -> i32;
    fn CloseHandle(hObject: isize) -> i32;
}

#[link(name = "iphlpapi")]
extern "system" {
    fn GetExtendedUdpTable(
        pUdpTable: *mut u8,
        pdwSize: *mut u32,
        bOrder: i32,
        ulAf: u32,
        TableClass: u32,
        Reserved: u32,
    ) -> u32;
}

const AF_INET: u32 = 2;
const UDP_TABLE_OWNER_PID: u32 = 1;

fn get_pid_by_name(name: &str) -> Option<u32> {
    unsafe {
        let snapshot = CreateToolhelp32Snapshot(2, 0); // TH32CS_SNAPPROCESS = 2
        if snapshot == -1 {
            return None;
        }

        let mut entry: PROCESSENTRY32W = std::mem::zeroed();
        entry.dwSize = std::mem::size_of::<PROCESSENTRY32W>() as u32;

        if Process32FirstW(snapshot, &mut entry) != 0 {
            loop {
                let len = entry.szExeFile.iter().position(|&c| c == 0).unwrap_or(entry.szExeFile.len());
                let exe_name = String::from_utf16_lossy(&entry.szExeFile[..len]);
                if exe_name.eq_ignore_ascii_case(name) {
                    CloseHandle(snapshot);
                    return Some(entry.th32ProcessID);
                }
                if Process32NextW(snapshot, &mut entry) == 0 {
                    break;
                }
            }
        }
        CloseHandle(snapshot);
        None
    }
}

fn get_udp_ports_for_pid(pid: u32) -> Vec<u16> {
    unsafe {
        let mut size: u32 = 0;
        GetExtendedUdpTable(std::ptr::null_mut(), &mut size, 0, AF_INET, UDP_TABLE_OWNER_PID, 0);
        if size == 0 {
            return Vec::new();
        }

        let mut buf = vec![0u8; size as usize];
        let res = GetExtendedUdpTable(buf.as_mut_ptr(), &mut size, 0, AF_INET, UDP_TABLE_OWNER_PID, 0);
        if res != 0 {
            return Vec::new();
        }

        if buf.len() < 4 {
            return Vec::new();
        }
        let num_entries = u32::from_ne_bytes(buf[0..4].try_into().unwrap()) as usize;
        let mut ports = Vec::new();
        let mut offset = 4;
        for _ in 0..num_entries {
            if offset + 12 > buf.len() {
                break;
            }
            let row_port_bytes = &buf[offset + 4..offset + 8];
            let row_pid_bytes = &buf[offset + 8..offset + 12];
            let row_port_dword = u32::from_ne_bytes(row_port_bytes.try_into().unwrap());
            let row_pid = u32::from_ne_bytes(row_pid_bytes.try_into().unwrap());

            if row_pid == pid {
                let port = u16::from_be((row_port_dword & 0xFFFF) as u16);
                if port > 0 {
                    ports.push(port);
                }
            }
            offset += 12;
        }
        ports
    }
}

// Ports GTA5.exe may hold open for non-P2P traffic (HTTPS/QUIC to Rockstar
// backend services, etc.) that must never be mistaken for the P2P game port.
const NON_P2P_PORTS: [u16; 2] = [80, 443];

pub fn get_gta_udp_port(default_port: u16) -> u16 {
    if let Some(pid) = get_pid_by_name("GTA5.exe") {
        let ports = get_udp_ports_for_pid(pid);
        if let Some(&port) = ports.iter().find(|p| !NON_P2P_PORTS.contains(p)) {
            println!("Detected GTA5.exe running with PID {} on UDP port {}", pid, port);
            return port;
        }
    }
    default_port
}

pub fn append_log_to_file(entry: &LogEntry) {
    use std::io::Write;
    
    let logs_dir = if let Ok(exe_path) = std::env::current_exe() {
        if let Some(parent) = exe_path.parent() {
            parent.join("logs")
        } else {
            std::path::PathBuf::from("logs")
        }
    } else {
        std::path::PathBuf::from("logs")
    };

    if !logs_dir.exists() {
        let _ = std::fs::create_dir_all(&logs_dir);
    }

    // Prune old logs first (keep up to 10 latest files)
    if let Ok(entries) = std::fs::read_dir(&logs_dir) {
        let mut log_files = Vec::new();
        for e in entries.flatten() {
            if let Some(name) = e.file_name().to_str() {
                if name.starts_with("connections_") && name.ends_with(".log") {
                    log_files.push(e.path());
                }
            }
        }
        if log_files.len() >= 10 {
            log_files.sort();
            let to_delete = log_files.len() - 9;
            for path in log_files.iter().take(to_delete) {
                let _ = std::fs::remove_file(path);
            }
        }
    }

    let today = chrono::Local::now().format("%Y-%m-%d").to_string();
    let file_path = logs_dir.join(format!("connections_{}.log", today));
    
    if let Ok(line) = serde_json::to_string(entry) {
        if let Ok(mut file) = std::fs::OpenOptions::new()
            .create(true)
            .append(true)
            .open(file_path)
        {
            let _ = writeln!(file, "{}", line);
        }
    }
}

pub fn log_system_message(msg: &str) {
    let log = LogEntry {
        timestamp: chrono::Local::now().format("%Y-%m-%d %H:%M:%S").to_string(),
        ip: "SYSTEM".to_string(),
        action: "INFO".to_string(),
        size: 0,
        reason: msg.to_string(),
    };
    append_log_to_file(&log);
}

#[derive(Default)]
struct RateStats {
    window_start: Option<Instant>,
    count: usize,
    suspicious_count: usize,
}



pub fn start_firewall(app: AppHandle) {
    let running = STATE.read().is_running;
    if running {
        return;
    }
    STATE.write().is_running = true;
    *STOP_FLAG.write() = false;

    // Load initial dynamic blacklist
    load_dynamic_blacklist(&app);

    std::thread::spawn(move || {
        let port = get_gta_udp_port(6672);
        let filter = format!("udp.DstPort == {} and udp.PayloadLength > 0 and ip", port);
        
        let w: WinDivert<windivert::layer::NetworkLayer> = match WinDivert::network(&filter, 0, WinDivertFlags::default()) {
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
        let mut known_allowed: HashSet<String> = HashSet::new();
        let mut last_session = STATE.read().active_session.clone();
        let mut last_locked = STATE.read().is_locked;
        let mut buf = [0u8; 65535];

        while !*STOP_FLAG.read() {
            let packet = match w.recv(Some(&mut buf)) {
                Ok(p) => p,
                Err(_) => break,
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
            let active_session = state.active_session.clone();
            let is_locked = state.is_locked;

            if active_session != last_session || is_locked != last_locked {
                known_allowed.clear();
                last_session = active_session.clone();
                last_locked = is_locked;
            }

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

            if known_allowed.contains(&ip_src) {
                reason = "Known Allowed".to_string();
            } else if is_banned {
                decision = false;
                reason = "Blocked - Flood Protection".to_string();
            } else if state.is_ip_blacklisted(&ip_src) {
                decision = false;
                reason = "Blocked - Blacklist".to_string();
            } else {
                match active_session.as_str() {
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
                        if is_locked {
                            if !is_friend && !is_lan && MATCHMAKING_SIZES.contains(&payload_len) {
                                decision = false;
                                reason = "Blocked - Locked Session".to_string();
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

            // Cache allowed IP addresses
            if decision {
                known_allowed.insert(ip_src.clone());
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
                            let _ = app.emit("play-sound", "ips");
                        }
                        if state.config.auto_lock_on_attack && !state.is_locked {
                            drop(state);
                            {
                                let mut state_write = STATE.write();
                                state_write.is_locked = true;
                            }
                            let _ = app.emit("status-changed", ());
                            crate::update_window_icon(&app);
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
                    let _ = app.emit("connection-log", log.clone());
                    append_log_to_file(&log);
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

    // Stop and delete the WinDivert driver service to force the blocking recv() call to abort
    // and release the files. Since the app is running as Administrator, this will succeed.
    use std::os::windows::process::CommandExt;
    let _ = std::process::Command::new("sc.exe")
        .args(&["stop", "WinDivert1.3"])
        .creation_flags(0x08000000) // CREATE_NO_WINDOW
        .output();
    let _ = std::process::Command::new("sc.exe")
        .args(&["delete", "WinDivert1.3"])
        .creation_flags(0x08000000)
        .output();

    let _ = std::process::Command::new("sc.exe")
        .args(&["stop", "WinDivert1.4"])
        .creation_flags(0x08000000)
        .output();
    let _ = std::process::Command::new("sc.exe")
        .args(&["delete", "WinDivert1.4"])
        .creation_flags(0x08000000)
        .output();
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_load_blacklist() {
        let mut ranges = Vec::new();
        let path = std::path::Path::new("../db.json");
        assert!(path.exists(), "db.json must exist in root");
        let content = std::fs::read_to_string(path).unwrap();
        let val: serde_json::Value = serde_json::from_str(&content).unwrap();
        let values = val.get("values").unwrap().as_array().unwrap();
        let mut found_azure = false;
        for cat in values {
            if cat.get("name").unwrap().as_str() == Some("AzureCloud") {
                found_azure = true;
                let prefixes = cat.get("properties").unwrap().get("addressPrefixes").unwrap().as_array().unwrap();
                for p in prefixes {
                    let prefix_str = p.as_str().unwrap();
                    if let Ok(net) = prefix_str.parse::<ipnet::Ipv4Net>() {
                        ranges.push(net);
                    }
                }
            }
        }
        assert!(found_azure, "AzureCloud category must exist in db.json");
        assert!(ranges.len() > 1000, "Should load thousands of Azure ranges");
        println!("Loaded {} Azure ranges successfully", ranges.len());
    }

    #[test]
    fn test_is_ip_relay_correctness() {
        let mut ranges = Vec::new();
        ranges.push("40.112.0.0/12".parse::<ipnet::Ipv4Net>().unwrap());
        ranges.push("192.168.1.0/24".parse::<ipnet::Ipv4Net>().unwrap());
        ranges.push("185.56.64.0/22".parse::<ipnet::Ipv4Net>().unwrap());
        
        let table = build_dynamic_blacklist_table(&ranges);
        let state = FirewallState {
            active_session: "Open".to_string(),
            is_locked: false,
            is_running: false,
            whitelist: std::collections::HashSet::new(),
            blacklist: std::collections::HashSet::new(),
            dynamic_blacklist: ranges.clone(),
            dynamic_blacklist_table: table,
            config: crate::config::Config::default(),
        };
        
        assert!(state.is_ip_relay("40.112.5.6"));
        assert!(state.is_ip_relay("40.127.255.254"));
        assert!(!state.is_ip_relay("40.128.0.1"));
        
        assert!(state.is_ip_relay("192.168.1.15"));
        assert!(!state.is_ip_relay("192.168.2.1"));
        
        assert!(state.is_ip_relay("185.56.64.5"));
        assert!(state.is_ip_relay("185.56.67.250"));
        assert!(!state.is_ip_relay("185.56.68.1"));
    }
}
