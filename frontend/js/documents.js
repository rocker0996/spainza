// Documents page: load user documents and handle pagination.
(function () {

  const CARDS_PER_PAGE = 12;

  function t(key, params) {
    return window.LkI18n ? window.LkI18n.t(key, params) : key;
  }
  let currentPage = 1;
  let allDocuments = [];
  let filteredDocuments = [];
  let currentUserName = "";
  let currentUserPermissions = [];
  let currentUserId = null;
  let targetUserId = null;
  let targetClientDisplayId = null;
  let isManagementDocumentsView = false;
  
  // Filter state
  let currentFilters = {
    status: 'all',
    priority: 'all'
  };

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
        "/api",
        window.location.protocol + "//" + window.location.hostname + ":5000/api",
      ];
    }

    return ["/api"];
  }

  const apiBases = resolveApiBases();

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  let documentsToastTimer = null;

  /** @param {"success"|"error"|"info"} variant */
  function showDocumentsToast(message, variant = "info") {
    const el = document.getElementById("documents-toast");
    if (!el || !message) {
      return;
    }
    const panelBase =
      "pointer-events-auto flex items-start gap-3 rounded-2xl px-4 py-3 shadow-lg border text-sm font-semibold font-body ";
    const panelClass =
      variant === "success"
        ? panelBase + "bg-green-50 text-green-900 border-green-200"
        : variant === "error"
          ? panelBase + "bg-red-50 text-red-900 border-red-200"
          : panelBase + "bg-surface-container-high text-on-surface border-outline-variant/30";
    const icon =
      variant === "success"
        ? "check_circle"
        : variant === "error"
          ? "error"
          : "info";
    const iconColor =
      variant === "success"
        ? "text-green-600"
        : variant === "error"
          ? "text-red-600"
          : "text-primary";
    el.innerHTML = `<div class="${panelClass}"><span class="material-symbols-outlined shrink-0 ${iconColor}">${icon}</span><span class="flex-1 leading-snug">${escapeHtml(message)}</span></div>`;
    el.classList.remove("hidden");
    if (documentsToastTimer) {
      clearTimeout(documentsToastTimer);
    }
    documentsToastTimer = setTimeout(() => {
      el.classList.add("hidden");
      el.innerHTML = "";
      documentsToastTimer = null;
    }, 4200);
  }

  function stripClientParamFromUrl() {
    try {
      const nu = new URL(window.location.href);
      if (!nu.searchParams.has("client")) {
        return;
      }
      nu.searchParams.delete("client");
      const qs = nu.searchParams.toString();
      window.history.replaceState(null, "", nu.pathname + (qs ? `?${qs}` : ""));
    } catch (e) {
      /* ignore */
    }
  }

  function isViewingOwnDocuments() {
    if (!targetUserId) {
      return true;
    }
    return (
      currentUserId != null && Number(targetUserId) === Number(currentUserId)
    );
  }

  async function resolveTargetUserIdFromUrl() {
    const urlParams = new URLSearchParams(window.location.search);
    const clientParam = urlParams.get("client");
    const legacy = urlParams.get("userId");

    if (clientParam !== null) {
      const clientRaw = clientParam.trim().toUpperCase();
      if (!clientRaw) {
        stripClientParamFromUrl();
        return null;
      }
      if (!/^[A-Z]{2}\d{4}$/.test(clientRaw)) {
        stripClientParamFromUrl();
        showDocumentsToast(t("documents.toast.clientUnknown"), "error");
        return null;
      }
      for (const baseUrl of apiBases) {
        try {
          const response = await fetch(
            `${baseUrl}/lk/case-client/resolve?client=${encodeURIComponent(clientRaw)}`,
            {
              credentials: "include",
            }
          );
          const data = await response.json().catch(() => ({}));
          if (response.ok && data.success && data.user_id != null) {
            try {
              const nu = new URL(window.location.href);
              nu.searchParams.set("client", data.display_id || clientRaw);
              nu.searchParams.delete("userId");
              window.history.replaceState(null, "", nu.pathname + nu.search);
            } catch (e) {
              /* ignore */
            }
            targetClientDisplayId = normalizeClientDisplayId(data.display_id || clientRaw);
            return Number(data.user_id);
          }
          if (response.status === 403 || response.status === 404) {
            showDocumentsToast(
              response.status === 403
                ? t("documents.noClientAccess")
                : t("documents.clientNotFound"),
              "error"
            );
            return null;
          }
        } catch (error) {
          /* try next base */
        }
      }
      showDocumentsToast(t("documents.toast.clientUnknown"), "error");
      return null;
    }

    if (legacy && /^\d+$/.test(String(legacy).trim())) {
      return parseInt(String(legacy).trim(), 10);
    }
    return null;
  }

  function confirmDocumentDeleteOnPage() {
    return new Promise((resolve) => {
      const existing = document.getElementById("document-delete-confirm-modal");
      if (existing) {
        existing.remove();
      }

      const modal = document.createElement("div");
      modal.id = "document-delete-confirm-modal";
      modal.className = "fixed inset-0 bg-black/50 flex items-center justify-center z-[70] p-4";
      modal.innerHTML = `
        <div class="bg-white rounded-2xl shadow-xl w-full max-w-md mx-4">
          <div class="px-6 py-4 border-b border-slate-100">
            <h3 class="font-manrope text-lg font-bold text-slate-800">${t("documents.deleteModalTitle")}</h3>
            <p class="text-sm text-slate-600 mt-2">${t("documents.deleteModalLead")}</p>
          </div>
          <div class="px-6 py-4 border-t border-slate-100 flex gap-3">
            <button type="button" data-doc-del-action="cancel" class="flex-1 py-3 bg-slate-100 text-slate-700 rounded-xl text-sm font-bold hover:bg-slate-200 transition-all">${t("common.cancel")}</button>
            <button type="button" data-doc-del-action="confirm" class="flex-1 py-3 bg-red-500 text-white rounded-xl text-sm font-bold hover:bg-red-600 transition-all">${t("documents.card.delete")}</button>
          </div>
        </div>
      `;

      document.body.appendChild(modal);

      function closeWith(ok) {
        modal.remove();
        resolve(ok);
      }

      modal.addEventListener("click", (event) => {
        if (event.target === modal) {
          closeWith(false);
          return;
        }
        const btn = event.target.closest("[data-doc-del-action]");
        if (!btn) {
          return;
        }
        const action = btn.getAttribute("data-doc-del-action");
        closeWith(action === "confirm");
      });
    });
  }

  function toDisplayDate(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return t("documents.card.dateUnknown");
    }
    const localeTag = window.LkI18n ? window.LkI18n.dateLocaleTag() : "ru-RU";
    return date.toLocaleString(localeTag, {
      day: "2-digit",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  function translateHistoryAction(action) {
    return window.LkI18n && window.LkI18n.translateHistoryAction
      ? window.LkI18n.translateHistoryAction(action)
      : action;
  }

  function translateHistoryDetails(details) {
    return window.LkI18n && window.LkI18n.translateDocumentHistoryDetails
      ? window.LkI18n.translateDocumentHistoryDetails(details)
      : details;
  }

  async function fetchFromApi(path) {
    let lastError = null;
    for (const baseUrl of apiBases) {
      try {
        const response = await fetch(baseUrl + path, {
          method: "GET",
          credentials: "include",
        });

        const data = await response.json().catch(() => ({}));

        if (!response.ok) {
          lastError =
            (typeof data.error === "string" && data.error) ||
            (typeof data.message === "string" && data.message) ||
            `HTTP ${response.status}`;
          continue;
        }

        return data;
      } catch (error) {
        lastError = error instanceof Error ? error.message : String(error);
      }
    }

    if (lastError) {
      console.error("documents API error:", path, lastError);
    }
    return null;
  }

  function getDocumentSortStage(documentData) {
    if (documentData.source === "request") {
      return "request";
    }
    if (documentData.status === "rejected") {
      return "replace";
    }
    if (documentData.status === "approved") {
      return "approved";
    }
    return "pending";
  }

  function sortDocumentsByViewPriority(documents) {
    const managementOrder = {
      pending: 1,   // Проверить
      request: 2,   // Запрос
      replace: 3,   // Заменить
      approved: 4,  // Принято
    };
    const clientOrder = {
      request: 1,   // Запрос
      replace: 2,   // Заменить
      approved: 3,  // Принято
      pending: 4,   // Проверить
    };
    const orderMap = isManagementDocumentsView ? managementOrder : clientOrder;

    return [...documents].sort((a, b) => {
      const stageA = getDocumentSortStage(a);
      const stageB = getDocumentSortStage(b);
      const orderA = orderMap[stageA] || 999;
      const orderB = orderMap[stageB] || 999;
      if (orderA !== orderB) {
        return orderA - orderB;
      }

      const timeA = new Date(a.last_action_at || 0).getTime();
      const timeB = new Date(b.last_action_at || 0).getTime();
      return timeB - timeA;
    });
  }

  function buildCard(documentData) {
    const isRequest = documentData.source === "request";
    const isUploaded = documentData.source === "uploaded";
    const status = documentData.status || "pending";
    
    // Determine card styling and badge based on status
    let borderColor, cardBg, statusLabel, statusBadge;
    
    if (isRequest) {
      // Request cards - orange
      borderColor = "border-orange-400";
      cardBg = "bg-orange-50/30";
      statusLabel = t("documents.card.labelManagerRequest");
      statusBadge = {
        text: t("documents.card.badgeRequest"),
        color: "bg-orange-500"
      };
    } else if (status === "approved") {
      // Approved cards - green
      borderColor = "border-green-500";
      cardBg = "bg-green-50/30";
      statusLabel = t("documents.card.labelApproved");
      statusBadge = {
        text: t("documents.card.badgeApproved"),
        color: "bg-green-500"
      };
    } else if (status === "rejected") {
      // Rejected cards - red
      borderColor = "border-red-500";
      cardBg = "bg-red-50/30";
      statusLabel = t("documents.card.labelRejected");
      statusBadge = {
        text: t("documents.card.badgeReplace"),
        color: "bg-red-500"
      };
    } else {
      // Pending/uploaded cards - blue
      borderColor = "border-blue-500";
      cardBg = "bg-blue-50/30";
      statusLabel = t("documents.card.labelUploaded");
      statusBadge = {
        text: t("documents.card.badgeReview"),
        color: "bg-blue-500"
      };
    }
    
    const priorityLabel = documentData.is_priority
      ? t("documents.card.priorityUrgent")
      : t("documents.card.priorityStandard");
    const badgeClasses = documentData.is_priority
      ? "bg-tertiary-container/10 text-tertiary-container"
      : "bg-primary-fixed text-primary-container";
    const priorityIconHtml = documentData.is_priority
      ? '<span class="material-symbols-outlined doc-card-badge-icon" aria-hidden="true">priority_high</span>'
      : "";

    const canModerateDocuments =
      currentUserPermissions.includes("full_access") ||
      currentUserPermissions.includes("approve_documents") ||
      currentUserPermissions.includes("review_documents");
    const canReplaceOwnUploaded =
      !targetUserId &&
      (currentUserPermissions.includes("full_access") ||
        currentUserPermissions.includes("upload_documents"));
    const canDownloadDocuments =
      canModerateDocuments ||
      currentUserPermissions.includes("download_documents");
    
    // Actions based on document type and status
    let actionsHtml;
    if (isRequest) {
      // For requests, show upload button
      actionsHtml = `
        <button data-action="upload" data-doc-id="${documentData.id}" data-doc-title="${escapeHtml(documentData.title)}" class="w-full min-h-[44px] py-2 sm:py-3 bg-orange-500 text-white rounded-lg sm:rounded-xl text-[11px] sm:text-sm font-bold hover:opacity-90 transition-all flex items-center justify-center gap-2" type="button">
          <span class="material-symbols-outlined text-[15px] sm:text-[18px]">upload</span>
          ${t("documents.card.uploadDocument")}
        </button>
      `;
    } else if (status === "approved" && canModerateDocuments) {
      // Approved document - show view and revoke buttons (view on top)
      actionsHtml = `
        <button data-action="view" data-doc-id="${documentData.id}" class="w-full min-h-[44px] py-2 sm:py-3 bg-blue-500 text-white rounded-lg sm:rounded-xl text-[11px] sm:text-sm font-bold hover:opacity-90 transition-all flex items-center justify-center gap-2 mb-2" type="button">
          <span class="material-symbols-outlined text-[15px] sm:text-[18px]">download</span>
          ${t("documents.card.download")}
        </button>
        <button data-action="revoke" data-doc-id="${documentData.id}" class="w-full min-h-[44px] py-2 sm:py-3 bg-slate-100 text-slate-700 rounded-lg sm:rounded-xl text-[11px] sm:text-sm font-bold hover:bg-slate-200 transition-all" type="button">${t("documents.card.revoke")}</button>
      `;
    } else if (status === "rejected" && canModerateDocuments) {
      // Rejected document - show view, replace file, and delete buttons
      actionsHtml = `
        <button data-action="view" data-doc-id="${documentData.id}" class="w-full min-h-[44px] py-2 sm:py-3 bg-blue-500 text-white rounded-lg sm:rounded-xl text-[11px] sm:text-sm font-bold hover:opacity-90 transition-all flex items-center justify-center gap-2 mb-2" type="button">
          <span class="material-symbols-outlined text-[15px] sm:text-[18px]">download</span>
          ${t("documents.card.download")}
        </button>
        <div class="flex flex-col gap-2 sm:flex-row">
          <button data-action="replace" data-doc-id="${documentData.id}" data-doc-title="${escapeHtml(documentData.title)}" class="flex-1 min-h-[44px] py-2 sm:py-3 bg-orange-500 text-white rounded-lg sm:rounded-xl text-[11px] sm:text-sm font-bold hover:bg-orange-600 transition-all flex items-center justify-center gap-2" type="button">
            <span class="material-symbols-outlined text-[15px] sm:text-[18px]">sync</span>
            ${t("documents.card.replace")}
          </button>
          <button data-action="delete" data-doc-id="${documentData.id}" class="flex-1 min-h-[44px] py-2 sm:py-3 bg-red-500 text-white rounded-lg sm:rounded-xl text-[11px] sm:text-sm font-bold hover:bg-red-600 transition-all flex items-center justify-center gap-2" type="button">
            <span class="material-symbols-outlined text-[15px] sm:text-[18px]">delete</span>
            ${t("documents.card.delete")}
          </button>
        </div>
      `;
    } else if (status === "rejected" && canReplaceOwnUploaded) {
      // Rejected document for client in own case - allow replace and download
      actionsHtml = `
        <button data-action="view" data-doc-id="${documentData.id}" class="w-full min-h-[44px] py-2 sm:py-3 bg-blue-500 text-white rounded-lg sm:rounded-xl text-[11px] sm:text-sm font-bold hover:opacity-90 transition-all flex items-center justify-center gap-2 mb-2" type="button">
          <span class="material-symbols-outlined text-[15px] sm:text-[18px]">download</span>
          ${t("documents.card.download")}
        </button>
        <button data-action="replace" data-doc-id="${documentData.id}" data-doc-title="${escapeHtml(documentData.title)}" class="w-full min-h-[44px] py-2 sm:py-3 bg-orange-500 text-white rounded-lg sm:rounded-xl text-[11px] sm:text-sm font-bold hover:bg-orange-600 transition-all flex items-center justify-center gap-2" type="button">
          <span class="material-symbols-outlined text-[15px] sm:text-[18px]">sync</span>
          ${t("documents.card.replace")}
        </button>
      `;
    } else if (isUploaded && canModerateDocuments) {
      // Pending uploaded document - show view on top, approve and reject below
      actionsHtml = `
        <button data-action="view" data-doc-id="${documentData.id}" class="w-full min-h-[44px] py-2 sm:py-3 bg-blue-500 text-white rounded-lg sm:rounded-xl text-[11px] sm:text-sm font-bold hover:opacity-90 transition-all flex items-center justify-center gap-2 mb-2" type="button">
          <span class="material-symbols-outlined text-[15px] sm:text-[18px]">download</span>
          ${t("documents.card.download")}
        </button>
        <div class="flex flex-col gap-2 sm:flex-row">
          <button data-action="approve" data-doc-id="${documentData.id}" class="flex-1 min-h-[44px] py-2 sm:py-3 bg-green-500 text-white rounded-lg sm:rounded-xl text-[11px] sm:text-sm font-bold hover:opacity-90 transition-all" type="button">${t("documents.card.approve")}</button>
          <button data-action="reject" data-doc-id="${documentData.id}" class="flex-1 min-h-[44px] py-2 sm:py-3 bg-red-500 text-white rounded-lg sm:rounded-xl text-[11px] sm:text-sm font-bold hover:opacity-90 transition-all" type="button">${t("documents.card.reject")}</button>
        </div>
      `;
    } else if (canDownloadDocuments && isUploaded) {
      if (canReplaceOwnUploaded && status !== "approved") {
        actionsHtml = `
          <button data-action="view" data-doc-id="${documentData.id}" class="w-full min-h-[44px] py-2 sm:py-3 bg-blue-500 text-white rounded-lg sm:rounded-xl text-[11px] sm:text-sm font-bold hover:opacity-90 transition-all flex items-center justify-center gap-2 mb-2" type="button">
            <span class="material-symbols-outlined text-[15px] sm:text-[18px]">download</span>
            ${t("documents.card.download")}
          </button>
          <button data-action="replace" data-doc-id="${documentData.id}" data-doc-title="${escapeHtml(documentData.title)}" class="w-full min-h-[44px] py-2 sm:py-3 bg-orange-500 text-white rounded-lg sm:rounded-xl text-[11px] sm:text-sm font-bold hover:bg-orange-600 transition-all flex items-center justify-center gap-2" type="button">
            <span class="material-symbols-outlined text-[15px] sm:text-[18px]">sync</span>
            ${t("documents.card.replace")}
          </button>
        `;
      } else {
        actionsHtml = `
          <button data-action="view" data-doc-id="${documentData.id}" class="w-full min-h-[44px] py-2 sm:py-3 bg-blue-500 text-white rounded-lg sm:rounded-xl text-[11px] sm:text-sm font-bold hover:opacity-90 transition-all flex items-center justify-center gap-2" type="button">
            <span class="material-symbols-outlined text-[15px] sm:text-[18px]">download</span>
            ${t("documents.card.download")}
          </button>
        `;
      }
    } else {
      actionsHtml = `
        <div class="w-full py-3 text-center bg-slate-50 text-slate-400 rounded-xl text-xs font-semibold uppercase tracking-wide">${t("documents.card.noAccess")}</div>
      `;
    }

    // Description for requests
    const requestDescription = documentData.description || documentData.request_description || "";
    const descriptionHtml = requestDescription
      ? `<p class="text-xs text-slate-600 mt-2 italic">${escapeHtml(requestDescription)}</p>`
      : '';
    
    // Rejection comment display
    const rejectionCommentHtml = status === "rejected" && documentData.rejection_comment
      ? `<div class="mt-3 p-3 bg-red-100 border border-red-200 rounded-lg">
          <p class="text-xs font-bold text-red-800 mb-1">${t("documents.card.rejectionReason")}</p>
          <p class="text-xs text-red-700">${escapeHtml(documentData.rejection_comment)}</p>
        </div>`
      : '';

    return `
      <article id="document-card-${documentData.id}" class="${cardBg} p-3 sm:p-5 md:p-6 rounded-lg sm:rounded-xl shadow-[0px_20px_40px_rgba(117,118,130,0.06)] group relative overflow-hidden flex flex-col h-full border-t-4 ${borderColor}">
        <div class="flex flex-wrap items-start justify-between gap-1 sm:gap-2 mb-2 sm:mb-4">
          <span class="${statusBadge.color} text-white text-[9px] sm:text-[10px] font-bold uppercase tracking-wide sm:tracking-widest px-2 py-0.5 sm:px-3 sm:py-1 rounded-full max-w-[58%] sm:max-w-none leading-tight">${statusBadge.text}</span>
          <span class="${badgeClasses} text-[9px] sm:text-[10px] font-bold uppercase tracking-normal sm:tracking-wide px-1.5 py-0.5 sm:px-2.5 sm:py-1 rounded-full inline-flex items-center gap-0.5 max-w-[40%] sm:max-w-none min-w-0 leading-tight">
            ${priorityIconHtml}<span class="truncate">${priorityLabel}</span>
          </span>
        </div>
        <div class="mb-2 sm:mb-6">
          <h3 class="text-sm sm:text-lg md:text-xl font-bold text-slate-800 leading-snug sm:leading-tight mb-1 line-clamp-3 sm:line-clamp-none break-words">${escapeHtml(documentData.title)}</h3>
          ${descriptionHtml}
          ${rejectionCommentHtml}
        </div>
        <div class="flex flex-col gap-2 sm:gap-3 md:flex-row md:items-center md:gap-4 py-2 sm:py-4 mb-2 sm:mb-6 border-y border-slate-50">
          <div class="flex-1 min-w-0">
            <p class="text-[9px] sm:text-[10px] uppercase tracking-wide text-slate-400 font-bold mb-0.5 sm:mb-1">${statusLabel}</p>
            <p class="text-xs sm:text-sm font-semibold text-slate-700 truncate sm:whitespace-normal sm:break-words">${toDisplayDate(documentData.last_action_at)}</p>
          </div>
          ${!isRequest ? `
          <div class="flex-1 min-w-0">
            <p class="text-[9px] sm:text-[10px] uppercase tracking-wide text-slate-400 font-bold mb-0.5 sm:mb-1">${t("documents.card.fileType")}</p>
            <p class="text-xs sm:text-sm font-semibold text-slate-700 line-clamp-2 sm:line-clamp-none break-words">${escapeHtml(documentData.file_type)}, ${escapeHtml(documentData.file_size)}</p>
          </div>
          ` : ''}
        </div>
        <div class="flex flex-col gap-1.5 sm:gap-2 mt-auto">
          ${actionsHtml}
        </div>
      </article>
    `;
  }

  function renderPagination(totalPages) {
    const paginationControls = document.getElementById("documents-pagination-controls");
    const pagesContainer = document.getElementById("documents-pages");
    const prevButton = document.getElementById("documents-prev-btn");
    const nextButton = document.getElementById("documents-next-btn");

    if (!paginationControls || !pagesContainer || !prevButton || !nextButton) {
      return;
    }

    if (totalPages <= 1) {
      paginationControls.style.display = "none";
      return;
    }

    paginationControls.style.display = "flex";
    pagesContainer.innerHTML = "";

    for (let page = 1; page <= totalPages; page += 1) {
      const button = document.createElement("button");
      button.type = "button";
      button.id = `documents-page-${page}`;
      button.textContent = String(page);
      button.className =
        page === currentPage
          ? "w-10 h-10 flex items-center justify-center rounded-xl bg-primary-container text-white shadow-md font-bold"
          : "w-10 h-10 flex items-center justify-center rounded-xl bg-white text-slate-600 shadow-sm hover:text-primary transition-all";
      button.addEventListener("click", () => {
        currentPage = page;
        renderDocuments();
      });
      pagesContainer.appendChild(button);
    }

    prevButton.disabled = currentPage <= 1;
    nextButton.disabled = currentPage >= totalPages;
  }

  function applyFilters() {
    // Start with all documents
    let filtered = [...allDocuments];
    
    // Filter by status
    if (currentFilters.status !== 'all') {
      if (currentFilters.status === 'request') {
        // Show only requests
        filtered = filtered.filter(doc => doc.source === 'request');
      } else if (currentFilters.status === 'pending') {
        // Show only pending documents (exclude requests)
        filtered = filtered.filter(doc => doc.source !== 'request' && doc.status === 'pending');
      } else {
        // Show documents with specific status
        filtered = filtered.filter(doc => doc.status === currentFilters.status);
      }
    }
    
    // Filter by priority
    if (currentFilters.priority !== 'all') {
      const isPriority = currentFilters.priority === 'urgent';
      filtered = filtered.filter(doc => doc.is_priority === isPriority);
    }
    
    filteredDocuments = sortDocumentsByViewPriority(filtered);
    currentPage = 1; // Reset to first page
    renderDocuments();
  }

  function renderDocuments() {
    const grid = document.getElementById("documents-grid");
    const summary = document.getElementById("documents-summary");
    
    // Use filtered documents if filters are active
    const documentsToShow = (currentFilters.status !== 'all' || currentFilters.priority !== 'all')
      ? filteredDocuments
      : sortDocumentsByViewPriority(allDocuments);
    
    const total = documentsToShow.length;
    const totalPages = Math.max(1, Math.ceil(total / CARDS_PER_PAGE));

    if (!grid || !summary) {
      return;
    }

    if (currentPage > totalPages) {
      currentPage = totalPages;
    }

    const start = (currentPage - 1) * CARDS_PER_PAGE;
    const pageDocuments = documentsToShow.slice(start, start + CARDS_PER_PAGE);

    if (!pageDocuments.length) {
      grid.innerHTML =
        `<div class="col-span-full bg-surface-container-lowest p-6 sm:p-8 rounded-xl shadow-[0px_20px_40px_rgba(117,118,130,0.06)] text-slate-500 font-medium text-center sm:text-left text-sm sm:text-base">${t("documents.empty")}</div>`;
      summary.textContent = t("documents.summary", { shown: 0, total: 0 });
      renderPagination(1);
      return;
    }

    grid.innerHTML = pageDocuments.map(buildCard).join("");
    summary.textContent = t("documents.summaryRange", {
      from: start + 1,
      to: Math.min(start + CARDS_PER_PAGE, total),
      total,
    });
    renderPagination(totalPages);
  }

  // Filter modal functions
  function openFilterModal() {
    const modal = document.getElementById('filter-modal');
    if (modal) {
      modal.classList.remove('hidden');
      modal.classList.add('flex');
    }
  }
  
  function closeFilterModal() {
    const modal = document.getElementById('filter-modal');
    if (modal) {
      modal.classList.add('hidden');
      modal.classList.remove('flex');
    }
  }
  
  function applyFilterFromModal() {
    const statusSelect = document.getElementById('filter-status');
    const prioritySelect = document.getElementById('filter-priority');
    
    if (statusSelect) {
      currentFilters.status = statusSelect.value;
    }
    if (prioritySelect) {
      currentFilters.priority = prioritySelect.value;
    }
    
    applyFilters();
    closeFilterModal();
  }
  
  function resetFilters() {
    currentFilters.status = 'all';
    currentFilters.priority = 'all';
    
    const statusSelect = document.getElementById('filter-status');
    const prioritySelect = document.getElementById('filter-priority');
    
    if (statusSelect) statusSelect.value = 'all';
    if (prioritySelect) prioritySelect.value = 'all';
    
    applyFilters();
    closeFilterModal();
  }
  
  // History modal functions
  function openHistoryModal() {
    const modal = document.getElementById('history-modal');
    if (modal) {
      modal.classList.remove('hidden');
      modal.classList.add('flex');
      loadDocumentHistory();
    }
  }
  
  function closeHistoryModal() {
    const modal = document.getElementById('history-modal');
    if (modal) {
      modal.classList.add('hidden');
      modal.classList.remove('flex');
    }
  }
  
  async function loadDocumentHistory() {
    const historyList = document.getElementById('history-log-list');
    if (!historyList) return;
    
    historyList.innerHTML = `<div class="p-8 text-center text-slate-500">${t("documents.historyLoading")}</div>`;
    
    const historyUserId = targetUserId || currentUserId;
    if (!historyUserId) {
      historyList.innerHTML = `<div class="p-8 text-center text-slate-500">${t("documents.historyClientOnly")}</div>`;
      return;
    }
    
    try {
      console.log('📜 Loading document history for user:', historyUserId);
      const historyData = await fetchFromApi(`/document-history/${historyUserId}`);
      console.log('📦 History data received:', historyData);
      
      if (!historyData || !historyData.success || !historyData.history) {
        console.error('❌ Invalid history data:', historyData);
        historyList.innerHTML = `<div class="p-8 text-center text-slate-500">${t("documents.historyLoadFailed")}</div>`;
        return;
      }
      
      const historyItems = historyData.history;
      
      if (historyItems.length === 0) {
        historyList.innerHTML = `<div class="p-8 text-center text-slate-500">${t("documents.historyEmpty")}</div>`;
        return;
      }
      
      historyList.innerHTML = historyItems.map(item => {
        const icon = getHistoryIcon(item.action);
        const editorName = item.editor?.name || item.editor?.email || t("common.manager");
        const actionLabel = translateHistoryAction(item.action);
        const editorAvatar = item.editor?.avatar;
        
        return `
          <div class="flex gap-4 p-4 bg-slate-50 rounded-xl">
            <div class="flex-shrink-0">
              ${editorAvatar
                ? `<img src="${editorAvatar}" alt="${escapeHtml(editorName)}" class="w-10 h-10 rounded-full object-cover" />`
                : `<div class="w-10 h-10 rounded-full ${icon.bg} flex items-center justify-center">
                    <span class="material-symbols-outlined text-[20px] ${icon.color}">${icon.name}</span>
                   </div>`
              }
            </div>
            <div class="flex-1 min-w-0">
              <div class="flex items-start justify-between gap-2">
                <div>
                  <p class="font-manrope font-bold text-sm text-slate-800">${escapeHtml(actionLabel)}</p>
                  ${item.details ? `<p class="text-xs text-slate-500 mt-1">${escapeHtml(translateHistoryDetails(item.details))}</p>` : ''}
                </div>
                <span class="text-xs text-slate-400 whitespace-nowrap">${formatTimeAgo(item.created_at)}</span>
              </div>
              <p class="text-xs text-slate-400 mt-2">${t("documents.history.byUser", { name: escapeHtml(editorName) })}</p>
            </div>
          </div>
        `;
      }).join('');
      
    } catch (error) {
      console.error('Error loading document history:', error);
      historyList.innerHTML = `<div class="p-8 text-center text-red-500">${t("documents.historyError")}</div>`;
    }
  }
  
  function getHistoryIcon(action) {
    const a = String(action || "").toLowerCase();
    if (a.includes("загружен") || a.includes("upload")) {
      return { name: 'upload', bg: 'bg-blue-100', color: 'text-blue-600' };
    } else if (a.includes("одобрен") || a.includes("approv")) {
      return { name: 'check_circle', bg: 'bg-green-100', color: 'text-green-600' };
    } else if (a.includes("отклонен") || a.includes("reject")) {
      return { name: 'cancel', bg: 'bg-red-100', color: 'text-red-600' };
    } else if (a.includes("отозван") || a.includes("revok")) {
      return { name: 'undo', bg: 'bg-orange-100', color: 'text-orange-600' };
    } else if (a.includes("удален") || a.includes("delet")) {
      return { name: 'delete', bg: 'bg-gray-100', color: 'text-gray-600' };
    } else {
      return { name: 'history', bg: 'bg-gray-100', color: 'text-gray-600' };
    }
  }
  
  function formatTimeAgo(dateInput) {
    if (window.LkI18n && window.LkI18n.formatTimeAgo) {
      return window.LkI18n.formatTimeAgo(dateInput);
    }
    return String(dateInput || "");
  }

  function normalizeClientDisplayId(value) {
    const clientRaw = String(value || "").trim().toUpperCase();
    return /^[A-Z]{2}\d{4}$/.test(clientRaw) ? clientRaw : null;
  }

  function getClientDisplayIdFromUrl() {
    return normalizeClientDisplayId(
      new URLSearchParams(window.location.search).get("client"),
    );
  }

  function getClientDisplayIdForLinks() {
    return getClientDisplayIdFromUrl() || targetClientDisplayId || null;
  }

  function syncClientParamInUrl(clientId) {
    if (!clientId) {
      return;
    }
    try {
      const nu = new URL(window.location.href);
      nu.searchParams.set("client", clientId);
      nu.searchParams.delete("userId");
      window.history.replaceState(null, "", nu.pathname + nu.search);
    } catch (e) {
      /* ignore */
    }
  }

  async function ensureTargetClientDisplayId() {
    const fromUrl = getClientDisplayIdFromUrl();
    if (fromUrl) {
      targetClientDisplayId = fromUrl;
      return fromUrl;
    }
    if (targetClientDisplayId) {
      return targetClientDisplayId;
    }
    if (!targetUserId) {
      return null;
    }

    const userPayload = await fetchFromApi(`/users/${targetUserId}`);
    const resolved = normalizeClientDisplayId(
      userPayload?.user?.display_id || userPayload?.display_id,
    );
    if (resolved) {
      targetClientDisplayId = resolved;
      syncClientParamInUrl(resolved);
    }
    return targetClientDisplayId;
  }

  const HEADER_ACTION_PRIMARY_CLASS =
    "flex-1 min-[420px]:flex-none justify-center px-4 py-2.5 min-h-[44px] rounded-xl bg-gradient-to-r from-primary-container to-secondary text-white font-manrope font-bold text-sm transition-opacity shadow-md hover:opacity-90 flex items-center gap-2 active:scale-[0.98]";

  function showHeaderToolbarButton(element, visible, href) {
    if (!element) {
      return;
    }
    element.style.display = visible ? "flex" : "none";
    if (href) {
      element.setAttribute("href", href);
    }
  }

  function setupClientOwnCaseButtons() {
    const backBtn = document.getElementById("back-btn");
    const historyBtn = document.getElementById("history-btn");
    const filterBtn = document.getElementById("filter-btn");

    showHeaderToolbarButton(backBtn, true, "./dashboard.html");
    showHeaderToolbarButton(historyBtn, true);

    if (filterBtn && filterBtn.parentElement && !document.getElementById("own-document-btn")) {
      const ownDocBtn = document.createElement("button");
      ownDocBtn.id = "own-document-btn";
      ownDocBtn.type = "button";
      ownDocBtn.className = HEADER_ACTION_PRIMARY_CLASS;
      ownDocBtn.innerHTML =
        `<span class="material-symbols-outlined text-[18px] shrink-0">add</span><span class="truncate">${t("documents.card.ownDocument")}</span>`;
      ownDocBtn.addEventListener("click", () => handleUploadClick(null, null));
      filterBtn.parentElement.insertBefore(ownDocBtn, filterBtn);
    }
  }

  function refreshDocumentsHeaderI18n() {
    const manageBtn = document.getElementById("manage-case-btn");
    if (manageBtn && manageBtn.style.display !== "none") {
      manageBtn.innerHTML = `<span class="material-symbols-outlined text-[18px] shrink-0">folder_managed</span><span class="truncate">${t("clients.manageCase")}</span>`;
    }
    const ownDocBtn = document.getElementById("own-document-btn");
    if (ownDocBtn) {
      ownDocBtn.innerHTML = `<span class="material-symbols-outlined text-[18px] shrink-0">add</span><span class="truncate">${t("documents.card.ownDocument")}</span>`;
    }
  }

  function setupManagementClientDocumentsButtons() {
    const clientId = getClientDisplayIdForLinks();
    const filterBtn = document.getElementById("filter-btn");
    if (!clientId || !filterBtn?.parentElement) {
      return;
    }

    let manageBtn = document.getElementById("manage-case-btn");
    if (!manageBtn) {
      manageBtn = document.createElement("a");
      manageBtn.id = "manage-case-btn";
      manageBtn.className = `${HEADER_ACTION_PRIMARY_CLASS} no-underline`;
      filterBtn.parentElement.insertBefore(manageBtn, filterBtn);
    }
    manageBtn.href = `./case.html?client=${encodeURIComponent(clientId)}`;
    manageBtn.innerHTML = `<span class="material-symbols-outlined text-[18px] shrink-0">folder_managed</span><span class="truncate">${t("clients.manageCase")}</span>`;
    manageBtn.style.display = "flex";

    const legacyRequestBtn = document.getElementById("request-document-btn");
    if (legacyRequestBtn) {
      legacyRequestBtn.remove();
    }
  }

  async function applyDocumentsHeaderActions() {
    const backBtn = document.getElementById("back-btn");
    const historyBtn = document.getElementById("history-btn");
    const pageSubtitle = document.getElementById("page-subtitle");
    const clientCodeInUrl = getClientDisplayIdFromUrl();

    if (
      !targetUserId &&
      clientCodeInUrl &&
      canModerateUsersForHeader()
    ) {
      targetClientDisplayId = clientCodeInUrl;
      showHeaderToolbarButton(backBtn, true, "./clients.html");
      showHeaderToolbarButton(historyBtn, true);
      if (pageSubtitle) {
        pageSubtitle.style.display = "none";
      }
      setupManagementClientDocumentsButtons();
      return;
    }

    if (isViewingOwnDocuments()) {
      const isClientUploader =
        currentUserPermissions.includes("upload_documents") && !canModerateUsersForHeader();
      if (isClientUploader || !targetUserId) {
        setupClientOwnCaseButtons();
      } else if (backBtn) {
        showHeaderToolbarButton(backBtn, true, "./dashboard.html");
        showHeaderToolbarButton(historyBtn, true);
      }
      if (pageSubtitle) {
        pageSubtitle.style.display = "";
      }
      return;
    }

    showHeaderToolbarButton(backBtn, true, "./clients.html");
    showHeaderToolbarButton(historyBtn, true);
    if (pageSubtitle) {
      pageSubtitle.style.display = "none";
    }

    const pageTitle = document.getElementById("page-title");
    if (pageTitle && currentUserName) {
      pageTitle.textContent = t("documents.pageTitleClient", { name: currentUserName });
    }

    await ensureTargetClientDisplayId();
    setupManagementClientDocumentsButtons();
  }

  function canModerateUsersForHeader() {
    return (
      currentUserPermissions.includes("full_access") ||
      currentUserPermissions.includes("review_documents") ||
      currentUserPermissions.includes("approve_documents") ||
      currentUserPermissions.includes("view_all_users") ||
      currentUserPermissions.includes("view_lower_users") ||
      currentUserPermissions.includes("view_assignable_users") ||
      currentUserPermissions.includes("view_assigned_clients")
    );
  }

  async function initDocumentsPage() {
    targetUserId = await resolveTargetUserIdFromUrl();

    const userPayload = await fetchFromApi("/user");
    let isPortalStaff = false;
    if (userPayload) {
      currentUserId = userPayload.id || null;
      currentUserPermissions = Array.isArray(userPayload.permissions)
        ? userPayload.permissions
        : [];
      const roleLevel = parseFloat(String(userPayload.role && userPayload.role.level), 10);
      isPortalStaff = !Number.isNaN(roleLevel) && roleLevel <= 4;
    }

    const canModerateUsers = canModerateUsersForHeader();
    const viewingOwnDocuments = isViewingOwnDocuments();

    const canViewAssignedClientDocuments =
      Boolean(targetUserId) &&
      isPortalStaff &&
      currentUserPermissions.includes("view_assigned_clients");

    const canAccessDocuments =
      canViewAssignedClientDocuments ||
      (!(isPortalStaff && !targetUserId) &&
        (currentUserPermissions.includes("full_access") ||
          currentUserPermissions.includes("review_documents") ||
          currentUserPermissions.includes("approve_documents") ||
          currentUserPermissions.includes("upload_documents") ||
          currentUserPermissions.includes("download_documents")));
    isManagementDocumentsView =
      currentUserPermissions.includes("full_access") ||
      currentUserPermissions.includes("review_documents") ||
      currentUserPermissions.includes("approve_documents");
    if (!canAccessDocuments) {
      if (typeof window.redirectLkAccessDenied === "function") {
        window.redirectLkAccessDenied();
      } else {
        window.location.replace("/frontend/lk/404.html");
      }
      return;
    }

    await applyDocumentsHeaderActions();

    // Fetch documents with optional userId parameter
    const documentsUrl =
      targetUserId && !viewingOwnDocuments
        ? `/documents?userId=${targetUserId}`
        : "/documents";
    console.log('🔍 Fetching documents from:', documentsUrl);
    console.log('🔍 Target user ID:', targetUserId);
    
    const documentsPayload = await fetchFromApi(documentsUrl);
    console.log('📦 Documents payload received:', documentsPayload);
    
    if (!documentsPayload) {
      showDocumentsToast(t("documents.toast.loadFailed"), "error");
    }

    if (documentsPayload) {
      allDocuments = documentsPayload.documents || [];
      currentUserName = documentsPayload.user_name || t("common.user");
      if (!targetClientDisplayId && documentsPayload.client_display_id) {
        targetClientDisplayId = normalizeClientDisplayId(documentsPayload.client_display_id);
        if (targetClientDisplayId) {
          syncClientParamInUrl(targetClientDisplayId);
        }
      }
      
      console.log('📄 Total documents loaded:', allDocuments.length);
      console.log('📄 Documents:', allDocuments);
    } else {
      allDocuments = [];
      console.error('❌ No documents payload received');
    }

    renderDocuments();

    const prevButton = document.getElementById("documents-prev-btn");
    const nextButton = document.getElementById("documents-next-btn");

    if (prevButton) {
      prevButton.addEventListener("click", () => {
        if (currentPage > 1) {
          currentPage -= 1;
          renderDocuments();
        }
      });
    }

    if (nextButton) {
      nextButton.addEventListener("click", () => {
        const totalPages = Math.ceil(allDocuments.length / CARDS_PER_PAGE);
        if (currentPage < totalPages) {
          currentPage += 1;
          renderDocuments();
        }
      });
    }
    
    // Setup filter button
    const filterBtn = document.getElementById("filter-btn");
    if (filterBtn) {
      filterBtn.addEventListener("click", openFilterModal);
    }
    
    // Setup history button
    const historyBtn = document.getElementById("history-btn");
    if (historyBtn) {
      historyBtn.addEventListener("click", openHistoryModal);
    }
    
    // Setup filter modal buttons
    const closeFilterBtn = document.getElementById("close-filter-modal");
    const applyFilterBtn = document.getElementById("apply-filters");
    const resetFilterBtn = document.getElementById("reset-filters");
    
    if (closeFilterBtn) closeFilterBtn.addEventListener("click", closeFilterModal);
    if (applyFilterBtn) applyFilterBtn.addEventListener("click", applyFilterFromModal);
    if (resetFilterBtn) resetFilterBtn.addEventListener("click", resetFilters);
    
    // Setup history modal buttons
    const closeHistoryBtn = document.getElementById("close-history-modal");
    if (closeHistoryBtn) closeHistoryBtn.addEventListener("click", closeHistoryModal);
    
    // Close modals on backdrop click
    const filterModal = document.getElementById('filter-modal');
    if (filterModal) {
      filterModal.addEventListener('click', (e) => {
        if (e.target === filterModal) {
          closeFilterModal();
        }
      });
    }
    
    const historyModal = document.getElementById('history-modal');
    if (historyModal) {
      historyModal.addEventListener('click', (e) => {
        if (e.target === historyModal) {
          closeHistoryModal();
        }
      });
    }
  }

  function handleUploadClick(documentId, requestTitle) {
    const fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.accept = '.pdf,.doc,.docx,.txt,.xls,.xlsx,.ppt,.pptx,.zip,.rar,.png,.jpg,.jpeg,.gif,.webp';
    
    fileInput.onchange = async (e) => {
      const file = e.target.files[0];
      if (!file) return;

      let uploadTitle = requestTitle || file.name;
      const isOwnDocumentUpload = !documentId && !requestTitle;

      if (isOwnDocumentUpload) {
        const defaultTitle = file.name.includes(".")
          ? file.name.substring(0, file.name.lastIndexOf("."))
          : file.name;
        const enteredTitle = await requestDocumentTitleOnPage(defaultTitle || "");

        if (enteredTitle === null) {
          return;
        }

        uploadTitle = String(enteredTitle).trim();
      }
      
      console.log('📤 Starting upload:', file.name, file.type, file.size);
      
      const uploadBtn = document.getElementById(`document-upload-${documentId}`);
      if (uploadBtn) {
        uploadBtn.disabled = true;
        uploadBtn.innerHTML = `<span class="material-symbols-outlined text-[18px] animate-spin">progress_activity</span> ${t("documents.uploading")}`;
      }
      
      try {
        const result = await uploadDocument(file, uploadTitle, documentId);
        console.log('✅ Upload successful:', result);
        
        const documentsUrl = targetUserId ? `/documents?userId=${targetUserId}` : "/documents";
        console.log('🔄 Reloading documents from:', documentsUrl);
        const documentsPayload = await fetchFromApi(documentsUrl);
        if (documentsPayload) {
          allDocuments = documentsPayload.documents || [];
          console.log('📄 Documents reloaded, count:', allDocuments.length);
          renderDocuments();
        }
        const isRequestUpload = Boolean(documentId);
        showDocumentsToast(
          isRequestUpload
            ? t("documents.uploadSentReview")
            : t("documents.uploadSuccess"),
          "success"
        );
      } catch (error) {
        console.error('❌ Upload error:', error);
        showDocumentsToast(t("documents.uploadError", { error: error.message }), "error");
        
        if (uploadBtn) {
          uploadBtn.disabled = false;
          uploadBtn.innerHTML = `<span class="material-symbols-outlined text-[15px] sm:text-[18px]">upload</span> ${t("documents.card.uploadDocument")}`;
        }
      }
    };
    
    fileInput.click();
  }

  function requestDocumentTitleOnPage(defaultTitle) {
    return new Promise((resolve) => {
      const existingModal = document.getElementById("document-title-modal");
      if (existingModal) {
        existingModal.remove();
      }

      const modal = document.createElement("div");
      modal.id = "document-title-modal";
      modal.className = "fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4";
      modal.innerHTML = `
        <div class="bg-white rounded-2xl shadow-xl w-full max-w-md mx-4">
          <div class="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
            <h3 class="font-manrope text-lg font-bold text-slate-800">${t("documents.titleModal")}</h3>
            <button type="button" data-doc-title-action="close" class="text-slate-400 hover:text-slate-600 transition-colors">
              <span class="material-symbols-outlined">close</span>
            </button>
          </div>
          <div class="p-6">
            <label class="block text-sm font-semibold text-slate-700 mb-2">${t("documents.titleModalLabel")}</label>
            <input
              id="document-title-input"
              type="text"
              class="w-full px-4 py-3 border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
              placeholder="${t("documents.titleModalPlaceholder")}"
              value="${escapeHtml(defaultTitle || "")}"
            />
            <p id="document-title-error" class="text-xs text-red-500 mt-2 hidden">${t("documents.titleRequired")}</p>
          </div>
          <div class="px-6 py-4 border-t border-slate-100 flex gap-3">
            <button type="button" data-doc-title-action="cancel" class="flex-1 py-3 bg-slate-100 text-slate-700 rounded-xl text-sm font-bold hover:bg-slate-200 transition-all">${t("common.cancel")}</button>
            <button type="button" data-doc-title-action="confirm" class="flex-1 py-3 bg-blue-500 text-white rounded-xl text-sm font-bold hover:bg-blue-600 transition-all">${t("common.save")}</button>
          </div>
        </div>
      `;

      document.body.appendChild(modal);

      const input = modal.querySelector("#document-title-input");
      const error = modal.querySelector("#document-title-error");

      function closeWith(result) {
        modal.remove();
        resolve(result);
      }

      function submit() {
        const value = String(input?.value || "").trim();
        if (!value) {
          if (error) {
            error.classList.remove("hidden");
          }
          input?.focus();
          return;
        }
        closeWith(value);
      }

      modal.addEventListener("click", (event) => {
        if (event.target === modal) {
          closeWith(null);
          return;
        }

        const actionButton = event.target.closest("[data-doc-title-action]");
        if (!actionButton) {
          return;
        }

        const action = actionButton.getAttribute("data-doc-title-action");
        if (action === "confirm") {
          submit();
        } else {
          closeWith(null);
        }
      });

      input?.addEventListener("input", () => {
        if (error) {
          error.classList.add("hidden");
        }
      });

      input?.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
          event.preventDefault();
          submit();
        } else if (event.key === "Escape") {
          event.preventDefault();
          closeWith(null);
        }
      });

      setTimeout(() => {
        input?.focus();
        input?.select();
      }, 0);
    });
  }

  async function uploadDocument(file, title, requestId) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('title', title);
    formData.append('request_id', requestId || '');
    if (targetUserId) {
      formData.append('user_id', targetUserId);
    }
    
    const apiBases = resolveApiBases();
    let lastError = null;
    
    for (const baseUrl of apiBases) {
      try {
        const response = await fetch(baseUrl + '/documents/upload', {
          method: 'POST',
          credentials: 'include',
          body: formData
        });
        
        if (!response.ok) {
          if (response.status === 413) {
            throw new Error(t("documents.fileTooLarge"));
          }
          const errorData = await response.json().catch(() => ({}));
          throw new Error(errorData.error || `HTTP ${response.status}`);
        }
        
        const data = await response.json();
        if (!data.success) {
          throw new Error(data.error || 'Upload failed');
        }
        
        return data;
      } catch (err) {
        lastError = err;
        continue;
      }
    }
    
    throw lastError || new Error('Upload failed');
  }

  // View/download document
  async function viewDocument(documentId) {
    const apiBases = resolveApiBases();
    
    for (const baseUrl of apiBases) {
      try {
        const response = await fetch(baseUrl + `/documents/${documentId}/download`, {
          method: 'GET',
          credentials: 'include',
        });
        
        if (response.ok) {
          const blob = await response.blob();
          const url = window.URL.createObjectURL(blob);
          window.open(url, '_blank');
          return;
        }
      } catch (err) {
        console.error('View error:', err);
      }
    }
    
    showDocumentsToast(t("documents.toast.openFailed"), "error");
  }

  // Approve document
  async function approveDocument(documentId) {
    const apiBases = resolveApiBases();
    
    for (const baseUrl of apiBases) {
      try {
        const response = await fetch(baseUrl + `/documents/${documentId}/approve`, {
          method: 'POST',
          credentials: 'include',
          headers: {
            'Content-Type': 'application/json'
          }
        });
        
        if (response.ok) {
          // Reload documents
          const documentsUrl = targetUserId ? `/documents?userId=${targetUserId}` : "/documents";
          const documentsPayload = await fetchFromApi(documentsUrl);
          if (documentsPayload) {
            allDocuments = documentsPayload.documents || [];
            renderDocuments();
          }
          showDocumentsToast(t("documents.toast.approved"), "success");
          return;
        }
      } catch (err) {
        console.error('Approve error:', err);
      }
    }
    
    showDocumentsToast(t("documents.toast.approveFailed"), "error");
  }

  // Reject document with modal
  let currentRejectDocId = null;
  
  function openRejectModal(documentId) {
    currentRejectDocId = documentId;
    const modal = document.getElementById('rejection-modal');
    const textarea = document.getElementById('rejection-comment');
    if (modal && textarea) {
      textarea.value = '';
      modal.classList.remove('hidden');
      modal.classList.add('flex');
    }
  }
  
  function closeRejectModal() {
    const modal = document.getElementById('rejection-modal');
    if (modal) {
      modal.classList.add('hidden');
      modal.classList.remove('flex');
    }
    currentRejectDocId = null;
  }
  
  async function confirmRejectDocument() {
    if (!currentRejectDocId) return;
    
    const textarea = document.getElementById('rejection-comment');
    const comment = textarea?.value.trim();
    
    if (!comment) {
      showDocumentsToast(t("documents.toast.rejectReasonRequired"), "error");
      return;
    }
    
    const apiBases = resolveApiBases();
    
    for (const baseUrl of apiBases) {
      try {
        const response = await fetch(baseUrl + `/documents/${currentRejectDocId}/reject`, {
          method: 'POST',
          credentials: 'include',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({ comment })
        });
        
        if (response.ok) {
          closeRejectModal();
          
          // Reload documents
          const documentsUrl = targetUserId ? `/documents?userId=${targetUserId}` : "/documents";
          const documentsPayload = await fetchFromApi(documentsUrl);
          if (documentsPayload) {
            allDocuments = documentsPayload.documents || [];
            renderDocuments();
          }
          showDocumentsToast(t("documents.toast.rejected"), "success");
          return;
        }
      } catch (err) {
        console.error('Reject error:', err);
      }
    }
    
    showDocumentsToast(t("documents.toast.rejectFailed"), "error");
  }

  // Revoke approval
  async function revokeApproval(documentId) {
    const apiBases = resolveApiBases();
    
    for (const baseUrl of apiBases) {
      try {
        const response = await fetch(baseUrl + `/documents/${documentId}/revoke`, {
          method: 'POST',
          credentials: 'include',
          headers: {
            'Content-Type': 'application/json'
          }
        });
        
        if (response.ok) {
          // Reload documents
          const documentsUrl = targetUserId ? `/documents?userId=${targetUserId}` : "/documents";
          const documentsPayload = await fetchFromApi(documentsUrl);
          if (documentsPayload) {
            allDocuments = documentsPayload.documents || [];
            renderDocuments();
          }
          showDocumentsToast(t("documents.toast.revoked"), "success");
          return;
        }
      } catch (err) {
        console.error('Revoke error:', err);
      }
    }
    
    showDocumentsToast(t("documents.toast.revokeFailed"), "error");
  }

  // Replace file for rejected document
  function handleReplaceFile(documentId, documentTitle) {
    const fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.accept = '.pdf,.doc,.docx,.txt,.xls,.xlsx,.ppt,.pptx,.zip,.rar,.png,.jpg,.jpeg,.gif,.webp';
    
    fileInput.onchange = async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      
      console.log('🔄 Replacing file for document:', documentId, file.name);
      
      try {
        const apiBases = resolveApiBases();
        const formData = new FormData();
        formData.append('file', file);
        formData.append('title', documentTitle || file.name);

        for (const baseUrl of apiBases) {
          try {
            const replaceResponse = await fetch(baseUrl + `/documents/${documentId}/replace`, {
              method: 'POST',
              credentials: 'include',
              body: formData
            });

            if (replaceResponse.ok) {
              const result = await replaceResponse.json();
              if (!result.success) {
                throw new Error(result.error || 'Replace failed');
              }
              console.log('✅ File replaced successfully:', result);

              const documentsUrl = targetUserId ? `/documents?userId=${targetUserId}` : "/documents";
              const documentsPayload = await fetchFromApi(documentsUrl);
              if (documentsPayload) {
                allDocuments = documentsPayload.documents || [];
                renderDocuments();
              }
              showDocumentsToast(t("documents.toast.replaced"), "success");
              return;
            }

            if (replaceResponse.status === 413) {
              throw new Error(t("documents.fileTooLarge"));
            }
          } catch (err) {
            console.error('Replace error:', err);
          }
        }

        showDocumentsToast(t("documents.toast.replaceFailed"), "error");
      } catch (error) {
        console.error('❌ Replace error:', error);
        showDocumentsToast(t("documents.toast.replaceFileError", { error: error.message }), "error");
      }
    };
    
    fileInput.click();
  }

  // Delete document
  async function deleteDocument(documentId) {
    const confirmed = await confirmDocumentDeleteOnPage();
    if (!confirmed) {
      return;
    }
    
    const apiBases = resolveApiBases();
    
    for (const baseUrl of apiBases) {
      try {
        const response = await fetch(baseUrl + `/documents/${documentId}`, {
          method: 'DELETE',
          credentials: 'include',
          headers: {
            'Content-Type': 'application/json'
          }
        });
        
        if (response.ok) {
          // Reload documents
          const documentsUrl = targetUserId ? `/documents?userId=${targetUserId}` : "/documents";
          const documentsPayload = await fetchFromApi(documentsUrl);
          if (documentsPayload) {
            allDocuments = documentsPayload.documents || [];
            renderDocuments();
          }
          showDocumentsToast(t("documents.toast.deleted"), "success");
          return;
        }
      } catch (err) {
        console.error('Delete error:', err);
      }
    }
    
    showDocumentsToast(t("documents.toast.deleteFailed"), "error");
  }

  // Event delegation for all document actions
  document.addEventListener('click', (e) => {
    const button = e.target.closest('button[data-action]');
    if (!button) return;
    
    const action = button.dataset.action;
    const docId = button.dataset.docId;
    const docTitle = button.dataset.docTitle;
    
    switch (action) {
      case 'upload':
        handleUploadClick(docId, docTitle);
        break;
      case 'view':
        viewDocument(docId);
        break;
      case 'approve':
        approveDocument(docId);
        break;
      case 'reject':
        openRejectModal(docId);
        break;
      case 'revoke':
        revokeApproval(docId);
        break;
      case 'replace':
        handleReplaceFile(docId, docTitle);
        break;
      case 'delete':
        deleteDocument(docId);
        break;
    }
  });

  // Modal event listeners
  const closeModalBtn = document.getElementById('close-rejection-modal');
  const cancelBtn = document.getElementById('cancel-rejection');
  const confirmBtn = document.getElementById('confirm-rejection');
  
  if (closeModalBtn) closeModalBtn.addEventListener('click', closeRejectModal);
  if (cancelBtn) cancelBtn.addEventListener('click', closeRejectModal);
  if (confirmBtn) confirmBtn.addEventListener('click', confirmRejectDocument);
  
  // Close modal on backdrop click
  const modal = document.getElementById('rejection-modal');
  if (modal) {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) {
        closeRejectModal();
      }
    });
  }

  window.addEventListener("lk-locale-change", () => {
    if (window.LkI18n) window.LkI18n.applyDocument();
    refreshDocumentsHeaderI18n();
    renderDocuments();
    const historyModal = document.getElementById("history-modal");
    if (historyModal && !historyModal.classList.contains("hidden")) {
      loadDocumentHistory();
    }
  });

  initDocumentsPage();
})();
