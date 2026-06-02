(function () {

  const defaultAvatar = "../img/Avatar.jpg";
  /** Запасной id поддержки, если в сессии ещё нет support_user_id. */
  const SUPPORT_USER_ID_FALLBACK = 3;
  let dashboardSessionUser = null;
  let dashboardConversations = [];
  let dashboardLastCaseData = null;
  let quickReplyHandlersBound = false;

  /**
   * Кому показывать превью: персональный менеджер из сессии, иначе поддержка.
   * @param {Record<string, unknown> | null | undefined} sessionUser — ответ GET /api/user
   */
  function supportUserIdFromSession(sessionUser) {
    const raw = sessionUser?.support_user_id;
    const parsed = raw != null ? Number(raw) : NaN;
    if (Number.isFinite(parsed) && parsed > 0) {
      return parsed;
    }
    return SUPPORT_USER_ID_FALLBACK;
  }

  function resolveMessageDeskTarget(sessionUser) {
    const am = sessionUser?.assigned_manager;
    const rawId = am && typeof am === "object" ? am.id : null;
    const mid = rawId != null ? Number(rawId) : NaN;
    const managerDisplayId =
      am && typeof am === "object" && am.display_id
        ? String(am.display_id).trim().toUpperCase()
        : "";
    if (Number.isFinite(mid) && mid > 0 && managerDisplayId) {
      return { mode: "manager", userId: mid, displayId: managerDisplayId, manager: am };
    }
    const sd = sessionUser?.support_display_id
      ? String(sessionUser.support_display_id).trim().toUpperCase()
      : "";
    return {
      mode: "support",
      userId: supportUserIdFromSession(sessionUser),
      displayId: sd,
      manager: null,
    };
  }

  /** Найти чат с менеджером или поддержкой (учитывает display_id и входящие от поддержки). */
  function findDeskConversation(items, target) {
    const list = Array.isArray(items) ? items : [];
    const uid = Number(target.userId);
    const displayId = target.displayId ? String(target.displayId).trim().toUpperCase() : "";

    let conv =
      list.find((c) => Number(c.other_user_id) === uid) ||
      (displayId
        ? list.find(
            (c) =>
              String(c.other_user_display_id || "").trim().toUpperCase() === displayId
          )
        : null) ||
      list.find((c) => String(c.other_user_role || "").toLowerCase() === "support");

    if (!conv && target.mode === "support") {
      const withInbound = list.filter((c) => {
        const txt = c.last_inbound_message;
        return txt != null && String(txt).trim() !== "";
      });
      if (withInbound.length === 1) {
        conv = withInbound[0];
      } else if (withInbound.length > 1) {
        conv =
          withInbound.find((c) => Number(c.other_user_id) === uid) ||
          (displayId
            ? withInbound.find(
                (c) =>
                  String(c.other_user_display_id || "").trim().toUpperCase() === displayId
              )
            : null) ||
          withInbound[0];
      }
    }

    return conv || null;
  }

  async function apiGet(path) {
    const response = await fetch(path, {
      method: "GET",
      credentials: "include",
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    return response.json();
  }

  async function apiRequest(path, options = {}) {
    const headers = {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    };
    const response = await fetch(path, {
      ...options,
      credentials: "include",
      headers,
    });
    if (!response.ok) {
      let errorText = `HTTP ${response.status}`;
      try {
        const payload = await response.json();
        if (payload?.error) errorText = payload.error;
      } catch {
        // keep fallback HTTP status
      }
      throw new Error(errorText);
    }
    return response.json();
  }

  function escapeHtml(value) {
    return String(value || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function buildProtectedApiUrl(relativeUrl) {
    const normalized = String(relativeUrl || "").trim();
    if (!normalized) {
      return "";
    }
    return normalized.startsWith("/") ? normalized : `/${normalized}`;
  }

  function t(key, params) {
    return window.LkI18n ? window.LkI18n.t(key, params) : key;
  }

  function formatTimeAgo(value) {
    if (!value) return t("common.justNow");
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return t("common.justNow");

    const seconds = Math.floor((Date.now() - date.getTime()) / 1000);
    if (seconds < 60) return t("common.justNow");
    if (seconds < 3600) {
      return t("common.minAgo", { n: Math.floor(seconds / 60) });
    }
    if (seconds < 86400) {
      return t("common.hoursAgo", { n: Math.floor(seconds / 3600) });
    }
    return t("common.daysAgo", { n: Math.floor(seconds / 86400) });
  }

  function renderTimelineFromCase(caseData) {
    dashboardLastCaseData = caseData;
    const container = document.getElementById("dashboard-timeline");
    if (!container) return;

    const timeline = Array.isArray(caseData?.timeline) ? caseData.timeline : [];
    if (timeline.length === 0) {
      container.innerHTML = `
        <div class="text-sm text-on-surface-variant font-body bg-surface-container-low p-4 rounded-[12px]">
          ${t("dashboard.timelineEmpty")}
        </div>
      `;
      return;
    }

    const rows = timeline
      .map((step) => {
        const status = String(step?.status || "pending");
        const title = escapeHtml(step?.title || t("dashboard.stepUntitled"));
        const description = escapeHtml(step?.description || "");

        const icon =
          status === "completed"
            ? `<div class="w-8 h-8 rounded-full bg-primary-fixed flex items-center justify-center z-10 shrink-0"><span class="material-symbols-outlined text-primary-container text-[16px]">check</span></div>`
            : status === "active"
              ? `<div class="w-8 h-8 rounded-full bg-surface-container-lowest border-2 border-tertiary-container flex items-center justify-center z-10 shrink-0"><div class="w-2.5 h-2.5 rounded-full bg-tertiary-container animate-pulse"></div></div>`
              : `<div class="w-8 h-8 rounded-full bg-surface-container-high flex items-center justify-center z-10 shrink-0"><span class="material-symbols-outlined text-outline text-[16px]">schedule</span></div>`;

        const body =
          status === "active"
            ? `<div class="bg-surface-container-low p-5 rounded-[12px] flex-1"><div class="flex justify-between items-start mb-2"><h3 class="text-base font-semibold font-headline text-on-surface">${title}</h3><span class="bg-tertiary-container text-on-tertiary px-2 py-1 rounded-[4px] text-[10px] font-bold uppercase tracking-wider font-label">${escapeHtml(t("dashboard.currentStage"))}</span></div><p class="text-sm text-on-surface-variant font-body">${description || escapeHtml(t("dashboard.noDescription"))}</p></div>`
            : `<div><h3 class="text-base font-semibold font-headline text-on-surface">${title}</h3><p class="text-sm text-on-surface-variant font-body mt-1">${description || escapeHtml(t("dashboard.noDescription"))}</p></div>`;

        return `<div class="flex gap-6 relative ${status === "pending" ? "opacity-50" : ""}">${icon}${body}</div>`;
      })
      .join("");

    container.innerHTML = `
      <div class="absolute left-[31px] top-4 bottom-8 w-[2px] bg-outline-variant/20"></div>
      ${rows}
    `;
  }

  function renderCountry(caseData) {
    const countryValue = String(caseData?.country || "").trim();
    const roleLevelNode = document.getElementById("user-role-level");
    if (!roleLevelNode) return;
    roleLevelNode.textContent = countryValue || t("dashboard.countryNotSet");
  }

  function renderArchiveDocument(caseData) {
    const container = document.getElementById("dashboard-key-documents");
    if (!container) return;

    const archiveUrl = caseData?.archive_download_url;
    const archiveName = caseData?.archive_file_name;

    if (!archiveUrl || !archiveName) {
      container.innerHTML = `
        <div class="text-sm text-on-surface-variant font-body p-4 bg-surface-container-low rounded-[12px]">
          ${t("dashboard.archiveNotUploaded")}
        </div>
      `;
      return;
    }

    const safeName = escapeHtml(archiveName);
    container.innerHTML = `
      <div class="flex items-center justify-between p-4 bg-surface-container-low rounded-[12px] group">
        <div class="flex items-center gap-4 min-w-0">
          <div class="w-10 h-10 rounded-[8px] bg-secondary-fixed text-on-secondary-fixed flex items-center justify-center">
            <span class="material-symbols-outlined">folder_zip</span>
          </div>
          <div class="min-w-0">
            <p class="font-semibold text-sm font-headline text-on-surface truncate" title="${safeName}">${safeName}</p>
            <p class="text-xs text-outline font-body mt-0.5">${escapeHtml(t("dashboard.archiveLabel"))}</p>
          </div>
        </div>
        <a href="${escapeHtml(buildProtectedApiUrl(archiveUrl))}" download class="text-outline hover:text-primary-container transition-colors p-2 shrink-0" title="${escapeHtml(t("dashboard.downloadArchive"))}">
          <span class="material-symbols-outlined text-[20px]">download</span>
        </a>
      </div>
    `;
  }

  function formatMessagePreviewForUi(raw) {
    const s = String(raw ?? "").trim();
    if (!s) {
      return "";
    }
    if (s.startsWith("[[SPAINZA_MANAGER_COMPLAINT]]")) {
      return t("dashboard.complaintPreview");
    }
    return s;
  }

  function renderLatestMessage(conversations, sessionUser) {
    const avatarNode = document.getElementById("dashboard-last-message-avatar");
    const nameNode = document.getElementById("dashboard-last-message-name");
    const metaNode = document.getElementById("dashboard-last-message-meta");
    const textNode = document.getElementById("dashboard-last-message-text");

    if (!avatarNode || !nameNode || !metaNode || !textNode) return;

    const items = Array.isArray(conversations) ? conversations : [];
    const target = resolveMessageDeskTarget(sessionUser);
    const conv = findDeskConversation(items, target);
    const mgr = target.manager && typeof target.manager === "object" ? target.manager : null;
    const managerRoleRu =
      mgr && mgr.role && typeof mgr.role === "object" ? String(mgr.role.name_ru || "").trim() : "";
    const managerTitle =
      (mgr && mgr.role && mgr.role.key && window.LkI18n
        ? window.LkI18n.roleLabel(mgr.role.key)
        : "") ||
      managerRoleRu ||
      t("dashboard.managerDefaultTitle");

    if (!conv) {
      if (target.mode === "manager" && mgr) {
        avatarNode.src = mgr.avatar || defaultAvatar;
        nameNode.textContent = String(mgr.name || "").trim() || managerTitle;
        metaNode.textContent = t("dashboard.noConversationMeta", { title: managerTitle });
        textNode.textContent = t("dashboard.chatAfterFirstMessage");
        return;
      }
      nameNode.textContent = t("dashboard.supportName");
      metaNode.textContent = t("common.noMessages");
      textNode.textContent = t("dashboard.supportEmptyHint");
      avatarNode.src = defaultAvatar;
      return;
    }

    const displayName =
      String(conv.other_user_name || "").trim() ||
      String(conv.other_user_email || "").trim() ||
      (target.mode === "manager"
        ? String(mgr?.name || "").trim() || managerTitle
        : t("dashboard.supportName"));
    avatarNode.src =
      conv.other_user_avatar ||
      (target.mode === "manager" ? mgr?.avatar || "" : "") ||
      defaultAvatar;
    nameNode.textContent = displayName;

    const inboundRaw =
      conv.last_inbound_message != null && conv.last_inbound_message !== ""
        ? conv.last_inbound_message
        : null;
    const preview = formatMessagePreviewForUi(inboundRaw);
    const inboundTime = conv.last_inbound_message_time || conv.last_message_at;

    if (!preview) {
      const who =
        target.mode === "manager"
          ? t("dashboard.whoManager")
          : t("dashboard.whoSupport");
      const roleBit =
        target.mode === "manager"
          ? String(conv.other_user_role || "").trim() || managerTitle
          : String(conv.other_user_role || "").trim() || t("dashboard.supportName");
      metaNode.textContent = t("dashboard.noInboundMeta", { role: roleBit });
      textNode.textContent = t("dashboard.noInboundFrom", { who });
      return;
    }

    const metaRole =
      target.mode === "manager"
        ? String(conv.other_user_role || "").trim() || managerTitle
        : String(conv.other_user_role || "").trim() || t("dashboard.supportName");
    metaNode.textContent = `${metaRole} • ${formatTimeAgo(inboundTime)}`;
    textNode.textContent = preview;
  }

  function getQuickReplyNodes() {
    return {
      inputNode: document.getElementById("dashboard-quick-reply-input"),
      sendNode: document.getElementById("dashboard-quick-reply-send"),
    };
  }

  function updateQuickReplyUiForTarget(sessionUser) {
    const { inputNode, sendNode } = getQuickReplyNodes();
    if (!inputNode || !sendNode) return;
    const target = resolveMessageDeskTarget(sessionUser);
    if (target.mode === "manager") {
      inputNode.placeholder = t("dashboard.quickReplyManager");
      sendNode.title = t("dashboard.sendToManager");
      return;
    }
    inputNode.placeholder = t("dashboard.quickReplySupport");
    sendNode.title = t("dashboard.sendToSupport");
  }

  async function ensureConversationWithUser(target) {
    const displayId = target && target.displayId ? String(target.displayId).trim().toUpperCase() : "";
    if (displayId) {
      const existing = dashboardConversations.find(
        (item) => String(item?.other_user_display_id || "").toUpperCase() === displayId
      );
      if (existing?.id) {
        return existing.id;
      }
      const created = await apiRequest("/api/conversations/create", {
        method: "POST",
        body: JSON.stringify({ display_id: displayId, restore: true }),
      });
      if (!created?.conversation_id) {
        throw new Error(t("dashboard.chatCreateFailed"));
      }
      return created.conversation_id;
    }
    const targetId = Number(target?.userId);
    if (!Number.isFinite(targetId) || targetId < 1) {
      throw new Error(t("dashboard.chatCreateFailed"));
    }
    const existing = dashboardConversations.find(
      (item) => Number(item?.other_user_id) === targetId
    );
    if (existing?.id) {
      return existing.id;
    }
    const created = await apiRequest("/api/conversations/create", {
      method: "POST",
      body: JSON.stringify({ user_id: targetId, restore: true }),
    });
    if (!created?.conversation_id) {
      throw new Error(t("dashboard.chatCreateFailed"));
    }
    return created.conversation_id;
  }

  async function sendQuickReplyFromDashboard() {
    const { inputNode, sendNode } = getQuickReplyNodes();
    if (!inputNode || !sendNode) return;
    const messageText = String(inputNode.value || "").trim();
    if (!messageText) {
      inputNode.focus();
      return;
    }
    if (!dashboardSessionUser) {
      window.alert(t("dashboard.profileNotLoaded"));
      return;
    }
    const target = resolveMessageDeskTarget(dashboardSessionUser);
    inputNode.disabled = true;
    sendNode.disabled = true;
    try {
      const conversationId = await ensureConversationWithUser(target);
      await apiRequest(`/api/conversations/${conversationId}/messages`, {
        method: "POST",
        body: JSON.stringify({ message_text: messageText }),
      });
      inputNode.value = "";
      const openRef = target.displayId || String(target.userId || "");
      const openId = encodeURIComponent(String(openRef).trim());
      window.location.href = `./messages.html?openUserId=${openId}`;
    } catch (error) {
      console.error("Dashboard quick reply failed:", error);
      window.alert(t("dashboard.sendFailed"));
    } finally {
      inputNode.disabled = false;
      sendNode.disabled = false;
      inputNode.focus();
    }
  }

  function bindQuickReplyHandlers() {
    if (quickReplyHandlersBound) return;
    const { inputNode, sendNode } = getQuickReplyNodes();
    if (!inputNode || !sendNode) return;
    quickReplyHandlersBound = true;
    sendNode.addEventListener("click", (event) => {
      event.preventDefault();
      sendQuickReplyFromDashboard();
    });
    inputNode.addEventListener("keydown", (event) => {
      if (event.key !== "Enter") return;
      event.preventDefault();
      sendQuickReplyFromDashboard();
    });
  }

  function resolveSessionUser() {
    const cached = window.getLkCurrentUser?.();
    if (cached && cached.id != null) {
      return Promise.resolve(cached);
    }
    return new Promise((resolve, reject) => {
      const onReady = (event) => {
        cleanup();
        resolve(event.detail);
      };
      const timer = window.setTimeout(async () => {
        cleanup();
        try {
          resolve(await apiGet("/api/user"));
        } catch (error) {
          reject(error);
        }
      }, 100);
      const cleanup = () => {
        window.removeEventListener("lk-user-ready", onReady);
        window.clearTimeout(timer);
      };
      window.addEventListener("lk-user-ready", onReady, { once: true });
    });
  }

  async function initDashboardBindings() {
    try {
      const user = await resolveSessionUser();
      dashboardSessionUser = user;
      const userId = user?.id;
      if (!userId) return;
      const caseLink = document.getElementById("dashboard-open-case-link");
      if (caseLink) {
        const did = String(user.display_id || "")
          .trim()
          .toUpperCase();
        if (/^[A-Z]{2}\d{4}$/.test(did)) {
          caseLink.href = `./case.html?client=${encodeURIComponent(did)}`;
        } else {
          caseLink.href = `./case.html?userId=${encodeURIComponent(String(userId))}`;
        }
      }

      let casePayload = null;
      try {
        casePayload = await apiGet(`/api/case-data/${userId}`);
      } catch (error) {
        casePayload = null;
      }
      const caseData = casePayload?.case_data || null;
      renderTimelineFromCase(caseData);
      renderArchiveDocument(caseData);
      renderCountry(caseData);

      bindQuickReplyHandlers();
      updateQuickReplyUiForTarget(user);

      const conversations = await apiGet("/api/conversations");
      dashboardConversations = Array.isArray(conversations) ? conversations : [];
      renderLatestMessage(dashboardConversations, user);
    } catch (error) {
      console.error("Dashboard data load failed:", error);
    }
  }

  function refreshDashboardLocale() {
    renderTimelineFromCase(dashboardLastCaseData);
    renderArchiveDocument(dashboardLastCaseData);
    renderCountry(dashboardLastCaseData);
    if (dashboardSessionUser) {
      updateQuickReplyUiForTarget(dashboardSessionUser);
      renderLatestMessage(dashboardConversations, dashboardSessionUser);
    }
    if (window.LkI18n) {
      window.LkI18n.applyDocument();
    }
  }

  window.addEventListener("lk-locale-change", refreshDashboardLocale);

  let dashboardStarted = false;
  function startDashboard() {
    if (dashboardStarted) {
      return;
    }
    dashboardStarted = true;
    void initDashboardBindings();
  }

  window.addEventListener("lk-user-ready", startDashboard, { once: true });

  if (window.getLkCurrentUser?.()) {
    startDashboard();
  } else if (typeof window.whenLkSessionReady === "function") {
    void window.whenLkSessionReady().then(startDashboard).catch(() => {});
  }
})();
