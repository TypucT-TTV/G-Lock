<script lang="ts">
  import { invoke } from "@tauri-apps/api/core";
  import { listen } from "@tauri-apps/api/event";
  import { onMount } from "svelte";

  // State definitions using Svelte 5 runes
  let activeTab = $state("dashboard"); // "dashboard", "lists", "settings", "help"
  let status = $state({ active_session: "Open", is_locked: false, is_running: false });
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
      nav_help: "Справка / Донат",
      wl_title: "Белый список (Whitelist)",
      bl_title: "Черный список (Blacklist)",
      btn_clear: "Очистить список",
      btn_add_ip: "Добавить IP-адрес",
      drawer_title: "Добавить в список",
      drawer_placeholder: "Введите IP или CIDR...",
      btn_save: "Сохранить",
      btn_cancel: "Отмена",
      settings_sound: "Звуковые сигналы оповещения",
      settings_ips: "Система предотвращения вторжений (IPS)",
      settings_multiplier: "Адаптивный множитель PPS:",
      settings_measurement: "Время замера базовой активности (сек):",
      settings_fallback: "Резервный порог флуда (PPS):",
      settings_autolock: "Авто-запирание сессии при атаке (Auto-Lock)",
      settings_lang: "Язык интерфейса:",
      settings_saved: "Настройки успешно сохранены!",
      copy_success: "IP-адрес скопирован в буфер обмена",
      err_relay: "Защита: Нельзя добавить реле-сервер Rockstar в белый список!"
    },
    en: {
      status_open: "🟢 OPEN",
      status_locked: "🔴 LOCKED",
      status_solo: "⚡ SOLO SESSION",
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
      nav_help: "Help / Support",
      wl_title: "Whitelist",
      bl_title: "Blacklist",
      btn_clear: "Clear List",
      btn_add_ip: "Add IP Address",
      drawer_title: "Add to List",
      drawer_placeholder: "Enter IP or CIDR...",
      btn_save: "Save",
      btn_cancel: "Cancel",
      settings_sound: "Enable Audio Beep Alerts",
      settings_ips: "Intrusion Prevention System (IPS)",
      settings_multiplier: "Adaptive PPS Multiplier:",
      settings_measurement: "Base Activity Measure Duration (sec):",
      settings_fallback: "Fallback Flood Threshold (PPS):",
      settings_autolock: "Auto-Lock Session on Attack",
      settings_lang: "Interface Language:",
      settings_saved: "Settings saved successfully!",
      copy_success: "IP Address copied to clipboard",
      err_relay: "Security Alert: Cannot whitelist official Rockstar/Azure relay IP!"
    }
  };

  // Get active localization
  let activeLang = $derived(settings.language === "en" ? t.en : t.ru);

  async function fetchStatus() {
    status = await invoke("get_status");
  }

  async function fetchLists() {
    lists = await invoke("get_lists");
  }

  async function fetchSettings() {
    settings = await invoke("get_settings");
  }

  onMount(() => {
    fetchStatus();
    fetchLists();
    fetchSettings();

    // Listen to Tauri events
    const statusUnsub = listen("status-changed", () => {
      fetchStatus();
    });

    const listsUnsub = listen("lists-changed", () => {
      fetchLists();
    });

    const logUnsub = listen("connection-log", (event) => {
      const payload = event.payload as any;
      logs = [payload, ...logs.slice(0, 99)];
    });

    return () => {
      statusUnsub.then(fn => fn());
      listsUnsub.then(fn => fn());
      logUnsub.then(fn => fn());
    };
  });

  async function handleToggleLock() {
    status = await invoke("toggle_lock");
  }

  async function handleStartSession(mode: string) {
    status = await invoke("start_session", { sessionType: mode });
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

<div class="app-layout">
  <!-- Left Sidebar Navigation -->
  <aside class="sidebar">
    <div class="logo-container">
      <div class="logo-hexagon">G</div>
      <h2>G-Lock <span class="ver">v2.0</span></h2>
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
      <button class="nav-btn" class:active={activeTab === "help"} onclick={() => activeTab = "help"}>
        <span class="icon">💬</span> {activeLang.nav_help}
      </button>
    </nav>

    <div class="footer-links">
      <a href="https://www.donationalerts.com/r/typuct_donate" target="_blank" class="donate-link">
        💰 Поблагодарить ТурисТа
      </a>
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
          <div class="status-card" class:locked={status.is_locked} onclick={handleToggleLock}>
            <div class="glow-layer"></div>
            <div class="card-inner">
              <span class="status-label">STATUS</span>
              <h2 class="status-text">
                {#if status.active_session === "Solo"}
                  {activeLang.status_solo}
                {:else if status.is_locked}
                  {activeLang.status_locked}
                {:else}
                  {activeLang.status_open}
                {/if}
              </h2>
              <span class="status-tip">Кликните, чтобы переключить замок (F9)</span>
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
          <!-- Audio Alarm Switch -->
          <div class="settings-section">
            <label class="switch-container">
              <input type="checkbox" bind:checked={settings.sound_enabled} />
              <span class="slider"></span>
              <span class="label-text">{activeLang.settings_sound}</span>
            </label>
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

          <!-- Language Switcher -->
          <div class="settings-section">
            <h3>🌐 {activeLang.settings_lang}</h3>
            <div class="lang-switch-buttons">
              <button class="lang-btn" class:active={settings.language === "ru"} onclick={() => settings.language = "ru"}>RU</button>
              <button class="lang-btn" class:active={settings.language === "en"} onclick={() => settings.language = "en"}>EN</button>
            </div>
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

    <!-- Tab 4: Help -->
    {#if activeTab === "help"}
      <div class="tab-panel">
        <header class="panel-header">
          <h1>{activeLang.nav_help}</h1>
        </header>

        <section class="help-content">
          <div class="info-card">
            <h3>ℹ️ О проекте G-Lock</h3>
            <p>
              G-Lock — это персональный фаервол для безопасной игры в GTA Online. Он полностью
              автоматизирует правила Windows Filtering Platform через низкоуровневый драйвер
              WinDivert, блокируя посторонних игроков, читеров и защищая от DDoS-атак.
            </p>
          </div>

          <div class="info-card">
            <h3>🔑 Горячие клавиши</h3>
            <ul>
              <li><strong>F9</strong> — Быстрое запирание / отпирание текущей сессии из игры.</li>
              <li><strong>Ctrl + F9</strong> — Экстренное разблокирование (Panic Unlock).</li>
            </ul>
          </div>

          <div class="info-card">
            <h3>💸 Поддержка разработчика</h3>
            <p>
              Если программа помогла вам комфортно играть без читеров, вы можете отблагодарить автора
              доната. Все средства идут на развитие полезных инструментов для GTA сообщества.
            </p>
            <a href="https://www.donationalerts.com/r/typuct_donate" target="_blank" class="donate-btn-large">
              🎁 Отправить донат (donationalerts.com)
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
  }

  .logo-container {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 40px;
  }

  .logo-hexagon {
    width: 36px;
    height: 36px;
    background: linear-gradient(135deg, var(--accent-cyan), var(--accent-magenta));
    clip-path: polygon(25% 0%, 75% 0%, 100% 50%, 75% 100%, 25% 100%, 0% 50%);
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 800;
    color: #000;
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

  .donate-link {
    color: var(--accent-yellow);
    text-decoration: none;
    font-size: 0.9rem;
    font-weight: 500;
    transition: opacity 0.2s;
  }

  .donate-link:hover {
    opacity: 0.8;
  }

  /* Content Panel */
  .content-viewport {
    flex-grow: 1;
    position: relative;
    overflow: hidden;
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

  .status-card:not(.locked) {
    border-color: rgba(46, 204, 113, 0.3);
  }

  .status-card:not(.locked) .glow-layer {
    background: radial-gradient(circle at center, rgba(46, 204, 113, 0.15) 0%, transparent 70%);
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

  .lang-switch-buttons {
    display: flex;
    gap: 12px;
  }

  .lang-btn {
    width: 48px;
    height: 36px;
    border-radius: 6px;
    background-color: rgba(255, 255, 255, 0.02);
    border: 1px solid rgba(255, 255, 255, 0.08);
    color: var(--text-dim);
    cursor: pointer;
    font-weight: 600;
    transition: all 0.2s;
  }

  .lang-btn:hover {
    border-color: var(--accent-cyan);
    color: #fff;
  }

  .lang-btn.active {
    background-color: var(--accent-cyan);
    border-color: var(--accent-cyan);
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

  /* Help Tab */
  .help-content {
    display: flex;
    flex-direction: column;
    gap: 20px;
    max-width: 700px;
    overflow-y: auto;
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

  .info-card ul {
    margin: 8px 0 0 0;
    padding-left: 20px;
    color: var(--text-dim);
    line-height: 1.6;
    font-size: 0.95rem;
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

  /* Keyframe Animations */
  @keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
  }

  @keyframes slideIn {
    from { transform: translateX(100%); }
    to { transform: translateX(0); }
  }
</style>
