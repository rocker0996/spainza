// User and admin messaging logic with backend integration.
(function () {
  const byId = {
    activeName: document.getElementById("active-chat-name"),
    activeRole: document.getElementById("active-chat-role"),
    activeAvatar: document.getElementById("active-chat-avatar"),
    messagesContainer: document.getElementById("messages-container"),
    conversationsList: document.getElementById("conversations-list"),
    searchInput: document.getElementById("conversation-search-input"),
    messageInput: document.getElementById("message-input"),
    sendButton: document.getElementById("send-message-btn"),
    attachDocument: document.getElementById("attach-document-btn"),
    attachImage: document.getElementById("attach-image-btn"),
    sharedDocsButton: document.getElementById("shared-docs-btn"),
    sharedDocsCount: document.getElementById("shared-docs-count"),
    newConversation: document.getElementById("new-conversation-btn"),
    activeMenu: document.getElementById("active-chat-menu-btn"),
    chatMenuDropdown: document.getElementById("chat-menu-dropdown"),
    clearHistoryBtn: document.getElementById("clear-history-btn"),
    deleteChatBtn: document.getElementById("delete-chat-btn"),
    // Message search elements
    messageSearchToggle: document.getElementById("message-search-toggle-btn"),
    messageSearchBar: document.getElementById("message-search-bar"),
    messageSearchInput: document.getElementById("message-search-input"),
    messageSearchClose: document.getElementById("message-search-close-btn"),
    searchPrevBtn: document.getElementById("search-prev-btn"),
    searchNextBtn: document.getElementById("search-next-btn"),
    searchResultsInfo: document.getElementById("search-results-info"),
    searchCurrentIndex: document.getElementById("search-current-index"),
    searchTotalResults: document.getElementById("search-total-results"),
  };

  if (!byId.conversationsList || !byId.messagesContainer) {
    return;
  }

  function t(key, params) {
    return window.LkI18n ? window.LkI18n.t(key, params) : key;
  }

  function roleLabel(roleKey) {
    return window.LkI18n ? window.LkI18n.roleLabel(roleKey) : roleKey || t("roles.user");
  }

  function chatDisplayName(conversation) {
    return window.LkI18n
      ? window.LkI18n.chatDisplayName(conversation)
      : conversation?.other_user_name || t("clients.noName");
  }

  function apiLocaleHeaders(extra) {
    return {
      ...(extra || {}),
      "X-User-Locale": window.LkI18n ? window.LkI18n.getLocale() : "ru",
    };
  }

  function apiLocaleBody(extra) {
    return JSON.stringify({
      ...(extra || {}),
      locale: window.LkI18n ? window.LkI18n.getLocale() : "ru",
    });
  }

  function resolveApiBases() {
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
        `${window.location.protocol}//${window.location.hostname}:5000/api`,
        "/api",
      ];
    }
    return ["/api"];
  }

  const apiBases = resolveApiBases();

  /** Strip leading /api so bases like /api can be prefixed once. */
  function toApiPath(path) {
    const normalized = path.startsWith("/") ? path : `/${path}`;
    if (normalized.startsWith("/api/")) {
      return normalized.slice(4);
    }
    if (normalized === "/api") {
      return "";
    }
    return normalized;
  }

  const messagesMain = document.getElementById("messages-main");
  const chatBackBtn = document.getElementById("chat-back-btn");
  const chatPane = document.getElementById("chat-pane");
  const chatDropOverlay = document.getElementById("chat-drop-overlay");
  const chatAttachmentPreview = document.getElementById("chat-attachment-preview");
  const MOBILE_MQ = window.matchMedia("(max-width: 767px)");

  const IMAGE_EXTENSIONS = new Set(["png", "jpg", "jpeg", "gif", "webp"]);
  const DOCUMENT_EXTENSIONS = new Set([
    "pdf", "doc", "docx", "txt", "xls", "xlsx", "ppt", "pptx", "zip", "rar", "7z", "tar", "gz",
  ]);
  const MAX_IMAGE_BYTES = 10 * 1024 * 1024;
  const MAX_FILE_BYTES = 25 * 1024 * 1024;

  /** @type {{ file: File, kind: 'image'|'file', previewUrl: string|null, status: 'ready'|'uploading' } | null} */
  let pendingAttachment = null;
  let dragDepth = 0;

  let mobileViewState = "list";
  let lastLoadedConversationId = null;
  let messageCountsByConversation = {};
  let messagesAnimateMode = "none";

  function isMobile() {
    return MOBILE_MQ.matches;
  }

  function prefersReducedMotion() {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }

  function popChatAvatar() {
    const avatar = document.getElementById("active-chat-avatar");
    if (!avatar || prefersReducedMotion()) return;
    avatar.classList.remove("avatar-pop");
    void avatar.offsetWidth;
    avatar.classList.add("avatar-pop");
  }

  function setMobileView(view) {
    if (!messagesMain || !isMobile()) {
      if (messagesMain) {
        messagesMain.classList.remove(
          "messages-view-list",
          "messages-view-chat",
          "messages-slide-forward",
          "messages-slide-back"
        );
      }
      mobileViewState = view === "chat" ? "chat" : "list";
      return;
    }

    const prev = mobileViewState;
    const next = view === "chat" ? "chat" : "list";

    messagesMain.classList.remove(
      "messages-view-list",
      "messages-view-chat",
      "messages-slide-forward",
      "messages-slide-back"
    );

    if (next === "chat") {
      messagesMain.classList.add("messages-view-chat");
      if (prev !== "chat") {
        messagesMain.classList.add("messages-slide-forward");
        popChatAvatar();
      }
    } else {
      messagesMain.classList.add("messages-view-list");
      if (prev === "chat") {
        messagesMain.classList.add("messages-slide-back");
      }
    }

    mobileViewState = next;
  }

  /** Чат поддержки (совпадает с profile.js). */
  const SUPPORT_USER_ID = 3;
  const COMPLAINT_MESSAGE_PREFIX = "[[SPAINZA_MANAGER_COMPLAINT]]";

  let conversations = [];
  let activeConversationId = null;
  let searchTerm = "";
  let currentUserId = null;
  /** Публичные номера из GET /api/user для автосоздания чатов (поддержка, менеджер). */
  let sessionSupportDisplayId = null;
  let sessionManagerDisplayId = null;

  // Message search state
  let messageSearchTerm = "";
  let searchResults = [];
  let currentSearchIndex = -1;
  
  // Modal elements
  const modal = document.getElementById("new-chat-modal");
  const userIdInput = document.getElementById("user-id-input");
  const createChatBtn = document.getElementById("create-chat-btn");
  const cancelModalBtn = document.getElementById("cancel-modal-btn");
  const closeModalBtn = document.getElementById("close-modal-btn");
  const modalError = document.getElementById("modal-error");
  const confirmModal = document.getElementById("chat-confirm-modal");
  const alertModal = document.getElementById("chat-alert-modal");
  let confirmDialogResolve = null;
  let alertDialogResolve = null;

  function lockBodyScrollForModal() {
    document.body.classList.add("overflow-hidden");
  }

  function unlockBodyScrollForModal() {
    if (!document.querySelector(".chat-modal.is-open")) {
      document.body.classList.remove("overflow-hidden");
    }
  }

  function openChatOverlayModal(modalEl) {
    if (!modalEl) return;
    modalEl.classList.remove("hidden");
    modalEl.setAttribute("aria-hidden", "false");
    lockBodyScrollForModal();
    requestAnimationFrame(() => modalEl.classList.add("is-open"));
  }

  function closeChatOverlayModal(modalEl) {
    return new Promise((resolve) => {
      if (!modalEl) {
        resolve();
        return;
      }
      modalEl.classList.remove("is-open");
      modalEl.setAttribute("aria-hidden", "true");
      const finish = () => {
        modalEl.classList.add("hidden");
        unlockBodyScrollForModal();
        resolve();
      };
      if (prefersReducedMotion()) {
        finish();
        return;
      }
      setTimeout(finish, 380);
    });
  }

  function showChatConfirm({ title, message, confirmText, variant = "warning" }) {
    return new Promise((resolve) => {
      if (!confirmModal) {
        resolve(false);
        return;
      }

      const titleEl = document.getElementById("chat-confirm-title");
      const messageEl = document.getElementById("chat-confirm-message");
      const okBtn = document.getElementById("chat-confirm-ok");
      const iconWrap = document.getElementById("chat-confirm-icon-wrap");
      const iconEl = document.getElementById("chat-confirm-icon");

      if (titleEl) titleEl.textContent = title;
      if (messageEl) messageEl.textContent = message;
      if (okBtn) okBtn.textContent = confirmText;

      if (variant === "danger") {
        if (iconWrap) {
          iconWrap.className =
            "w-12 h-12 rounded-xl bg-red-50 flex items-center justify-center mb-4";
        }
        if (iconEl) {
          iconEl.textContent = "delete";
          iconEl.className = "material-symbols-outlined text-[28px] text-red-600";
        }
        if (okBtn) {
          okBtn.className =
            "flex-1 py-3 px-4 bg-red-600 text-white font-semibold rounded-xl hover:bg-red-700 transition-colors shadow-md shadow-red-500/20";
        }
      } else {
        if (iconWrap) {
          iconWrap.className =
            "w-12 h-12 rounded-xl bg-amber-50 flex items-center justify-center mb-4";
        }
        if (iconEl) {
          iconEl.textContent = "history";
          iconEl.className = "material-symbols-outlined text-[28px] text-amber-600";
        }
        if (okBtn) {
          okBtn.className =
            "flex-1 py-3 px-4 bg-amber-600 text-white font-semibold rounded-xl hover:bg-amber-700 transition-colors shadow-md";
        }
      }

      confirmDialogResolve = resolve;
      openChatOverlayModal(confirmModal);
    });
  }

  function showChatAlert({ title, message, icon = "info" }) {
    return new Promise((resolve) => {
      if (!alertModal) {
        resolve();
        return;
      }

      const titleEl = document.getElementById("chat-alert-title");
      const messageEl = document.getElementById("chat-alert-message");
      const iconEl = document.getElementById("chat-alert-icon");

      if (titleEl) titleEl.textContent = title;
      if (messageEl) messageEl.textContent = message;
      if (iconEl) iconEl.textContent = icon;

      alertDialogResolve = resolve;
      openChatOverlayModal(alertModal);
    });
  }

  function finishChatConfirm(ok) {
    const resolve = confirmDialogResolve;
    confirmDialogResolve = null;
    closeChatOverlayModal(confirmModal).then(() => {
      if (resolve) resolve(ok);
    });
  }

  function finishChatAlert() {
    const resolve = alertDialogResolve;
    alertDialogResolve = null;
    closeChatOverlayModal(alertModal).then(() => {
      if (resolve) resolve();
    });
  }

  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function isComplaintMessage(text) {
    const s = String(text || "");
    return s.startsWith(COMPLAINT_MESSAGE_PREFIX);
  }

  function complaintMessageBody(text) {
    const s = String(text || "");
    const nl = s.indexOf("\n");
    if (s.startsWith(COMPLAINT_MESSAGE_PREFIX) && nl !== -1) {
      return s.slice(nl + 1).trim();
    }
    return s.trim();
  }

  function renderComplaintCardHtml(messageText) {
    const body = complaintMessageBody(messageText);
    return `
      <div class="rounded-xl border-[3px] border-red-600 bg-red-50/95 p-4 text-on-surface shadow-sm ring-1 ring-red-200/60">
        <div class="flex items-center gap-2 text-red-900 font-bold text-[11px] uppercase tracking-wide mb-3">
          <span class="material-symbols-outlined text-[18px]">gavel</span>
          ${t("chat.complaintCard")}
        </div>
        <pre class="text-[13px] leading-relaxed whitespace-pre-wrap font-sans text-on-surface m-0">${escapeHtml(body)}</pre>
      </div>
    `;
  }

  // Message search functions
  function highlightText(text, searchTerm) {
    if (!searchTerm || !text) return escapeHtml(text);
    
    const escapedText = escapeHtml(text);
    const escapedSearch = escapeHtml(searchTerm);
    const regex = new RegExp(`(${escapedSearch.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
    
    return escapedText.replace(regex, '<mark class="search-highlight">$1</mark>');
  }

  function performMessageSearch(term) {
    messageSearchTerm = term.toLowerCase().trim();
    searchResults = [];
    currentSearchIndex = -1;

    if (!messageSearchTerm) {
      clearMessageSearch();
      return;
    }

    const activeConversation = findConversation(activeConversationId);
    if (!activeConversation || !activeConversation.messages) {
      return;
    }

    // Find all messages containing the search term
    activeConversation.messages.forEach((message, index) => {
      if (message.message_text && message.message_text.toLowerCase().includes(messageSearchTerm)) {
        searchResults.push(index);
      }
    });

    updateSearchUI();
    
    if (searchResults.length > 0) {
      currentSearchIndex = 0;
      highlightCurrentResult();
    }
  }

  function updateSearchUI() {
    if (searchResults.length > 0) {
      byId.searchResultsInfo.classList.remove('hidden');
      byId.searchTotalResults.textContent = searchResults.length;
      byId.searchCurrentIndex.textContent = currentSearchIndex + 1;
      byId.searchPrevBtn.disabled = false;
      byId.searchNextBtn.disabled = false;
    } else {
      byId.searchResultsInfo.classList.add('hidden');
      byId.searchPrevBtn.disabled = true;
      byId.searchNextBtn.disabled = true;
      
      if (messageSearchTerm) {
        byId.searchTotalResults.textContent = '0';
        byId.searchCurrentIndex.textContent = '0';
        byId.searchResultsInfo.classList.remove('hidden');
      }
    }
  }

  function highlightCurrentResult() {
    renderMessages();
    
    if (currentSearchIndex >= 0 && currentSearchIndex < searchResults.length) {
      const targetMessageIndex = searchResults[currentSearchIndex];
      const messageElements = byId.messagesContainer.querySelectorAll('[data-message-index]');
      
      messageElements.forEach((el) => {
        const elIndex = parseInt(el.getAttribute('data-message-index'));
        
        if (elIndex === targetMessageIndex) {
          // This is the current search result
          el.scrollIntoView({ behavior: 'smooth', block: 'center' });
          
          // Replace regular highlights with active highlight
          const highlights = el.querySelectorAll('.search-highlight');
          highlights.forEach(h => {
            h.classList.remove('search-highlight');
            h.classList.add('search-highlight-active');
          });
          el.classList.remove('message-dimmed');
        } else if (searchResults.includes(elIndex)) {
          // Keep other results highlighted but not active
          el.classList.remove('message-dimmed');
        } else {
          // Dim messages that don't match
          el.classList.add('message-dimmed');
        }
      });
      
      byId.searchCurrentIndex.textContent = currentSearchIndex + 1;
    }
  }

  function navigateSearch(direction) {
    if (searchResults.length === 0) return;
    
    if (direction === 'next') {
      currentSearchIndex = (currentSearchIndex + 1) % searchResults.length;
    } else if (direction === 'prev') {
      currentSearchIndex = currentSearchIndex - 1;
      if (currentSearchIndex < 0) {
        currentSearchIndex = searchResults.length - 1;
      }
    }
    
    highlightCurrentResult();
  }

  function clearMessageSearch() {
    messageSearchTerm = "";
    searchResults = [];
    currentSearchIndex = -1;
    
    if (byId.messageSearchInput) {
      byId.messageSearchInput.value = "";
    }
    
    updateSearchUI();
    renderMessages();
    
    // Remove dimming from all messages
    const messageElements = byId.messagesContainer.querySelectorAll('[data-message-index]');
    messageElements.forEach(el => el.classList.remove('message-dimmed'));
  }

  function toggleMessageSearch() {
    if (!byId.messageSearchBar) return;

    const isOpen = byId.messageSearchBar.classList.contains("is-open");

    if (isOpen) {
      byId.messageSearchBar.classList.remove("is-open");
      byId.messageSearchBar.setAttribute("aria-hidden", "true");
      clearMessageSearch();
    } else {
      byId.messageSearchBar.classList.add("is-open");
      byId.messageSearchBar.setAttribute("aria-hidden", "false");
      if (byId.messageSearchInput) {
        requestAnimationFrame(() => byId.messageSearchInput.focus());
      }
    }
  }

  function getFileIcon(extension) {
    const iconMap = {
      'pdf': 'picture_as_pdf',
      'doc': 'description',
      'docx': 'description',
      'txt': 'description',
      'xls': 'table_chart',
      'xlsx': 'table_chart',
      'ppt': 'slideshow',
      'pptx': 'slideshow',
      'zip': 'folder_zip',
      'rar': 'folder_zip',
      'png': 'image',
      'jpg': 'image',
      'jpeg': 'image',
      'gif': 'image',
      'webp': 'image'
    };
    return iconMap[extension] || 'insert_drive_file';
  }

  function buildProtectedApiUrl(relativeUrl) {
    const normalized = String(relativeUrl || "").trim();
    if (!normalized) {
      return "";
    }
    return normalized.startsWith("/") ? normalized : `/${normalized}`;
  }

  async function apiRequest(url, options = {}) {
    const pathSuffix = toApiPath(url);
    const isFormData = typeof FormData !== "undefined" && options.body instanceof FormData;
    const headers = {
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
      ...apiLocaleHeaders(),
      ...options.headers,
    };

    let lastError = null;
    for (const baseUrl of apiBases) {
      try {
        const response = await fetch(`${baseUrl}${pathSuffix}`, {
          ...options,
          credentials: "include",
          headers,
        });

        if (!response.ok) {
          const error = await response.json().catch(() => ({ error: "Request failed" }));
          lastError = new Error(error.error || `HTTP ${response.status}`);
          continue;
        }

        return await response.json();
      } catch (error) {
        lastError = error instanceof Error ? error : new Error(String(error));
      }
    }

    throw lastError || new Error("Request failed");
  }

  async function loadCurrentUser() {
    try {
      const data = await apiRequest("/api/user");
      currentUserId = data.id;
      sessionSupportDisplayId = data.support_display_id
        ? String(data.support_display_id).trim().toUpperCase()
        : null;
      const am = data.assigned_manager;
      sessionManagerDisplayId =
        am && am.display_id ? String(am.display_id).trim().toUpperCase() : null;
      return data;
    } catch (error) {
      console.error("Failed to load current user:", error);
      window.location.href = "../login.html";
    }
  }

  async function ensureDefaultChats() {
    try {
      if (sessionSupportDisplayId) {
        await apiRequest("/api/conversations/create", {
          method: "POST",
          body: JSON.stringify({ display_id: sessionSupportDisplayId, restore: true }),
        }).catch(() => {});
      } else {
        await apiRequest("/api/conversations/create", {
          method: "POST",
          body: JSON.stringify({ user_id: SUPPORT_USER_ID }),
        }).catch(() => {});
      }

      try {
        const caseRes = await apiRequest(`/api/case-data/${currentUserId}`);
        const cd = caseRes && caseRes.case_data ? caseRes.case_data : caseRes;
        const managerId = cd && cd.manager_id != null ? Number(cd.manager_id) : null;
        if (managerId && Number.isFinite(managerId) && managerId !== SUPPORT_USER_ID) {
          if (sessionManagerDisplayId) {
            await apiRequest("/api/conversations/create", {
              method: "POST",
              body: JSON.stringify({ display_id: sessionManagerDisplayId, restore: true }),
            }).catch(() => {});
          } else {
            await apiRequest("/api/conversations/create", {
              method: "POST",
              body: JSON.stringify({ user_id: managerId }),
            }).catch(() => {});
          }
        }
      } catch (error) {
        console.log("No case data or manager assigned yet");
      }
    } catch (error) {
      console.error("Failed to ensure default chats:", error);
    }
  }

  async function loadConversations() {
    try {
      // Сначала убедимся, что базовые чаты созданы
      await ensureDefaultChats();
      
      const data = await apiRequest("/api/conversations");
      conversations = data;
      
      if (conversations.length > 0 && !activeConversationId && !isMobile()) {
        activeConversationId = conversations[0].id;
      }
      
      renderConversations();
      
      if (activeConversationId) {
        await loadMessages(activeConversationId);
      } else if (!isMobile()) {
        byId.messagesContainer.innerHTML =
          `<div class="p-6 text-sm text-outline">${t("chat.selectOrCreate")}</div>`;
        byId.activeName.textContent = '';
        byId.activeRole.textContent = '';
      }
    } catch (error) {
      console.error("Failed to load conversations:", error);
      byId.conversationsList.innerHTML =
        `<div class="p-6 text-sm text-red-500">${t("chat.loadChatsError", { error: error.message })}</div>`;
    }
  }

  async function loadMessages(conversationId) {
    try {
      const messages = await apiRequest(`/api/conversations/${conversationId}/messages`);
      const conversation = conversations.find(c => c.id === conversationId);
      const prevCount = messageCountsByConversation[conversationId] || 0;
      const isNewConversation = lastLoadedConversationId !== conversationId;

      if (conversation) {
        conversation.messages = messages;
        conversation.unread_count = 0;
      }

      if (isNewConversation) {
        messagesAnimateMode = "thread";
      } else if (messages.length > prevCount) {
        messagesAnimateMode = "tail";
      } else {
        messagesAnimateMode = "none";
      }

      messageCountsByConversation[conversationId] = messages.length;
      lastLoadedConversationId = conversationId;

      renderMessages();
      renderConversations();
      
      // Update unread badge in parent window (lk.js)
      if (window.loadUnreadMessagesCount && typeof window.loadUnreadMessagesCount === 'function') {
        window.loadUnreadMessagesCount();
      }
    } catch (error) {
      console.error("Failed to load messages:", error);
      byId.messagesContainer.innerHTML =
        `<div class="p-6 text-sm text-red-500">${t("chat.loadMessagesError")}</div>`;
    }
  }

  function formatTime(timestamp) {
    if (!timestamp) return "--:--";

    const date = new Date(timestamp);
    const now = new Date();
    const diffDays = Math.floor((now - date) / (1000 * 60 * 60 * 24));

    const loc = window.LkI18n ? window.LkI18n.dateLocaleTag() : "ru-RU";
    if (diffDays === 0) {
      return date.toLocaleTimeString(loc, { hour: "2-digit", minute: "2-digit" });
    }
    if (diffDays < 7) {
      return date.toLocaleDateString(loc, {
        weekday: "short",
        hour: "2-digit",
        minute: "2-digit",
      });
    }
    return date.toLocaleDateString(loc, { day: "2-digit", month: "2-digit" });
  }

  function getDateKey(timestamp) {
    const date = new Date(timestamp);
    if (Number.isNaN(date.getTime())) {
      return "";
    }
    return `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`;
  }

  function startOfLocalDay(date) {
    return new Date(date.getFullYear(), date.getMonth(), date.getDate());
  }

  function formatDateSeparator(timestamp) {
    const date = new Date(timestamp);
    if (Number.isNaN(date.getTime())) {
      return "";
    }

    const now = new Date();
    const today = startOfLocalDay(now);
    const msgDay = startOfLocalDay(date);
    const diffDays = Math.round((today - msgDay) / 86400000);
    const loc = window.LkI18n ? window.LkI18n.dateLocaleTag() : "ru-RU";

    if (diffDays === 0) {
      return t("chat.today");
    }
    if (diffDays === 1) {
      return t("chat.yesterday");
    }

    const opts = { day: "numeric", month: "long" };
    if (date.getFullYear() !== now.getFullYear()) {
      opts.year = "numeric";
    }
    return date.toLocaleDateString(loc, opts);
  }

  /** Время внутри пузыря сообщения — только часы и минуты. */
  function formatMessageTime(timestamp) {
    if (!timestamp) return "--:--";
    const date = new Date(timestamp);
    if (Number.isNaN(date.getTime())) {
      return "--:--";
    }
    const loc = window.LkI18n ? window.LkI18n.dateLocaleTag() : "ru-RU";
    return date.toLocaleTimeString(loc, { hour: "2-digit", minute: "2-digit" });
  }

  function getFileExtension(filename) {
    const name = String(filename || "");
    const dot = name.lastIndexOf(".");
    if (dot < 1) {
      return "";
    }
    return name.slice(dot + 1).toLowerCase();
  }

  function classifyAttachmentFile(file) {
    if (!file) {
      return null;
    }
    const ext = getFileExtension(file.name);
    if (IMAGE_EXTENSIONS.has(ext) || (file.type && file.type.startsWith("image/"))) {
      return "image";
    }
    if (DOCUMENT_EXTENSIONS.has(ext)) {
      return "file";
    }
    return null;
  }

  function mapAttachmentError(error) {
    const raw = error instanceof Error ? error.message : String(error || "");
    const lower = raw.toLowerCase();

    if (lower.includes("too large") || lower.includes("413")) {
      if (pendingAttachment && pendingAttachment.kind === "image") {
        return t("chat.imageTooLarge");
      }
      return t("chat.fileTooLarge");
    }
    if (lower.includes("not allowed") || lower.includes("file type")) {
      return t("chat.fileTypeNotAllowed");
    }
    if (
      lower.includes("invalid file") ||
      lower.includes("signature") ||
      lower.includes("content type") ||
      lower.includes("office document")
    ) {
      return t("chat.fileUnsafe");
    }
    if (pendingAttachment && pendingAttachment.kind === "image") {
      return t("chat.imageUploadError");
    }
    return t("chat.fileUploadError", { error: raw });
  }

  async function showAttachmentError(message, title) {
    await showChatAlert({
      title: title || t("chat.errorTitle"),
      message,
      icon: "error",
    });
  }

  function revokePendingPreviewUrl() {
    if (pendingAttachment && pendingAttachment.previewUrl) {
      URL.revokeObjectURL(pendingAttachment.previewUrl);
    }
  }

  function clearPendingAttachment() {
    revokePendingPreviewUrl();
    pendingAttachment = null;
    renderAttachmentPreview();
  }

  function validateAttachmentFile(file) {
    const kind = classifyAttachmentFile(file);
    if (!kind) {
      return { ok: false, message: t("chat.fileTypeNotAllowed") };
    }
    const maxBytes = kind === "image" ? MAX_IMAGE_BYTES : MAX_FILE_BYTES;
    if (file.size > maxBytes) {
      return {
        ok: false,
        message: kind === "image" ? t("chat.imageTooLarge") : t("chat.fileTooLarge"),
      };
    }
    return { ok: true, kind };
  }

  function renderAttachmentPreview(uploadPercent) {
    if (!chatAttachmentPreview) {
      return;
    }

    if (!pendingAttachment) {
      chatAttachmentPreview.classList.add("hidden");
      chatAttachmentPreview.innerHTML = "";
      return;
    }

    const { file, kind, previewUrl, status } = pendingAttachment;
    const ext = getFileExtension(file.name);
    const icon = kind === "image" && previewUrl ? "" : getFileIcon(ext);
    const isUploading = status === "uploading";
    const percent = typeof uploadPercent === "number" ? Math.min(100, Math.max(0, uploadPercent)) : 0;

    const thumb =
      kind === "image" && previewUrl
        ? `<img src="${escapeHtml(previewUrl)}" class="chat-attachment-preview__thumb" alt=""/>`
        : `<div class="chat-attachment-preview__thumb bg-white flex items-center justify-center border border-stone-200">
             <span class="material-symbols-outlined text-[28px] text-primary-container">${icon || "insert_drive_file"}</span>
           </div>`;

    const statusText = isUploading
      ? t("chat.uploadingAttachment", { percent: Math.round(percent) })
      : t("chat.attachmentReady");

    chatAttachmentPreview.classList.remove("hidden");
    chatAttachmentPreview.innerHTML = `
      <div class="chat-attachment-preview__card">
        ${thumb}
        <div class="flex-1 min-w-0">
          <div class="text-sm font-medium text-on-surface truncate">${escapeHtml(file.name)}</div>
          <div class="text-xs text-outline mt-0.5">${escapeHtml(statusText)}</div>
          ${
            isUploading
              ? `<div class="chat-attachment-preview__progress" role="progressbar" aria-valuenow="${Math.round(percent)}" aria-valuemin="0" aria-valuemax="100">
                   <div class="chat-attachment-preview__progress-bar" style="width: ${percent}%"></div>
                 </div>`
              : ""
          }
        </div>
        <button type="button" class="p-2 hover:bg-stone-200 rounded-lg transition-colors text-outline shrink-0 chat-attachment-remove" title="${escapeHtml(t("chat.removeAttachment"))}" ${isUploading ? "disabled" : ""}>
          <span class="material-symbols-outlined text-[20px]">close</span>
        </button>
      </div>
    `;

    const removeBtn = chatAttachmentPreview.querySelector(".chat-attachment-remove");
    if (removeBtn && !isUploading) {
      removeBtn.addEventListener("click", clearPendingAttachment);
    }
  }

  function queueAttachment(file) {
    if (!activeConversationId) {
      showAttachmentError(t("chat.selectChatForFile"));
      return;
    }

    const validation = validateAttachmentFile(file);
    if (!validation.ok) {
      showAttachmentError(validation.message);
      return;
    }

    revokePendingPreviewUrl();
    const kind = validation.kind;
    let previewUrl = null;
    if (kind === "image") {
      previewUrl = URL.createObjectURL(file);
    }

    pendingAttachment = { file, kind, previewUrl, status: "ready" };
    renderAttachmentPreview();
    if (byId.messageInput) {
      byId.messageInput.focus();
    }
  }

  function setDropOverlayVisible(visible) {
    if (!chatDropOverlay) {
      return;
    }
    if (visible) {
      chatDropOverlay.classList.remove("hidden");
      chatDropOverlay.classList.add("is-active");
      chatDropOverlay.setAttribute("aria-hidden", "false");
    } else {
      chatDropOverlay.classList.add("hidden");
      chatDropOverlay.classList.remove("is-active");
      chatDropOverlay.setAttribute("aria-hidden", "true");
    }
  }

  function bindDragAndDrop() {
    const target = chatPane || byId.messagesContainer;
    if (!target) {
      return;
    }

    target.addEventListener("dragenter", (event) => {
      if (!event.dataTransfer || !Array.from(event.dataTransfer.types).includes("Files")) {
        return;
      }
      event.preventDefault();
      dragDepth += 1;
      setDropOverlayVisible(true);
    });

    target.addEventListener("dragover", (event) => {
      if (!event.dataTransfer || !Array.from(event.dataTransfer.types).includes("Files")) {
        return;
      }
      event.preventDefault();
      event.dataTransfer.dropEffect = "copy";
      setDropOverlayVisible(true);
    });

    target.addEventListener("dragleave", (event) => {
      if (!event.dataTransfer || !Array.from(event.dataTransfer.types).includes("Files")) {
        return;
      }
      const root = chatPane || target;
      if (event.relatedTarget && root.contains(event.relatedTarget)) {
        return;
      }
      dragDepth = 0;
      setDropOverlayVisible(false);
    });

    target.addEventListener("drop", (event) => {
      if (!event.dataTransfer || !event.dataTransfer.files.length) {
        return;
      }
      event.preventDefault();
      dragDepth = 0;
      setDropOverlayVisible(false);
      const file = event.dataTransfer.files[0];
      if (file) {
        queueAttachment(file);
      }
    });
  }

  function findConversation(id) {
    return conversations.find((item) => item.id === id);
  }

  /** Превью в списке чатов: без служебного маркера жалобы. */
  function formatChatListPreview(raw) {
    const s = String(raw ?? "").trim();
    if (!s) {
      return t("common.noMessages");
    }
    if (s === "Фото") return t("chat.photo");
    if (s === "Файл") return t("chat.file");
    if (s.startsWith(COMPLAINT_MESSAGE_PREFIX)) {
      return t("chat.complaintPreview");
    }
    if (window.LkI18n) {
      return window.LkI18n.translateSystemMessage(s);
    }
    return s;
  }

  function renderConversationItem(conversation) {
    const lastMessage = formatChatListPreview(conversation.last_message);
    const time = formatTime(conversation.last_message_time);
    const isActive = conversation.id === activeConversationId;
    const unread = conversation.unread_count > 0
      ? `<span class="pulser bg-primary text-white text-[10px] w-5 h-5 rounded-full font-bold flex items-center justify-center flex-shrink-0">${conversation.unread_count}</span>`
      : "";

    // Аватар пользователя или иконка по умолчанию
    const avatar = conversation.other_user_avatar
      ? `<img src="${escapeHtml(conversation.other_user_avatar)}" class="w-12 h-12 rounded-xl object-cover flex-shrink-0" alt="Avatar" />`
      : `<div class="w-12 h-12 rounded-xl bg-secondary-container/20 flex items-center justify-center text-secondary flex-shrink-0">
           <span class="material-symbols-outlined" style="font-variation-settings: 'FILL' 1;">person</span>
         </div>`;

    return `
      <button class="w-full text-left p-4 flex items-center gap-4 transition-colors ${
        isActive ? "bg-primary-container/5 border-l-4 border-primary-container" : "hover:bg-stone-50 border-l-4 border-transparent"
      }" data-conversation-id="${conversation.id}" type="button">
        ${avatar}
        <div class="flex-grow min-w-0">
          <div class="flex justify-between items-baseline mb-0.5">
            <h3 class="font-semibold text-on-surface truncate">${escapeHtml(chatDisplayName(conversation))}</h3>
            <span class="text-[10px] text-outline font-medium">${escapeHtml(time)}</span>
          </div>
          <div class="flex items-center justify-between gap-2">
            <p class="text-sm text-on-surface-variant font-medium truncate">${escapeHtml(lastMessage)}</p>
            ${unread}
          </div>
        </div>
      </button>
    `;
  }

  function renderConversations() {
    const filtered = conversations.filter((conversation) => {
      if (!searchTerm) {
        return true;
      }
      const haystack = `${conversation.other_user_name} ${conversation.other_user_role}`.toLowerCase();
      return haystack.includes(searchTerm);
    });

    if (!filtered.length) {
      byId.conversationsList.innerHTML =
        `<div class="p-6 text-sm text-outline">${t("chat.chatsNotFound")}</div>`;
      return;
    }

    // Сортировка: чат с поддержкой (ID 3) всегда наверху
    const sorted = filtered.sort((a, b) => {
      const isSupportA = a.other_user_id === SUPPORT_USER_ID;
      const isSupportB = b.other_user_id === SUPPORT_USER_ID;
      
      if (isSupportA && !isSupportB) return -1;
      if (!isSupportA && isSupportB) return 1;
      return 0; // Остальные в исходном порядке
    });

    byId.conversationsList.innerHTML = sorted.map(renderConversationItem).join("");
  }

  function renderMessages() {
    const activeConversation = findConversation(activeConversationId);
    
    if (!activeConversation) {
      byId.messagesContainer.innerHTML =
        `<div class="p-6 text-sm text-outline">${t("chat.selectChat")}</div>`;
      byId.activeName.textContent = '';
      byId.activeRole.textContent = '';
      byId.sharedDocsCount.textContent = t('chat.documents');
      // Скрыть аватар
      const avatarImg = document.querySelector('#active-chat-avatar');
      if (avatarImg) {
        avatarImg.style.display = 'none';
      }
      return;
    }

    byId.activeName.textContent = chatDisplayName(activeConversation);
    byId.activeRole.textContent = roleLabel(activeConversation.other_user_role);
    byId.sharedDocsCount.textContent = t('chat.documents');
    
    // Обновить аватар в заголовке чата
    const avatarImg = document.querySelector('#active-chat-avatar');
    if (avatarImg) {
      avatarImg.style.display = 'block';
      if (activeConversation.other_user_avatar) {
        avatarImg.src = activeConversation.other_user_avatar;
      } else {
        // Если нет аватара, используем placeholder
        avatarImg.src = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"%3E%3Cpath fill="%23999" d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/%3E%3C/svg%3E';
      }
    }

    const messages = activeConversation.messages || [];
    let lastDateKey = "";

    const messagesMarkup = messages
      .map((message, index) => {
        let dateSeparatorHtml = "";
        if (message.created_at) {
          const dateKey = getDateKey(message.created_at);
          if (dateKey && dateKey !== lastDateKey) {
            lastDateKey = dateKey;
            const dateLabel = formatDateSeparator(message.created_at);
            if (dateLabel) {
              dateSeparatorHtml = `
                <div class="msg-date-separator msg-row" data-message-index="${index}" style="--msg-i: ${index}">
                  <span class="msg-date-separator__pill">${escapeHtml(dateLabel)}</span>
                </div>
              `;
            }
          }
        }
        // Системное сообщение
        if (message.is_system_message) {
          const isDelete = window.LkI18n && window.LkI18n.isSystemDeleteMessage(message.message_text);
          const boxClass = isDelete
            ? "bg-red-50 border border-red-200"
            : "bg-amber-50 border border-amber-200";
          const textClass = isDelete ? "text-red-800" : "text-amber-800";
          const icon = isDelete ? "delete" : "info";
          const iconClass = isDelete ? "text-red-600" : "";
          return `${dateSeparatorHtml}
            <div class="msg-row msg-row--system flex justify-center my-4" data-message-index="${index}" style="--msg-i: ${index}">
              <div class="${boxClass} px-4 py-2 rounded-xl max-w-md">
                <div class="flex items-start gap-2 ${textClass}">
                  <span class="material-symbols-outlined text-[18px] shrink-0 ${iconClass}">${icon}</span>
                  <span class="text-xs font-medium whitespace-pre-wrap break-words">${escapeHtml(window.LkI18n ? window.LkI18n.translateSystemMessage(message.message_text) : message.message_text)}</span>
                </div>
              </div>
            </div>
          `;
        }
        
        const isMe = message.sender_id === currentUserId;
        const time = formatMessageTime(message.created_at);
        
        let content = '';
        if (message.image_url) {
          content = `<img src="${escapeHtml(buildProtectedApiUrl(message.image_url))}" class="max-w-xs rounded-lg" alt="Image"/>`;
        }
        if (message.file_url) {
          const fileName = message.file_name || 'file';
          const fileExt = fileName.split('.').pop().toLowerCase();
          const fileIcon = getFileIcon(fileExt);
          content += `
            <a href="${escapeHtml(buildProtectedApiUrl(message.file_url))}" download="${escapeHtml(fileName)}"
               class="flex items-center gap-3 p-3 bg-stone-50 rounded-lg hover:bg-stone-100 transition-colors border border-stone-200">
              <span class="material-symbols-outlined text-[32px] text-primary-container">${fileIcon}</span>
              <div class="flex-1 min-w-0">
                <div class="text-sm font-medium text-on-surface truncate">${escapeHtml(fileName)}</div>
                <div class="text-xs text-outline">${t("chat.clickToDownload")}</div>
              </div>
              <span class="material-symbols-outlined text-outline">download</span>
            </a>
          `;
        }
        if (message.message_text) {
          if (isComplaintMessage(message.message_text)) {
            content += renderComplaintCardHtml(message.message_text);
          } else {
            const textContent = messageSearchTerm
              ? highlightText(message.message_text, messageSearchTerm)
              : escapeHtml(message.message_text);
            content += `<div class="text-sm leading-relaxed whitespace-pre-wrap break-words">${textContent}</div>`;
          }
        }

        if (isMe) {
          return `${dateSeparatorHtml}
            <div class="msg-row msg-row--out flex flex-col items-end gap-1.5 self-end max-w-[85%]" data-message-index="${index}" style="--msg-i: ${index}">
              <div class="bg-white p-4 rounded-2xl rounded-br-none chat-shadow text-on-surface-variant">
                ${content}
              </div>
              <div class="flex items-center gap-1.5 px-1">
                <span class="text-[10px] text-outline font-medium">${escapeHtml(time)}</span>
                <span class="material-symbols-outlined text-[14px] text-blue-500" style="font-variation-settings: 'FILL' 1;">check_circle</span>
              </div>
            </div>
          `;
        }

        // Аватар отправителя
        const senderAvatar = message.sender_avatar
          ? `<img src="${escapeHtml(message.sender_avatar)}" class="w-8 h-8 rounded-lg object-cover flex-shrink-0 mb-1" alt="Avatar" />`
          : `<div class="w-8 h-8 rounded-lg bg-secondary-container/20 flex items-center justify-center text-secondary flex-shrink-0 mb-1">
               <span class="material-symbols-outlined text-[20px]">person</span>
             </div>`;

        return `${dateSeparatorHtml}
          <div class="msg-row msg-row--in flex gap-3 max-w-[85%] items-end" data-message-index="${index}" style="--msg-i: ${index}">
            ${senderAvatar}
            <div class="flex flex-col gap-1.5">
              <div class="bg-primary-fixed/30 p-4 rounded-2xl rounded-bl-none text-on-surface-variant shadow-lg shadow-primary/10">
                ${content}
              </div>
              <span class="text-[10px] text-outline font-medium px-1">${escapeHtml(time)}</span>
            </div>
          </div>
        `;
      })
      .join("");

    const animateMode = messagesAnimateMode;
    messagesAnimateMode = "none";
    const tailPopIndex =
      animateMode === "tail" && messages.length > 0 ? messages.length - 1 : -1;

    byId.messagesContainer.innerHTML = messagesMarkup || "";

    if (!prefersReducedMotion()) {
      if (animateMode === "thread") {
        byId.messagesContainer.classList.add("messages-thread-enter");
        requestAnimationFrame(() => {
          requestAnimationFrame(() => {
            byId.messagesContainer.classList.remove("messages-thread-enter");
          });
        });
      } else if (tailPopIndex >= 0) {
        const lastRow = byId.messagesContainer.querySelector(
          `[data-message-index="${tailPopIndex}"]`
        );
        if (lastRow) {
          lastRow.classList.add("msg-row--pop");
        }
      }
    }

    byId.messagesContainer.scrollTop = byId.messagesContainer.scrollHeight;
  }

  async function selectConversation(id) {
    if (id !== activeConversationId) {
      clearPendingAttachment();
    }
    activeConversationId = id;
    await loadMessages(id);
    if (isMobile()) {
      setMobileView("chat");
    }
  }

  async function openConversationWithUser(openUserRef) {
    const normalized = canonicalPublicDisplayIdFromParam(openUserRef);
    if (!isCompletePublicDisplayId(normalized) || !currentUserId) {
      return;
    }
    let conv = conversations.find(
      (c) => String(c.other_user_display_id || "").toUpperCase() === normalized
    );
    if (!conv) {
      try {
        const data = await apiRequest("/api/conversations/create", {
          method: "POST",
          body: JSON.stringify({ display_id: normalized, restore: true }),
        });
        await loadConversations();
        conv = conversations.find(
          (c) =>
            c.id === data.conversation_id ||
            String(c.other_user_display_id || "").toUpperCase() === normalized
        );
      } catch (error) {
        console.error("openConversationWithUser:", error);
        await showChatAlert({
          title: t("chat.errorTitle"),
          message: t("chat.openChatFailed"),
          icon: "error",
        });
        return;
      }
    }
    if (conv) {
      activeConversationId = conv.id;
      await loadMessages(conv.id);
      renderConversations();
      if (isMobile()) {
        setMobileView("chat");
      }
    }
  }

  function postMessageAttachmentWithProgress(formData, onProgress) {
    const pathSuffix = toApiPath(`/api/conversations/${activeConversationId}/messages`);

    return new Promise((resolve, reject) => {
      let baseIndex = 0;

      const tryNextBase = () => {
        if (baseIndex >= apiBases.length) {
          reject(new Error("Upload failed"));
          return;
        }

        const baseUrl = apiBases[baseIndex];
        baseIndex += 1;
        const xhr = new XMLHttpRequest();
        xhr.open("POST", `${baseUrl}${pathSuffix}`, true);
        xhr.withCredentials = true;
        const headers = apiLocaleHeaders();
        Object.keys(headers).forEach((key) => {
          xhr.setRequestHeader(key, headers[key]);
        });

        xhr.upload.addEventListener("progress", (event) => {
          if (event.lengthComputable && typeof onProgress === "function") {
            onProgress((event.loaded / event.total) * 100);
          }
        });

        xhr.addEventListener("load", () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            try {
              resolve(JSON.parse(xhr.responseText || "{}"));
            } catch {
              resolve({});
            }
            return;
          }

          if (xhr.status === 413) {
            reject(new Error(t("chat.fileTooLarge")));
            return;
          }

          let errMsg = `HTTP ${xhr.status}`;
          try {
            const payload = JSON.parse(xhr.responseText || "{}");
            if (payload.error) {
              errMsg = payload.error;
            }
          } catch {
            // ignore
          }

          if (baseIndex < apiBases.length) {
            tryNextBase();
            return;
          }
          reject(new Error(errMsg));
        });

        xhr.addEventListener("error", () => {
          if (baseIndex < apiBases.length) {
            tryNextBase();
            return;
          }
          reject(new Error("Upload failed"));
        });

        xhr.send(formData);
      };

      tryNextBase();
    });
  }

  async function sendMessage() {
    const input = byId.messageInput;
    if (!input) {
      return;
    }

    const text = input.value.trim();
    const hasAttachment = Boolean(pendingAttachment && pendingAttachment.file);

    if (!text && !hasAttachment) {
      input.focus();
      return;
    }

    if (!activeConversationId) {
      await showAttachmentError(t("chat.selectChat"));
      return;
    }

    if (byId.sendButton) {
      byId.sendButton.classList.add("is-sending");
      byId.sendButton.disabled = true;
    }

    try {
      if (hasAttachment) {
        const { file, kind } = pendingAttachment;
        pendingAttachment.status = "uploading";
        renderAttachmentPreview(0);

        const formData = new FormData();
        if (text) {
          formData.append("message_text", text);
        }
        if (kind === "image") {
          formData.append("image", file);
        } else {
          formData.append("file", file);
        }

        await postMessageAttachmentWithProgress(formData, (percent) => {
          renderAttachmentPreview(percent);
        });

        clearPendingAttachment();
        input.value = "";
      } else {
        await apiRequest(`/api/conversations/${activeConversationId}/messages`, {
          method: "POST",
          body: JSON.stringify({ message_text: text }),
        });
        input.value = "";
      }

      await loadMessages(activeConversationId);
      await loadConversations();
    } catch (error) {
      console.error("Failed to send message:", error);
      if (pendingAttachment) {
        pendingAttachment.status = "ready";
        renderAttachmentPreview();
      }
      const message = hasAttachment ? mapAttachmentError(error) : t("chat.sendError");
      await showAttachmentError(message);
    } finally {
      if (byId.sendButton) {
        byId.sendButton.classList.remove("is-sending");
        byId.sendButton.disabled = false;
      }
    }
  }

  function openFilePicker(accept, onSelected) {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = accept;
    input.onchange = (e) => {
      const file = e.target.files && e.target.files[0];
      if (file) {
        onSelected(file);
      }
    };
    input.click();
  }

  /** Публичный номер собеседника: 2 латинские буквы + 4 цифры (как в профиле). */
  function normalizePublicDisplayIdInput(raw) {
    const s = String(raw ?? "").toUpperCase().replace(/[^A-Z0-9]/g, "");
    let i = 0;
    let letters = "";
    while (i < s.length && letters.length < 2) {
      const ch = s.charAt(i);
      if (ch >= "A" && ch <= "Z") {
        letters += ch;
        i += 1;
      } else if (ch >= "0" && ch <= "9") {
        break;
      } else {
        i += 1;
      }
    }
    let digits = "";
    while (i < s.length && digits.length < 4) {
      const ch = s.charAt(i++);
      if (ch >= "0" && ch <= "9") {
        digits += ch;
      }
    }
    return letters + digits;
  }

  function isCompletePublicDisplayId(value) {
    return /^[A-Z]{2}\d{4}$/.test(String(value || ""));
  }

  function canonicalPublicDisplayIdFromParam(raw) {
    return String(raw ?? "").trim().toUpperCase().replace(/\s+/g, "");
  }

  function bindPublicDisplayIdInput(el) {
    if (!el) {
      return;
    }
    const sync = () => {
      const next = normalizePublicDisplayIdInput(el.value);
      if (el.value !== next) {
        el.value = next;
      }
    };
    el.addEventListener("input", sync);
    el.addEventListener("blur", sync);
    el.addEventListener("paste", (event) => {
      event.preventDefault();
      const text = (event.clipboardData || window.clipboardData)?.getData("text") || "";
      const insert = normalizePublicDisplayIdInput(text);
      if (!insert) {
        return;
      }
      const start = el.selectionStart ?? el.value.length;
      const end = el.selectionEnd ?? el.value.length;
      const before = el.value.slice(0, start);
      const after = el.value.slice(end);
      el.value = normalizePublicDisplayIdInput(before + insert + after);
      const caret = el.value.length;
      requestAnimationFrame(() => {
        try {
          el.setSelectionRange(caret, caret);
        } catch {
          // ignore
        }
      });
    });
  }

  function showModal() {
    if (!modal) return;
    openChatOverlayModal(modal);
    if (userIdInput) {
      userIdInput.value = "";
      requestAnimationFrame(() => userIdInput.focus());
    }
    if (modalError) {
      modalError.classList.add("hidden");
      modalError.textContent = "";
    }
  }

  function hideModal() {
    closeChatOverlayModal(modal);
  }

  async function createNewConversation() {
    if (!userIdInput) return;
    
    const token = normalizePublicDisplayIdInput(userIdInput.value);

    if (!isCompletePublicDisplayId(token)) {
      if (modalError) {
        modalError.textContent = t("chat.invalidPublicId");
        modalError.classList.remove("hidden");
      }
      return;
    }

    // Disable button during request
    if (createChatBtn) {
      createChatBtn.disabled = true;
      createChatBtn.textContent = t("chat.creating");
    }

    try {
      const data = await apiRequest("/api/conversations/create", {
        method: "POST",
        body: JSON.stringify({ display_id: token, restore: true }),
      });

      hideModal();
      await loadConversations();
      activeConversationId = data.conversation_id;
      await loadMessages(activeConversationId);
      if (isMobile()) {
        setMobileView("chat");
      }
    } catch (error) {
      console.error("Failed to create conversation:", error);
      if (modalError) {
        modalError.textContent = t("chat.errorGeneric", { error: error.message });
        modalError.classList.remove("hidden");
      }
    } finally {
      if (createChatBtn) {
        createChatBtn.disabled = false;
        createChatBtn.textContent = t("chat.createChat");
      }
    }
  }

  async function clearHistory() {
    if (!activeConversationId) {
      return;
    }

    const activeConversation = findConversation(activeConversationId);
    if (!activeConversation) {
      return;
    }

    const confirmClear = await showChatConfirm({
      title: t("chat.clearHistoryTitle"),
      message: t("chat.clearHistoryMessage", {
        name: chatDisplayName(activeConversation),
      }),
      confirmText: t("chat.clearHistoryConfirm"),
      variant: "warning",
    });

    if (!confirmClear) {
      return;
    }

    try {
      await apiRequest(`/api/conversations/${activeConversationId}/clear`, {
        method: "POST",
        headers: apiLocaleHeaders(),
        body: apiLocaleBody(),
      });

      // Скрыть меню
      if (byId.chatMenuDropdown) {
        byId.chatMenuDropdown.classList.remove("is-visible");
        byId.chatMenuDropdown.classList.add("hidden");
      }

      await loadMessages(activeConversationId);
    } catch (error) {
      console.error("Failed to clear history:", error);
      await showChatAlert({
        title: t("chat.errorTitle"),
        message: t("chat.clearHistoryError", { error: error.message }),
        icon: "error",
      });
    }
  }

  async function deleteChat() {
    if (!activeConversationId) {
      return;
    }

    const activeConversation = findConversation(activeConversationId);
    if (!activeConversation) {
      return;
    }

    // Запретить удаление чата с поддержкой (ID 3)
    if (activeConversation.other_user_id === SUPPORT_USER_ID) {
      await showChatAlert({
        title: t("chat.cannotDeleteTitle"),
        message: t("chat.cannotDeleteSupport"),
        icon: "block",
      });
      return;
    }

    const confirmDelete = await showChatConfirm({
      title: t("chat.deleteChatTitle"),
      message: t("chat.deleteChatMessage", {
        name: chatDisplayName(activeConversation),
      }),
      confirmText: t("chat.deleteChatConfirm"),
      variant: "danger",
    });

    if (!confirmDelete) {
      return;
    }

    try {
      await apiRequest(`/api/conversations/${activeConversationId}`, {
        method: "DELETE",
        headers: apiLocaleHeaders(),
      });

      // Скрыть меню
      if (byId.chatMenuDropdown) {
        byId.chatMenuDropdown.classList.remove("is-visible");
        byId.chatMenuDropdown.classList.add("hidden");
      }

      activeConversationId = null;
      if (isMobile()) {
        setMobileView("list");
      }

      await loadConversations();
    } catch (error) {
      console.error("Failed to delete chat:", error);
      await showChatAlert({
        title: t("chat.errorTitle"),
        message: t("chat.deleteChatError", { error: error.message }),
        icon: "error",
      });
    }
  }

  function toggleChatMenu() {
    if (!byId.chatMenuDropdown) {
      return;
    }

    const isOpen = byId.chatMenuDropdown.classList.contains("is-visible");
    if (isOpen) {
      byId.chatMenuDropdown.classList.remove("is-visible");
      byId.chatMenuDropdown.classList.add("hidden");
    } else {
      byId.chatMenuDropdown.classList.remove("hidden");
      requestAnimationFrame(() => {
        byId.chatMenuDropdown.classList.add("is-visible");
      });
    }
  }

  if (chatBackBtn) {
    chatBackBtn.addEventListener("click", () => {
      clearPendingAttachment();
      lastLoadedConversationId = null;
      setMobileView("list");
    });
  }

  let resizeTimer;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(async () => {
      if (!isMobile()) {
        setMobileView(null);
        if (conversations.length > 0 && !activeConversationId) {
          activeConversationId = conversations[0].id;
          await loadMessages(activeConversationId);
        }
        return;
      }
      setMobileView(activeConversationId ? "chat" : "list");
    }, 150);
  });

  // Event listeners
  byId.conversationsList.addEventListener("click", (event) => {
    const button = event.target.closest("[data-conversation-id]");
    if (!button) {
      return;
    }
    const conversationId = button.getAttribute("data-conversation-id");
    if (!conversationId) {
      return;
    }
    selectConversation(conversationId);
  });

  if (byId.searchInput) {
    byId.searchInput.addEventListener("input", (event) => {
      searchTerm = String(event.target.value || "").trim().toLowerCase();
      renderConversations();
    });
  }

  if (byId.sendButton) {
    byId.sendButton.addEventListener("click", sendMessage);
  }

  if (byId.messageInput) {
    byId.messageInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        sendMessage();
      }
    });
  }

  if (byId.attachImage) {
    byId.attachImage.addEventListener("click", () => {
      openFilePicker("image/*", queueAttachment);
    });
  }

  if (byId.attachDocument) {
    byId.attachDocument.addEventListener("click", () => {
      openFilePicker(
        ".pdf,.doc,.docx,.txt,.xls,.xlsx,.ppt,.pptx,.zip,.rar,.7z,.png,.jpg,.jpeg,.gif,.webp",
        queueAttachment
      );
    });
  }

  bindDragAndDrop();

  if (byId.sharedDocsButton) {
    byId.sharedDocsButton.addEventListener("click", () => {
      window.location.href = "./documents.html";
    });
  }

  if (byId.newConversation) {
    byId.newConversation.addEventListener("click", showModal);
  }

  // Modal event listeners
  if (createChatBtn) {
    createChatBtn.addEventListener("click", createNewConversation);
  }

  if (cancelModalBtn) {
    cancelModalBtn.addEventListener("click", hideModal);
  }

  if (closeModalBtn) {
    closeModalBtn.addEventListener("click", hideModal);
  }

  if (userIdInput) {
    bindPublicDisplayIdInput(userIdInput);
    userIdInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        createNewConversation();
        return;
      }
      if (
        event.key === "Backspace" ||
        event.key === "Delete" ||
        event.key === "Tab" ||
        event.key === "Escape" ||
        event.key.startsWith("Arrow") ||
        event.key === "Home" ||
        event.key === "End"
      ) {
        return;
      }
      if (event.ctrlKey || event.metaKey || event.altKey) {
        return;
      }
      const el = userIdInput;
      const cur = normalizePublicDisplayIdInput(el.value);
      const letters = cur.match(/^[A-Z]*/)?.[0]?.length ?? 0;
      if (event.key.length === 1) {
        if (letters < 2) {
          if (!/[A-Za-z]/.test(event.key)) {
            event.preventDefault();
          }
        } else if (!/[0-9]/.test(event.key)) {
          event.preventDefault();
        }
      }
    });
  }

  // Close modal on backdrop click
  if (modal) {
    modal.addEventListener("click", (event) => {
      if (
        event.target === modal ||
        event.target.classList.contains("chat-modal__backdrop")
      ) {
        hideModal();
      }
    });
  }

  const chatConfirmCancel = document.getElementById("chat-confirm-cancel");
  const chatConfirmOk = document.getElementById("chat-confirm-ok");
  const chatAlertOk = document.getElementById("chat-alert-ok");

  if (chatConfirmCancel) {
    chatConfirmCancel.addEventListener("click", () => finishChatConfirm(false));
  }
  if (chatConfirmOk) {
    chatConfirmOk.addEventListener("click", () => finishChatConfirm(true));
  }
  if (chatAlertOk) {
    chatAlertOk.addEventListener("click", () => finishChatAlert());
  }

  if (confirmModal) {
    confirmModal.addEventListener("click", (event) => {
      if (
        event.target === confirmModal ||
        event.target.classList.contains("chat-modal__backdrop")
      ) {
        finishChatConfirm(false);
      }
    });
  }

  if (alertModal) {
    alertModal.addEventListener("click", (event) => {
      if (
        event.target === alertModal ||
        event.target.classList.contains("chat-modal__backdrop")
      ) {
        finishChatAlert();
      }
    });
  }

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    if (confirmModal && confirmModal.classList.contains("is-open")) {
      finishChatConfirm(false);
      return;
    }
    if (alertModal && alertModal.classList.contains("is-open")) {
      finishChatAlert();
    }
  });

  if (byId.activeMenu) {
    byId.activeMenu.addEventListener("click", (event) => {
      event.stopPropagation();
      toggleChatMenu();
    });
  }

  if (byId.clearHistoryBtn) {
    byId.clearHistoryBtn.addEventListener("click", (event) => {
      event.stopPropagation();
      clearHistory();
    });
  }

  if (byId.deleteChatBtn) {
    byId.deleteChatBtn.addEventListener("click", (event) => {
      event.stopPropagation();
      deleteChat();
    });
  }

  // Close dropdown when clicking outside
  document.addEventListener("click", (event) => {
    if (byId.chatMenuDropdown && byId.chatMenuDropdown.classList.contains("is-visible")) {
      if (!byId.chatMenuDropdown.contains(event.target) && event.target !== byId.activeMenu) {
        byId.chatMenuDropdown.classList.remove("is-visible");
        byId.chatMenuDropdown.classList.add("hidden");
      }
    }
  });

  // Message search event listeners
  if (byId.messageSearchToggle) {
    byId.messageSearchToggle.addEventListener("click", toggleMessageSearch);
  }

  if (byId.messageSearchClose) {
    byId.messageSearchClose.addEventListener("click", toggleMessageSearch);
  }

  if (byId.messageSearchInput) {
    byId.messageSearchInput.addEventListener("input", (event) => {
      const term = event.target.value;
      performMessageSearch(term);
    });

    byId.messageSearchInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        navigateSearch('next');
      } else if (event.key === "Escape") {
        toggleMessageSearch();
      }
    });
  }

  if (byId.searchNextBtn) {
    byId.searchNextBtn.addEventListener("click", () => navigateSearch('next'));
  }

  if (byId.searchPrevBtn) {
    byId.searchPrevBtn.addEventListener("click", () => navigateSearch('prev'));
  }

  window.addEventListener("lk-locale-change", () => {
    if (window.LkI18n) {
      window.LkI18n.applyDocument();
    }
    renderConversations();
    renderMessages();
    renderAttachmentPreview();
  });

  // Initialize
  (async function init() {
    await loadCurrentUser();
    await loadConversations();
    const params = new URLSearchParams(window.location.search);
    const openUid = params.get("openUserId");
    if (openUid) {
      await openConversationWithUser(openUid);
      if (window.history && window.history.replaceState) {
        window.history.replaceState(null, "", window.location.pathname);
      }
    }
    if (isMobile()) {
      setMobileView(activeConversationId ? "chat" : "list");
    }
  })();
})();
