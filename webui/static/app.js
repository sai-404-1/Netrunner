const state = {
  view: "dashboard",
  hosts: [],
  groups: [],
  modules: [],
  templates: [],
  scheduled: [],
  sshKeys: [],
  taskRuns: [],
  currentRunId: null,
};

let wsConnection = null;
let wsRetryTimer = null;

function wsUrl() {
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}/ws`;
}

function connectWebSocket() {
  if (wsConnection?.readyState === WebSocket.OPEN || wsConnection?.readyState === WebSocket.CONNECTING) {
    return;
  }
  try {
    wsConnection = new WebSocket(wsUrl());
    wsConnection.onopen = () => {
      if (state.currentRunId) {
        subscribeToRun(state.currentRunId);
      }
    };
    wsConnection.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        handleWsMessage(data);
      } catch (error) {
        console.error("WebSocket message parse error", error);
      }
    };
    wsConnection.onclose = () => {
      wsConnection = null;
      wsRetryTimer = setTimeout(connectWebSocket, 3000);
    };
    wsConnection.onerror = (error) => {
      console.error("WebSocket error", error);
    };
  } catch (error) {
    console.error("Failed to connect WebSocket", error);
  }
}

function subscribeToRun(runId) {
  if (wsConnection?.readyState === WebSocket.OPEN) {
    wsConnection.send(JSON.stringify({ action: "subscribe", run_id: runId }));
  }
}

function handleWsMessage(data) {
  if (data.type !== "task_status" || !data.run) return;
  const run = data.run;
  const index = state.taskRuns.findIndex((r) => r.id === run.id);
  if (index >= 0) {
    state.taskRuns[index] = run;
  } else {
    state.taskRuns.unshift(run);
  }
  if (state.view === "history") {
    renderHistoryTable();
  }
  if (state.view === "dashboard") {
    loadDashboard();
  }
  if (state.view === "run" && state.currentRunId === run.id) {
    renderRunResult(run);
  }
}

function closeWebSocket() {
  if (wsRetryTimer) {
    clearTimeout(wsRetryTimer);
    wsRetryTimer = null;
  }
  if (wsConnection) {
    wsConnection.close();
    wsConnection = null;
  }
}

const viewMeta = {
  dashboard: ["Обзор", "Сводная панель состояния системы"],
  hosts: ["Хосты", "Реестр управляемых узлов и добавление новых машин"],
  modules: ["Модули", "Доступные для исполнения модули"],
  run: ["Запуск задачи", "Выбор цели, модуля и выполнение действия"],
  history: ["История", "Журнал выполненных задач и их результаты"],
  inventory: ["Инвентаризация", "Снимки состояния удалённых узлов"],
  schedule: ["Планировщик", "Создание и запуск запланированных задач"],
  keys: ["Ключи", "Управление SSH-ключами"],
  reports: ["Отчёты", "Формирование и просмотр файлов отчётности"],
};

function byId(id) {
  return document.getElementById(id);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  const payload = await response.json();
  if (!payload.ok) {
    throw new Error(payload.error || "Неизвестная ошибка API");
  }
  return payload.data;
}

function showToast(message, type = "ok") {
  const toast = byId("toast");
  toast.textContent = message;
  toast.className = `toast ${type === "error" ? "error" : ""}`;
  setTimeout(() => toast.classList.add("hidden"), 3200);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function taskStatusLabel(status) {
  const map = {
    success: "Завершено",
    error: "Ошибка",
    running: "Выполняется",
    pending: "В очереди",
    cancelled: "Отменено",
  };
  return map[status] || status || "—";
}

function taskStatusBadge(status) {
  const cls =
    status === "success"
      ? "success"
      : status === "error"
      ? "error"
      : status === "running"
      ? "running"
      : status === "cancelled"
      ? "warning"
      : "";
  return `<span class="badge ${cls}">${escapeHtml(taskStatusLabel(status))}</span>`;
}

function booleanBadge(value, yes = "Да", no = "Нет") {
  const cls = value ? "success" : "";
  return `<span class="badge ${cls}">${escapeHtml(value ? yes : no)}</span>`;
}

function labelBadge(text, cls = "") {
  return `<span class="badge ${cls}">${escapeHtml(text)}</span>`;
}

function formatDate(iso) {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    return d.toLocaleString("ru-RU", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

const EYE_ICON = `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>`;
const ICON_DELETE = `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path><line x1="10" y1="11" x2="10" y2="17"></line><line x1="14" y1="11" x2="14" y2="17"></line></svg>`;
const ICON_EDIT = `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>`;
const ICON_REFRESH = `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.3"></path></svg>`;
const ICON_PLAY = `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>`;
const ICON_COPY = `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>`;
const ICON_SAVE = `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>`;
const ICON_ADD = `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>`;

function renderTable(id, columns, rows, emptyText = "Нет данных", emptyCentered = false) {
  const table = byId(id);
  const wrapper = table?.closest(".table-wrap");
  if (wrapper) {
    wrapper.style.border = "";
    wrapper.style.background = "";
  }
  if (!rows || rows.length === 0) {
    if (emptyCentered && wrapper) {
      wrapper.style.border = "none";
      wrapper.style.background = "transparent";
      table.innerHTML = `<tbody><tr><td colspan="${columns.length}"><p class="empty-center">${emptyText}</p></td></tr></tbody>`;
    } else {
      table.innerHTML = `<tbody><tr><td class="muted" colspan="${columns.length}">${emptyText}</td></tr></tbody>`;
    }
    return;
  }
  const head = `<thead><tr>${columns.map((col) => `<th>${escapeHtml(col.title)}</th>`).join("")}</tr></thead>`;
  const body = rows
    .map((row) => `<tr>${columns.map((col) => `<td>${col.render ? col.render(row) : escapeHtml(row[col.key])}</td>`).join("")}</tr>`)
    .join("");
  table.innerHTML = `${head}<tbody>${body}</tbody>`;
}

function fillSelect(select, items, makeLabel) {
  select.innerHTML = items.map((item) => `<option value="${escapeHtml(item.id)}">${escapeHtml(makeLabel(item))}</option>`).join("");
}

function fillModuleSelect(preselectedSlug) {
  const runnable = state.modules.filter((item) => item.supports_task_runner);
  byId("run-module").innerHTML = runnable
    .map((item) => `<option value="${escapeHtml(item.slug)}" ${item.slug === preselectedSlug ? "selected" : ""}>${escapeHtml(item.name)} (${escapeHtml(item.slug)})</option>`)
    .join("");
  updateRunFormVisibility();
}

function currentTargets(type) {
  return type === "group" ? state.groups : state.hosts;
}

function fillTargetSelect(selectId, type) {
  const select = byId(selectId);
  const targets = currentTargets(type);
  fillSelect(select, targets, (item) => `${item.name || "Без имени"} #${item.id}`);
}

function updateTargetSelects() {
  fillTargetSelect("run-target", byId("run-target-type").value);
  fillTargetSelect("schedule-target", byId("schedule-target-type").value);
}

function updateRunFormVisibility() {
  const moduleSlug = byId("run-module")?.value;
  const commandField = byId("command-field");
  const aptField = byId("apt-field");
  if (commandField) {
    commandField.style.display = moduleSlug === "mass_ssh" ? "block" : "none";
  }
  if (aptField) {
    aptField.style.display = moduleSlug === "apt_package_manager" ? "block" : "none";
  }
}

window.switchView = function switchView(view, opts = {}) {
  state.view = view;
  document.querySelectorAll(".view").forEach((el) => el.classList.remove("active"));
  document.querySelectorAll(".nav-link").forEach((el) => el.classList.remove("active"));
  byId(`view-${view}`).classList.add("active");
  document.querySelector(`[data-view="${view}"]`).classList.add("active");
  const [title, subtitle] = viewMeta[view];
  byId("page-title").textContent = title;
  byId("page-subtitle").textContent = subtitle;
  loadCurrentView(opts);
}

async function loadBaseLists() {
  const [hosts, groups, modules, templates] = await Promise.all([
    api("/api/hosts"),
    api("/api/groups"),
    api("/api/modules"),
    api("/api/task-templates"),
  ]);
  state.hosts = hosts;
  state.groups = groups;
  state.modules = modules;
  state.templates = templates;
  fillModuleSelect();
  updateTargetSelects();
  fillSelect(byId("schedule-template"), templates, (item) => `${item.name} #${item.id}`);
}

async function loadDashboard() {
  const [summary, hosts] = await Promise.all([api("/api/summary"), api("/api/hosts")]);
  const onlineHosts = (hosts || []).filter((h) => h.is_active).length;
  const cards = [
    ["Онлайн", onlineHosts],
    ["Модули", summary.modules],
    ["Группы", summary.groups],
    ["Отчёты", summary.reports],
  ];
  byId("summary-cards").innerHTML = cards.map(([title, value]) => `<article class="card"><span>${title}</span><strong>${value}</strong></article>`).join("");
  renderTaskRuns("recent-runs-table", summary.recent_task_runs || [], false, true);
  renderDashboardHostStatus(hosts || []);
}

function renderDashboardHostStatus(hosts) {
  const container = byId("dashboard-hosts-status");
  if (!hosts.length) {
    container.innerHTML = `<p class="muted">Нет зарегистрированных хостов</p>`;
    return;
  }
  const active = hosts.filter((h) => h.is_active).length;
  const inactive = hosts.length - active;
  container.innerHTML = `
    <div class="status-summary">
      <div class="status-item"><span class="status-dot ok"></span><strong>${active}</strong> активных</div>
      <div class="status-item"><span class="status-dot error"></span><strong>${inactive}</strong> недоступных</div>
    </div>
    <div class="table-wrap"><table>
      <thead><tr><th>Хост</th><th>Адрес</th><th>Статус</th></tr></thead>
      <tbody>
        ${hosts.map((h) => `
          <tr>
            <td>${escapeHtml(h.name)}</td>
            <td>${escapeHtml(h.username)}@${escapeHtml(h.address)}:${escapeHtml(h.port)}</td>
            <td>${booleanBadge(h.is_active, "Активен", "Недоступен")}</td>
          </tr>
        `).join("")}
      </tbody>
    </table></div>
  `;
}

function renderHosts(rows) {
  const filtered = filterHosts(rows);
  renderTable("hosts-table", [
    { title: "Имя", key: "name" },
    { title: "Пользователь", key: "username" },
    { title: "IP-адрес", render: (r) => `<span class="truncate">${escapeHtml(r.address)}</span>` },
    { title: "Порт", key: "port" },
    { title: "Активен", render: (r) => booleanBadge(r.is_active) },
    { title: "Был в сети", render: (r) => escapeHtml(r.last_seen ? formatDate(r.last_seen) : "—") },
    { title: "Группа", render: (r) => escapeHtml(r.group_name || "—") },
    { title: "Описание", render: (r) => `<span class="truncate">${escapeHtml(r.description || "")}</span>` },
    { title: "", render: (r) => `
      <div class="row-actions">
        <button class="secondary" onclick="checkHost(${r.id}, this)" title="Проверить доступность">${ICON_REFRESH}</button>
        <button class="secondary" onclick="editHost(${r.id})" title="Редактировать">${ICON_EDIT}</button>
        <button class="secondary" style="color:var(--error)" onclick="deleteHost(${r.id})" title="Удалить">${ICON_DELETE}</button>
      </div>` },
  ], filtered);
}

function renderGroups(rows) {
  renderTable("groups-table", [
    { title: "Название", key: "name" },
    { title: "Тип", key: "kind" },
    { title: "Описание", render: (r) => `<span class="truncate">${escapeHtml(r.description || "")}</span>` },
    { title: "Хостов", render: (r) => escapeHtml((r.hosts || []).length) },
    { title: "", render: (r) => `
      <div class="row-actions">
        <button class="secondary" onclick="editGroup(${r.id})" title="Редактировать">${ICON_EDIT}</button>
        <button class="secondary" style="color:var(--error)" onclick="deleteGroup(${r.id})" title="Удалить">${ICON_DELETE}</button>
      </div>` },
  ], rows);
}

function renderModulesTable(rows, tableId, showActions) {
  renderTable(tableId, [
    { title: "Название", key: "name" },
    { title: "Slug", key: "slug" },
    { title: "Описание", render: (r) => `<span class="truncate">${escapeHtml(r.description || "")}</span>` },
    { title: "", render: (r) => `
      <div class="row-actions">
        ${showActions ? `
          <button class="secondary" onclick="editModule(${r.id})" title="Редактировать">${ICON_EDIT}</button>
          <button class="secondary" style="color:var(--error)" onclick="deleteModule(${r.id})" title="Удалить">${ICON_DELETE}</button>
        ` : `
          <button class="secondary placeholder" disabled aria-hidden="true">${ICON_EDIT}</button>
          <button class="secondary placeholder" disabled aria-hidden="true">${ICON_DELETE}</button>
        `}
        <button class="btn-play" onclick="playModule('${escapeHtml(r.slug)}')">${ICON_PLAY} Запуск</button>
      </div>` },
  ], rows);
}

function renderModules(rows) {
  const visible = rows.filter((r) => r.web_ui_visible !== false);
  const builtin = visible.filter((r) => r.is_builtin);
  const user = visible.filter((r) => !r.is_builtin);
  const container = byId("modules-table");
  if (!container) return;
  container.innerHTML = `
    <h4 style="margin:0 0 10px">Встроенные модули</h4>
    <div class="table-wrap"><table id="modules-table-builtin"></table></div>
    <h4 style="margin:24px 0 10px">Пользовательские модули</h4>
    <div class="table-wrap"><table id="modules-table-user"></table></div>
  `;
  renderModulesTable(builtin, "modules-table-builtin", false);
  renderModulesTable(user, "modules-table-user", true);
}

function formatPerHostSummary(run) {
  if (!run.per_host_json) return "";
  try {
    const items = JSON.parse(run.per_host_json);
    if (!Array.isArray(items) || items.length === 0) return "";
    return `<span class="per-host-summary">${items.length} хостов</span>`;
  } catch {
    return "";
  }
}

function renderPerHostResults(run) {
  if (!run.per_host_json) return "";
  try {
    const items = JSON.parse(run.per_host_json);
    if (!Array.isArray(items) || items.length === 0) return "";
    return items
      .map(
        (item) => `
          <div class="per-host-result">
            <div class="per-host-header">
              <strong>${escapeHtml(item.name || item.address || item.host_id || "Хост")}</strong>
              <span class="muted">${escapeHtml(item.address || "")}${item.port ? `:${item.port}` : ""}</span>
            </div>
            <pre>${escapeHtml(item.output || "Нет вывода")}</pre>
          </div>
        `
      )
      .join("");
  } catch {
    return "";
  }
}

function renderTaskRuns(tableId, rows, emptyCentered = false, compact = false) {
  const columns = [];
  columns.push(
    { title: "Модуль", render: (r) => escapeHtml((state.modules.find((m) => m.id === r.module_id) || {}).name || r.module_id) },
    { title: "Цель", render: (r) => `${escapeHtml(r.target_type)}:${escapeHtml(r.target_id)}` },
    { title: "Статус", render: (r) => taskStatusBadge(r.status) },
    { title: "Запуск", render: (r) => formatDate(r.started_at || r.finished_at || r.created_at) },
    { title: "Результат", render: (r) => {
      const text = (r.stdout_text || r.stderr_text || "") || "";
      const summary = formatPerHostSummary(r);
      return compact
        ? `<span class="truncate-dashboard">${escapeHtml(text)} ${summary}</span>`
        : `<span class="truncate-history">${escapeHtml(text)} ${summary}</span>`;
    } },
    { title: "", render: (r) => {
      const text = (r.stdout_text || r.stderr_text || "") || "";
      const perHost = renderPerHostResults(r);
      const fullOutput = perHost ? `${text}\n\n--- По хостам ---\n${perHost}` : text;
      return `<button class="secondary" onclick="openOutputModal(\`${escapeHtml(fullOutput)}\`, 'Результат задачи #${r.id}')" title="Показать">${EYE_ICON}</button>`;
    } },
  );
  renderTable(tableId, columns, rows, "Нет данных", emptyCentered);
}

function renderHistoryTable() {
  renderTaskRuns("history-table", state.taskRuns);
}

function renderRunResult(run) {
  if (!run) return;
  const perHost = renderPerHostResults(run);
  const stdout = run.stdout_text || "";
  const stderr = run.stderr_text || "";
  const output = [stdout, stderr ? `--- stderr ---\n${stderr}` : "", perHost]
    .filter(Boolean)
    .join("\n\n");
  byId("run-result").textContent = output || `Задача #${run.id} завершена со статусом ${run.status}`;
  byId("expand-output-btn").style.display = "inline-flex";
  updateRunCancelButton(run);
}

function updateRunCancelButton(run) {
  const btn = byId("cancel-run-btn");
  if (!btn) return;
  btn.disabled = run.status !== "running" && run.status !== "pending";
  btn.style.display = run.status === "running" || run.status === "pending" ? "inline-flex" : "none";
}

function renderInventory(tableId, rows) {
  renderTable(tableId, [
    { title: "ID", key: "id" },
    { title: "Host ID", key: "host_id" },
    { title: "Hostname", key: "hostname" },
    { title: "OS", render: (r) => `<span class="truncate">${escapeHtml(r.os_name || "")}</span>` },
    { title: "Kernel", key: "kernel" },
    { title: "RAM MB", key: "ram_mb" },
    { title: "Disk free GB", key: "disks_free_gb" },
    { title: "Дата", render: (r) => formatDate(r.collected_at) },
  ], rows);
}

function renderScheduled(tableId, rows) {
  renderTable(tableId, [
    { title: "Название", key: "name" },
    { title: "Шаблон", render: (r) => escapeHtml((state.templates.find((t) => t.id === r.template_id) || {}).name || r.template_id) },
    { title: "Цель", render: (r) => {
      const targetName = (currentTargets(r.target_type).find((t) => t.id === r.target_id) || {}).name || r.target_id;
      return `${r.target_type === "host" ? "хост" : "группа"}:${escapeHtml(targetName)}`;
    } },
    { title: "Запуск", render: (r) => formatDate(r.run_at) },
    { title: "Активна", render: (r) => `
      <label style="display:inline-flex;align-items:center;gap:6px;cursor:pointer;font-weight:650;">
        <input type="checkbox" ${r.is_enabled ? "checked" : ""} onchange="toggleSchedule(${r.id}, this.checked)">
        ${r.is_enabled ? "Да" : "Нет"}
      </label>` },
    { title: "", render: (r) => `
      <div class="row-actions">
        <button class="secondary schedule-edit-btn" data-schedule-id="${r.id}" title="Редактировать">
          <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>
        </button>
        <button class="secondary schedule-delete-btn" style="color:var(--error)" data-schedule-id="${r.id}" title="Удалить">${ICON_DELETE}</button>
      </div>` },
  ], rows);
}

window.deleteSchedule = async function (id) {
  if (!confirm("Удалить запланированную задачу?")) return;
  try {
    await api("/api/schedule/delete", { method: "POST", body: JSON.stringify({ id }) });
    showToast("Задача удалена");
    await loadScheduled();
  } catch (error) {
    showToast(error.message, "error");
  }
};

function renderReports(rows) {
  const container = byId("reports-list");
  if (!rows || rows.length === 0) {
    container.innerHTML = `<p class="muted">Нет сформированных отчётов</p>`;
    return;
  }
  container.innerHTML = rows.map((r) => {
    const name = escapeHtml(r.name || `Отчёт #${r.id}`);
    const fileName = escapeHtml(r.file_path.replace(/^.*[\\/]/, ""));
    let summary = "";
    try {
      const s = JSON.parse(r.summary_json || "{}");
      if (r.report_type === "host_status") {
        summary = `хостов: ${s.total || 0}, доступно: ${s.active || 0}, недоступно: ${s.inactive || 0}`;
      } else if (r.report_type === "filesystem") {
        summary = `хостов: ${s.hosts || 0}`;
      } else if (r.report_type === "task_history") {
        summary = `запусков: ${s.total || 0}`;
      } else {
        summary = `записей: ${s.rows || 0}`;
      }
    } catch {
      summary = "";
    }
    return `
    <div class="report-item" role="button" data-file-path="${fileName}" data-name="${name}">
      <div class="report-info">
        <strong>${name}</strong>
        <span class="report-date">${formatDate(r.created_at)}${summary ? ` • ${summary}` : ""}</span>
      </div>
      <div class="report-actions">
        <button class="secondary" onclick="event.stopPropagation(); viewReport('${fileName}', '${name}')" title="Просмотр">${EYE_ICON}</button>
      </div>
    </div>
  `}).join("");
}

window.viewReport = async function(filePath, title) {
  try {
    const fileName = filePath.replace(/^.*[\\/]/, "");
    const text = await fetch(`/reports/${encodeURIComponent(fileName)}`).then(r => r.text());
    openOutputModal(text, title);
  } catch (error) {
    showToast(error.message, "error");
  }
};

function renderKeys(rows) {
  renderTable("keys-table", [
    { title: "Имя", key: "name" },
    { title: "Тип", render: (r) => escapeHtml(r.key_type || "—") },
    { title: "Fingerprint", render: (r) => `<span class="truncate">${escapeHtml(r.fingerprint || "—")}</span>` },
    { title: "Создан", render: (r) => formatDate(r.created_at) },
    { title: "По умолчанию", render: (r) => booleanBadge(r.is_default) },
    { title: "", render: (r) => `
      <div class="row-actions">
        <button class="secondary" onclick="viewKeyPublic(${r.id})" title="Показать публичный ключ">${EYE_ICON}</button>
      </div>` },
  ], rows, "Нет сохранённых ключей");
}

window.viewKeyPublic = async function(id) {
  const key = state.sshKeys.find((k) => k.id === id);
  if (!key || !key.public_key) {
    showToast("Публичный ключ не найден", "error");
    return;
  }
  const text = `${key.public_key}\n\nFingerprint: ${key.fingerprint || "—"}\nType: ${key.key_type || "—"}`;
  openOutputModal(text, `Публичный ключ: ${key.name}`);
};

function filterHosts(rows) {
  const search = (byId("host-search")?.value || "").toLowerCase();
  const groupId = byId("host-group-filter")?.value || "";
  let filtered = rows;
  if (search) {
    filtered = filtered.filter((h) =>
      `${h.name} ${h.address} ${h.username} ${h.description}`.toLowerCase().includes(search)
    );
  }
  if (groupId === "none") {
    filtered = filtered.filter((h) => !h.group_id);
  } else if (groupId) {
    const group = state.groups.find((g) => String(g.id) === groupId);
    if (group) {
      const groupHostIds = (group.hosts || []).map((h) => h.id || h);
      filtered = filtered.filter((h) => groupHostIds.includes(h.id));
    }
  }
  return filtered;
}

async function loadSSHKeys() {
  const keys = await api("/api/ssh-keys");
  state.sshKeys = keys;
  const defaultOption = { id: "", name: "По умолчанию" };
  const keyLabel = (k) => `${k.name || "Без имени"} (${k.key_type || k.private_key_path || ""})`;
  fillSelect(byId("host-key"), [defaultOption, ...keys], keyLabel);
  fillSelect(byId("host-edit-key"), [defaultOption, ...keys], keyLabel);
}

async function loadHosts() {
  await loadBaseLists();
  await loadSSHKeys();
  fillSelect(byId("host-group"), [{ id: "", name: "Без группы" }, ...state.groups], (g) => g.name || "Без имени");
  fillSelect(byId("host-group-filter"), [{ id: "", name: "Все хосты" }, { id: "none", name: "Без группы" }, ...state.groups], (g) => g.name || "Без имени");
  renderHosts(state.hosts);
  renderGroups(state.groups);
}

async function loadModules() {
  await loadBaseLists();
  renderModules(state.modules);
}

async function loadHistory() {
  await loadBaseLists();
  const rows = await api("/api/task-runs?limit=100");
  state.taskRuns = rows;
  renderHistoryTable();
  connectWebSocket();
}

async function loadInventory() {
  const rows = await api("/api/inventory");
  renderInventory("inventory-table", rows);
}

async function loadScheduled() {
  await loadBaseLists();
  const rows = await api("/api/scheduled");
  state.scheduled = rows;
  renderScheduled("scheduled-table", rows);
}

async function loadReports() {
  const [rows, taskRuns] = await Promise.all([api("/api/reports"), api("/api/task-runs?limit=100")]);
  fillTaskRunSelectForReport(taskRuns);
  renderReports(rows);
}

function fillTaskRunSelectForReport(rows) {
  const select = byId("report-task-run");
  if (!rows || rows.length === 0) {
    select.innerHTML = `<option value="">Нет запусков</option>`;
    return;
  }
  select.innerHTML = rows.map((r) => {
    const moduleName = (state.modules.find((m) => m.id === r.module_id) || {}).name || r.module_id;
    const target = `${r.target_type}:${r.target_id}`;
    const status = r.status === "success" ? "✓" : r.status === "error" ? "✗" : "○";
    return `<option value="${r.id}">#${r.id} ${status} ${moduleName} → ${target}</option>`;
  }).join("");
}

async function loadRunView(preselectedSlug) {
  await loadBaseLists();
  if (preselectedSlug) {
    fillModuleSelect(preselectedSlug);
  }
}

async function loadKeys() {
  const keys = await api("/api/ssh-keys");
  state.sshKeys = keys;
  renderKeys(keys);
}

async function loadCurrentView(opts = {}) {
  try {
    if (state.view === "dashboard") await loadDashboard();
    if (state.view === "hosts") await loadHosts();
    if (state.view === "keys") await loadKeys();
    if (state.view === "modules") await loadModules();
    if (state.view === "run") await loadRunView(opts.preselectedSlug);
    if (state.view === "history") await loadHistory();
    if (state.view === "inventory") await loadInventory();
    if (state.view === "schedule") await loadScheduled();
    if (state.view === "reports") await loadReports();
  } catch (error) {
    showToast(error.message, "error");
  }
}

window.playModule = function(slug) {
  switchView("run", { preselectedSlug: slug });
};

window.openOutputModal = function(text, title) {
  byId("modal-output").textContent = text;
  byId("output-modal").querySelector("h3").textContent = title || "Результат выполнения";
  byId("output-modal").classList.add("active");
};

window.closeOutputModal = function() {
  byId("output-modal").classList.remove("active");
};

function exportText(text, filename) {
  const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename || "report.txt";
  a.click();
  URL.revokeObjectURL(url);
  showToast("Отчёт сохранён");
}

window.deleteHost = async function(id) {
  if (!confirm(`Удалить хост #${id}?`)) return;
  try {
    await api("/api/hosts/delete", { method: "POST", body: JSON.stringify({ id }) });
    showToast("Хост удалён");
    await loadHosts();
  } catch (error) {
    showToast(error.message, "error");
  }
};

window.checkHost = async function(id, btn) {
  const icon = btn.querySelector("svg");
  icon?.classList.add("spinning");
  try {
    const result = await api("/api/hosts/check", { method: "POST", body: JSON.stringify({ id }) });
    showToast(`Хост ${result.name}: ${result.is_active ? "доступен" : "недоступен"}`);
    await loadHosts();
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    icon?.classList.remove("spinning");
  }
};

window.checkAllHosts = async function() {
  const btn = byId("check-all-hosts-btn");
  const icon = btn.querySelector("svg");
  icon?.classList.add("spinning");
  try {
    const result = await api("/api/hosts/check-all", { method: "POST", body: JSON.stringify({}) });
    showToast(`Проверено: ${result.checked} хостов, доступно ${result.active}`);
    await loadHosts();
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    icon?.classList.remove("spinning");
  }
};

window.editHost = function(id) {
  const host = state.hosts.find(h => h.id === id);
  if (!host) return;
  fillSelect(byId("host-edit-group"), [{ id: "", name: "Без группы" }, ...state.groups], (g) => g.name || "Без имени");
  byId("host-edit-id").value = host.id;
  byId("host-edit-name").value = host.name;
  byId("host-edit-username").value = host.username;
  byId("host-edit-address").value = host.address;
  byId("host-edit-port").value = host.port;
  byId("host-edit-group").value = host.group_id || "";
  byId("host-edit-key").value = host.ssh_key_id || "";
  byId("host-edit-description").value = host.description || "";
  byId("host-edit-key-path-text").value = "";
  byId("host-edit-key-file").value = "";
  byId("host-edit-modal").classList.add("active");
};

window.editGroup = function(id) {
  const group = state.groups.find(g => g.id === id);
  if (!group) return;
  byId("group-edit-id").value = group.id;
  byId("group-edit-name").value = group.name;
  byId("group-edit-description").value = group.description || "";
  byId("group-edit-modal").classList.add("active");
};

window.deleteGroup = async function(id) {
  const group = state.groups.find(g => g.id === id);
  if (!confirm(`Удалить группу "${group?.name || id}"? Хосты в группе останутся без группы.`)) return;
  try {
    await api("/api/groups/delete", { method: "POST", body: JSON.stringify({ id }) });
    showToast("Группа удалена");
    await loadHosts();
  } catch (error) {
    showToast(error.message, "error");
  }
};

function closeHostEditModal() {
  byId("host-edit-modal").classList.remove("active");
}

function closeGroupEditModal() {
  byId("group-edit-modal").classList.remove("active");
}

window.deleteModule = async function(id) {
  if (!confirm(`Удалить модуль #${id}?`)) return;
  try {
    await api("/api/modules/delete", { method: "POST", body: JSON.stringify({ id }) });
    showToast("Модуль удалён");
    await loadModules();
  } catch (error) {
    showToast(error.message, "error");
  }
};

window.editModule = function(id) {
  const module = state.modules.find((m) => m.id === id);
  if (!module) return;
  byId("module-edit-id").value = module.id;
  byId("module-edit-name").value = module.name;
  byId("module-edit-slug").value = module.slug;
  byId("module-edit-description").value = module.description || "";
  byId("module-edit-enabled").checked = Boolean(module.is_enabled);
  byId("module-edit-modal").classList.add("active");
};

function closeModuleEditModal() {
  byId("module-edit-modal").classList.remove("active");
}

window.clearHistory = async function() {
  if (!confirm("Очистить всю историю выполненных задач?")) return;
  try {
    await api("/api/task-runs/clear", { method: "POST", body: JSON.stringify({}) });
    showToast("История очищена");
    await loadHistory();
  } catch (error) {
    showToast(error.message, "error");
  }
};

window.editSchedule = function(id) {
  const task = state.scheduled.find((s) => s.id === id);
  if (!task) return;
  fillSelect(byId("schedule-edit-template"), state.templates, (item) => `${item.name} #${item.id}`);
  fillSelect(byId("schedule-edit-target"), currentTargets(task.target_type), (item) => `${item.name || "Без имени"} #${item.id}`);
  byId("schedule-edit-id").value = task.id;
  byId("schedule-edit-name").value = task.name;
  byId("schedule-edit-template").value = task.template_id;
  byId("schedule-edit-target-type").value = task.target_type;
  byId("schedule-edit-target").value = task.target_id;
  byId("schedule-edit-run-at").value = task.run_at ? task.run_at.slice(0, 16) : "";
  byId("schedule-edit-enabled").checked = Boolean(task.is_enabled);
  byId("schedule-edit-modal").classList.add("active");
};

function closeScheduleEditModal() {
  byId("schedule-edit-modal").classList.remove("active");
}

window.toggleSchedule = async function(id, enabled) {
  try {
    await api("/api/schedule/update", {
      method: "POST",
      body: JSON.stringify({ id, is_enabled: enabled }),
    });
    showToast(enabled ? "Задача активирована" : "Задача отключена");
    await loadScheduled();
  } catch (error) {
    showToast(error.message, "error");
  }
};

function formDataObject(form) {
  return Object.fromEntries(new FormData(form).entries());
}

function toLocalISO(date) {
  const pad = (n) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}${getOffset(date)}`;
}

function getOffset(date) {
  const offset = -date.getTimezoneOffset();
  const sign = offset >= 0 ? "+" : "-";
  const h = pad(Math.floor(Math.abs(offset) / 60));
  const m = pad(Math.abs(offset) % 60);
  return `${sign}${h}:${m}`;
}

function pad(n) {
  return String(n).padStart(2, "0");
}

function scheduleRunAt() {
  const input = byId("schedule-run-at");
  if (!input) return "";
  if (!input.value) return "";
  return toLocalISO(new Date(input.value));
}

document.addEventListener("DOMContentLoaded", async () => {
  document.querySelectorAll(".nav-link").forEach((button) => {
    button.addEventListener("click", () => switchView(button.dataset.view));
  });

  byId("run-target-type").addEventListener("change", updateTargetSelects);
  byId("schedule-target-type").addEventListener("change", updateTargetSelects);
  byId("run-module").addEventListener("change", updateRunFormVisibility);

  byId("modal-close-btn").addEventListener("click", closeOutputModal);
  byId("output-modal").addEventListener("click", (e) => {
    if (e.target === byId("output-modal")) closeOutputModal();
  });
  byId("modal-copy-btn").addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(byId("modal-output").textContent);
      showToast("Скопировано в буфер обмена");
    } catch (error) {
      showToast("Не удалось скопировать", "error");
    }
  });
  byId("modal-export-btn").addEventListener("click", () => {
    exportText(byId("modal-output").textContent, "report.txt");
  });

  byId("expand-output-btn").addEventListener("click", () => {
    const text = byId("run-result").textContent;
    openOutputModal(text, "Результат запуска");
  });

  async function readFileData(file) {
    if (!file) return null;
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result.split(",")[1]);
      reader.onerror = () => reject(reader.error);
      reader.readAsDataURL(file);
    });
  }

  byId("host-key-path-text").addEventListener("click", () => byId("host-key-file").click());
  byId("host-key-file").addEventListener("change", (event) => {
    const file = event.target.files[0];
    if (file) {
      byId("host-key-path-text").value = file.name;
    }
  });

  byId("host-edit-key-path-text").addEventListener("click", () => byId("host-edit-key-file").click());
  byId("host-edit-key-file").addEventListener("change", (event) => {
    const file = event.target.files[0];
    if (file) {
      byId("host-edit-key-path-text").value = file.name;
    }
  });

  byId("key-generate-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const data = formDataObject(form);
    const resultContainer = byId("key-generate-result");
    resultContainer.innerHTML = "";
    try {
      const result = await api("/api/keys/generate", {
        method: "POST",
        body: JSON.stringify(data),
      });
      resultContainer.innerHTML = `
        <div class="panel" style="margin-top:8px;padding:14px;">
          <p><strong>Ключ создан:</strong> ${escapeHtml(result.name)} (${escapeHtml(result.key_type)})</p>
          <p><strong>Fingerprint:</strong> <span class="truncate">${escapeHtml(result.fingerprint)}</span></p>
          <label style="margin-top:10px;">Публичный ключ
            <textarea id="generated-public-key" readonly rows="4">${escapeHtml(result.public_key)}</textarea>
          </label>
          <div class="form-actions" style="margin-top:10px;">
            <button type="button" class="secondary" onclick="copyGeneratedPublicKey()">${ICON_COPY} <span>Копировать</span></button>
            <button type="button" class="secondary" onclick="exportText(byId('generated-public-key').value, '${escapeHtml(result.name)}.pub')">${ICON_SAVE} <span>Сохранить</span></button>
          </div>
        </div>
      `;
      form.reset();
      await loadKeys();
    } catch (error) {
      showToast(error.message, "error");
    }
  });

  window.copyGeneratedPublicKey = function() {
    const textarea = byId("generated-public-key");
    if (!textarea) return;
    navigator.clipboard.writeText(textarea.value).then(() => showToast("Скопировано"), () => showToast("Не удалось скопировать", "error"));
  };

  byId("host-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const data = formDataObject(form);
    data.port = Number(data.port || 22);
    try {
      const file = byId("host-key-file").files[0];
      if (file) {
        const fileData = await readFileData(file);
        const key = await api("/api/ssh-keys", {
          method: "POST",
          body: JSON.stringify({ name: file.name, file_data: fileData }),
        });
        data.ssh_key_id = key.id;
      } else {
        data.ssh_key_id = data.ssh_key_id ? Number(data.ssh_key_id) : null;
      }
      data.group_id = data.group_id ? Number(data.group_id) : null;
      delete data.ssh_key_path;
      if (!data.password) {
        delete data.password;
      }
      const host = await api("/api/hosts", { method: "POST", body: JSON.stringify(data) });
      if (data.group_id) {
        await api("/api/groups/add-host", { method: "POST", body: JSON.stringify({ group_id: data.group_id, host_id: host.id }) });
      }
      showToast("Хост добавлен");
      form.reset();
      byId("host-key-path-text").value = "";
      byId("host-key-file").value = "";
      await loadHosts();
    } catch (error) {
      showToast(error.message, "error");
    }
  });

  byId("host-search").addEventListener("input", () => renderHosts(state.hosts));
  byId("host-group-filter").addEventListener("change", () => renderHosts(state.hosts));
  byId("check-all-hosts-btn").addEventListener("click", checkAllHosts);

  byId("host-edit-close-btn").addEventListener("click", closeHostEditModal);
  byId("host-edit-modal").addEventListener("click", (e) => {
    if (e.target === byId("host-edit-modal")) closeHostEditModal();
  });
  byId("host-edit-save-btn").addEventListener("click", async () => {
    const form = byId("host-edit-form");
    const data = formDataObject(form);
    data.id = Number(data.id);
    data.port = Number(data.port || 22);
    try {
      const file = byId("host-edit-key-file").files[0];
      if (file) {
        const fileData = await readFileData(file);
        const key = await api("/api/ssh-keys", {
          method: "POST",
          body: JSON.stringify({ name: file.name, file_data: fileData }),
        });
        data.ssh_key_id = key.id;
      } else {
        data.ssh_key_id = data.ssh_key_id ? Number(data.ssh_key_id) : null;
      }
      data.group_id = data.group_id ? Number(data.group_id) : null;
      delete data.ssh_key_path;
      if (!data.password) {
        delete data.password;
      }
      await api("/api/hosts/update", { method: "POST", body: JSON.stringify(data) });
      showToast("Хост обновлён");
      closeHostEditModal();
      await loadHosts();
    } catch (error) {
      showToast(error.message, "error");
    }
  });

  function closeGroupCreateModal() {
    byId("group-create-modal").classList.remove("active");
    byId("group-create-form").reset();
  }

  byId("create-group-btn").addEventListener("click", () => {
    byId("group-create-modal").classList.add("active");
    byId("group-create-name").focus();
  });

  byId("group-create-close-btn").addEventListener("click", closeGroupCreateModal);
  byId("group-create-modal").addEventListener("click", (e) => {
    if (e.target === byId("group-create-modal")) closeGroupCreateModal();
  });
  byId("group-create-save-btn").addEventListener("click", async () => {
    const form = byId("group-create-form");
    const data = formDataObject(form);
    try {
      await api("/api/groups", { method: "POST", body: JSON.stringify(data) });
      showToast("Группа создана");
      closeGroupCreateModal();
      await loadHosts();
    } catch (error) {
      showToast(error.message, "error");
    }
  });

  byId("group-edit-close-btn").addEventListener("click", closeGroupEditModal);
  byId("group-edit-modal").addEventListener("click", (e) => {
    if (e.target === byId("group-edit-modal")) closeGroupEditModal();
  });
  byId("group-edit-save-btn").addEventListener("click", async () => {
    const form = byId("group-edit-form");
    const data = formDataObject(form);
    data.id = Number(data.id);
    try {
      await api("/api/groups/update", { method: "POST", body: JSON.stringify(data) });
      showToast("Группа обновлена");
      closeGroupEditModal();
      await loadHosts();
    } catch (error) {
      showToast(error.message, "error");
    }
  });

  byId("module-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const data = formDataObject(form);
    data.class_name = "UserModule";
    const file = byId("module-file").files[0];
    if (file) {
      data.module_path = `/modules/${file.name}`;
      data.file_data = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result.split(",")[1]);
        reader.onerror = () => reject(reader.error);
        reader.readAsDataURL(file);
      });
    }
    try {
      await api("/api/modules", { method: "POST", body: JSON.stringify(data) });
      showToast("Модуль добавлен");
      form.reset();
      byId("module-path-text").value = "";
      await loadModules();
    } catch (error) {
      showToast(error.message, "error");
    }
  });

  byId("module-path-text").addEventListener("click", () => byId("module-file").click());
  byId("module-file").addEventListener("change", (event) => {
    const file = event.target.files[0];
    if (file) {
      byId("module-path-text").value = `/modules/${file.name}`;
    }
  });

  byId("module-edit-close-btn").addEventListener("click", closeModuleEditModal);
  byId("module-edit-modal").addEventListener("click", (e) => {
    if (e.target === byId("module-edit-modal")) closeModuleEditModal();
  });
  byId("module-edit-save-btn").addEventListener("click", async () => {
    const form = byId("module-edit-form");
    const data = formDataObject(form);
    data.id = Number(data.id);
    data.is_enabled = byId("module-edit-enabled").checked;
    try {
      await api("/api/modules/update", { method: "POST", body: JSON.stringify(data) });
      showToast("Модуль обновлён");
      closeModuleEditModal();
      await loadModules();
    } catch (error) {
      showToast(error.message, "error");
    }
  });

  byId("schedule-edit-target-type").addEventListener("change", () => {
    fillSelect(byId("schedule-edit-target"), currentTargets(byId("schedule-edit-target-type").value), (item) => `${item.name || "Без имени"} #${item.id}`);
  });
  byId("scheduled-table").addEventListener("click", (e) => {
    const editBtn = e.target.closest(".schedule-edit-btn");
    if (editBtn) editSchedule(Number(editBtn.dataset.scheduleId));
    const deleteBtn = e.target.closest(".schedule-delete-btn");
    if (deleteBtn) deleteSchedule(Number(deleteBtn.dataset.scheduleId));
  });
  byId("schedule-edit-close-btn").addEventListener("click", closeScheduleEditModal);
  byId("schedule-edit-modal").addEventListener("click", (e) => {
    if (e.target === byId("schedule-edit-modal")) closeScheduleEditModal();
  });
  byId("schedule-edit-save-btn").addEventListener("click", async () => {
    const form = byId("schedule-edit-form");
    const data = formDataObject(form);
    data.id = Number(data.id);
    data.template_id = Number(data.template_id);
    data.target_id = Number(data.target_id);
    data.is_enabled = byId("schedule-edit-enabled").checked;
    const runAtInput = byId("schedule-edit-run-at").value;
    data.run_at = runAtInput ? toLocalISO(new Date(runAtInput)) : "";
    try {
      await api("/api/schedule/update", { method: "POST", body: JSON.stringify(data) });
      showToast("Задача обновлена");
      closeScheduleEditModal();
      await loadScheduled();
    } catch (error) {
      showToast(error.message, "error");
    }
  });

  byId("run-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = formDataObject(event.currentTarget);
    const args = {};
    if (data.module_slug === "mass_ssh") {
      args.command = data.command || "uname -a";
    } else if (data.module_slug === "apt_package_manager") {
      args.action = data.apt_action || "update";
      args.packages = data.apt_packages || "";
      args.sudo_password = data.apt_sudo_password || null;
    }

    byId("run-result").textContent = "Запуск задачи...";
    byId("expand-output-btn").style.display = "none";
    try {
      const { run_id } = await api("/api/run", {
        method: "POST",
        body: JSON.stringify({
          module_slug: data.module_slug,
          target_type: data.target_type,
          target_id: Number(data.target_id),
          args,
        }),
      });
      state.currentRunId = run_id;
      connectWebSocket();
      subscribeToRun(run_id);
      byId("run-result").textContent = `Задача #${run_id} запущена, ожидание результатов...`;
      updateRunCancelButton({ status: "running" });

      const poll = async () => {
        const run = await api(`/api/run/${run_id}/status`);
        renderRunResult(run);
        if (run.status === "running" || run.status === "pending") {
          setTimeout(poll, 1000);
          return;
        }
        state.currentRunId = null;
        showToast(run.status === "success" ? "Задача завершена" : "Задача завершена", run.status === "success" ? "ok" : "error");
      };
      poll();
    } catch (error) {
      byId("run-result").textContent = error.message;
      showToast(error.message, "error");
    }
  });

  byId("cancel-run-btn")?.addEventListener("click", async () => {
    if (!state.currentRunId) return;
    try {
      const result = await api(`/api/run/${state.currentRunId}/cancel`, {
        method: "POST",
        body: JSON.stringify({}),
      });
      if (result.cancelled) {
        showToast("Задача отменена");
      } else {
        showToast("Задача уже не активна", "error");
      }
    } catch (error) {
      showToast(error.message, "error");
    }
  });

  byId("schedule-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = formDataObject(event.currentTarget);
    data.template_id = Number(data.template_id);
    data.target_id = Number(data.target_id);
    data.run_at = scheduleRunAt();
    try {
      await api("/api/schedule", { method: "POST", body: JSON.stringify(data) });
      showToast("Запланированная задача создана");
      event.currentTarget.reset();
      await loadScheduled();
    } catch (error) {
      showToast(error.message, "error");
    }
  });

  byId("scheduler-tick-btn").addEventListener("click", async () => {
    try {
      await api("/api/scheduler/tick", { method: "POST", body: JSON.stringify({}) });
      showToast("Планировщик проверен");
      await loadScheduled();
    } catch (error) {
      showToast(error.message, "error");
    }
  });

  byId("reports-list").addEventListener("click", (e) => {
    const item = e.target.closest(".report-item");
    if (!item) return;
    viewReport(item.dataset.filePath, item.dataset.name);
  });

  function openReportsClearModal() {
    byId("reports-clear-modal").classList.add("active");
  }

  function closeReportsClearModal() {
    byId("reports-clear-modal").classList.remove("active");
  }

  byId("reports-clear-btn").addEventListener("click", openReportsClearModal);
  byId("reports-clear-cancel-btn").addEventListener("click", closeReportsClearModal);
  byId("reports-clear-modal").addEventListener("click", (e) => {
    if (e.target === byId("reports-clear-modal")) closeReportsClearModal();
  });
  byId("reports-clear-confirm-btn").addEventListener("click", async () => {
    try {
      await api("/api/reports/clear", { method: "POST", body: JSON.stringify({}) });
      showToast("Отчёты очищены");
      closeReportsClearModal();
      await loadReports();
    } catch (error) {
      showToast(error.message, "error");
    }
  });

  byId("report-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = formDataObject(event.currentTarget);
    data.task_run_id = Number(data.task_run_id || 0);
    if (!data.task_run_id) {
      showToast("Выберите задачу", "error");
      return;
    }
    try {
      const result = await api("/api/reports/export", { method: "POST", body: JSON.stringify(data) });
      const summary = result.report?.summary_json ? JSON.parse(result.report.summary_json) : {};
      const summaryText = `задача: ${summary.module_name || '—'}, хостов: ${summary.hosts || 0}, статус: ${summary.status || '—'}`;
      byId("report-result").textContent = `Отчёт сформирован: ${result.file_path}\n${summaryText}`;
      showToast("Отчёт сформирован");
      await loadReports();
    } catch (error) {
      showToast(error.message, "error");
    }
  });

  await loadBaseLists();
  await loadDashboard();
});
