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
    pub active_session: String, // "Open" or "Lock"
    pub is_locked: bool,
    pub is_running: bool,
    pub driver_error: Option<String>,
    pub blacklist: HashSet<String>,
    pub dynamic_blacklist: Vec<ipnet::Ipv4Net>,
    pub dynamic_blacklist_table: Vec<Vec<ipnet::Ipv4Net>>,
    pub config: crate::config::Config,
    pub current_port: u16,
}

impl FirewallState {
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
    blacklist_subnets: Vec<ipnet::Ipv4Net>,
}

static SUBNETS: Lazy<RwLock<ParsedSubnets>> = Lazy::new(|| {
    RwLock::new(ParsedSubnets {
        blacklist_subnets: Vec::new(),
    })
});

pub static STATE: Lazy<Arc<RwLock<FirewallState>>> = Lazy::new(|| {
    let config = crate::config::load_config();
    let blacklist: HashSet<String> = config.blacklist.keys().cloned().collect();

    let mut bl_subnets = Vec::new();

    for ip in &blacklist {
        if ip.contains('/') {
            if let Ok(net) = ip.parse::<ipnet::Ipv4Net>() {
                bl_subnets.push(net);
            }
        }
    }

    {
        let mut sub = SUBNETS.write();
        sub.blacklist_subnets = bl_subnets;
    }

    Arc::new(RwLock::new(FirewallState {
        active_session: "Open".to_string(),
        is_locked: false,
        is_running: false,
        driver_error: None,
        blacklist,
        dynamic_blacklist: Vec::new(),
        dynamic_blacklist_table: vec![Vec::new(); 65536],
        config,
        current_port: 6672,
    }))
});

impl FirewallState {
    fn blacklist_subnets(&self) -> Vec<ipnet::Ipv4Net> {
        SUBNETS.read().blacklist_subnets.clone()
    }
}

// Global thread control
static STOP_FLAG: Lazy<Arc<RwLock<bool>>> = Lazy::new(|| Arc::new(RwLock::new(false)));
static WORKER_RUNNING: Lazy<Arc<RwLock<bool>>> = Lazy::new(|| Arc::new(RwLock::new(false)));

fn fetch_ripe_prefixes(asn: u32) -> Result<Vec<ipnet::Ipv4Net>, Box<dyn std::error::Error>> {
    let url = format!(
        "https://stat.ripe.net/data/announced-prefixes/data.json?resource=AS{}",
        asn
    );
    let client = reqwest::blocking::Client::builder()
        .user_agent("G-Lock/1.0 (GTA5-Firewall; +https://github.com)")
        .timeout(Duration::from_secs(10))
        .build()?;
    let resp = client.get(&url).send()?.error_for_status()?;
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
        let start_key = (u32::from(net.network()) >> 16) as usize;
        let end_key = (u32::from(net.broadcast()) >> 16) as usize;
        for bucket in table.iter_mut().take(end_key + 1).skip(start_key) {
            bucket.push(net);
        }
    }
    table
}

pub fn load_dynamic_blacklist(app: &AppHandle) {
    let mut ranges = Vec::new();
    log_system_message("SYSTEM: Starting load_dynamic_blacklist...");

    // 1.1. T2 Hardcoded prefixes
    let t2_prefixes = [
        "185.56.64.0/24",
        "185.56.64.0/22",
        "185.56.65.0/24",
        "185.56.66.0/24",
        "185.56.67.0/24",
        "104.255.104.0/24",
        "104.255.104.0/22",
        "104.255.105.0/24",
        "104.255.106.0/24",
        "104.255.107.0/24",
        "192.81.240.0/24",
        "192.81.240.0/22",
        "192.81.241.0/24",
        "192.81.242.0/24",
        "192.81.243.0/24",
        "192.81.244.0/24",
        "192.81.244.0/22",
        "192.81.245.0/24",
        "192.81.246.0/24",
        "192.81.247.0/24",
        "198.133.210.0/24",
    ];
    for p in &t2_prefixes {
        if let Ok(net) = p.parse::<ipnet::Ipv4Net>() {
            if !ranges.contains(&net) {
                ranges.push(net);
            }
        }
    }

    // 2. Load Azure Cloud from db.json if present
    use tauri::path::BaseDirectory;
    use tauri::Manager;
    let mut db_content = None;

    if let Ok(resource_path) = app.path().resolve("db.json", BaseDirectory::Resource) {
        log_system_message(&format!(
            "SYSTEM: Resolved Tauri resource path to {:?}",
            resource_path
        ));
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
                        if let Some(prefixes) = cat
                            .get("properties")
                            .and_then(|p| p.get("addressPrefixes"))
                            .and_then(|a| a.as_array())
                        {
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
                log_system_message(&format!(
                    "SYSTEM: Successfully loaded {} Azure ranges from db.json.",
                    count
                ));
            }
        } else {
            log_system_message("SYSTEM ERROR: Failed to parse db.json as JSON.");
        }
    } else {
        log_system_message("SYSTEM WARNING: db.json could not be loaded from any source.");
    }

    log_system_message(&format!(
        "SYSTEM: Total dynamic blacklist size: {} ranges.",
        ranges.len()
    ));
    let table = build_dynamic_blacklist_table(&ranges);
    {
        let mut state = STATE.write();
        state.dynamic_blacklist = ranges;
        state.dynamic_blacklist_table = table;
    }
    log_system_message("SYSTEM: load_dynamic_blacklist finished successfully.");

    // Refresh Take-Two ranges without delaying Tauri startup or the packet worker.
    std::thread::spawn(|| {
        let mut fetched = Vec::new();
        for asn in &[202021, 46555] {
            match fetch_ripe_prefixes(*asn) {
                Ok(nets) => {
                    log_system_message(&format!(
                        "SYSTEM: Fetched {} prefixes for AS{}",
                        nets.len(),
                        asn
                    ));
                    fetched.extend(nets);
                }
                Err(e) => log_system_message(&format!(
                    "SYSTEM WARNING: Failed to refresh prefixes for AS{}: {:?}",
                    asn, e
                )),
            }
        }
        if fetched.is_empty() {
            return;
        }
        let mut ranges = STATE.read().dynamic_blacklist.clone();
        for network in fetched {
            if !ranges.contains(&network) {
                ranges.push(network);
            }
        }
        let table = build_dynamic_blacklist_table(&ranges);
        let mut state = STATE.write();
        state.dynamic_blacklist = ranges;
        state.dynamic_blacklist_table = table;
    });
}

pub fn update_subnets_cache() {
    let state = STATE.read();
    let mut bl_subnets = Vec::new();

    for ip in &state.blacklist {
        if ip.contains('/') {
            if let Ok(net) = ip.parse::<ipnet::Ipv4Net>() {
                bl_subnets.push(net);
            }
        }
    }

    let mut sub = SUBNETS.write();
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
    dst_ip: String,
    payload_len: usize,
}

impl ParsedPacket {
    fn peer_ip(&self, outbound: bool) -> &str {
        if outbound {
            &self.dst_ip
        } else {
            &self.src_ip
        }
    }
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
    let dst_ip = format!("{}.{}.{}.{}", data[16], data[17], data[18], data[19]);
    let payload_len = data.len() - (ihl + 8);
    Some(ParsedPacket {
        src_ip,
        dst_ip,
        payload_len,
    })
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
                let len = entry
                    .szExeFile
                    .iter()
                    .position(|&c| c == 0)
                    .unwrap_or(entry.szExeFile.len());
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
        GetExtendedUdpTable(
            std::ptr::null_mut(),
            &mut size,
            0,
            AF_INET,
            UDP_TABLE_OWNER_PID,
            0,
        );
        if size == 0 {
            return Vec::new();
        }

        let mut buf = vec![0u8; size as usize];
        let res = GetExtendedUdpTable(
            buf.as_mut_ptr(),
            &mut size,
            0,
            AF_INET,
            UDP_TABLE_OWNER_PID,
            0,
        );
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

pub fn get_gta_udp_port(default_port: u16) -> u16 {
    if let Some(pid) = get_pid_by_name("GTA5.exe") {
        let ports = get_udp_ports_for_pid(pid);
        if ports.contains(&default_port) {
            log_system_message(&format!(
                "SYSTEM: Confirmed GTA5.exe PID {} listening on UDP port {}.",
                pid, default_port
            ));
        } else if !ports.is_empty() {
            log_system_message(&format!(
                "SYSTEM: GTA5.exe PID {} has UDP sockets {:?}, but none can be safely identified as P2P; using {}.",
                pid, ports, default_port
            ));
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

struct RateStats {
    window_start: Instant,
    count: usize,
    suspicious_count: usize,
    last_seen: Instant,
}

impl RateStats {
    fn new(now: Instant) -> Self {
        Self {
            window_start: now,
            count: 0,
            suspicious_count: 0,
            last_seen: now,
        }
    }
}

const MAX_TRACKED_IPS: usize = 4096;
const TRACKING_TTL: Duration = Duration::from_secs(5 * 60);
const KNOWN_PEER_TTL: Duration = Duration::from_secs(30 * 60);
const PRUNE_INTERVAL: Duration = Duration::from_secs(5);
const ALERT_COOLDOWN: Duration = Duration::from_secs(10);

struct PacketContext {
    payload_len: usize,
    is_locked: bool,
    is_banned: bool,
    is_blacklisted: bool,
    is_known: bool,
    is_relay: bool,
    is_lan: bool,
}

struct PacketDecision {
    allow: bool,
    reason: &'static str,
    cache_peer: bool,
}

fn decide_packet(context: PacketContext) -> PacketDecision {
    // A user blacklist rule is absolute, including heartbeat-sized traffic.
    if context.is_blacklisted {
        return PacketDecision {
            allow: false,
            reason: "Blocked - Blacklist",
            cache_peer: false,
        };
    }
    if HEARTBEAT_SIZES.contains(&context.payload_len) {
        return PacketDecision {
            allow: true,
            reason: if context.is_relay {
                "Service/Heartbeat (Relay)"
            } else {
                "Service/Heartbeat"
            },
            cache_peer: false,
        };
    }
    if context.is_banned {
        return PacketDecision {
            allow: false,
            reason: "Blocked - Flood Protection",
            cache_peer: false,
        };
    }
    if context.is_known {
        return PacketDecision {
            allow: true,
            reason: "Known Allowed",
            cache_peer: true,
        };
    }
    // Lock preserves already-known peers but rejects every new peer.
    if context.is_locked {
        return PacketDecision {
            allow: false,
            reason: if context.is_relay {
                "Blocked - Locked Session (Relay)"
            } else {
                "Blocked - Unknown During Locked Session"
            },
            cache_peer: false,
        };
    }

    if context.is_lan {
        return PacketDecision {
            allow: true,
            reason: "LAN",
            cache_peer: false,
        };
    }
    PacketDecision {
        allow: true,
        reason: "Open Session",
        cache_peer: !context.is_relay,
    }
}

fn evict_oldest_timestamp(map: &mut HashMap<String, Instant>) {
    if let Some(oldest) = map
        .iter()
        .min_by_key(|(_, timestamp)| **timestamp)
        .map(|(ip, _)| ip.clone())
    {
        map.remove(&oldest);
    }
}

fn evict_oldest_rate(map: &mut HashMap<String, RateStats>) {
    if let Some(oldest) = map
        .iter()
        .min_by_key(|(_, stats)| stats.last_seen)
        .map(|(ip, _)| ip.clone())
    {
        map.remove(&oldest);
    }
}

const ERROR_SERVICE_DISABLED: i32 = 1058;

fn is_service_disabled_error(error: &WinDivertError) -> bool {
    matches!(
        error,
        WinDivertError::IOError(io_error)
            if io_error.raw_os_error() == Some(ERROR_SERVICE_DISABLED)
    )
}

fn repair_windivert_service() -> Result<(), String> {
    use std::os::windows::process::CommandExt;

    let executable = std::env::current_exe()
        .map_err(|error| format!("cannot locate current executable: {error}"))?;
    let executable_dir = executable
        .parent()
        .ok_or_else(|| "current executable has no parent directory".to_string())?;
    let driver_path = executable_dir.join("WinDivert64.sys");
    if !driver_path.is_file() {
        return Err(format!(
            "WinDivert64.sys is missing at {}",
            driver_path.display()
        ));
    }

    // WinDivert creates a demand-start kernel service. A stale installation can
    // leave that service disabled (Windows error 1058), so restore both its
    // startup mode and binary path to the driver shipped with this executable.
    let kernel_driver_path = format!(r"\??\{}", driver_path.display());
    let output = std::process::Command::new("sc.exe")
        .args([
            "config",
            "WinDivert",
            "type=",
            "kernel",
            "start=",
            "demand",
            "binPath=",
            &kernel_driver_path,
        ])
        .creation_flags(0x08000000) // CREATE_NO_WINDOW
        .output()
        .map_err(|error| format!("failed to run Service Control Manager: {error}"))?;

    if output.status.success() {
        log_system_message(&format!(
            "SYSTEM: Restored WinDivert service to demand start at {}.",
            driver_path.display()
        ));
        Ok(())
    } else {
        Err(format!(
            "Service Control Manager returned exit code {:?}",
            output.status.code()
        ))
    }
}

pub fn start_firewall(app: AppHandle) {
    let mut worker_running = WORKER_RUNNING.write();
    if *worker_running {
        return;
    }
    *worker_running = true;
    *STOP_FLAG.write() = false;

    // Bundled relay ranges load immediately; RIPE refresh continues in the background.
    load_dynamic_blacklist(&app);
    let port = get_gta_udp_port(6672);
    {
        let mut state = STATE.write();
        state.current_port = port;
        state.is_running = true;
        state.driver_error = None;
    }
    let _ = app.emit("status-changed", ());
    std::thread::spawn(move || run_packet_capture(app, port));
}

#[derive(Clone, Copy)]
struct RuntimeSettings {
    ips_enabled: bool,
    ips_floor: usize,
    ips_fallback: usize,
    ips_ban_duration: u64,
    ips_adaptive_multiplier: usize,
    ips_measurement_seconds: u64,
    ips_global_pps_ceiling: usize,
    auto_lock_on_attack: bool,
    sound_enabled: bool,
    verbose_logging_enabled: bool,
    verbose_flood_threshold: usize,
}

impl RuntimeSettings {
    fn from_config(config: &crate::config::Config) -> Self {
        Self {
            ips_enabled: config.ips_enabled,
            ips_floor: config.ips_pps_threshold as usize,
            ips_fallback: config.ips_fallback_threshold as usize,
            ips_ban_duration: config.ips_ban_duration as u64,
            ips_adaptive_multiplier: config.ips_adaptive_multiplier as usize,
            ips_measurement_seconds: config.ips_adaptive_measurement_seconds as u64,
            ips_global_pps_ceiling: config.ips_global_pps_ceiling as usize,
            auto_lock_on_attack: config.auto_lock_on_attack,
            sound_enabled: config.sound_enabled,
            verbose_logging_enabled: config.verbose_logging_enabled,
            verbose_flood_threshold: config.verbose_flood_threshold as usize,
        }
    }
}

fn run_packet_capture(app: AppHandle, port: u16) {
    let filter = format!(
        "(udp.SrcPort == {0} or udp.DstPort == {0}) and udp.PayloadLength > 0 and ip",
        port
    );
    log_system_message(&format!(
        "SYSTEM: Opening WinDivert on UDP port {} (filter: {})",
        port, filter
    ));

    let first_open = WinDivert::network(&filter, 0, WinDivertFlags::default());
    let open_result = match first_open {
        Err(error) if is_service_disabled_error(&error) => {
            log_system_message(
                "SYSTEM WARNING: WinDivert service is disabled; attempting automatic repair.",
            );
            match repair_windivert_service() {
                Ok(()) => {
                    std::thread::sleep(Duration::from_millis(100));
                    WinDivert::network(&filter, 0, WinDivertFlags::default())
                }
                Err(repair_error) => {
                    log_system_message(&format!(
                        "SYSTEM ERROR: Failed to repair disabled WinDivert service: {}",
                        repair_error
                    ));
                    Err(error)
                }
            }
        }
        result => result,
    };

    let w: WinDivert<windivert::layer::NetworkLayer> = match open_result {
        Ok(handle) => handle,
        Err(e) => {
            let err_msg = if is_service_disabled_error(&e) {
                "Windows service WinDivert is disabled and automatic repair failed".to_string()
            } else {
                e.to_string()
            };
            log_system_message(&format!(
                "SYSTEM ERROR: Failed to open WinDivert handle: {}",
                err_msg
            ));
            {
                let mut state = STATE.write();
                state.is_running = false;
                state.driver_error = Some(err_msg);
            }
            *WORKER_RUNNING.write() = false;
            let _ = app.emit("status-changed", ());
            return;
        }
    };
    log_system_message("SYSTEM: WinDivert handle opened successfully, packet capture started.");

    let session_start = Instant::now();
    let mut rates: HashMap<String, RateStats> = HashMap::new();
    let mut temp_blacklist: HashMap<String, Instant> = HashMap::new();
    let mut known_allowed: HashMap<String, Instant> = HashMap::new();
    let mut last_log_time: HashMap<String, Instant> = HashMap::new();

    let initial_config = STATE.read().config.clone();
    let mut current_threshold = (initial_config.ips_fallback_threshold as usize)
        .max(initial_config.ips_pps_threshold as usize);
    let mut measured_max_pps = 0;
    let mut adaptive_calibrated = false;

    let mut last_locked = STATE.read().is_locked;
    let mut last_prune = Instant::now();
    let mut global_window_start = Instant::now();
    let mut global_suspicious_count = 0usize;
    let mut last_alert: Option<Instant> = None;
    let mut buf = [0u8; 65535];

    while !*STOP_FLAG.read() {
        let packet = match w.recv(Some(&mut buf)) {
            Ok(packet) => packet,
            Err(e) => {
                if !*STOP_FLAG.read() {
                    log_system_message(&format!(
                        "SYSTEM ERROR: WinDivert recv failed, capture loop exiting: {:?}",
                        e
                    ));
                }
                break;
            }
        };

        let parsed = match parse_ipv4_udp(&packet.data) {
            Some(parsed) => parsed,
            None => {
                let hex_data = packet
                    .data
                    .iter()
                    .take(20)
                    .map(|byte| format!("{:02X}", byte))
                    .collect::<Vec<String>>()
                    .join(" ");
                log_system_message(&format!(
                    "SYSTEM ERROR: Unparsed packet (Len: {}, Hex: [{}]). Reinjecting.",
                    packet.data.len(),
                    hex_data
                ));
                if let Err(e) = w.send(&packet) {
                    log_system_message(&format!(
                        "SYSTEM ERROR: WinDivert send failed (unparsed): {:?}",
                        e
                    ));
                }
                continue;
            }
        };

        let outbound = packet.address.outbound();
        let ip_src = parsed.peer_ip(outbound).to_string();
        let payload_len = parsed.payload_len;
        let now = Instant::now();

        let (is_locked, is_blacklisted, is_relay, settings) = {
            let state = STATE.read();
            (
                state.is_locked,
                state.is_ip_blacklisted(&ip_src),
                state.is_ip_relay(&ip_src),
                RuntimeSettings::from_config(&state.config),
            )
        };
        let is_lan = is_lan_ip(&ip_src);

        if last_locked && !is_locked {
            known_allowed.clear();
        }
        last_locked = is_locked;

        if now.duration_since(last_prune) >= PRUNE_INTERVAL {
            rates.retain(|_, stats| now.duration_since(stats.last_seen) < TRACKING_TTL);
            temp_blacklist.retain(|_, expires_at| now < *expires_at);
            known_allowed.retain(|_, seen_at| now.duration_since(*seen_at) < KNOWN_PEER_TTL);
            last_log_time.retain(|_, seen_at| now.duration_since(*seen_at) < TRACKING_TTL);
            last_prune = now;
        }

        let is_service =
            HEARTBEAT_SIZES.contains(&payload_len) || MATCHMAKING_SIZES.contains(&payload_len);
        let is_suspicious = !outbound && !is_service && !is_lan && !is_relay;
        let is_banned = settings.ips_enabled
            && temp_blacklist
                .get(&ip_src)
                .is_some_and(|expires_at| now < *expires_at);

        let packet_decision = decide_packet(PacketContext {
            payload_len,
            is_locked,
            is_banned,
            is_blacklisted,
            is_known: known_allowed.contains_key(&ip_src),
            is_relay,
            is_lan,
        });

        let mut is_new_connection = false;
        if packet_decision.allow && packet_decision.cache_peer {
            is_new_connection = !known_allowed.contains_key(&ip_src);
            if known_allowed.len() >= MAX_TRACKED_IPS && !known_allowed.contains_key(&ip_src) {
                evict_oldest_timestamp(&mut known_allowed);
            }
            known_allowed.insert(ip_src.clone(), now);
        }

        if rates.len() >= MAX_TRACKED_IPS && !rates.contains_key(&ip_src) {
            evict_oldest_rate(&mut rates);
        }
        let stats = rates
            .entry(ip_src.clone())
            .or_insert_with(|| RateStats::new(now));
        stats.last_seen = now;
        stats.count += 1;
        if is_suspicious {
            stats.suspicious_count += 1;
            global_suspicious_count += 1;
        }

        let mut observed_pps = None;
        let mut ip_attack = false;
        if now.duration_since(stats.window_start) >= Duration::from_secs(1) {
            let pps = stats.suspicious_count;
            observed_pps = Some(pps);
            stats.window_start = now;
            stats.count = 0;
            stats.suspicious_count = 0;

            if !adaptive_calibrated {
                let elapsed = now.duration_since(session_start);
                if elapsed < Duration::from_secs(settings.ips_measurement_seconds) {
                    measured_max_pps = measured_max_pps.max(pps);
                } else {
                    current_threshold = if measured_max_pps > 0 {
                        (measured_max_pps.max(5) * settings.ips_adaptive_multiplier)
                            .max(settings.ips_floor)
                    } else {
                        settings.ips_fallback.max(settings.ips_floor)
                    };
                    adaptive_calibrated = true;
                    log_system_message(&format!(
                        "SYSTEM: Adaptive IPS calibrated at {} PPS.",
                        current_threshold
                    ));
                }
            }
            if adaptive_calibrated {
                current_threshold = if measured_max_pps > 0 {
                    (measured_max_pps.max(5) * settings.ips_adaptive_multiplier)
                        .max(settings.ips_floor)
                } else {
                    settings.ips_fallback.max(settings.ips_floor)
                };
            }

            if settings.ips_enabled && is_suspicious && pps >= current_threshold {
                if temp_blacklist.len() >= MAX_TRACKED_IPS && !temp_blacklist.contains_key(&ip_src)
                {
                    evict_oldest_timestamp(&mut temp_blacklist);
                }
                temp_blacklist.insert(
                    ip_src.clone(),
                    now + Duration::from_secs(settings.ips_ban_duration),
                );
                ip_attack = true;
            }
        }

        let mut global_attack = false;
        if now.duration_since(global_window_start) >= Duration::from_secs(1) {
            global_attack =
                settings.ips_enabled && global_suspicious_count >= settings.ips_global_pps_ceiling;
            if global_attack {
                log_system_message(&format!(
                    "SYSTEM ALERT: Global traffic ceiling exceeded ({} PPS).",
                    global_suspicious_count
                ));
            }
            global_suspicious_count = 0;
            global_window_start = now;
        }

        if (ip_attack || global_attack)
            && last_alert.is_none_or(|alert| now.duration_since(alert) >= ALERT_COOLDOWN)
        {
            if settings.sound_enabled {
                let _ = app.emit("play-sound", "ips");
            }
            if settings.auto_lock_on_attack && !is_locked {
                {
                    let mut state = STATE.write();
                    state.is_locked = true;
                    state.active_session = "Lock".to_string();
                }
                let _ = app.emit("status-changed", ());
                crate::update_window_icon(&app);
            }
            last_alert = Some(now);
        }

        let rate_log = settings.verbose_logging_enabled
            && observed_pps.is_some_and(|pps| pps >= settings.verbose_flood_threshold);
        let should_log = !packet_decision.allow
            || is_relay
            || MATCHMAKING_SIZES.contains(&payload_len)
            || is_new_connection
            || rate_log;
        if should_log {
            let can_log = last_log_time
                .get(&ip_src)
                .is_none_or(|last| now.duration_since(*last) >= Duration::from_secs(15));
            if can_log {
                if last_log_time.len() >= MAX_TRACKED_IPS && !last_log_time.contains_key(&ip_src) {
                    evict_oldest_timestamp(&mut last_log_time);
                }
                last_log_time.insert(ip_src.clone(), now);
                let log = LogEntry {
                    timestamp: chrono::Local::now().format("%Y-%m-%d %H:%M:%S").to_string(),
                    ip: ip_src.clone(),
                    action: if packet_decision.allow {
                        "ALLOW".to_string()
                    } else {
                        "BLOCK".to_string()
                    },
                    size: payload_len,
                    reason: packet_decision.reason.to_string(),
                };
                let _ = app.emit("connection-log", log.clone());
                if settings.verbose_logging_enabled || !packet_decision.allow {
                    append_log_to_file(&log);
                }
            }
        }

        if packet_decision.allow {
            if let Err(e) = w.send(&packet) {
                log_system_message(&format!(
                    "SYSTEM ERROR: WinDivert send failed (allowed): {:?}",
                    e
                ));
            }
        }
    }

    {
        let mut state = STATE.write();
        state.is_running = false;
    }
    *WORKER_RUNNING.write() = false;
    let _ = app.emit("status-changed", ());
}

pub fn stop_firewall_worker() {
    *STOP_FLAG.write() = true;
}

pub fn shutdown_firewall() {
    stop_firewall_worker();

    // Send a dummy UDP packet to localhost on the active G-Lock port to unblock w.recv()
    let port = STATE.read().current_port;
    if let Ok(socket) = std::net::UdpSocket::bind("127.0.0.1:0") {
        let _ = socket.send_to(&[0], format!("127.0.0.1:{}", port));
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn detects_disabled_windivert_service_error() {
        let error =
            WinDivertError::IOError(std::io::Error::from_raw_os_error(ERROR_SERVICE_DISABLED));
        assert!(is_service_disabled_error(&error));
    }

    #[test]
    fn test_load_blacklist() {
        let mut ranges = Vec::new();
        let path = std::path::Path::new("db.json");
        assert!(path.exists(), "bundled db.json must exist in src-tauri");
        let content = std::fs::read_to_string(path).unwrap();
        let val: serde_json::Value = serde_json::from_str(&content).unwrap();
        let values = val.get("values").unwrap().as_array().unwrap();
        let mut found_azure = false;
        for cat in values {
            if cat.get("name").unwrap().as_str() == Some("AzureCloud") {
                found_azure = true;
                let prefixes = cat
                    .get("properties")
                    .unwrap()
                    .get("addressPrefixes")
                    .unwrap()
                    .as_array()
                    .unwrap();
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
        let ranges = vec![
            "40.112.0.0/12".parse::<ipnet::Ipv4Net>().unwrap(),
            "192.168.1.0/24".parse::<ipnet::Ipv4Net>().unwrap(),
            "185.56.64.0/22".parse::<ipnet::Ipv4Net>().unwrap(),
        ];

        let table = build_dynamic_blacklist_table(&ranges);
        let state = FirewallState {
            active_session: "Open".to_string(),
            is_locked: false,
            is_running: false,
            driver_error: None,
            blacklist: std::collections::HashSet::new(),
            dynamic_blacklist: ranges.clone(),
            dynamic_blacklist_table: table,
            config: crate::config::Config::default(),
            current_port: 6672,
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

    #[test]
    fn heartbeat_is_allowed_unless_ip_is_blacklisted() {
        let allowed = decide_packet(PacketContext {
            payload_len: 18,
            is_locked: true,
            is_banned: true,
            is_blacklisted: false,
            is_known: false,
            is_relay: true,
            is_lan: false,
        });
        let decision = decide_packet(PacketContext {
            payload_len: 18,
            is_locked: true,
            is_banned: true,
            is_blacklisted: true,
            is_known: false,
            is_relay: true,
            is_lan: false,
        });
        assert!(allowed.allow);
        assert!(!decision.allow);
        assert_eq!(decision.reason, "Blocked - Blacklist");
    }

    #[test]
    fn blacklist_overrides_known_peer_cache() {
        let decision = decide_packet(PacketContext {
            payload_len: 100,
            is_locked: false,
            is_banned: false,
            is_blacklisted: true,
            is_known: true,
            is_relay: false,
            is_lan: false,
        });
        assert!(!decision.allow);
        assert_eq!(decision.reason, "Blocked - Blacklist");
    }

    #[test]
    fn locked_session_allows_only_known_peers() {
        let known = decide_packet(PacketContext {
            payload_len: 100,
            is_locked: true,
            is_banned: false,
            is_blacklisted: false,
            is_known: true,
            is_relay: false,
            is_lan: false,
        });
        let unknown = decide_packet(PacketContext {
            payload_len: 100,
            is_locked: true,
            is_banned: false,
            is_blacklisted: false,
            is_known: false,
            is_relay: false,
            is_lan: false,
        });
        assert!(known.allow);
        assert!(!unknown.allow);
    }

    #[test]
    fn parser_uses_ipv4_header_length() {
        let mut packet = vec![0_u8; 24 + 8 + 12];
        packet[0] = 0x46; // IPv4, IHL = 24 bytes
        packet[9] = 17; // UDP
        packet[12..16].copy_from_slice(&[203, 0, 113, 7]);
        packet[16..20].copy_from_slice(&[198, 51, 100, 9]);
        let parsed = parse_ipv4_udp(&packet).unwrap();
        assert_eq!(parsed.src_ip, "203.0.113.7");
        assert_eq!(parsed.dst_ip, "198.51.100.9");
        assert_eq!(parsed.peer_ip(false), "203.0.113.7");
        assert_eq!(parsed.peer_ip(true), "198.51.100.9");
        assert_eq!(parsed.payload_len, 12);
    }

    #[test]
    fn relay_table_supports_default_route() {
        let ranges = vec!["0.0.0.0/0".parse::<ipnet::Ipv4Net>().unwrap()];
        let table = build_dynamic_blacklist_table(&ranges);
        assert_eq!(table.len(), 65_536);
        assert!(table.iter().all(|bucket| bucket.len() == 1));
    }
}
