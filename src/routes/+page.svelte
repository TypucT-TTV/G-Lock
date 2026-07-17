<script lang="ts">
  import { invoke } from "@tauri-apps/api/core";
  import { listen } from "@tauri-apps/api/event";
  import { onMount } from "svelte";

  type Settings = {
    blacklist: Record<string, string>;
    language: "ru" | "en";
    hotkey_vk: number;
    hotkey_name: string;
    sound_enabled: boolean;
    sound_lock_freq: number;
    sound_lock_dur: number;
    sound_lock_vol: number;
    sound_unlock_freq: number;
    sound_unlock_dur: number;
    sound_unlock_vol: number;
    zoom_factor: number;
    verbose_logging_enabled: boolean;
    verbose_flood_threshold: number;
    ips_enabled: boolean;
    ips_pps_threshold: number;
    ips_ban_duration: number;
    auto_lock_on_attack: boolean;
    panic_hotkey_vk: number;
    panic_hotkey_ctrl: boolean;
    panic_hotkey_name: string;
    ips_adaptive_multiplier: number;
    ips_adaptive_measurement_seconds: number;
    ips_fallback_threshold: number;
    ips_global_pps_ceiling: number;
    window_w: number | null;
    window_h: number | null;
    window_x: number | null;
    window_y: number | null;
  };

  type HelpArticle = {
    id: string;
    title: string;
    short: string;
    full: string;
    points?: string[];
    warning?: string;
  };

  // State definitions using Svelte 5 runes
  let activeTab = $state("dashboard"); // "dashboard", "settings", "logs", "help", "donate"
  let status = $state({ active_session: "Open", is_locked: false, is_running: false, driver_error: null as string | null });
  let lists = $state({ blacklist: [] as string[] });
  let settings = $state<Settings>({
    blacklist: {},
    language: "ru",
    hotkey_vk: 0x78,
    hotkey_name: "F9",
    sound_enabled: true,
    sound_lock_freq: 900,
    sound_lock_dur: 200,
    sound_lock_vol: 80,
    sound_unlock_freq: 400,
    sound_unlock_dur: 200,
    sound_unlock_vol: 80,
    zoom_factor: 1,
    verbose_logging_enabled: true,
    verbose_flood_threshold: 50,
    ips_enabled: true,
    ips_pps_threshold: 150,
    ips_ban_duration: 60,
    ips_adaptive_multiplier: 5,
    ips_adaptive_measurement_seconds: 45,
    ips_fallback_threshold: 250,
    ips_global_pps_ceiling: 2000,
    auto_lock_on_attack: false,
    panic_hotkey_vk: 0x78,
    panic_hotkey_ctrl: true,
    panic_hotkey_name: "Ctrl+F9",
    window_w: null,
    window_h: null,
    window_x: null,
    window_y: null,
  });

  // UI helpers
  let logs = $state([] as Array<{ timestamp: string; ip: string; action: string; size: number; reason: string }>);
  let showDrawer = $state(false);
  let drawerIpInput = $state("");
  let drawerError = $state("");
  let saveStatusMsg = $state("");

  // Translations dictionary
  const t = {
    ru: {
      status_open: "🟢 ОТКРЫТО",
      status_locked: "🔴 ЗАПЕРТО",
      status_error: "⚠️ ОШИБКА ДРАЙВЕРА",
      status_tip: "Переключение доступно кнопкой или клавишей F9",
      status_desc_open: "Новые игроки могут подключаться. Blacklist и IPS продолжают работать.",
      status_desc_locked: "Новые игроки заблокированы. Уже обнаруженные участники остаются в сессии.",
      err_driver_fail: "Драйвер WinDivert не запущен (проверьте права/антивирус): ",
      lock_session: "Запереть сессию",
      stop_session: "Открыть сессию",
      live_activity: "Сетевая активность в реальном времени",
      live_activity_note: "Сначала может появиться relay-адрес Rockstar. Реальный peer IP виден только при прямом P2P; один IP не всегда означает одного конкретного игрока.",
      legend_allowed: "Разрешено",
      legend_relay: "Relay Rockstar",
      legend_blocked: "Заблокировано",
      col_time: "Время",
      col_action: "Действие",
      col_ip: "IP-адрес",
      col_detail: "Детали",
      nav_dash: "Панель управления",
      nav_settings: "Настройки",
      nav_help: "Справка",
      nav_donate: "Поблагодарить",
      nav_logs: "Логи",
      logs_title: "Логи соединений",
      logs_empty: "Лог-файлы еще не созданы или пусты. Они появятся после фиксации сетевой активности фаерволом.",
      btn_open_in_notepad: "Открыть в Блокноте",
      logs_file_list_title: "Список сохраненных файлов логов:",
      logs_view_title: "Содержимое лога:",
      blocked_ips_title: "Дополнительно: заблокированные IP",
      blocked_ips_description: "Адрес блокируется в обоих направлениях после того, как прямой peer IP становится виден G-Lock. Это не блокировка игрока по нику и не гарантия предотвращения первоначального входа через Rockstar.",
      blocked_ips_warning: "Внешний IP может измениться или использоваться несколькими игроками через NAT/CGNAT. Добавляйте только проверенные IPv4/CIDR.",
      blocked_ips_empty: "Заблокированных адресов нет.",
      btn_clear: "Очистить список",
      btn_delete: "Удалить",
      btn_add_ip: "Добавить IP-адрес",
      drawer_title: "Добавить заблокированный IP",
      drawer_placeholder: "Введите IP или CIDR...",
      btn_save: "Сохранить",
      btn_cancel: "Отмена",
      settings_sound: "Звуковые сигналы оповещения",
      settings_sound_title: "Настройка звуков",
      settings_sound_vol: "Громкость звука:",
      settings_sound_lock: "Звук блокировки (Lock):",
      settings_sound_unlock: "Звук разблокировки (Unlock):",
      sound_type_beep: "Стандартный сигнал (Beep)",
      sound_type_custom: "Пользовательский аудиофайл",
      btn_test_sound: "▶ Тест",
      btn_reset_sound: "🔄 Сброс",
      sound_file_loaded: "Аудиофайл успешно загружен",
      sound_file_empty: "Файл не выбран (нажмите для загрузки)",
      err_sound_size: "Ошибка: Звуковой файл должен быть меньше 1 МБ!",
      settings_ips: "Система предотвращения вторжений (IPS)",
      settings_enable_ips: "Включить лимиты трафика (IPS)",
      settings_ips_description: "IPS отслеживает подозрительный входящий P2P-трафик. Это дополнительная защита от флуда, а не гарантия против любой DDoS-атаки.",
      settings_multiplier: "Адаптивный множитель PPS:",
      settings_multiplier_hint: "Во сколько раз допустимый PPS должен быть выше измеренной фоновой активности.",
      settings_measurement: "Время замера базовой активности (сек):",
      settings_measurement_hint: "Период после запуска фильтрации, за который G-Lock оценивает нормальный фон.",
      settings_fallback: "Резервный порог флуда (PPS):",
      settings_fallback_hint: "Используется, если надёжно измерить фон не удалось; также задаёт нижнюю границу адаптивного порога.",
      settings_global_ceiling: "Глобальный предел трафика (PPS):",
      settings_global_hint: "Суммарный предел для подозрительного потока с множества меняющихся IP.",
      settings_autolock: "Авто-запирание сессии при атаке (Auto-Lock)",
      settings_autolock_hint: "При тревоге переводит сессию в состояние «Заперто» и запрещает новые подключения.",
      settings_lang: "Язык интерфейса:",
      settings_saved: "Настройки успешно сохранены!",
      settings_save: "Сохранить настройки",
      copy_success: "IP-адрес скопирован в буфер обмена",
      copy_title: "Кликните для копирования",
      log_file_empty: "Этот файл лога пуст или не содержит корректных записей.",
      log_select_hint: "Выберите файл лога слева для просмотра или открытия в Блокноте.",
      guardian_credit: "При разработке G-Lock использовался Guardian 3.5.0 от TheMythologist, изначально созданный Speyedr. Guardian, WinDivert 2.2.2 и Rust-библиотека windivert распространяются по LGPL v3; NOTICE, LICENSE, GPL-3.0.txt, THIRD_PARTY_NOTICES.md и ссылки на исходники входят в поставку.",
      donate_title: "Поддержка проекта G-Lock",
      donate_p1: "Всем привет. Меня зовут Тёма ТурисТ, я стример.",
      donate_p2: "Я сделал G-Lock для себя. Меня годами преследовали читеры на стримах — крашили игру мне и моим друзьям, срывали эфиры, и сделать с этим ничего было нельзя. Поддержки не было, готовых решений тоже. Тогда я написал защиту сам.",
      donate_p3: "И когда однажды я отыграл целый стрим без единого краша — понял, что это работает. Решил не держать при себе и выложить в открытый доступ, чтобы любой, кого достали гриферы, мог защититься так же.",
      donate_p4: "G-Lock полностью бесплатный, с открытым кодом и без рекламы — и таким останется. Если он спас твой стрим или просто помог спокойно поиграть с друзьями, буду благодарен за любую поддержку. Это идет на время разработки и помогает делать тул лучше. Спасибо, что вы есть 🛡️",
      btn_donate_da: "🎁 Отправить донат (donationalerts.com)",
      blocked_threats_msg: "G-Lock зафиксировал {n} блокировок за эту сессию 🛡️ Если помогло — ",
      support_link: "поддержите разработку"
    },
    en: {
      status_open: "🟢 OPEN",
      status_locked: "🔴 LOCKED",
      status_error: "⚠️ DRIVER ERROR",
      status_tip: "Use this button or press F9 to toggle the session lock",
      status_desc_open: "New players may connect. The Blacklist and IPS remain active.",
      status_desc_locked: "New players are blocked. Peers already detected in this session stay connected.",
      err_driver_fail: "WinDivert driver not running (check privileges/antivirus): ",
      lock_session: "Lock Session",
      stop_session: "Open Session",
      live_activity: "Real-time Network Activity Logs",
      live_activity_note: "A Rockstar relay address may appear first. The real peer IP is visible only during direct P2P traffic, and one IP does not always identify one specific player.",
      legend_allowed: "Allowed",
      legend_relay: "Rockstar relay",
      legend_blocked: "Blocked",
      col_time: "Time",
      col_action: "Action",
      col_ip: "IP Address",
      col_detail: "Details",
      nav_dash: "Dashboard",
      nav_settings: "Settings",
      nav_help: "Help / FAQ",
      nav_donate: "Donate",
      nav_logs: "Logs",
      logs_title: "Connection Logs",
      logs_empty: "Log files have not been created yet or are empty. They will appear after the firewall starts recording network activity.",
      btn_open_in_notepad: "Open in Notepad",
      logs_file_list_title: "Saved log files list:",
      logs_view_title: "Log contents:",
      blocked_ips_title: "Advanced: Blocked IP addresses",
      blocked_ips_description: "An address is dropped in both directions after its direct peer IP becomes visible to G-Lock. This is not a nickname-based player ban and cannot guarantee prevention of the initial Rockstar-mediated join.",
      blocked_ips_warning: "Public IPs may change or be shared by multiple players through NAT/CGNAT. Add only verified IPv4/CIDR rules.",
      blocked_ips_empty: "No blocked addresses.",
      btn_clear: "Clear List",
      btn_delete: "Delete",
      btn_add_ip: "Add IP Address",
      drawer_title: "Add a blocked IP",
      drawer_placeholder: "Enter IP or CIDR...",
      btn_save: "Save",
      btn_cancel: "Cancel",
      settings_sound: "Enable Audio Alerts",
      settings_sound_title: "Audio Alarm & Sound Settings",
      settings_sound_vol: "Sound Volume:",
      settings_sound_lock: "Lock Alert Sound:",
      settings_sound_unlock: "Unlock Alert Sound:",
      sound_type_beep: "Standard Beep Signal",
      sound_type_custom: "Custom Audio File",
      btn_test_sound: "▶ Test",
      btn_reset_sound: "🔄 Reset",
      sound_file_loaded: "Audio file loaded successfully",
      sound_file_empty: "No file selected (click to upload)",
      err_sound_size: "Error: Audio file must be smaller than 1 MB!",
      settings_ips: "Intrusion Prevention System (IPS)",
      settings_enable_ips: "Enable traffic limits (IPS)",
      settings_ips_description: "IPS watches suspicious inbound P2P traffic. It is an extra flood-control layer, not a guarantee against every DDoS attack.",
      settings_multiplier: "Adaptive PPS Multiplier:",
      settings_multiplier_hint: "How many times the allowed PPS may exceed the measured background activity.",
      settings_measurement: "Base Activity Measure Duration (sec):",
      settings_measurement_hint: "How long G-Lock observes normal traffic after filtering starts.",
      settings_fallback: "Fallback Flood Threshold (PPS):",
      settings_fallback_hint: "Used when a reliable baseline cannot be measured and as the minimum adaptive threshold.",
      settings_global_ceiling: "Global Traffic Ceiling (PPS):",
      settings_global_hint: "Aggregate ceiling for suspicious traffic arriving from many changing IP addresses.",
      settings_autolock: "Auto-Lock Session on Attack",
      settings_autolock_hint: "Changes the session to Locked after an alert and blocks new joins.",
      settings_lang: "Interface Language:",
      settings_saved: "Settings saved successfully!",
      settings_save: "Save settings",
      copy_success: "IP Address copied to clipboard",
      copy_title: "Click to copy",
      log_file_empty: "This log file is empty or contains no valid entries.",
      log_select_hint: "Select a log file on the left to view it or open it in Notepad.",
      guardian_credit: "G-Lock was developed using Guardian 3.5.0 by TheMythologist, originally created by Speyedr. Guardian, WinDivert 2.2.2, and the windivert Rust crate are distributed under LGPL v3; NOTICE, LICENSE, GPL-3.0.txt, THIRD_PARTY_NOTICES.md, and upstream source links are included with the application.",
      donate_title: "Support G-Lock Development",
      donate_p1: "Hi everyone! I'm Tyoma Tourist, a streamer.",
      donate_p2: "I originally built G-Lock for myself. For years, griefers and modders stalked me on stream — constantly crashing my game, kicking my friends, and ruining broadcasts. There was no help from support and no working solutions. So, I decided to write my own protection.",
      donate_p3: "When I finally completed a whole stream without a single crash, I knew it worked. I decided to make it open-source so anyone tired of griefers could play peacefully too.",
      donate_p4: "G-Lock is and will always remain completely free, open-source, and ad-free. If it saved your stream or simply helped you and your friends play in peace, I would be grateful for any support. It directly funds development time and helps make this tool even better. Thank you for being here 🛡️",
      btn_donate_da: "🎁 Send Donation (donationalerts.com)",
      blocked_threats_msg: "G-Lock recorded {n} blocked events this session 🛡️ If it helped — ",
      support_link: "support development"
    }
  };

  // Get active localization
  let activeLang = $derived(settings.language === "en" ? t.en : t.ru);
  let currentStatusDescription = $derived(
    status.is_locked ? activeLang.status_desc_locked : activeLang.status_desc_open
  );

  // Accordion expanded ID state
  let expandedHelpId = $state("");
  let blockedThreatsCount = $state(0);

  function toggleHelpAccordion(id: string) {
    if (expandedHelpId === id) {
      expandedHelpId = "";
    } else {
      expandedHelpId = id;
    }
  }

  // Localized Help Accordion Articles
  const helpArticles = $derived<HelpArticle[]>(
    settings.language === "en"
      ? [
          {
            id: "connection-path",
            title: "🔗 How a player connection appears",
            short: "Rockstar signaling usually appears before the direct peer IP.",
            full: "G-Lock first sees traffic used to arrange the connection and may show a Rockstar/Azure relay address. A remote peer IP becomes visible only when direct GTA P2P traffic starts.",
            points: [
              "A relay IP is a service endpoint, not the identity of a player.",
              "One public IP can be shared by multiple devices or players through NAT/CGNAT.",
              "G-Lock cannot map an IP address to a GTA nickname."
            ]
          },
          {
            id: "session-lock",
            title: "🔒 Open and Locked",
            short: "G-Lock has one session control: allow or reject new peer connections.",
            full: "Open allows new peers. Locked keeps peers already detected during the current run and rejects unknown new peers. Opening the session does not turn G-Lock off: IPS and manually blocked IP rules remain active.",
            points: [
              "Unlock before searching for a different populated lobby, then lock again after it loads.",
              "Use the status-card button or press F9 to toggle Open/Locked.",
              "Ctrl+F9 performs a panic unlock into Open."
            ]
          },
          {
            id: "unsupported-modes",
            title: "🧪 Why Solo and Whitelist modes are not offered",
            short: "Rockstar reveals the useful peer IP too late for reliable pre-admission filtering.",
            full: "A joining player first communicates through Rockstar infrastructure, while the direct peer IP appears only later. Packet-size heuristics cannot reliably distinguish every service packet from a player connection, so Solo and Whitelist modes were removed from the supported UI instead of presenting them as dependable protection."
          },
          {
            id: "blocked-ips",
            title: "🚫 Advanced blocked IP rules",
            short: "A verified IPv4/CIDR rule drops captured traffic after the real peer IP is visible.",
            full: "Blocked IP rules are managed under Settings → Advanced. They apply in both directions before heartbeat or known-peer checks, but they operate on network addresses rather than GTA identities.",
            points: [
              "A rule cannot guarantee prevention of the initial Rockstar-mediated join.",
              "Residential public IPs may change, so saved rules can become stale.",
              "NAT/CGNAT may cause multiple players to share one public IP."
            ],
            warning: "Add only addresses you have independently verified."
          },
          {
            id: "ips",
            title: "🛡️ What IPS actually protects",
            short: "It rate-limits suspicious P2P floods; it is not universal DDoS protection.",
            full: "IPS measures inbound non-service P2P traffic, derives a per-IP threshold from the startup baseline, and temporarily bans an address that exceeds it. A separate global ceiling detects aggregate traffic from many changing IPs. LAN and Rockstar/Azure relay addresses are excluded from suspicious-rate counting.",
            warning: "IPS covers the traffic captured by G-Lock; it cannot protect the entire internet connection from every volumetric attack."
          },
          {
            id: "logs",
            title: "📊 Real-time Network Log",
            short: "The log shows packet decisions, not a verified player roster.",
            full: "ALLOW or BLOCK applies to the captured packet. Blue identifies relay traffic, green an allowed peer packet, and red a blocked packet. Click the IP to copy it; the log intentionally has no one-click blocking actions.",
            points: [
              "Known Allowed means the peer was learned before the session was locked.",
              "Flood Protection means the temporary IPS limit was exceeded."
            ]
          },
          {
            id: "limits",
            title: "⚠️ Scope and privacy",
            short: "G-Lock is a packet filter, not an anti-cheat or identity service.",
            full: "G-Lock filters IPv4 UDP P2P traffic on GTA's port 6672. It does not inject code, read game memory, identify a player by nickname, or inspect every connection made by Windows.",
            warning: "Connection logs and data.json can contain public IP addresses. Review them before sharing."
          },
          {
            id: "troubleshooting",
            title: "🧭 Why a friend cannot join",
            short: "Open the session before admitting a friend or changing lobby.",
            full: "Locked rejects unknown new peers. Open the session before the friend joins, wait for the connection to establish, and lock it again afterward.",
            points: [
              "Unlock before changing lobby or admitting a new peer.",
              "Check the red log row and its reason.",
              "Check Advanced blocked IP rules if the same address is repeatedly rejected."
            ]
          },
          {
            id: "hotkeys",
            title: "🔑 Global Hotkeys",
            short: "Keys to control G-Lock without tab-switching out of GTA.",
            full: "F9 toggles Open/Locked. Ctrl+F9 performs a panic unlock into Open. Ctrl+/Ctrl- changes UI zoom and Ctrl+0 resets it."
          }
        ]
      : [
          {
            id: "connection-path",
            title: "🔗 Как появляется подключение игрока",
            short: "Сигнализация Rockstar обычно появляется раньше прямого peer IP.",
            full: "Сначала G-Lock видит трафик, который организует соединение, поэтому в журнале может появиться relay-адрес Rockstar/Azure. Удалённый peer IP становится виден только после начала прямого GTA P2P-трафика.",
            points: [
              "Relay IP — служебная точка, а не идентификатор игрока.",
              "Один внешний IP может использоваться несколькими устройствами или игроками через NAT/CGNAT.",
              "G-Lock не умеет сопоставлять IP с ником GTA."
            ]
          },
          {
            id: "session-lock",
            title: "🔒 Открыто и заперто",
            short: "У G-Lock одно управление сессией: разрешать или отклонять новые peer-подключения.",
            full: "Открыто разрешает новых peer. Заперто сохраняет участников, уже обнаруженных во время текущего запуска, и отклоняет неизвестных новых. Открытие сессии не выключает G-Lock: IPS и ручные правила блокировки IP продолжают работать.",
            points: [
              "Перед поиском другого населённого лобби откройте сессию и заприте снова после загрузки.",
              "Используйте кнопку в карточке статуса или клавишу F9.",
              "Ctrl+F9 выполняет экстренное открытие сессии."
            ]
          },
          {
            id: "unsupported-modes",
            title: "🧪 Почему нет режимов Solo и Whitelist",
            short: "Rockstar раскрывает полезный peer IP слишком поздно для надёжной фильтрации до входа.",
            full: "Входящий игрок сначала общается через инфраструктуру Rockstar, а прямой peer IP появляется только позже. Эвристики по размеру пакета не позволяют надёжно отличить весь служебный трафик от подключения игрока, поэтому Solo и Whitelist убраны из поддерживаемого интерфейса, а не выдаются за гарантированную защиту."
          },
          {
            id: "blocked-ips",
            title: "🚫 Дополнительные правила блокировки IP",
            short: "Проверенное правило IPv4/CIDR отбрасывает трафик после появления реального peer IP.",
            full: "Заблокированные IP управляются в разделе «Настройки → Дополнительно». Правило действует в обоих направлениях раньше heartbeat и кэша известных peer, но относится к сетевому адресу, а не к личности или нику GTA.",
            points: [
              "Правило не гарантирует предотвращение первоначального входа через Rockstar.",
              "Домашний внешний IP может измениться, и сохранённое правило устареет.",
              "Из-за NAT/CGNAT один публичный IP могут использовать несколько игроков."
            ],
            warning: "Добавляйте только адреса, которые проверили независимо."
          },
          {
            id: "ips",
            title: "🛡️ От чего реально защищает IPS",
            short: "Он ограничивает подозрительный P2P-флуд, но не заменяет полноценную DDoS-защиту.",
            full: "IPS измеряет входящий non-service P2P-трафик, выводит порог для каждого IP из стартового фонового замера и временно банит адрес при превышении. Отдельный глобальный предел замечает суммарный поток с множества меняющихся IP. LAN и relay-адреса Rockstar/Azure исключены из подсчёта подозрительной частоты.",
            warning: "IPS охватывает трафик, который перехватывает G-Lock, и не может защитить весь интернет-канал от любой объёмной атаки."
          },
          {
            id: "logs",
            title: "📊 Интерактивный лог активности",
            short: "Журнал показывает решения по пакетам, а не подтверждённый список игроков.",
            full: "ALLOW или BLOCK относится к перехваченному пакету. Синий означает relay, зелёный — разрешённый peer-пакет, красный — заблокированный. Клик по IP копирует адрес; намеренно опасных кнопок мгновенной блокировки в журнале нет.",
            points: [
              "Known Allowed — peer был изучен до запирания сессии.",
              "Flood Protection — превышен временный лимит IPS."
            ]
          },
          {
            id: "limits",
            title: "⚠️ Границы работы и приватность",
            short: "G-Lock — пакетный фильтр, а не античит и не сервис идентификации.",
            full: "G-Lock фильтрует IPv4 UDP P2P-трафик на порту GTA 6672. Он не внедряет код, не читает память игры, не определяет игрока по нику и не анализирует вообще все соединения Windows.",
            warning: "В логах соединений и data.json могут находиться внешние IP. Проверяйте файлы перед публикацией."
          },
          {
            id: "troubleshooting",
            title: "🧭 Почему друг не может подключиться",
            short: "Откройте сессию перед подключением друга или сменой лобби.",
            full: "Состояние «Заперто» отклоняет неизвестных новых peer. Откройте сессию перед входом друга, дождитесь установки соединения и после этого заприте её снова.",
            points: [
              "Откройте сессию перед сменой лобби или допуском нового peer.",
              "Посмотрите красную строку журнала и указанную причину.",
              "Проверьте дополнительные заблокированные IP, если один адрес постоянно отклоняется."
            ]
          },
          {
            id: "hotkeys",
            title: "🔑 Глобальные горячие клавиши",
            short: "Управление фаерволом без переключения из игры.",
            full: "F9 переключает Open/Locked. Ctrl+F9 выполняет экстренное открытие сессии. Ctrl + / Ctrl - меняют масштаб интерфейса, Ctrl + 0 сбрасывает его."
          }
        ]
  );

  async function fetchStatus() {
    try {
      status = await invoke("get_status");
    } catch (error) {
      console.error("Failed to load firewall status", error);
    }
  }

  async function fetchLists() {
    try {
      lists = await invoke("get_lists");
    } catch (error) {
      console.error("Failed to load protection lists", error);
    }
  }

  async function fetchSettings() {
    try {
      const loaded = await invoke<Settings>("get_settings");
      settings = loaded;
      soundVolume = loaded.sound_lock_vol;
      if (!localStorage.getItem("g_lock_zoom")) {
        zoomFactor = loaded.zoom_factor;
      }
    } catch (error) {
      console.error("Failed to load settings", error);
    }
  }

  let zoomFactor = $state(1.0);
  let mounted = $state(false);

  // Sound manager state
  let soundVolume = $state(80);
  let lockSoundType = $state("beep" as "beep" | "custom");
  let unlockSoundType = $state("beep" as "beep" | "custom");
  let lockSoundCustom = $state("");
  let unlockSoundCustom = $state("");

  // Logs list state
  let logFilesList = $state([] as string[]);
  let selectedLogFile = $state(null as string | null);
  let selectedLogEntries = $state([] as any[]);

  $effect(() => {
    if (activeTab === "logs") {
      fetchLogFilesList();
    }
  });

  async function fetchLogFilesList() {
    try {
      logFilesList = await invoke("list_log_files");
    } catch (e) {
      console.error(e);
    }
  }

  async function handleSelectLogFile(file: string) {
    selectedLogFile = file;
    try {
      selectedLogEntries = await invoke("read_log_file", { filename: file });
    } catch (e) {
      console.error(e);
      selectedLogEntries = [];
    }
  }

  async function handleOpenInNotepad() {
    if (!selectedLogFile) return;
    try {
      await invoke("open_log_file_in_notepad", { filename: selectedLogFile });
    } catch (e) {
      alert(e);
    }
  }

  // Auto-sync sound settings to localStorage
  $effect(() => {
    if (!mounted) return;
    localStorage.setItem("g_lock_sound_vol", soundVolume.toString());
  });
  $effect(() => {
    if (!mounted) return;
    localStorage.setItem("g_lock_sound_lock_type", lockSoundType);
  });
  $effect(() => {
    if (!mounted) return;
    localStorage.setItem("g_lock_sound_unlock_type", unlockSoundType);
  });
  $effect(() => {
    if (!mounted) return;
    if (lockSoundCustom) {
      localStorage.setItem("g_lock_sound_lock_custom", lockSoundCustom);
    } else {
      localStorage.removeItem("g_lock_sound_lock_custom");
    }
  });
  $effect(() => {
    if (!mounted) return;
    if (unlockSoundCustom) {
      localStorage.setItem("g_lock_sound_unlock_custom", unlockSoundCustom);
    } else {
      localStorage.removeItem("g_lock_sound_unlock_custom");
    }
  });

  function playSynthBeep(freq: number, duration: number, vol: number) {
    try {
      const ctx = new (window.AudioContext || (window as any).webkitAudioContext)();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      
      osc.type = "sine";
      osc.frequency.setValueAtTime(freq, ctx.currentTime);
      
      gain.gain.setValueAtTime(vol / 100, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.00001, ctx.currentTime + duration / 1000);
      
      osc.connect(gain);
      gain.connect(ctx.destination);
      
      osc.start();
      osc.stop(ctx.currentTime + duration / 1000);
      osc.onended = () => ctx.close();
    } catch (e) {
      console.error("AudioContext error: ", e);
    }
  }

  function playCustomSound(base64Data: string, vol: number) {
    try {
      const audio = new Audio(base64Data);
      audio.volume = vol / 100;
      audio.play().catch((error) => console.error("Audio playback error: ", error));
    } catch (e) {
      console.error("Audio playback error: ", e);
    }
  }

  function triggerAudioAlert(type: "lock" | "unlock" | "ips") {
    if (!settings.sound_enabled) return;
    
    if (type === "lock" || type === "ips") {
      if (lockSoundType === "custom" && lockSoundCustom) {
        playCustomSound(lockSoundCustom, soundVolume);
      } else {
        playSynthBeep(settings.sound_lock_freq, settings.sound_lock_dur, soundVolume);
      }
    } else if (type === "unlock") {
      if (unlockSoundType === "custom" && unlockSoundCustom) {
        playCustomSound(unlockSoundCustom, soundVolume);
      } else {
        playSynthBeep(settings.sound_unlock_freq, settings.sound_unlock_dur, soundVolume);
      }
    }
  }

  function handleSoundUpload(e: Event, type: "lock" | "unlock") {
    const input = e.target as HTMLInputElement;
    if (!input.files || input.files.length === 0) return;
    
    const file = input.files[0];
    if (file.size > 1024 * 1024) {
      alert(activeLang.err_sound_size);
      input.value = "";
      return;
    }
    
    const reader = new FileReader();
    reader.onload = () => {
      const base64 = reader.result as string;
      if (type === "lock") {
        lockSoundCustom = base64;
      } else {
        unlockSoundCustom = base64;
      }
    };
    reader.readAsDataURL(file);
  }



  onMount(() => {
    // Load sound settings
    soundVolume = parseInt(localStorage.getItem("g_lock_sound_vol") || "80");
    lockSoundType = (localStorage.getItem("g_lock_sound_lock_type") as any) || "beep";
    unlockSoundType = (localStorage.getItem("g_lock_sound_unlock_type") as any) || "beep";
    lockSoundCustom = localStorage.getItem("g_lock_sound_lock_custom") || "";
    unlockSoundCustom = localStorage.getItem("g_lock_sound_unlock_custom") || "";

    // Load zoom level
    const savedZoom = localStorage.getItem("g_lock_zoom");
    if (savedZoom) {
      zoomFactor = parseFloat(savedZoom);
    }

    mounted = true;

    fetchStatus();
    fetchLists();
    fetchSettings();

    // Zoom keys listener (Ctrl + / Ctrl - / Ctrl 0)
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.ctrlKey) {
        if (e.key === "=" || e.key === "+") {
          e.preventDefault();
          zoomFactor = Math.min(zoomFactor + 0.1, 2.0);
          localStorage.setItem("g_lock_zoom", zoomFactor.toString());
        } else if (e.key === "-") {
          e.preventDefault();
          zoomFactor = Math.max(zoomFactor - 0.1, 0.5);
          localStorage.setItem("g_lock_zoom", zoomFactor.toString());
        } else if (e.key === "0") {
          e.preventDefault();
          zoomFactor = 1.0;
          localStorage.setItem("g_lock_zoom", zoomFactor.toString());
        }
      }
    };
    window.addEventListener("keydown", handleKeyDown);

    // Listen to Tauri events
    const statusUnsub = listen("status-changed", () => {
      fetchStatus();
    });

    const listsUnsub = listen("lists-changed", () => {
      fetchLists();
    });

    const logUnsub = listen("connection-log", (event) => {
      const payload = event.payload as any;
      if (payload.action === "BLOCK") {
        blockedThreatsCount += 1;
      }
      logs = [payload, ...logs.slice(0, 99)];
    });

    const playSoundUnsub = listen("play-sound", (event) => {
      const payload = event.payload as "lock" | "unlock" | "ips";
      triggerAudioAlert(payload);
    });

    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      statusUnsub.then(fn => fn());
      listsUnsub.then(fn => fn());
      logUnsub.then(fn => fn());
      playSoundUnsub.then(fn => fn());
    };
  });

  async function handleToggleLock() {
    status = await invoke("toggle_lock");
  }

  async function handleDeleteFromList(ip: string) {
    lists = await invoke("delete_from_list", { listType: "blacklist", ip });
  }

  async function handleClearList() {
    if (confirm(activeLang.btn_clear + "?")) {
      lists = await invoke("clear_list", { listType: "blacklist" });
    }
  }

  function openAddDrawer() {
    drawerIpInput = "";
    drawerError = "";
    showDrawer = true;
  }

  async function submitDrawer() {
    if (!drawerIpInput.trim()) return;
    try {
      lists = await invoke("add_to_list", { listType: "blacklist", ip: drawerIpInput.trim() });
      showDrawer = false;
    } catch (e: any) {
      drawerError = e.toString();
    }
  }

  async function handleSaveSettings() {
    try {
      settings.sound_lock_vol = soundVolume;
      settings.sound_unlock_vol = soundVolume;
      settings.zoom_factor = zoomFactor;
      await invoke("save_settings", { config: settings });
      saveStatusMsg = activeLang.settings_saved;
      setTimeout(() => { saveStatusMsg = ""; }, 3000);
    } catch (e: any) {
      alert(e);
    }
  }

  function copyIpToClipboard(ip: string) {
    navigator.clipboard.writeText(ip);
  }
</script>

<div class="app-layout" style="transform: scale({zoomFactor}); width: {100 / zoomFactor}vw; height: {100 / zoomFactor}vh; transform-origin: top left; position: absolute; top: 0; left: 0;">
  <!-- Left Sidebar Navigation -->
  <aside class="sidebar">
    <div class="logo-container">
      <img src="/logo.png" class="logo-img" alt="logo" />
      <h2>G-Lock <span class="ver">v2.0.44</span></h2>
    </div>

    <nav class="nav-links">
      <button class="nav-btn" class:active={activeTab === "dashboard"} onclick={() => activeTab = "dashboard"}>
        <span class="icon">📊</span> {activeLang.nav_dash}
      </button>
      <button class="nav-btn" class:active={activeTab === "settings"} onclick={() => activeTab = "settings"}>
        <span class="icon">⚙️</span> {activeLang.nav_settings}
      </button>
      <button class="nav-btn" class:active={activeTab === "logs"} onclick={() => activeTab = "logs"}>
        <span class="icon">📁</span> {activeLang.nav_logs}
      </button>
      <button class="nav-btn" class:active={activeTab === "help"} onclick={() => activeTab = "help"}>
        <span class="icon">💬</span> {activeLang.nav_help}
      </button>
      <button class="nav-btn" class:active={activeTab === "donate"} onclick={() => activeTab = "donate"}>
        <span class="icon">🎁</span> {activeLang.nav_donate}
      </button>
    </nav>

    <div class="footer-links">
      <div class="lang-selector-sidebar">
        <button class="lang-pill" class:active={settings.language === "ru"} onclick={async () => { settings.language = "ru"; await handleSaveSettings(); }}>RU</button>
        <button class="lang-pill" class:active={settings.language === "en"} onclick={async () => { settings.language = "en"; await handleSaveSettings(); }}>EN</button>
      </div>
    </div>
  </aside>

  <!-- Main Content Space -->
  <main class="content-viewport">
    <!-- Sliding Side Drawer (No Popups!) -->
    {#if showDrawer}
      <button type="button" class="drawer-overlay" aria-label={activeLang.btn_cancel} onclick={() => showDrawer = false}></button>
      <div class="drawer">
        <h3>{activeLang.drawer_title}</h3>
        <div class="form-group">
          <input
            type="text"
            placeholder={activeLang.drawer_placeholder}
            bind:value={drawerIpInput}
            onkeydown={(e) => e.key === "Enter" && submitDrawer()}
          />
          {#if drawerError}
            <span class="error-msg">{drawerError}</span>
          {/if}
        </div>
        <div class="drawer-actions">
          <button class="btn btn-save" onclick={submitDrawer}>{activeLang.btn_save}</button>
          <button class="btn btn-cancel" onclick={() => showDrawer = false}>{activeLang.btn_cancel}</button>
        </div>
      </div>
    {/if}

    <!-- Tab 1: Dashboard -->
    {#if activeTab === "dashboard"}
      <div class="tab-panel">
        <header class="panel-header">
          <h1>{activeLang.nav_dash}</h1>
        </header>

        <section class="dashboard-grid">
          <!-- Big Status Glowing Card -->
          <div
            class="status-card"
            class:locked={status.is_locked}
            class:error={!!status.driver_error}
          >
            <div class="glow-layer"></div>
            <div class="card-inner">
              <span class="status-label">STATUS</span>
              <h2 class="status-text">
                {#if status.driver_error}
                  {activeLang.status_error}
                {:else if status.is_locked}
                  {activeLang.status_locked}
                {:else}
                  {activeLang.status_open}
                {/if}
              </h2>
              {#if !status.driver_error}
                <p class="status-description">{currentStatusDescription}</p>
              {/if}
              <span class="status-tip">
                {#if status.driver_error}
                  {activeLang.err_driver_fail} {status.driver_error}
                {:else}
                  {activeLang.status_tip}
                {/if}
              </span>

              {#if !status.driver_error}
                <button type="button" class="status-toggle-btn" class:unlock={status.is_locked} onclick={handleToggleLock}>
                  {status.is_locked ? `🔓 ${activeLang.stop_session}` : `🔒 ${activeLang.lock_session}`}
                </button>
              {/if}
              
              <div class="threats-banner">
                <span>
                  {activeLang.blocked_threats_msg.replace("{n}", blockedThreatsCount.toString())}
                  <button type="button" class="support-inline-link" onclick={(event) => { event.stopPropagation(); activeTab = "donate"; }}>
                    {activeLang.support_link}
                  </button>
                </span>
              </div>
            </div>
          </div>

        </section>

        <!-- Live Network Activity Log -->
        <section class="logs-panel">
          <h3>{activeLang.live_activity}</h3>
          <div class="guidance-strip compact-guidance">
            <span class="guidance-icon">ℹ️</span>
            <p>{activeLang.live_activity_note}</p>
          </div>
          <div class="log-legend" aria-label={activeLang.live_activity}>
            <span class="legend-item allowed">{activeLang.legend_allowed}</span>
            <span class="legend-item relay">{activeLang.legend_relay}</span>
            <span class="legend-item blocked">{activeLang.legend_blocked}</span>
          </div>
          <div class="table-container">
            <table class="logs-table">
              <thead>
                <tr>
                  <th style="width: 90px;">{activeLang.col_time}</th>
                  <th style="width: 80px;">{activeLang.col_action}</th>
                  <th style="width: 140px;">{activeLang.col_ip}</th>
                  <th>{activeLang.col_detail}</th>
                </tr>
              </thead>
              <tbody>
                {#each logs as log}
                  {@const isRelay = log.reason.toLowerCase().includes("relay") || log.reason.toLowerCase().includes("tunnel")}
                  <tr class="log-row" class:relay-row={isRelay} class:blocked-row={log.action === "BLOCK"}>
                    <td>{log.timestamp.split(" ")[1] || log.timestamp}</td>
                    <td class="act-col">{log.action}</td>
                    <td class="ip-col" onclick={() => copyIpToClipboard(log.ip)} title={activeLang.copy_title}>
                      {log.ip} {isRelay ? "[RELAY R*]" : ""}
                    </td>
                    <td>{log.reason} (Size: {log.size})</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    {/if}

    <!-- Tab 2: Settings -->
    {#if activeTab === "settings"}
      <div class="tab-panel">
        <header class="panel-header">
          <h1>{activeLang.nav_settings}</h1>
        </header>

        <section class="settings-form">
          <!-- Advanced Audio Alert Configuration -->
          <div class="settings-section">
            <h3>🔊 {activeLang.settings_sound_title}</h3>
            
            <div class="setting-item">
              <label class="switch-container">
                <input type="checkbox" bind:checked={settings.sound_enabled} />
                <span class="slider"></span>
                <span class="label-text">{activeLang.settings_sound}</span>
              </label>
            </div>

            {#if settings.sound_enabled}
              <div class="setting-item">
                <div class="slider-header">
                  <span>{activeLang.settings_sound_vol}</span>
                  <span class="slider-value">{soundVolume}%</span>
                </div>
                <input type="range" min="0" max="100" bind:value={soundVolume} />
              </div>

              <div class="setting-item sound-picker">
                <span class="sound-picker-title">{activeLang.settings_sound_lock}</span>
                <div class="sound-mode-toggle">
                  <button type="button" class="toggle-pill" class:active={lockSoundType === "beep"} onclick={() => lockSoundType = "beep"}>{activeLang.sound_type_beep}</button>
                  <button type="button" class="toggle-pill" class:active={lockSoundType === "custom"} onclick={() => lockSoundType = "custom"}>{activeLang.sound_type_custom}</button>
                </div>
                {#if lockSoundType === "custom"}
                  <div class="file-upload-row">
                    <label class="file-upload-btn">
                      <input type="file" accept="audio/*" onchange={(e) => handleSoundUpload(e, "lock")} style="display: none;" />
                      <span>{lockSoundCustom ? activeLang.sound_file_loaded : activeLang.sound_file_empty}</span>
                    </label>
                    {#if lockSoundCustom}
                      <div class="sound-btn-group">
                        <button type="button" class="btn-action" onclick={() => playCustomSound(lockSoundCustom, soundVolume)}>{activeLang.btn_test_sound}</button>
                        <button type="button" class="btn-action reset" onclick={() => { lockSoundCustom = ""; lockSoundType = "beep"; }}>{activeLang.btn_reset_sound}</button>
                      </div>
                    {/if}
                  </div>
                {:else}
                  <div class="file-upload-row">
                    <button type="button" class="btn-action" onclick={() => playSynthBeep(settings.sound_lock_freq, settings.sound_lock_dur, soundVolume)}>{activeLang.btn_test_sound}</button>
                  </div>
                {/if}
              </div>

              <div class="setting-item sound-picker">
                <span class="sound-picker-title">{activeLang.settings_sound_unlock}</span>
                <div class="sound-mode-toggle">
                  <button type="button" class="toggle-pill" class:active={unlockSoundType === "beep"} onclick={() => unlockSoundType = "beep"}>{activeLang.sound_type_beep}</button>
                  <button type="button" class="toggle-pill" class:active={unlockSoundType === "custom"} onclick={() => unlockSoundType = "custom"}>{activeLang.sound_type_custom}</button>
                </div>
                {#if unlockSoundType === "custom"}
                  <div class="file-upload-row">
                    <label class="file-upload-btn">
                      <input type="file" accept="audio/*" onchange={(e) => handleSoundUpload(e, "unlock")} style="display: none;" />
                      <span>{unlockSoundCustom ? activeLang.sound_file_loaded : activeLang.sound_file_empty}</span>
                    </label>
                    {#if unlockSoundCustom}
                      <div class="sound-btn-group">
                        <button type="button" class="btn-action" onclick={() => playCustomSound(unlockSoundCustom, soundVolume)}>{activeLang.btn_test_sound}</button>
                        <button type="button" class="btn-action reset" onclick={() => { unlockSoundCustom = ""; unlockSoundType = "beep"; }}>{activeLang.btn_reset_sound}</button>
                      </div>
                    {/if}
                  </div>
                {:else}
                  <div class="file-upload-row">
                    <button type="button" class="btn-action" onclick={() => playSynthBeep(settings.sound_unlock_freq, settings.sound_unlock_dur, soundVolume)}>{activeLang.btn_test_sound}</button>
                  </div>
                {/if}
              </div>
            {/if}
          </div>

          <!-- IPS Configurations -->
          <div class="settings-section">
            <h3>🔒 {activeLang.settings_ips}</h3>
            <p class="section-description">{activeLang.settings_ips_description}</p>

            <div class="setting-item">
              <label class="switch-container">
                <input type="checkbox" bind:checked={settings.ips_enabled} />
                <span class="slider"></span>
                <span class="label-text">{activeLang.settings_enable_ips}</span>
              </label>
            </div>

            {#if settings.ips_enabled}
              <div class="setting-item">
                <div class="slider-header">
                  <span>{activeLang.settings_multiplier}</span>
                  <span class="slider-value">{settings.ips_adaptive_multiplier}x</span>
                </div>
                <input type="range" min="2" max="15" bind:value={settings.ips_adaptive_multiplier} />
                <p class="setting-help">{activeLang.settings_multiplier_hint}</p>
              </div>

              <div class="setting-item">
                <div class="slider-header">
                  <span>{activeLang.settings_measurement}</span>
                  <span class="slider-value">{settings.ips_adaptive_measurement_seconds} s</span>
                </div>
                <input type="range" min="15" max="120" bind:value={settings.ips_adaptive_measurement_seconds} />
                <p class="setting-help">{activeLang.settings_measurement_hint}</p>
              </div>

              <div class="setting-item">
                <div class="slider-header">
                  <span>{activeLang.settings_fallback}</span>
                  <span class="slider-value">{settings.ips_fallback_threshold} PPS</span>
                </div>
                <input type="range" min="50" max="500" step="10" bind:value={settings.ips_fallback_threshold} />
                <p class="setting-help">{activeLang.settings_fallback_hint}</p>
              </div>

              <div class="setting-item">
                <div class="slider-header">
                  <span>{activeLang.settings_global_ceiling}</span>
                  <span class="slider-value">{settings.ips_global_pps_ceiling} PPS</span>
                </div>
                <input type="range" min="500" max="10000" step="100" bind:value={settings.ips_global_pps_ceiling} />
                <p class="setting-help">{activeLang.settings_global_hint}</p>
              </div>

              <div class="setting-item">
                <label class="switch-container">
                  <input type="checkbox" bind:checked={settings.auto_lock_on_attack} />
                  <span class="slider"></span>
                  <span class="label-text">{activeLang.settings_autolock}</span>
                </label>
                <p class="setting-help switch-help">{activeLang.settings_autolock_hint}</p>
              </div>
            {/if}
          </div>

          <div class="settings-section advanced-blocklist">
            <div class="pane-header">
              <h3>🚫 {activeLang.blocked_ips_title}</h3>
              <button class="add-ip-btn" title={activeLang.btn_add_ip} aria-label={activeLang.btn_add_ip} onclick={openAddDrawer}>+</button>
            </div>
            <p class="section-description">{activeLang.blocked_ips_description}</p>
            <p class="blocklist-warning">⚠️ {activeLang.blocked_ips_warning}</p>
            <div class="list-box settings-list-box">
              {#if lists.blacklist.length === 0}
                <div class="empty-state compact-empty">{activeLang.blocked_ips_empty}</div>
              {:else}
                {#each lists.blacklist as ip}
                  <div class="list-item">
                    <span class="ip-val">{ip}</span>
                    <button class="del-btn" aria-label={`${activeLang.btn_delete}: ${ip}`} onclick={() => handleDeleteFromList(ip)}>✕</button>
                  </div>
                {/each}
              {/if}
            </div>
            {#if lists.blacklist.length > 0}
              <button class="clear-btn" onclick={handleClearList}>🧹 {activeLang.btn_clear}</button>
            {/if}
          </div>

          <!-- Save Button -->
          <div class="settings-actions">
            <button class="save-settings-btn" onclick={handleSaveSettings}>💾 {activeLang.settings_save}</button>
            {#if saveStatusMsg}
              <span class="save-status">{saveStatusMsg}</span>
            {/if}
          </div>
        </section>
      </div>
    {/if}

    <!-- Tab 3.5: Logs -->
    {#if activeTab === "logs"}
      <div class="tab-panel">
        <header class="panel-header">
          <h1>{activeLang.logs_title}</h1>
        </header>

        <div class="guidance-strip logs-guidance">
          <span class="guidance-icon">ℹ️</span>
          <p>{activeLang.live_activity_note}</p>
        </div>

        <section class="logs-layout-grid">
          <!-- Left side: list of log files -->
          <div class="logs-sidebar-card glass-panel">
            <h3>{activeLang.logs_file_list_title}</h3>
            {#if logFilesList.length === 0}
              <div class="empty-state">{activeLang.logs_empty}</div>
            {:else}
              <div class="log-files-list">
                {#each logFilesList as file}
                  <button 
                    type="button" 
                    class="log-file-item" 
                    class:selected={selectedLogFile === file}
                    onclick={() => handleSelectLogFile(file)}
                  >
                    <span>📄 {file}</span>
                  </button>
                {/each}
              </div>
            {/if}
          </div>

          <!-- Right side: details and content of the selected log file -->
          <div class="logs-content-card glass-panel">
            {#if selectedLogFile}
              <div class="log-content-header">
                <h3>{activeLang.logs_view_title} {selectedLogFile}</h3>
                <button type="button" class="btn-primary" onclick={handleOpenInNotepad}>
                  {activeLang.btn_open_in_notepad}
                </button>
              </div>
              <div class="log-content-table-wrapper">
                {#if selectedLogEntries.length === 0}
                  <div class="empty-state">{activeLang.log_file_empty}</div>
                {:else}
                  <table class="log-table">
                    <thead>
                      <tr>
                        <th>{activeLang.col_time}</th>
                        <th>{activeLang.col_action}</th>
                        <th>{activeLang.col_ip}</th>
                        <th>{activeLang.col_detail}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {#each selectedLogEntries as entry}
                        <tr class={entry.action === "BLOCK" ? "log-block" : "log-allow"}>
                          <td class="time-col">{entry.timestamp}</td>
                          <td class="action-col">
                            <span class="action-badge" class:block={entry.action === "BLOCK"}>
                              {entry.action}
                            </span>
                          </td>
                          <td class="ip-col">{entry.ip}</td>
                          <td class="reason-col">{entry.reason} (Size: {entry.size})</td>
                        </tr>
                      {/each}
                    </tbody>
                  </table>
                {/if}
              </div>
            {:else}
              <div class="select-prompt">
                <span class="prompt-icon">📁</span>
                <p>{activeLang.log_select_hint}</p>
              </div>
            {/if}
          </div>
        </section>
      </div>
    {/if}

    <!-- Tab 4: Help -->
    {#if activeTab === "help"}
      <div class="tab-panel">
        <header class="panel-header">
          <h1>{activeLang.nav_help}</h1>
        </header>

        <section class="help-content">
          <div class="info-card">
            <h3>ℹ️ {settings.language === "en" ? "About G-Lock" : "О проекте G-Lock"}</h3>
            <p>
              {settings.language === "en"
                ? "G-Lock is a local IPv4/UDP packet filter for controlling GTA Online P2P sessions through WinDivert. It does not read game memory or identify players by nickname, and its IPS is an additional flood-control layer rather than universal DDoS protection."
                : "G-Lock — локальный фильтр IPv4/UDP-пакетов для управления P2P-сессией GTA Online через WinDivert. Он не читает память игры, не определяет игроков по нику, а его IPS является дополнительной защитой от флуда, но не универсальной DDoS-защитой."}
            </p>
            <p class="guardian-credit">{activeLang.guardian_credit}</p>
            <p class="guardian-links">
              <a href="https://gitlab.com/digitalarc/guardian" target="_blank" rel="noopener noreferrer">Guardian source</a>
              <span>·</span>
              <a href="https://gitlab.com/Speyedr/guardian-fastload-fix" target="_blank" rel="noopener noreferrer">Original source</a>
              <span>•</span>
              <a href="https://github.com/basil00/WinDivert" target="_blank" rel="noopener noreferrer">WinDivert source</a>
              <span>•</span>
              <a href="https://github.com/Rubensei/windivert-rust" target="_blank" rel="noopener noreferrer">Rust crate source</a>
              <span>·</span>
              <span>GNU LGPL v3</span>
            </p>
          </div>

          <!-- FAQ Accordion -->
          <div class="faq-accordion">
            {#each helpArticles as article}
              <div class="accordion-item" class:expanded={expandedHelpId === article.id}>
                <button type="button" class="accordion-header" onclick={() => toggleHelpAccordion(article.id)}>
                  <h3>{article.title}</h3>
                  <span class="accordion-icon">{expandedHelpId === article.id ? "▼" : "▶"}</span>
                </button>
                {#if expandedHelpId === article.id}
                  <div class="accordion-content">
                    <p class="accordion-short"><strong>{settings.language === "en" ? "Summary" : "Коротко"}:</strong> {article.short}</p>
                    <p class="accordion-full">{article.full}</p>
                    {#if article.points}
                      <ul class="accordion-points">
                        {#each article.points as point}
                          <li>{point}</li>
                        {/each}
                      </ul>
                    {/if}
                    {#if article.warning}
                      <p class="accordion-warning">⚠️ {article.warning}</p>
                    {/if}
                  </div>
                {/if}
              </div>
            {/each}
          </div>
        </section>
      </div>
    {/if}

    <!-- Tab 5: Donate -->
    {#if activeTab === "donate"}
      <div class="tab-panel">
        <header class="panel-header">
          <h1>{activeLang.nav_donate}</h1>
        </header>

        <section class="donate-content">
          <div class="info-card donate-card text-center">
            <span class="donate-emoji">🎁</span>
            <h2>{activeLang.donate_title}</h2>
            <div class="donate-text-paragraphs">
              <p class="desc">{activeLang.donate_p1}</p>
              <p class="desc">{activeLang.donate_p2}</p>
              <p class="desc">{activeLang.donate_p3}</p>
              <p class="desc">{activeLang.donate_p4}</p>
            </div>
            <a href="https://www.donationalerts.com/r/typuct_donate" target="_blank" rel="noopener noreferrer" class="donate-btn-large">
              {activeLang.btn_donate_da}
            </a>
          </div>
        </section>
      </div>
    {/if}
  </main>
</div>

<style>
  :root {
    --bg-main: #0c0f16;
    --bg-sidebar: #111622;
    --bg-card: #161f32;
    --border-glow: rgba(57, 242, 236, 0.2);
    --border-glow-active: rgba(57, 242, 236, 0.6);
    --accent-cyan: #39f2ec;
    --accent-magenta: #ff3df0;
    --accent-yellow: #f1c40f;
    --accent-green: #2ecc71;
    --accent-red: #e74c3c;
    --text-main: #e0e6f0;
    --text-dim: #8b9bb4;
    --font-stack: 'Outfit', 'Inter', -apple-system, sans-serif;
  }

  :global(body) {
    margin: 0;
    padding: 0;
    background-color: var(--bg-main);
    color: var(--text-main);
    font-family: var(--font-stack);
    overflow: hidden;
  }

  .app-layout {
    display: flex;
    width: 100vw;
    height: 100vh;
    background: radial-gradient(circle at 70% 20%, rgba(22, 31, 50, 0.4) 0%, var(--bg-main) 70%);
  }

  /* Left Sidebar Styling */
  .sidebar {
    width: 250px;
    min-width: 250px;
    flex: 0 0 250px;
    background-color: var(--bg-sidebar);
    border-right: 1px solid rgba(255, 255, 255, 0.05);
    display: flex;
    flex-direction: column;
    padding: 24px;
    box-sizing: border-box;
    overflow-x: hidden;
    overflow-y: auto;
  }

  .logo-container {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 40px;
  }

  .logo-img {
    width: 32px;
    height: 32px;
    object-fit: contain;
  }

  .logo-container h2 {
    margin: 0;
    font-size: 1.25rem;
    font-weight: 700;
    letter-spacing: 0.5px;
  }

  .ver {
    font-size: 0.75rem;
    color: var(--accent-cyan);
    font-weight: 500;
  }

  .nav-links {
    display: flex;
    flex-direction: column;
    gap: 8px;
    flex-grow: 1;
  }

  .nav-btn {
    background: none;
    border: none;
    color: var(--text-dim);
    padding: 12px 16px;
    text-align: left;
    font-size: 0.95rem;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.25s ease;
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .nav-btn:hover {
    color: var(--text-main);
    background-color: rgba(255, 255, 255, 0.02);
  }

  .nav-btn.active {
    color: #fff;
    background: linear-gradient(90deg, rgba(57, 242, 236, 0.15), transparent);
    border-left: 3px solid var(--accent-cyan);
    padding-left: 13px;
  }

  .footer-links {
    margin-top: auto;
  }



  /* Content Panel */
  .content-viewport {
    flex-grow: 1;
    min-width: 0;
    position: relative;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    padding: 32px;
    box-sizing: border-box;
  }

  .tab-panel {
    display: flex;
    flex-direction: column;
    height: 100%;
    animation: fadeIn 0.3s ease;
  }

  .panel-header {
    margin-bottom: 24px;
  }

  .panel-header h1 {
    margin: 0;
    font-size: 1.75rem;
    font-weight: 700;
  }

  /* Dashboard View */
  .dashboard-grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: 24px;
    margin-bottom: 24px;
  }

  .status-card {
    background-color: var(--bg-card);
    border-radius: 12px;
    border: 1px solid rgba(255, 255, 255, 0.05);
    padding: 24px;
    cursor: default;
    position: relative;
    overflow: hidden;
    transition: all 0.3s ease;
  }

  .status-card.locked {
    border-color: rgba(231, 76, 60, 0.3);
  }

  .status-card.locked .glow-layer {
    background: radial-gradient(circle at center, rgba(231, 76, 60, 0.15) 0%, transparent 70%);
  }

  .status-card:not(.locked):not(.error) {
    border-color: rgba(46, 204, 113, 0.3);
  }

  .status-card:not(.locked):not(.error) .glow-layer {
    background: radial-gradient(circle at center, rgba(46, 204, 113, 0.15) 0%, transparent 70%);
  }

  .status-card.error {
    border-color: rgba(231, 76, 60, 0.6);
    cursor: not-allowed;
  }

  .status-card.error .glow-layer {
    background: radial-gradient(circle at center, rgba(231, 76, 60, 0.25) 0%, transparent 70%);
  }

  .glow-layer {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    pointer-events: none;
    transition: all 0.3s ease;
  }

  .card-inner {
    position: relative;
    z-index: 2;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .status-label {
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 1px;
    color: var(--text-dim);
  }

  .status-text {
    margin: 0;
    font-size: 1.8rem;
    font-weight: 800;
  }

  .status-description {
    margin: 2px 0 0;
    max-width: 620px;
    color: var(--text-main);
    font-size: 0.9rem;
    line-height: 1.45;
  }

  .status-tip {
    font-size: 0.8rem;
    color: var(--text-dim);
    margin-top: 8px;
  }

  .status-toggle-btn {
    align-self: flex-start;
    margin-top: 8px;
    padding: 10px 18px;
    border: 1px solid rgba(231, 76, 60, 0.45);
    border-radius: 8px;
    background: rgba(231, 76, 60, 0.1);
    color: var(--text-main);
    font-family: var(--font-stack);
    font-weight: 700;
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .status-toggle-btn:hover {
    border-color: var(--accent-red);
    background: rgba(231, 76, 60, 0.18);
  }

  .status-toggle-btn.unlock {
    border-color: rgba(46, 204, 113, 0.45);
    background: rgba(46, 204, 113, 0.1);
  }

  .status-toggle-btn.unlock:hover {
    border-color: var(--accent-green);
    background: rgba(46, 204, 113, 0.18);
  }

  .threats-banner {
    margin-top: 14px;
    padding-top: 12px;
    border-top: 1px dashed rgba(255, 255, 255, 0.08);
    font-size: 0.85rem;
    color: var(--text-dim);
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .support-inline-link {
    background: none;
    border: none;
    padding: 0;
    margin: 0;
    font-size: 0.85rem;
    font-family: var(--font-stack);
    font-weight: 700;
    color: var(--accent-yellow);
    text-decoration: underline;
    cursor: pointer;
    transition: opacity 0.2s;
  }

  .support-inline-link:hover {
    opacity: 0.8;
  }

  /* Logs Panel */
  .logs-panel {
    background-color: var(--bg-card);
    border-radius: 12px;
    border: 1px solid rgba(255, 255, 255, 0.05);
    padding: 24px;
    flex-grow: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .logs-panel h3 {
    margin: 0 0 16px 0;
    font-size: 1.1rem;
    color: var(--text-dim);
  }

  .guidance-strip {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    padding: 12px 14px;
    border: 1px solid rgba(57, 242, 236, 0.15);
    border-radius: 9px;
    background: linear-gradient(135deg, rgba(57, 242, 236, 0.07), rgba(255, 61, 240, 0.025));
    color: var(--text-dim);
    backdrop-filter: blur(12px);
  }

  .guidance-strip p {
    margin: 0;
    font-size: 0.83rem;
    line-height: 1.45;
  }

  .guidance-icon {
    flex: 0 0 auto;
    color: var(--accent-cyan);
  }

  .compact-guidance {
    margin-bottom: 10px;
    padding: 9px 12px;
  }

  .log-legend {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 10px;
  }

  .legend-item {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 3px 8px;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.035);
    color: var(--text-dim);
    font-size: 0.72rem;
  }

  .legend-item::before {
    content: '';
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--accent-green);
  }

  .legend-item.relay::before { background: var(--accent-cyan); }
  .legend-item.blocked::before { background: var(--accent-red); }

  .table-container {
    overflow-y: auto;
    flex-grow: 1;
  }

  .logs-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.9rem;
    text-align: left;
  }

  .logs-table th {
    color: var(--text-dim);
    font-weight: 600;
    padding: 8px 12px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  }

  .logs-table td {
    padding: 8px 12px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.02);
  }

  .log-row {
    transition: background-color 0.2s;
    color: var(--accent-green);
  }

  .log-row:hover {
    background-color: rgba(255, 255, 255, 0.01);
  }

  .log-row.relay-row {
    color: var(--accent-cyan);
  }

  .log-row.blocked-row {
    color: var(--accent-red);
    background-color: rgba(231, 76, 60, 0.02);
  }

  .ip-col {
    cursor: pointer;
    text-decoration: underline dotted;
  }

  .pane-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
  }

  .pane-header h3 {
    margin: 0;
    font-size: 1.1rem;
  }

  .add-ip-btn {
    background: linear-gradient(135deg, var(--accent-cyan), var(--accent-magenta));
    border: none;
    color: #000;
    width: 32px;
    height: 32px;
    border-radius: 50%;
    font-weight: 700;
    font-size: 1.2rem;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: opacity 0.2s;
  }

  .add-ip-btn:hover {
    opacity: 0.9;
  }

  .list-box {
    flex-grow: 1;
    border: 1px solid rgba(255, 255, 255, 0.03);
    border-radius: 8px;
    background-color: rgba(0, 0, 0, 0.1);
    margin-bottom: 16px;
    overflow-y: auto;
    padding: 12px;
  }

  .list-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 12px;
    background-color: rgba(255, 255, 255, 0.02);
    border: 1px solid rgba(255, 255, 255, 0.03);
    border-radius: 6px;
    margin-bottom: 8px;
  }

  .ip-val {
    font-size: 0.95rem;
    font-weight: 500;
  }

  .del-btn {
    background: none;
    border: none;
    color: var(--text-dim);
    cursor: pointer;
    font-size: 0.85rem;
    padding: 2px 6px;
    border-radius: 4px;
    transition: all 0.2s;
  }

  .del-btn:hover {
    color: var(--accent-red);
    background-color: rgba(231, 76, 60, 0.1);
  }

  .clear-btn {
    background-color: rgba(255, 255, 255, 0.02);
    border: 1px solid rgba(255, 255, 255, 0.08);
    color: var(--text-dim);
    padding: 10px;
    border-radius: 8px;
    cursor: pointer;
    font-weight: 500;
    transition: all 0.2s;
  }

  .clear-btn:hover {
    border-color: var(--accent-red);
    color: #fff;
    background-color: rgba(231, 76, 60, 0.05);
  }

  /* Slide-in side drawer drawer */
  .drawer-overlay {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background-color: rgba(0, 0, 0, 0.5);
    backdrop-filter: blur(4px);
    border: 0;
    padding: 0;
    cursor: default;
    z-index: 99;
    animation: fadeIn 0.25s ease;
  }

  .drawer {
    position: absolute;
    top: 0;
    right: 0;
    bottom: 0;
    width: 320px;
    background-color: var(--bg-sidebar);
    border-left: 1px solid rgba(255, 255, 255, 0.08);
    box-shadow: -10px 0 30px rgba(0, 0, 0, 0.5);
    z-index: 100;
    padding: 32px 24px;
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    gap: 24px;
    animation: slideIn 0.25s cubic-bezier(0.16, 1, 0.3, 1);
  }

  .form-group {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .form-group input {
    background-color: rgba(0, 0, 0, 0.2);
    border: 1px solid rgba(255, 255, 255, 0.1);
    padding: 12px;
    border-radius: 8px;
    color: #fff;
    outline: none;
    font-size: 0.95rem;
    transition: border-color 0.2s;
  }

  .form-group input:focus {
    border-color: var(--accent-cyan);
  }

  .error-msg {
    color: var(--accent-red);
    font-size: 0.85rem;
  }

  .drawer-actions {
    display: flex;
    gap: 12px;
  }

  .btn {
    flex-grow: 1;
    padding: 12px;
    border-radius: 8px;
    font-weight: 600;
    cursor: pointer;
    border: none;
    transition: all 0.2s;
  }

  .btn-save {
    background: linear-gradient(135deg, var(--accent-cyan), var(--accent-magenta));
    color: #000;
  }

  .btn-cancel {
    background-color: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.08);
    color: var(--text-main);
  }

  .btn-cancel:hover {
    background-color: rgba(255, 255, 255, 0.06);
  }

  /* Settings Panel */
  .settings-form {
    background-color: var(--bg-card);
    border-radius: 12px;
    border: 1px solid rgba(255, 255, 255, 0.05);
    padding: 24px;
    display: flex;
    flex-direction: column;
    gap: 24px;
    max-width: 760px;
  }

  .settings-section {
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    padding-bottom: 20px;
  }

  .settings-section:last-of-type {
    border-bottom: none;
    padding-bottom: 0;
  }

  .settings-section h3 {
    margin: 0 0 16px 0;
    font-size: 1.05rem;
    color: var(--text-dim);
  }

  .section-description {
    margin: -6px 0 16px;
    color: var(--text-dim);
    font-size: 0.84rem;
    line-height: 1.45;
  }

  .advanced-blocklist .pane-header {
    margin-bottom: 12px;
  }

  .advanced-blocklist .pane-header h3 {
    margin-bottom: 0;
  }

  .blocklist-warning {
    margin: 0 0 14px;
    padding: 10px 12px;
    border: 1px solid rgba(241, 196, 15, 0.2);
    border-radius: 8px;
    background: rgba(241, 196, 15, 0.05);
    color: #d8c684;
    font-size: 0.78rem;
    line-height: 1.45;
  }

  .settings-list-box {
    max-height: 190px;
    min-height: 54px;
  }

  .compact-empty {
    padding: 10px;
  }

  .switch-container {
    display: flex;
    align-items: center;
    gap: 12px;
    cursor: pointer;
  }

  .switch-container input {
    display: none;
  }

  .slider {
    position: relative;
    width: 44px;
    height: 24px;
    background-color: rgba(255, 255, 255, 0.1);
    border-radius: 24px;
    transition: background-color 0.2s;
  }

  .slider::before {
    content: '';
    position: absolute;
    width: 18px;
    height: 18px;
    left: 3px;
    bottom: 3px;
    background-color: #fff;
    border-radius: 50%;
    transition: transform 0.2s;
  }

  .switch-container input:checked + .slider {
    background-color: var(--accent-cyan);
  }

  .switch-container input:checked + .slider::before {
    transform: translateX(20px);
  }

  .label-text {
    font-weight: 500;
    font-size: 0.95rem;
  }

  .setting-item {
    margin-bottom: 16px;
  }

  .setting-item:last-child {
    margin-bottom: 0;
  }

  .slider-header {
    display: flex;
    justify-content: space-between;
    font-size: 0.9rem;
    margin-bottom: 8px;
  }

  .slider-value {
    color: var(--accent-cyan);
    font-weight: 600;
  }

  .setting-item input[type="range"] {
    width: 100%;
    background-color: rgba(255, 255, 255, 0.1);
    accent-color: var(--accent-cyan);
    height: 6px;
    border-radius: 3px;
    outline: none;
  }

  .setting-help {
    margin: 6px 0 0;
    color: var(--text-dim);
    font-size: 0.76rem;
    line-height: 1.4;
  }

  .switch-help {
    margin-left: 56px;
  }

  .lang-selector-sidebar {
    display: flex;
    background-color: rgba(0, 0, 0, 0.2);
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 20px;
    padding: 2px;
    margin-top: 12px;
  }

  .lang-pill {
    flex: 1;
    background: none;
    border: none;
    color: var(--text-dim);
    padding: 6px 12px;
    border-radius: 18px;
    cursor: pointer;
    font-size: 0.8rem;
    font-weight: 700;
    transition: all 0.2s;
    outline: none;
  }

  .lang-pill:hover {
    color: var(--text-main);
  }

  .lang-pill.active {
    background: linear-gradient(135deg, var(--accent-cyan), var(--accent-magenta));
    color: #000;
  }

  .save-settings-btn {
    background: linear-gradient(135deg, var(--accent-cyan), var(--accent-magenta));
    border: none;
    color: #000;
    padding: 12px 24px;
    border-radius: 8px;
    font-weight: 700;
    cursor: pointer;
    transition: opacity 0.2s;
  }

  .save-settings-btn:hover {
    opacity: 0.9;
  }

  .save-status {
    color: var(--accent-green);
    font-weight: 600;
    font-size: 0.9rem;
    margin-left: 12px;
  }

  /* Sound Custom Styles */
  .sound-picker {
    background-color: rgba(0, 0, 0, 0.15);
    border: 1px solid rgba(255, 255, 255, 0.03);
    padding: 16px;
    border-radius: 8px;
    display: flex;
    flex-direction: column;
    gap: 12px;
    margin-top: 12px;
  }

  .sound-picker-title {
    font-weight: 600;
    font-size: 0.9rem;
    color: var(--text-dim);
  }

  .sound-mode-toggle {
    display: flex;
    background-color: rgba(0, 0, 0, 0.2);
    border-radius: 6px;
    padding: 3px;
    gap: 4px;
  }

  .toggle-pill {
    flex: 1;
    background: none;
    border: none;
    color: var(--text-dim);
    padding: 8px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.85rem;
    font-weight: 500;
    transition: all 0.2s;
  }

  .toggle-pill:hover {
    color: var(--text-main);
  }

  .toggle-pill.active {
    background-color: rgba(255, 255, 255, 0.08);
    color: var(--accent-cyan);
    font-weight: 600;
  }

  .file-upload-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    background-color: rgba(0, 0, 0, 0.1);
    padding: 10px 14px;
    border-radius: 6px;
    border: 1px dashed rgba(255, 255, 255, 0.08);
  }

  .file-upload-btn {
    cursor: pointer;
    font-size: 0.85rem;
    color: var(--text-dim);
    display: flex;
    align-items: center;
    gap: 8px;
    flex-grow: 1;
  }

  .file-upload-btn:hover {
    color: var(--accent-cyan);
  }

  .sound-btn-group {
    display: flex;
    gap: 8px;
  }

  .btn-action {
    background-color: rgba(57, 242, 236, 0.1);
    border: 1px solid rgba(57, 242, 236, 0.3);
    color: var(--accent-cyan);
    padding: 6px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.8rem;
    font-weight: 600;
    transition: all 0.2s;
  }

  .btn-action:hover {
    background-color: rgba(57, 242, 236, 0.2);
  }

  .btn-action.reset {
    background-color: rgba(255, 255, 255, 0.03);
    border-color: rgba(255, 255, 255, 0.1);
    color: var(--text-dim);
  }

  .btn-action.reset:hover {
    background-color: rgba(231, 76, 60, 0.1);
    border-color: rgba(231, 76, 60, 0.3);
    color: var(--accent-red);
  }

  /* Help Tab FAQ Accordion */
  .help-content {
    display: flex;
    flex-direction: column;
    gap: 20px;
    width: min(860px, 100%);
  }

  .faq-accordion {
    display: flex;
    flex-direction: column;
    gap: 12px;
    margin-top: 16px;
  }

  .accordion-item {
    background-color: var(--bg-card);
    border: 1px solid rgba(255, 255, 255, 0.04);
    border-radius: 8px;
    overflow: hidden;
    transition: all 0.25s ease;
  }

  .accordion-item.expanded {
    border-color: rgba(57, 242, 236, 0.2);
    box-shadow: 0 0 15px rgba(57, 242, 236, 0.03);
  }

  .accordion-header {
    width: 100%;
    background: none;
    border: none;
    padding: 16px 20px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    cursor: pointer;
    text-align: left;
    outline: none;
  }

  .accordion-header h3 {
    margin: 0;
    font-size: 1rem;
    font-weight: 600;
    color: var(--text-main);
    transition: color 0.2s;
  }

  .accordion-header:hover h3 {
    color: var(--accent-cyan);
  }

  .accordion-icon {
    font-size: 0.8rem;
    color: var(--text-dim);
    transition: transform 0.2s;
  }

  .accordion-content {
    padding: 0 20px 20px 20px;
    font-size: 0.9rem;
    line-height: 1.5;
    animation: fadeIn 0.25s ease;
  }

  .accordion-short {
    margin: 0 0 8px 0;
    color: var(--text-main);
  }

  .accordion-full {
    margin: 0;
    color: var(--text-dim);
  }

  .accordion-points {
    margin: 12px 0 0;
    padding-left: 20px;
    color: var(--text-dim);
  }

  .accordion-points li + li {
    margin-top: 6px;
  }

  .accordion-warning {
    margin: 12px 0 0;
    padding: 10px 12px;
    border-left: 3px solid var(--accent-yellow);
    border-radius: 4px;
    background: rgba(241, 196, 15, 0.06);
    color: #d9c985;
  }

  .info-card {
    background-color: var(--bg-card);
    border-radius: 12px;
    border: 1px solid rgba(255, 255, 255, 0.05);
    padding: 24px;
  }

  .info-card h3 {
    margin: 0 0 12px 0;
    font-size: 1.1rem;
  }

  .info-card p {
    margin: 0;
    line-height: 1.5;
    font-size: 0.95rem;
    color: var(--text-dim);
  }

  /* Donate Tab */
  .donate-content {
    display: flex;
    justify-content: center;
    align-items: center;
    height: 100%;
    min-height: 400px;
  }

  .donate-card {
    max-width: 500px;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 16px;
    text-align: center;
    padding: 40px 32px;
  }

  .donate-emoji {
    font-size: 4rem;
    margin-bottom: 8px;
    animation: bounce 2s infinite;
  }

  .donate-card h2 {
    margin: 0;
    font-size: 1.5rem;
    font-weight: 700;
    background: linear-gradient(135deg, var(--accent-cyan), var(--accent-magenta));
    -webkit-background-clip: text;
    background-clip: text;
    -webkit-text-fill-color: transparent;
  }

  .donate-text-paragraphs {
    display: flex;
    flex-direction: column;
    gap: 12px;
    text-align: left;
    margin: 12px 0;
  }

  .donate-card .desc {
    margin: 0;
    font-size: 0.95rem;
    color: var(--text-dim);
    line-height: 1.6;
  }

  .donate-btn-large {
    display: inline-block;
    background-color: var(--accent-yellow);
    color: #000;
    padding: 12px 24px;
    border-radius: 8px;
    font-weight: 700;
    text-decoration: none;
    margin-top: 16px;
    transition: transform 0.2s;
  }

  .donate-btn-large:hover {
    transform: translateY(-2px);
  }

  /* Logs Tab Styles */
  .logs-layout-grid {
    display: grid;
    grid-template-columns: 300px 1fr;
    gap: 20px;
    flex: 1;
    min-height: 0;
    overflow: hidden;
  }

  .guardian-credit {
    margin-top: 14px !important;
    padding-top: 14px;
    border-top: 1px solid rgba(255, 255, 255, 0.06);
  }

  .guardian-links {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 8px !important;
    font-size: 0.8rem !important;
  }

  .guardian-links a {
    color: var(--accent-cyan);
  }

  .logs-guidance {
    margin-bottom: 16px;
  }

  .logs-sidebar-card {
    display: flex;
    flex-direction: column;
    padding: 16px;
    overflow-y: auto;
  }

  .logs-content-card {
    display: flex;
    flex-direction: column;
    padding: 16px;
    overflow: hidden;
  }

  .log-files-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-top: 12px;
  }

  .log-file-item {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 8px;
    color: var(--text-main);
    padding: 12px;
    text-align: left;
    cursor: pointer;
    font-family: var(--font-stack);
    font-size: 14px;
    transition: all 0.2s ease;
  }

  .log-file-item:hover {
    background: rgba(57, 242, 236, 0.08);
    border-color: rgba(57, 242, 236, 0.2);
  }

  .log-file-item.selected {
    background: rgba(57, 242, 236, 0.15);
    border-color: var(--accent-cyan);
    box-shadow: 0 0 10px rgba(57, 242, 236, 0.2);
  }

  .log-content-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    padding-bottom: 12px;
    margin-bottom: 16px;
  }

  .btn-primary {
    background: linear-gradient(135deg, var(--accent-cyan), #00d2c6);
    border: none;
    border-radius: 8px;
    color: #0c0f16;
    padding: 8px 16px;
    font-weight: 600;
    cursor: pointer;
    font-family: var(--font-stack);
    transition: all 0.2s ease;
  }

  .btn-primary:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(57, 242, 236, 0.3);
  }

  .log-content-table-wrapper {
    flex: 1;
    overflow-y: auto;
    border-radius: 8px;
    background: rgba(0, 0, 0, 0.2);
    border: 1px solid rgba(255, 255, 255, 0.05);
  }

  .log-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
    font-family: 'Consolas', monospace;
  }

  .log-table th {
    background: rgba(0, 0, 0, 0.3);
    padding: 10px 12px;
    text-align: left;
    color: var(--text-dim);
    font-weight: 500;
    font-family: var(--font-stack);
  }

  .log-table td {
    padding: 8px 12px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.03);
  }

  .log-table tr:hover {
    background: rgba(255, 255, 255, 0.02);
  }

  .log-block {
    color: #ff6b6b;
  }

  .log-allow {
    color: #51cf66;
  }

  .action-badge {
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: bold;
    background: rgba(81, 207, 102, 0.15);
    color: #51cf66;
    display: inline-block;
  }

  .action-badge.block {
    background: rgba(255, 107, 107, 0.15);
    color: #ff6b6b;
  }

  .select-prompt {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    flex: 1;
    color: var(--text-dim);
  }

  .prompt-icon {
    font-size: 48px;
    margin-bottom: 16px;
    opacity: 0.5;
  }

  .time-col {
    color: var(--text-dim);
    width: 150px;
  }

  .action-col {
    width: 80px;
  }

  .ip-col {
    font-weight: bold;
    width: 140px;
  }

  /* Keyframe Animations */
  @keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
  }

  @keyframes slideIn {
    from { transform: translateX(100%); }
    to { transform: translateX(0); }
  }

  @keyframes bounce {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(-10px); }
  }
</style>
