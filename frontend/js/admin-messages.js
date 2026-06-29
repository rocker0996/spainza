/**
 * Management-only read-only message audit (01admin.html).
 */
(function () {
  const API_BASES = (function resolveApiBases() {
    if (window.API_BASE_URL) {
      return [String(window.API_BASE_URL).replace(/\/+$/, "")];
    }
    if (window.location.protocol === "file:") {
      return ["http://localhost:5000/api"];
    }
    const localHosts = ["localhost", "127.0.0.1", "0.0.0.0"];
    const isLocalHost = localHosts.includes(window.location.hostname);
    if (isLocalHost && window.location.port && window.location.port !== "5000") {
      return [
        "/api",
        window.location.protocol + "//" + window.location.hostname + ":5000/api",
      ];
    }
    return ["/api"];
  })();

  function normalizeUserId(value) {
    const n = Number(value);
    return Number.isFinite(n) && n > 0 ? n : null;
  }

  function t(key, params) {
    return window.LkI18n ? window.LkI18n.t(key, params) : key;
  }

  function roleLabel(roleKey) {
    return window.LkI18n ? window.LkI18n.roleLabel(roleKey) : roleKey || "";
  }

  function buildProtectedApiUrl(relativeUrl) {
    const normalized = String(relativeUrl || "").trim();
    if (!normalized) {
      return "";
    }
    return normalized.startsWith("/") ? normalized : `/${normalized}`;
  }

  async function apiFetch(path, options = {}) {
    const headers = { ...(options.headers || {}) };
    if (options.body && !(options.body instanceof FormData)) {
      headers["Content-Type"] = "application/json";
    }

    let lastError = null;
    for (const base of API_BASES) {
      try {
        const url = `${base}${path}`;
        const response = await fetch(url, { ...options, credentials: "include", headers });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
          const err = new Error(data.error || response.statusText || "request failed");
          err.status = response.status;
          err.payload = data;
          throw err;
        }
        return data;
      } catch (error) {
        lastError = error;
      }
    }
    throw lastError || new Error("network error");
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function formatTime(iso) {
    if (!iso) return "";
    const date = window.LkI18n?.parseInstant(iso) || new Date(iso);
    if (Number.isNaN(date.getTime())) return "";
    const now = new Date();
    const locale = window.LkI18n?.getLocale() === "en" ? "en-US" : "ru-RU";
    if (date.toDateString() === now.toDateString()) {
      return date.toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit" });
    }
    return date.toLocaleDateString(locale, { day: "numeric", month: "short" });
  }

  function initials(name) {
    const parts = String(name || "?").trim().split(/\s+/).filter(Boolean);
    if (!parts.length) return "?";
    return parts
      .slice(0, 2)
      .map((p) => p[0])
      .join("")
      .toUpperCase();
  }

  function getFileIcon(extension) {
    const iconMap = {
      pdf: "picture_as_pdf",
      doc: "description",
      docx: "description",
      zip: "folder_zip",
      png: "image",
      jpg: "image",
      jpeg: "image",
    };
    return iconMap[extension] || "insert_drive_file";
  }

  const MOBILE_MQ = window.matchMedia("(max-width: 767px)");

  const els = {
    pageWrap: document.getElementById("audit-page-wrap"),
    root: document.getElementById("audit-main"),
    columns: document.getElementById("audit-columns"),
    usersList: document.getElementById("audit-users-list"),
    userSearch: document.getElementById("audit-user-search"),
    convList: document.getElementById("audit-conversations-list"),
    convSearch: document.getElementById("audit-conversation-search"),
    subjectChip: document.getElementById("audit-subject-chip"),
    convCount: document.getElementById("audit-conversations-count"),
    messagesWrap: document.getElementById("audit-messages-container"),
    messages: document.getElementById("audit-messages-scroll"),
    threadTitle: document.getElementById("audit-thread-title"),
    threadMeta: document.getElementById("audit-thread-meta"),
    threadAvatars: document.getElementById("audit-thread-avatars"),
    emptyUsers: document.getElementById("audit-empty-users"),
    emptyConvs: document.getElementById("audit-empty-conversations"),
    emptyThread: document.getElementById("audit-empty-thread"),
    backUsers: document.getElementById("audit-back-users"),
    backConvs: document.getElementById("audit-back-conversations"),
    viewerInitial: document.getElementById("audit-viewer-initial"),
  };

  if (!els.root || !els.usersList) {
    return;
  }

  let allUsers = [];
  let conversations = [];
  let selectedSubject = null;
  let selectedConversationId = null;
  let subjectUserId = null;
  let eventsBound = false;
  let appReady = false;
  let usersLoading = false;

  function isMobile() {
    return MOBILE_MQ.matches;
  }

  function viewRoot() {
    return els.columns || els.root;
  }

  function setMobilePane(pane) {
    const target = viewRoot();
    if (!target) return;
    if (!isMobile()) {
      target.classList.remove(
        "audit-view-users",
        "audit-view-conversations",
        "audit-view-thread"
      );
      return;
    }
    target.classList.remove(
      "audit-view-users",
      "audit-view-conversations",
      "audit-view-thread"
    );
    target.classList.add(`audit-view-${pane}`);
  }

  function setPanelEmpty(emptyEl, visible, text) {
    if (!emptyEl) return;
    if (visible) {
      if (text) emptyEl.textContent = text;
      emptyEl.classList.remove("hidden");
    } else {
      emptyEl.classList.add("hidden");
    }
  }

  function showDenied() {
    if (typeof window.redirectLkAccessDenied === "function") {
      window.redirectLkAccessDenied();
      return;
    }
    window.location.replace("./404.html");
  }

  function hasFullAccess(userData) {
    const perms = userData?.permissions;
    if (Array.isArray(perms) && perms.includes("full_access")) {
      return true;
    }
    const role = (userData?.role?.key || userData?.role_key || "").toLowerCase();
    return role === "management";
  }

  function canBootstrap(userData) {
    return Boolean(userData && userData.id != null && hasFullAccess(userData));
  }

  function parseSubjectFromUrl() {
    const params = new URLSearchParams(window.location.search);
    const raw = params.get("subject") || params.get("user_id");
    return normalizeUserId(raw);
  }

  function userHaystack(user) {
    return [
      user.name,
      user.email,
      user.display_id,
      user.role?.key,
      roleLabel(user.role?.key),
    ]
      .join(" ")
      .toLowerCase();
  }

  function renderUserAvatar(user, className) {
    if (user.avatar) {
      return `<img src="${escapeHtml(user.avatar)}" class="${className}" alt="" />`;
    }
    return `<div class="${className} bg-secondary-container/30 flex items-center justify-center text-secondary font-semibold text-sm shrink-0">${escapeHtml(initials(user.name))}</div>`;
  }

  function renderUsers() {
    const q = (els.userSearch?.value || "").trim().toLowerCase();
    const filtered = allUsers.filter((u) => !q || userHaystack(u).includes(q));

    if (!filtered.length) {
      els.usersList.innerHTML = "";
      setPanelEmpty(els.emptyUsers, true, t("adminAudit.noUsers"));
      return;
    }
    setPanelEmpty(els.emptyUsers, false);

    els.usersList.innerHTML = filtered
      .map((user) => {
        const uid = normalizeUserId(user.id);
        const active = subjectUserId === uid;
        const displayId = user.display_id || "—";
        const roleKey = user.role?.key || "user";
        return `
          <button type="button" data-user-id="${uid}" class="audit-user-row w-full text-left p-3 rounded-xl flex items-center gap-3 cursor-pointer transition-colors ${
            active
              ? "bg-primary-fixed/30 border border-primary-container/20"
              : "hover:bg-surface-container-low border border-transparent"
          }">
            ${renderUserAvatar(user, "w-10 h-10 rounded-full object-cover shrink-0")}
            <div class="flex-1 min-w-0">
              <div class="flex justify-between items-center gap-2 mb-0.5">
                <h4 class="font-semibold text-sm truncate">${escapeHtml(user.name || t("clients.noName"))}</h4>
                <span class="text-[10px] text-on-surface-variant font-mono shrink-0">${escapeHtml(displayId)}</span>
              </div>
              <span class="text-[10px] font-semibold tracking-wider text-secondary uppercase">${escapeHtml(roleLabel(roleKey))}</span>
            </div>
          </button>
        `;
      })
      .join("");
  }

  function renderConversations() {
    if (!selectedSubject) {
      els.convList.innerHTML = "";
      if (els.subjectChip) els.subjectChip.textContent = "";
      if (els.convCount) els.convCount.textContent = "";
      setPanelEmpty(els.emptyConvs, true, t("adminAudit.noUser"));
      return;
    }

    const chipId = selectedSubject.display_id || "—";
    if (els.subjectChip) {
      els.subjectChip.textContent = `${selectedSubject.name || "—"} · ${chipId}`;
    }

    const q = (els.convSearch?.value || "").trim().toLowerCase();
    const filtered = conversations.filter((c) => {
      if (!q) return true;
      const hay = [
        c.other_user_name,
        c.other_user_display_id,
        c.other_user_role,
        roleLabel(c.other_user_role),
        c.last_message,
      ]
        .join(" ")
        .toLowerCase();
      return hay.includes(q);
    });

    if (els.convCount) {
      els.convCount.textContent = `(${conversations.length})`;
    }

    if (!filtered.length) {
      els.convList.innerHTML = "";
      setPanelEmpty(els.emptyConvs, true, t("adminAudit.noConversations"));
      return;
    }
    setPanelEmpty(els.emptyConvs, false);

    els.convList.innerHTML = filtered
      .map((conv) => {
        const active = selectedConversationId === conv.id;
        const time = formatTime(conv.last_message_time || conv.last_message_at);
        const preview = conv.last_message || "";
        const hiddenBadge = conv.hidden_for_subject
          ? `<span class="text-[9px] uppercase tracking-wide text-amber-700 bg-amber-50 px-1.5 py-0.5 rounded ml-1">${escapeHtml(t("adminAudit.hiddenChat"))}</span>`
          : "";
        const avatar = conv.other_user_avatar
          ? `<img src="${escapeHtml(conv.other_user_avatar)}" class="w-10 h-10 rounded-full object-cover shrink-0 mt-0.5" alt="" />`
          : `<div class="w-10 h-10 rounded-full bg-surface-variant/50 flex items-center justify-center text-on-surface-variant text-sm font-semibold shrink-0 mt-0.5">${escapeHtml(initials(conv.other_user_name))}</div>`;

        return `
          <button type="button" data-conv-id="${escapeHtml(conv.id)}" class="audit-conv-row w-full text-left p-3 rounded-xl flex gap-3 transition-colors relative ${
            active
              ? "bg-primary-fixed/30 border border-primary-container/20"
              : "hover:bg-surface-container-low border border-transparent"
          }">
            ${active ? '<div class="absolute left-0 top-2 bottom-2 w-1 bg-primary-container rounded-r"></div>' : ""}
            ${avatar}
            <div class="flex-1 min-w-0 pl-1">
              <div class="flex justify-between items-start gap-2 mb-1">
                <div class="min-w-0">
                  <h4 class="font-semibold text-sm truncate">${escapeHtml(conv.other_user_name || "—")}</h4>
                  <span class="text-[10px] font-semibold tracking-wider text-outline uppercase">${escapeHtml(roleLabel(conv.other_user_role))}</span>
                  ${hiddenBadge}
                </div>
                <span class="text-[10px] text-on-surface-variant shrink-0">${escapeHtml(time)}</span>
              </div>
              <p class="text-xs text-on-surface-variant truncate">${escapeHtml(preview)}</p>
            </div>
          </button>
        `;
      })
      .join("");
  }

  function renderMessages(data) {
    if (!els.messages) return;

    if (!data || !selectedSubject) {
      setPanelEmpty(els.emptyThread, true, t("adminAudit.noChat"));
      els.messages.classList.add("hidden");
      els.messages.innerHTML = "";
      return;
    }

    setPanelEmpty(els.emptyThread, false);
    els.messages.classList.remove("hidden");

    const subject = data.subject;
    const other = data.other_user;
    const subjectRole = roleLabel(subject.role?.key);
    const otherRole = roleLabel(other.role?.key);

    if (els.threadTitle) {
      els.threadTitle.textContent = `${subject.name || "—"} ↔ ${other.name || "—"}`;
    }
    if (els.threadMeta) {
      els.threadMeta.textContent = `${data.conversation_id} · ${subjectRole} ↔ ${otherRole}`;
    }
    if (els.threadAvatars) {
      els.threadAvatars.innerHTML = `
        ${renderUserAvatar(subject, "w-10 h-10 rounded-full object-cover border-2 border-white z-10")}
        ${renderUserAvatar(other, "w-10 h-10 rounded-full object-cover border-2 border-white -ml-3 z-0")}
      `;
    }

    const messages = data.messages || [];
    if (!messages.length) {
      els.messages.innerHTML = `<p class="text-center text-sm text-on-surface-variant py-8 w-full">${escapeHtml(t("adminAudit.noConversations"))}</p>`;
      return;
    }

    const markup = messages
      .map((message) => {
        if (message.is_system_message) {
          const isDelete =
            window.LkI18n && window.LkI18n.isSystemDeleteMessage(message.message_text);
          const boxClass = isDelete
            ? "bg-red-50 px-4 py-2 rounded-xl flex items-center gap-2 border border-red-200 max-w-lg"
            : "bg-surface-variant/40 px-4 py-2 rounded-xl flex items-center gap-2 border border-surface-variant/50 max-w-lg";
          const icon = isDelete ? "delete" : "info";
          const iconClass = isDelete ? "text-red-600" : "text-outline";
          const textClass = isDelete ? "text-red-800" : "text-on-surface-variant";
          const timeClass = isDelete ? "text-red-500" : "text-outline";
          return `
            <div class="flex justify-center my-3">
              <div class="${boxClass}">
                <span class="material-symbols-outlined text-[16px] ${iconClass} shrink-0">${icon}</span>
                <span class="text-xs font-medium ${textClass} whitespace-pre-wrap break-words">${escapeHtml(
                  window.LkI18n
                    ? window.LkI18n.translateSystemMessage(message.message_text)
                    : message.message_text
                )}</span>
                <span class="text-[10px] ${timeClass} ml-1 shrink-0">${escapeHtml(formatTime(message.created_at))}</span>
              </div>
            </div>
          `;
        }

        const isSubject = normalizeUserId(message.sender_id) === subjectUserId;
        let content = "";
        if (message.image_url) {
          content += `<img src="${escapeHtml(buildProtectedApiUrl(message.image_url))}" class="max-w-full rounded-lg border border-white/20" alt="" />`;
        }
        if (message.file_url) {
          const fileName = message.file_name || "file";
          const ext = fileName.split(".").pop().toLowerCase();
          content += `
            <a href="${escapeHtml(buildProtectedApiUrl(message.file_url))}" download="${escapeHtml(fileName)}" class="flex items-center gap-3 p-2 bg-surface-container-low rounded-xl border border-surface-variant/30 hover:bg-surface-variant/20 transition-colors max-w-full">
              <span class="material-symbols-outlined text-primary text-[24px] shrink-0">${getFileIcon(ext)}</span>
              <div class="flex-1 min-w-0">
                <p class="text-sm font-medium truncate">${escapeHtml(fileName)}</p>
              </div>
              <span class="material-symbols-outlined text-outline text-[20px] shrink-0">download</span>
            </a>
          `;
        }
        if (message.message_text) {
          content += `<p class="text-sm whitespace-pre-wrap break-words">${escapeHtml(message.message_text)}</p>`;
        }

        const time = formatTime(message.created_at);
        if (isSubject) {
          return `
            <div class="flex gap-3 max-w-full self-end flex-row-reverse ml-auto">
              ${renderUserAvatar(subject, "w-8 h-8 rounded-full object-cover shrink-0 mt-auto")}
              <div class="flex flex-col gap-1 items-end min-w-0">
                <div class="bg-primary-container text-on-primary p-3.5 rounded-2xl rounded-br-sm shadow-sm max-w-full">${content}</div>
                <span class="text-[10px] text-on-surface-variant">${escapeHtml(time)}</span>
              </div>
            </div>
          `;
        }

        return `
          <div class="flex gap-3 max-w-full">
            ${message.sender_avatar ? `<img src="${escapeHtml(message.sender_avatar)}" class="w-8 h-8 rounded-full shrink-0 mt-auto object-cover" alt="" />` : `<div class="w-8 h-8 rounded-full bg-surface-variant/60 flex items-center justify-center text-xs shrink-0 mt-auto">${escapeHtml(initials(message.sender_name))}</div>`}
            <div class="flex flex-col gap-1 items-start min-w-0">
              <div class="bg-white border border-surface-variant/40 p-3.5 rounded-2xl rounded-bl-sm shadow-sm text-on-surface max-w-full">${content}</div>
              <span class="text-[10px] text-on-surface-variant">${escapeHtml(time)}</span>
            </div>
          </div>
        `;
      })
      .join("");

    els.messages.innerHTML = markup;
    if (els.messages) {
      els.messages.scrollTop = els.messages.scrollHeight;
    }
  }

  async function loadUsers() {
    if (usersLoading) return;
    usersLoading = true;
    try {
      const data = await apiFetch("/admin/messages/users");
      allUsers = (data.users || []).map((u) => ({
        ...u,
        id: normalizeUserId(u.id),
      }));
      renderUsers();
      const preset = parseSubjectFromUrl();
      if (preset && allUsers.some((u) => u.id === preset)) {
        await selectSubject(preset);
      }
    } catch (error) {
      console.error("loadUsers:", error);
      if (error.status === 403) {
        showDenied();
        return;
      }
      allUsers = [];
      renderUsers();
      setPanelEmpty(els.emptyUsers, true, "Не удалось загрузить пользователей");
    } finally {
      usersLoading = false;
    }
  }

  async function selectSubject(userId) {
    const uid = normalizeUserId(userId);
    if (!uid) return;

    subjectUserId = uid;
    selectedSubject = allUsers.find((u) => u.id === uid) || null;
    selectedConversationId = null;
    renderUsers();

    setPanelEmpty(els.emptyConvs, true, "Загрузка чатов…");
    els.convList.innerHTML = "";

    const url = new URL(window.location.href);
    url.searchParams.set("subject", String(uid));
    window.history.replaceState({}, "", url);

    try {
      const data = await apiFetch(`/admin/messages/users/${uid}/conversations`);
      selectedSubject = data.subject
        ? { ...data.subject, id: normalizeUserId(data.subject.id) }
        : selectedSubject;
      conversations = data.conversations || [];
    } catch (error) {
      console.error("selectSubject:", error);
      conversations = [];
      setPanelEmpty(els.emptyConvs, true, "Ошибка загрузки чатов");
      renderConversations();
      renderMessages(null);
      return;
    }

    renderConversations();
    renderMessages(null);

    if (isMobile()) {
      setMobilePane("conversations");
    }
  }

  async function selectConversation(conversationId) {
    if (!subjectUserId || !conversationId) return;
    selectedConversationId = conversationId;
    renderConversations();

    setPanelEmpty(els.emptyThread, true, "Загрузка…");
    els.messages?.classList.add("hidden");

    try {
      const data = await apiFetch(
        `/admin/messages/conversations/${encodeURIComponent(conversationId)}/messages?subject_user_id=${subjectUserId}`
      );
      renderMessages(data);
    } catch (error) {
      console.error("selectConversation:", error);
      renderMessages(null);
    }

    if (isMobile()) {
      setMobilePane("thread");
    }
  }

  function bindEvents() {
    if (eventsBound) return;
    eventsBound = true;

    document.addEventListener("click", (event) => {
      const userBtn = event.target.closest("[data-user-id]");
      if (userBtn && els.usersList?.contains(userBtn)) {
        event.preventDefault();
        const uid = normalizeUserId(userBtn.getAttribute("data-user-id"));
        if (uid) void selectSubject(uid);
        return;
      }

      const convBtn = event.target.closest("[data-conv-id]");
      if (convBtn && els.convList?.contains(convBtn)) {
        event.preventDefault();
        const convId = convBtn.getAttribute("data-conv-id");
        if (convId) void selectConversation(convId);
      }
    });

    els.userSearch?.addEventListener("input", renderUsers);
    els.convSearch?.addEventListener("input", renderConversations);

    els.backUsers?.addEventListener("click", () => setMobilePane("users"));
    els.backConvs?.addEventListener("click", () => {
      setMobilePane("conversations");
      selectedConversationId = null;
      renderConversations();
      renderMessages(null);
    });

    MOBILE_MQ.addEventListener("change", () => {
      if (!isMobile()) {
        setMobilePane("users");
      } else if (selectedConversationId) {
        setMobilePane("thread");
      } else if (subjectUserId) {
        setMobilePane("conversations");
      } else {
        setMobilePane("users");
      }
    });
  }

  function initViewerBadge(userData) {
    if (!els.viewerInitial || !userData) return;
    const name = userData.name || userData.email || "A";
    els.viewerInitial.textContent = initials(name).charAt(0) || "A";
  }

  function bootstrapApp(userData) {
    if (!canBootstrap(userData)) {
      showDenied();
      return;
    }
    if (appReady) return;
    appReady = true;

    initViewerBadge(userData);
    bindEvents();
    setMobilePane("users");
    void loadUsers();
  }

  function readCachedProfile() {
    try {
      const raw = localStorage.getItem("currentUserProfile");
      if (!raw) return null;
      const payload = JSON.parse(raw);
      if (payload && payload.id != null) return payload;
    } catch {
      return null;
    }
    return null;
  }

  function tryBootstrapFromAvailableUser() {
    const live =
      window.__lkCurrentUser ||
      (typeof window.getLkCurrentUser === "function" ? window.getLkCurrentUser() : null) ||
      readCachedProfile();
    if (live) {
      window.__lkCurrentUser = live;
      bootstrapApp(live);
    }
  }

  window.addEventListener("lk-user-ready", (event) => {
    if (event.detail) {
      window.__lkCurrentUser = event.detail;
    }
    bootstrapApp(window.__lkCurrentUser);
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", tryBootstrapFromAvailableUser);
  } else {
    tryBootstrapFromAvailableUser();
  }
})();
