<script lang="ts">
  import { invoke } from "@tauri-apps/api/core";
  import { listen } from "@tauri-apps/api/event";
  import { onMount } from "svelte";

  // State definitions using Svelte 5 runes
  let activeTab = $state("dashboard"); // "dashboard", "lists", "settings", "help"
  let status = $state({ active_session: "Open", is_locked: false, is_running: false, driver_error: null as string | null });
  let lists = $state({ whitelist: [] as string[], blacklist: [] as string[] });
  let settings = $state({
    sound_enabled: true,
    sound_lock_freq: 900,
    sound_lock_dur: 200,
    sound_unlock_freq: 400,
    sound_unlock_dur: 200,
    ips_enabled: true,
    ips_adaptive_multiplier: 5,
    ips_adaptive_measurement_seconds: 45,
    ips_fallback_threshold: 250,
    auto_lock_on_attack: false,
    language: "ru"
  });

  // UI helpers
  let logs = $state([] as Array<{ timestamp: string; ip: string; action: string; size: number; reason: string }>);
  let showDrawer = $state(false);
  let drawerListType = $state(""); // "whitelist" or "blacklist"
  let drawerIpInput = $state("");
  let drawerError = $state("");
  let saveStatusMsg = $state("");

  // Translations dictionary
  const t = {
    ru: {
      status_open: "🟢 ОТКРЫТО",
      status_locked: "🔴 ЗАПЕРТО",
      status_solo: "⚡ SOLO-СЕССИЯ",
      status_error: "⚠️ ОШИБКА ДРАЙВЕРА",
      err_driver_fail: "Драйвер WinDivert не запущен (проверьте права/антивирус): ",
      lock_session: "Запереть сессию (Lock)",
      solo_session: "Solo-сессия",
      whitelist_session: "Сессия по вайтлисту",
      stop_session: "Остановить сессию",
      live_activity: "Сетевая активность в реальном времени",
      col_wl: "ВЛ",
      col_bl: "ЧЛ",
      col_time: "Время",
      col_action: "Действие",
      col_ip: "IP-адрес",
      col_detail: "Детали",
      nav_dash: "Панель управления",
      nav_lists: "Списки защиты",
      nav_settings: "Настройки",
      nav_help: "Справка",
      nav_donate: "Поблагодарить",
      nav_logs: "Логи",
      logs_title: "Логи соединений",
      logs_empty: "Лог-файлы еще не созданы или пусты. Они появятся после фиксации сетевой активности фаерволом.",
      btn_open_in_notepad: "Открыть в Блокноте",
      logs_file_list_title: "Список сохраненных файлов логов:",
      logs_view_title: "Содержимое лога:",
      wl_title: "Белый список (Whitelist)",
      bl_title: "Черный список (Blacklist)",
      btn_clear: "Очистить список",
      btn_add_ip: "Добавить IP-адрес",
      drawer_title: "Добавить в список",
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
      settings_multiplier: "Адаптивный множитель PPS:",
      settings_measurement: "Время замера базовой активности (сек):",
      settings_fallback: "Резервный порог флуда (PPS):",
      settings_autolock: "Авто-запирание сессии при атаке (Auto-Lock)",
      settings_lang: "Язык интерфейса:",
      settings_saved: "Настройки успешно сохранены!",
      copy_success: "IP-адрес скопирован в буфер обмена",
      err_relay: "Защита: Нельзя добавить реле-сервер Rockstar в белый список!",
      donate_title: "Поддержка проекта G-Lock",
      donate_p1: "Всем привет. Меня зовут Тёма ТурисТ, я стример.",
      donate_p2: "Я сделал G-Lock для себя. Меня годами преследовали читеры на стримах — крашили игру мне и моим друзьям, срывали эфиры, и сделать с этим ничего было нельзя. Поддержки не было, готовых решений тоже. Тогда я написал защиту сам.",
      donate_p3: "И когда однажды я отыграл целый стрим без единого краша — понял, что это работает. Решил не держать при себе и выложить в открытый доступ, чтобы любой, кого достали гриферы, мог защититься так же.",
      donate_p4: "G-Lock полностью бесплатный, с открытым кодом и без рекламы — и таким останется. Если он спас твой стрим или просто помог спокойно поиграть с друзьями, буду благодарен за любую поддержку. Это идет на время разработки и помогает делать тул лучше. Спасибо, что вы есть 🛡️",
      btn_donate_da: "🎁 Отправить донат (donationalerts.com)",
      blocked_threats_msg: "G-Lock отбил {n} атак за эту сессию 🛡️ Если помогло — ",
      support_link: "поддержите разработку"
    },
    en: {
      status_open: "🟢 OPEN",
      status_locked: "🔴 LOCKED",
      status_solo: "⚡ SOLO SESSION",
      status_error: "⚠️ DRIVER ERROR",
      err_driver_fail: "WinDivert driver not running (check privileges/antivirus): ",
      lock_session: "Lock Session",
      solo_session: "Solo Session",
      whitelist_session: "Whitelist Session",
      stop_session: "Stop Session",
      live_activity: "Real-time Network Activity Logs",
      col_wl: "WL",
      col_bl: "BL",
      col_time: "Time",
      col_action: "Action",
      col_ip: "IP Address",
      col_detail: "Details",
      nav_dash: "Dashboard",
      nav_lists: "Protection Lists",
      nav_settings: "Settings",
      nav_help: "Help / FAQ",
      nav_donate: "Donate",
      nav_logs: "Logs",
      logs_title: "Connection Logs",
      logs_empty: "Log files have not been created yet or are empty. They will appear after the firewall starts recording network activity.",
      btn_open_in_notepad: "Open in Notepad",
      logs_file_list_title: "Saved log files list:",
      logs_view_title: "Log contents:",
      wl_title: "Whitelist",
      bl_title: "Blacklist",
      btn_clear: "Clear List",
      btn_add_ip: "Add IP Address",
      drawer_title: "Add to List",
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
      settings_multiplier: "Adaptive PPS Multiplier:",
      settings_measurement: "Base Activity Measure Duration (sec):",
      settings_fallback: "Fallback Flood Threshold (PPS):",
      settings_autolock: "Auto-Lock Session on Attack",
      settings_lang: "Interface Language:",
      settings_saved: "Settings saved successfully!",
      copy_success: "IP Address copied to clipboard",
      err_relay: "Security Alert: Cannot whitelist official Rockstar/Azure relay IP!",
      donate_title: "Support G-Lock Development",
      donate_p1: "Hi everyone! I'm Tyoma Tourist, a streamer.",
      donate_p2: "I originally built G-Lock for myself. For years, griefers and modders stalked me on stream — constantly crashing my game, kicking my friends, and ruining broadcasts. There was no help from support and no working solutions. So, I decided to write my own protection.",
      donate_p3: "When I finally completed a whole stream without a single crash, I knew it worked. I decided to make it open-source so anyone tired of griefers could play peacefully too.",
      donate_p4: "G-Lock is and will always remain completely free, open-source, and ad-free. If it saved your stream or simply helped you and your friends play in peace, I would be grateful for any support. It directly funds development time and helps make this tool even better. Thank you for being here 🛡️",
      btn_donate_da: "🎁 Send Donation (donationalerts.com)",
      blocked_threats_msg: "G-Lock warded off {n} threats this session 🛡️ If it helped — ",
      support_link: "support development"
    }
  };

  // Get active localization
  let activeLang = $derived(settings.language === "en" ? t.en : t.ru);

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
  const helpArticles = $derived(
    settings.language === "en"
      ? [
          {
            id: "lock",
            title: "🔒 Lock Session Mode",
            short: "Blocks new player connections while keeping existing ones.",
            full: "This mode blocks incoming matchmaking requests. Players already inside your session will remain connected, but no new players can join. Use F9 globally to toggle this mode on/off. WARNING: Matchmaking is disabled while locked. Always unlock before searching for a new populated lobby, and re-lock only after loading is complete."
          },
          {
            id: "solo",
            title: "⚡ Solo Session Mode",
            short: "Splits you off into a completely empty lobby where you are the host.",
            full: "Blocks all incoming and current connections from other players. Your current lobby splits, migrating you into a completely solo lobby. Crucial Social Club, save synchronization, and Rockstar services traffic will remain allowed."
          },
          {
            id: "whitelist",
            title: "📜 Whitelist Session Mode",
            short: "Allows connections only from whitelisted IP addresses.",
            full: "Restricts all incoming connections except for those specifically defined in your Whitelist (e.g., your friends' IP addresses). Any unlisted IP attempting to connect is immediately blocked."
          },
          {
            id: "ips",
            title: "🛡️ Intrusion Prevention System (IPS)",
            short: "Automatically blocks network flood and DDoS attacks.",
            full: "IPS measures normal background traffic from other players. If any unknown IP address starts flooding packets above the adaptive threshold, IPS automatically bans that IP for a cooldown period (default: 60 seconds). Crucial Rockstar relays are exempt from bans."
          },
          {
            id: "lists",
            title: "✍️ Whitelist & Blacklist Editor",
            short: "Manage safe and blocked IP addresses manually.",
            full: "In the 'Protection Lists' tab, you can add, edit, or delete IP addresses and subnets in CIDR format (e.g., 192.168.1.0/24). Blacklisted IPs are always dropped, while whitelisted IPs bypass security constraints."
          },
          {
            id: "logs",
            title: "📊 Real-time Network Log",
            short: "Interactive view of all traffic and active player connections.",
            full: "Displays all incoming network packets. Click green/red buttons to quickly add IPs to Whitelist/Blacklist, or right-click to copy IPs. Color codes: Yellow (Friends), Green (P2P), Blue (Rockstar Relay), Red (Blocked)."
          },
          {
            id: "hotkeys",
            title: "🔑 Global Hotkeys",
            short: "Keys to control G-Lock without tab-switching out of GTA.",
            full: "F9: Toggle Lock Session on/off. Ctrl+F9: Panic Unlock (instantly drops all blocks). Ctrl+/Ctrl-: Zoom UI in/out. Ctrl+0: Reset UI zoom."
          }
        ]
      : [
          {
            id: "lock",
            title: "🔒 Режим «Запереть сессию»",
            short: "Блокирует подключение новых игроков, не разрывая связь с текущими.",
            full: "Этот режим фильтрует входящие P2P-пакеты матчмейкинга для новых IP-адресов. Игроки, которые уже находятся в вашей сессии, смогут остаться, но новые зайти не смогут. Нажмите F9 глобально для быстрого включения/выключения. ВНИМАНИЕ: Поиск новых лобби не работает в запертом режиме. Всегда разблокируйте сессию перед поиском новой игры, и заприте обратно после полной загрузки."
          },
          {
            id: "solo",
            title: "⚡ Режим «Solo-сессия»",
            short: "Отделяет вас в пустое лобби, где вы гарантированно будете хостом.",
            full: "Полностью блокирует соединения со всеми другими игроками. Текущее лобби разделится, и вы останетесь в сессии совершенно один. При этом критически важный трафик Rockstar Games, Social Club и облачных сохранений продолжает работать."
          },
          {
            id: "whitelist",
            title: "📜 Режим «Сессия по вайтлисту»",
            short: "Разрешает подключения только с IP-адресов из белого списка.",
            full: "Ограничивает все входящие P2P-подключения, кроме адресов друзей, внесенных в ваш Белый список. Любой другой игрок, пытающийся подключиться к вашей сессии, будет автоматически заблокирован."
          },
          {
            id: "ips",
            title: "🛡️ Система предотвращения вторжений (IPS)",
            short: "Автоматически блокирует сетевой флуд и DDoS-атаки.",
            full: "IPS замеряет обычную фоновую активность игроков. Если какой-то неизвестный IP превышает динамический лимит пакетов в секунду (PPS), IPS забанит его на время остывания (по умолчанию 60 секунд), чтобы предотвратить зависание лобби. Серверы Rockstar исключены из банов."
          },
          {
            id: "lists",
            title: "✍️ Управление списками защиты",
            short: "Ручное добавление и редактирование правил фильтрации.",
            full: "На вкладке 'Списки защиты' вы можете просматривать, добавлять, изменять и удалять IP-адреса и подсети в формате CIDR (например, 192.168.1.0/24). Черный список блокируется всегда, белый список имеет наивысший приоритет."
          },
          {
            id: "logs",
            title: "📊 Интерактивный лог активности",
            short: "Отображение сетевых пакетов и быстрые действия в реальном времени.",
            full: "Вы можете видеть IP-адреса игроков на панели лога. Клик по кнопке 🟢 добавляет IP в белый список, 🔴 — в черный. Правый клик позволяет скопировать адрес. Цвета: Желтый (Друзья), Зеленый (P2P), Синий (Релей R*), Красный (Блокирован)."
          },
          {
            id: "hotkeys",
            title: "🔑 Глобальные горячие клавиши",
            short: "Управление фаерволом без переключения из игры.",
            full: "F9: Быстро запереть/отпереть сессию. Ctrl+F9: Panic Unlock (экстренное разблокирование). Ctrl + / Ctrl -: Масштаб интерфейса. Ctrl + 0: Сбросить масштаб."
          }
        ]
  );

  async function fetchStatus() {
    status = await invoke("get_status");
  }

  async function fetchLists() {
    lists = await invoke("get_lists");
  }

  async function fetchSettings() {
    settings = await invoke("get_settings");
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
    } catch (e) {
      console.error("AudioContext error: ", e);
    }
  }

  function playCustomSound(base64Data: string, vol: number) {
    try {
      const audio = new Audio(base64Data);
      audio.volume = vol / 100;
      audio.play();
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
        playSynthBeep(900, 200, soundVolume);
      }
    } else if (type === "unlock") {
      if (unlockSoundType === "custom" && unlockSoundCustom) {
        playCustomSound(unlockSoundCustom, soundVolume);
      } else {
        playSynthBeep(400, 200, soundVolume);
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

  async function handleStartSession(mode: string) {
    if (status.active_session === mode) {
      await handleStopSession();
    } else {
      status = await invoke("start_session", { sessionType: mode });
    }
  }

  async function handleStopSession() {
    status = await invoke("stop_session");
  }

  async function handleAddToListDirect(listType: string, ip: string) {
    try {
      await invoke("add_to_list", { listType, ip });
    } catch (e: any) {
      if (e === "RELAY_PROTECTION") {
        alert(activeLang.err_relay);
      } else {
        alert(e);
      }
    }
  }

  async function handleDeleteFromList(listType: string, ip: string) {
    lists = await invoke("delete_from_list", { listType, ip });
  }

  async function handleClearList(listType: string) {
    if (confirm(activeLang.btn_clear + "?")) {
      lists = await invoke("clear_list", { listType });
    }
  }

  function openAddDrawer(listType: string) {
    drawerListType = listType;
    drawerIpInput = "";
    drawerError = "";
    showDrawer = true;
  }

  async function submitDrawer() {
    if (!drawerIpInput.trim()) return;
    try {
      await invoke("add_to_list", { listType: drawerListType, ip: drawerIpInput.trim() });
      showDrawer = false;
    } catch (e: any) {
      if (e === "RELAY_PROTECTION") {
        drawerError = activeLang.err_relay;
      } else {
        drawerError = e.toString();
      }
    }
  }

  async function handleSaveSettings() {
    try {
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
      <h2>G-Lock <span class="ver">v2.0.38</span></h2>
    </div>

    <nav class="nav-links">
      <button class="nav-btn" class:active={activeTab === "dashboard"} onclick={() => activeTab = "dashboard"}>
        <span class="icon">📊</span> {activeLang.nav_dash}
      </button>
      <button class="nav-btn" class:active={activeTab === "lists"} onclick={() => activeTab = "lists"}>
        <span class="icon">🛡️</span> {activeLang.nav_lists}
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
      <div class="drawer-overlay" onclick={() => showDrawer = false}></div>
      <div class="drawer">
        <h3>{activeLang.drawer_title} ({drawerListType === "whitelist" ? "WL" : "BL"})</h3>
        <div class="form-group">
          <input
            type="text"
            placeholder={activeLang.drawer_placeholder}
            bind:value={drawerIpInput}
            onkeydown={(e) => e.key === "Enter" && submitDrawer()}
            autofocus
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
          <div class="status-card" class:locked={status.is_locked} class:error={!!status.driver_error} onclick={status.driver_error ? null : handleToggleLock}>
            <div class="glow-layer"></div>
            <div class="card-inner">
              <span class="status-label">STATUS</span>
              <h2 class="status-text">
                {#if status.driver_error}
                  {activeLang.status_error}
                {:else if status.active_session === "Solo"}
                  {activeLang.status_solo}
                {:else if status.is_locked}
                  {activeLang.status_locked}
                {:else}
                  {activeLang.status_open}
                {/if}
              </h2>
              <span class="status-tip">
                {#if status.driver_error}
                  {activeLang.err_driver_fail} {status.driver_error}
                {:else}
                  Кликните, чтобы переключить замок (F9)
                {/if}
              </span>
              
              <div class="threats-banner" onclick={(e) => e.stopPropagation()}>
                <span>
                  {activeLang.blocked_threats_msg.replace("{n}", blockedThreatsCount.toString())}
                  <button type="button" class="support-inline-link" onclick={() => activeTab = "donate"}>
                    {activeLang.support_link}
                  </button>
                </span>
              </div>
            </div>
          </div>

          <!-- Session Controls Card -->
          <div class="controls-card">
            <h3>Режимы фильтрации</h3>
            <div class="controls-buttons">
              <button
                class="ctrl-btn"
                class:active={status.active_session === "Lock"}
                onclick={() => handleStartSession("Lock")}
              >
                🔒 {activeLang.lock_session}
              </button>
              <button
                class="ctrl-btn"
                class:active={status.active_session === "Solo"}
                onclick={() => handleStartSession("Solo")}
              >
                👤 {activeLang.solo_session}
              </button>
              <button
                class="ctrl-btn"
                class:active={status.active_session === "Whitelist"}
                onclick={() => handleStartSession("Whitelist")}
              >
                📋 {activeLang.whitelist_session}
              </button>
              <button class="ctrl-btn stop-btn" onclick={handleStopSession}>
                🛑 {activeLang.stop_session}
              </button>
            </div>
          </div>
        </section>

        <!-- Live Network Activity Log -->
        <section class="logs-panel">
          <h3>{activeLang.live_activity}</h3>
          <div class="table-container">
            <table class="logs-table">
              <thead>
                <tr>
                  <th style="width: 40px;">{activeLang.col_wl}</th>
                  <th style="width: 40px;">{activeLang.col_bl}</th>
                  <th style="width: 90px;">{activeLang.col_time}</th>
                  <th style="width: 80px;">{activeLang.col_action}</th>
                  <th style="width: 140px;">{activeLang.col_ip}</th>
                  <th>{activeLang.col_detail}</th>
                </tr>
              </thead>
              <tbody>
                {#each logs as log}
                  {@const isWl = lists.whitelist.includes(log.ip)}
                  {@const isRelay = log.reason.toLowerCase().includes("relay") || log.reason.toLowerCase().includes("tunnel")}
                  <tr class="log-row" class:wl-row={isWl} class:relay-row={isRelay} class:blocked-row={log.action === "BLOCK"}>
                    <td class="btn-cell">
                      <button class="quick-add wl" onclick={() => handleAddToListDirect("whitelist", log.ip)}>🟢</button>
                    </td>
                    <td class="btn-cell">
                      <button class="quick-add bl" onclick={() => handleAddToListDirect("blacklist", log.ip)}>🔴</button>
                    </td>
                    <td>{log.timestamp.split(" ")[1] || log.timestamp}</td>
                    <td class="act-col">{log.action}</td>
                    <td class="ip-col" onclick={() => copyIpToClipboard(log.ip)} title="Кликните для копирования">
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

    <!-- Tab 2: Protection Lists -->
    {#if activeTab === "lists"}
      <div class="tab-panel">
        <header class="panel-header flex-header">
          <h1>{activeLang.nav_lists}</h1>
        </header>

        <section class="lists-container">
          <!-- Whitelist Panel -->
          <div class="list-pane">
            <div class="pane-header">
              <h3>📜 {activeLang.wl_title}</h3>
              <button class="add-ip-btn" onclick={() => openAddDrawer("whitelist")}>+</button>
            </div>
            <div class="list-box">
              {#each lists.whitelist as ip}
                <div class="list-item">
                  <span class="ip-val">{ip}</span>
                  <button class="del-btn" onclick={() => handleDeleteFromList("whitelist", ip)}>✕</button>
                </div>
              {/each}
            </div>
            <button class="clear-btn" onclick={() => handleClearList("whitelist")}>🧹 {activeLang.btn_clear}</button>
          </div>

          <!-- Blacklist Panel -->
          <div class="list-pane">
            <div class="pane-header">
              <h3>🚫 {activeLang.bl_title}</h3>
              <button class="add-ip-btn" onclick={() => openAddDrawer("blacklist")}>+</button>
            </div>
            <div class="list-box">
              {#each lists.blacklist as ip}
                <div class="list-item">
                  <span class="ip-val">{ip}</span>
                  <button class="del-btn" onclick={() => handleDeleteFromList("blacklist", ip)}>✕</button>
                </div>
              {/each}
            </div>
            <button class="clear-btn" onclick={() => handleClearList("blacklist")}>🧹 {activeLang.btn_clear}</button>
          </div>
        </section>
      </div>
    {/if}

    <!-- Tab 3: Settings -->
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
                    <button type="button" class="btn-action" onclick={() => playSynthBeep(900, 200, soundVolume)}>{activeLang.btn_test_sound}</button>
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
                    <button type="button" class="btn-action" onclick={() => playSynthBeep(400, 200, soundVolume)}>{activeLang.btn_test_sound}</button>
                  </div>
                {/if}
              </div>
            {/if}
          </div>

          <!-- IPS Configurations -->
          <div class="settings-section">
            <h3>🔒 {activeLang.settings_ips}</h3>

            <div class="setting-item">
              <label class="switch-container">
                <input type="checkbox" bind:checked={settings.ips_enabled} />
                <span class="slider"></span>
                <span class="label-text">Включить лимиты трафика (IPS)</span>
              </label>
            </div>

            {#if settings.ips_enabled}
              <div class="setting-item">
                <div class="slider-header">
                  <span>{activeLang.settings_multiplier}</span>
                  <span class="slider-value">{settings.ips_adaptive_multiplier}x</span>
                </div>
                <input type="range" min="2" max="15" bind:value={settings.ips_adaptive_multiplier} />
              </div>

              <div class="setting-item">
                <div class="slider-header">
                  <span>{activeLang.settings_measurement}</span>
                  <span class="slider-value">{settings.ips_adaptive_measurement_seconds}с</span>
                </div>
                <input type="range" min="15" max="120" bind:value={settings.ips_adaptive_measurement_seconds} />
              </div>

              <div class="setting-item">
                <div class="slider-header">
                  <span>{activeLang.settings_fallback}</span>
                  <span class="slider-value">{settings.ips_fallback_threshold} PPS</span>
                </div>
                <input type="range" min="50" max="500" step="10" bind:value={settings.ips_fallback_threshold} />
              </div>

              <div class="setting-item">
                <label class="switch-container">
                  <input type="checkbox" bind:checked={settings.auto_lock_on_attack} />
                  <span class="slider"></span>
                  <span class="label-text">{activeLang.settings_autolock}</span>
                </label>
              </div>
            {/if}
          </div>

          <!-- Save Button -->
          <div class="settings-actions">
            <button class="save-settings-btn" onclick={handleSaveSettings}>💾 Сохранить настройки</button>
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
                  <div class="empty-state">Этот файл лога пуст или не содержит корректных записей.</div>
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
                <p>Выберите файл лога слева, чтобы просмотреть его содержимое, или откройте в Блокноте.</p>
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
                ? "G-Lock is a personal firewall for safe gaming in GTA Online. It automates Windows Filtering Platform rules via the WinDivert driver, blocking malicious players, griefers, modders, and protecting you from network floods and DDoS attacks."
                : "G-Lock — это персональный фаервол для безопасной игры в GTA Online. Он полностью автоматизирует правила Windows Filtering Platform через низкоуровневый драйвер WinDivert, блокируя посторонних игроков, читеров и защищая от DDoS-атак."}
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
            <a href="https://www.donationalerts.com/r/typuct_donate" target="_blank" class="donate-btn-large">
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
    background-color: var(--bg-sidebar);
    border-right: 1px solid rgba(255, 255, 255, 0.05);
    display: flex;
    flex-direction: column;
    padding: 24px;
    box-sizing: border-box;
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

  .flex-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  /* Dashboard View */
  .dashboard-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 24px;
    margin-bottom: 24px;
  }

  .status-card {
    background-color: var(--bg-card);
    border-radius: 12px;
    border: 1px solid rgba(255, 255, 255, 0.05);
    padding: 24px;
    cursor: pointer;
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

  .status-tip {
    font-size: 0.8rem;
    color: var(--text-dim);
    margin-top: 8px;
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

  .controls-card {
    background-color: var(--bg-card);
    border-radius: 12px;
    border: 1px solid rgba(255, 255, 255, 0.05);
    padding: 24px;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .controls-card h3 {
    margin: 0;
    font-size: 1.1rem;
    color: var(--text-dim);
  }

  .controls-buttons {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
  }

  .ctrl-btn {
    background-color: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.08);
    color: var(--text-main);
    padding: 10px;
    border-radius: 8px;
    cursor: pointer;
    font-weight: 500;
    transition: all 0.2s;
  }

  .ctrl-btn:hover {
    background-color: rgba(255, 255, 255, 0.06);
    border-color: var(--accent-cyan);
  }

  .ctrl-btn.active {
    background: linear-gradient(135deg, rgba(57, 242, 236, 0.2), transparent);
    border-color: var(--accent-cyan);
    box-shadow: 0 0 10px rgba(57, 242, 236, 0.1);
  }

  .ctrl-btn.stop-btn {
    border-color: rgba(231, 76, 60, 0.2);
  }

  .ctrl-btn.stop-btn:hover {
    background-color: rgba(231, 76, 60, 0.1);
    border-color: var(--accent-red);
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
  }

  .log-row:hover {
    background-color: rgba(255, 255, 255, 0.01);
  }

  .log-row.wl-row {
    color: var(--accent-yellow);
  }

  .log-row.relay-row {
    color: var(--accent-cyan);
  }

  .log-row.blocked-row {
    color: var(--accent-red);
    background-color: rgba(231, 76, 60, 0.02);
  }

  .btn-cell {
    padding: 4px 6px !important;
    text-align: center;
  }

  .quick-add {
    background: none;
    border: none;
    cursor: pointer;
    font-size: 0.95rem;
    padding: 0;
    transition: transform 0.15s;
  }

  .quick-add:hover {
    transform: scale(1.25);
  }

  .ip-col {
    cursor: pointer;
    text-decoration: underline dotted;
  }

  /* Lists tab */
  .lists-container {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 24px;
    height: calc(100% - 60px);
  }

  .list-pane {
    background-color: var(--bg-card);
    border-radius: 12px;
    border: 1px solid rgba(255, 255, 255, 0.05);
    padding: 24px;
    display: flex;
    flex-direction: column;
    overflow: hidden;
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
    max-width: 600px;
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
    max-width: 700px;
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
    height: calc(100vh - 120px);
    overflow: hidden;
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
