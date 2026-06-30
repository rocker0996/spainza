(function () {

  const defaultAvatar = "../img/Avatar.jpg";
  /** Запасной id поддержки, если в сессии ещё нет support_user_id. */
  const SUPPORT_USER_ID_FALLBACK = 3;
  let dashboardSessionUser = null;
  let dashboardConversations = [];
  let dashboardLastCaseData = null;
  let dashboardClientBadges = null;
  let dashboardStaffUsers = [];
  let dashboardStaffBadges = null;
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

  const staffDashboardI18n = {
    ru: {
      "dashboard.staffEyebrow": "Операционный пульт",
      "dashboard.staffTitle": "Рабочая главная",
      "dashboard.staffSubtitle": "Клиенты, документы, сообщения и ближайшие даты в одном рабочем обзоре.",
      "dashboard.staffTemplates": "Шаблоны",
      "dashboard.staffKpiClients": "Клиенты",
      "dashboard.staffKpiClientsHint": "в доступе",
      "dashboard.staffKpiPendingDocs": "Документы",
      "dashboard.staffKpiPendingDocsHint": "клиентов ждут проверки",
      "dashboard.staffKpiMessages": "Сообщения",
      "dashboard.staffKpiMessagesHint": "непрочитанных",
      "dashboard.staffKpiDeadlines": "Даты",
      "dashboard.staffKpiDeadlinesHint": "в ближайшие 14 дней",
      "dashboard.staffPriorityQueue": "Очередь приоритетов",
      "dashboard.staffUpcomingDates": "Ближайшие даты",
      "dashboard.staffInbox": "Последние сообщения",
      "dashboard.staffCase": "Кейс",
      "dashboard.staffDocs": "Документы",
      "dashboard.staffMessages": "Сообщения",
      "dashboard.staffNotes": "Заметки",
      "dashboard.staffNoPriority": "Нет клиентов, требующих действия",
      "dashboard.staffNoDeadlines": "Нет ближайших дат",
      "dashboard.staffNoMessages": "Нет последних сообщений",
      "dashboard.staffNoDate": "Дата не указана",
      "dashboard.staffDeadlineOverdue": "Просрочено",
      "dashboard.staffDeadlineToday": "Сегодня",
      "dashboard.staffDeadlineTomorrow": "Завтра",
      "dashboard.staffDeadlineInDays": "через {n} дн.",
      "dashboard.staffUnnamedClient": "Клиент без имени",
      "dashboard.staffFocusTitle": "Фокус дня",
      "dashboard.staffFocusHint": "сводка",
      "dashboard.staffFocusDeadline": "Ближайшая дата",
      "dashboard.staffFocusDocuments": "Документы",
      "dashboard.staffFocusDialog": "Диалог",
      "dashboard.staffFocusLoad": "Нагрузка",
      "dashboard.staffFocusLoadValue": "{n} активных кейсов",
      "dashboard.staffImportantActions": "Важные действия",
      "dashboard.staffActionOverdue": "Дата уже прошла: {date}",
      "dashboard.staffActionNoDate": "Нужно указать дату консульства",
      "dashboard.staffActionPendingDocs": "Документы на проверке: {n}",
      "dashboard.staffNoImportantActions": "Срочных действий сейчас нет",
    },
    en: {
      "dashboard.staffEyebrow": "Operations console",
      "dashboard.staffTitle": "Work dashboard",
      "dashboard.staffSubtitle": "Clients, documents, messages, and upcoming dates in one operational view.",
      "dashboard.staffTemplates": "Templates",
      "dashboard.staffKpiClients": "Clients",
      "dashboard.staffKpiClientsHint": "visible",
      "dashboard.staffKpiPendingDocs": "Documents",
      "dashboard.staffKpiPendingDocsHint": "clients need review",
      "dashboard.staffKpiMessages": "Messages",
      "dashboard.staffKpiMessagesHint": "unread",
      "dashboard.staffKpiDeadlines": "Dates",
      "dashboard.staffKpiDeadlinesHint": "next 14 days",
      "dashboard.staffPriorityQueue": "Priority queue",
      "dashboard.staffUpcomingDates": "Upcoming dates",
      "dashboard.staffInbox": "Recent messages",
      "dashboard.staffCase": "Case",
      "dashboard.staffDocs": "Documents",
      "dashboard.staffMessages": "Messages",
      "dashboard.staffNotes": "Notes",
      "dashboard.staffNoPriority": "No clients need action",
      "dashboard.staffNoDeadlines": "No upcoming dates",
      "dashboard.staffNoMessages": "No recent messages",
      "dashboard.staffNoDate": "No date set",
      "dashboard.staffDeadlineOverdue": "Overdue",
      "dashboard.staffDeadlineToday": "Today",
      "dashboard.staffDeadlineTomorrow": "Tomorrow",
      "dashboard.staffDeadlineInDays": "in {n} days",
      "dashboard.staffUnnamedClient": "Unnamed client",
      "dashboard.staffFocusTitle": "Daily focus",
      "dashboard.staffFocusHint": "summary",
      "dashboard.staffFocusDeadline": "Next date",
      "dashboard.staffFocusDocuments": "Documents",
      "dashboard.staffFocusDialog": "Conversation",
      "dashboard.staffFocusLoad": "Workload",
      "dashboard.staffFocusLoadValue": "{n} active cases",
      "dashboard.staffImportantActions": "Important actions",
      "dashboard.staffActionOverdue": "Date has passed: {date}",
      "dashboard.staffActionNoDate": "Set the consulate date",
      "dashboard.staffActionPendingDocs": "Documents to review: {n}",
      "dashboard.staffNoImportantActions": "No urgent actions right now",
    },
  };

  const clientDashboardI18n = {
    ru: {
      "dashboard.clientEyebrow": "Личный кабинет",
      "dashboard.clientTitle": "Ваш кейс Spainza",
      "dashboard.clientSubtitle": "Ключевой статус, ближайшие действия и связь с командой в одном месте.",
      "dashboard.clientActionsTitle": "Что нужно от вас",
      "dashboard.clientOpenDocuments": "Открыть документы",
      "dashboard.clientDocumentsTitle": "Документы",
      "dashboard.clientSummaryStatus": "Статус",
      "dashboard.clientSummaryStage": "Текущий этап",
      "dashboard.clientSummaryDate": "Консульство",
      "dashboard.clientSummaryCountry": "Страна",
      "dashboard.clientStatusCompleted": "Кейс завершён",
      "dashboard.clientStatusActive": "В работе",
      "dashboard.clientStatusWaitingDocs": "Ожидаем документы",
      "dashboard.clientStatusRejectedDocs": "Нужно заменить документ",
      "dashboard.clientNoStage": "Этап пока не указан",
      "dashboard.clientNoDate": "Дата не указана",
      "dashboard.clientDocsRequired": "Нужно загрузить документы",
      "dashboard.clientDocsRequiredMeta": "{n} в ожидании: {items}",
      "dashboard.clientRejectedDocsRequired": "Нужно заменить документы",
      "dashboard.clientRejectedDocsRequiredMeta": "{n} отклонено. Проверьте комментарий и загрузите новую версию.",
      "dashboard.clientDocsReady": "Документы на вашей стороне в порядке",
      "dashboard.clientDocsReadyMeta": "Новых запросов от команды сейчас нет.",
      "dashboard.clientNextStep": "Следующий шаг",
      "dashboard.clientNextStepMeta": "Ознакомьтесь с текущим этапом кейса.",
      "dashboard.clientUpcomingAppointment": "Ближайшая дата",
      "dashboard.clientUpcomingAppointmentMeta": "Запись в консульство: {date}",
      "dashboard.clientMessageAction": "Есть новое сообщение",
      "dashboard.clientMessageActionMeta": "Ответьте команде в сообщениях.",
      "dashboard.clientNoActions": "Сейчас действий от вас не требуется",
      "dashboard.clientNoActionsMeta": "Мы обновим этот блок, когда появится новый запрос.",
      "dashboard.clientRequestedDocuments": "Запрошенные документы",
      "dashboard.clientRequestedDocumentsMeta": "Загрузите файлы в разделе документов.",
      "dashboard.clientArchiveReady": "Готовый пакет",
      "dashboard.clientArchivePending": "Готовый пакет ещё не загружен",
      "dashboard.clientMoreItems": "ещё {n}",
    },
    en: {
      "dashboard.clientEyebrow": "Client portal",
      "dashboard.clientTitle": "Your Spainza case",
      "dashboard.clientSubtitle": "Key status, next actions, and your team channel in one place.",
      "dashboard.clientActionsTitle": "Needed from you",
      "dashboard.clientOpenDocuments": "Open documents",
      "dashboard.clientDocumentsTitle": "Documents",
      "dashboard.clientSummaryStatus": "Status",
      "dashboard.clientSummaryStage": "Current stage",
      "dashboard.clientSummaryDate": "Consulate",
      "dashboard.clientSummaryCountry": "Country",
      "dashboard.clientStatusCompleted": "Case completed",
      "dashboard.clientStatusActive": "In progress",
      "dashboard.clientStatusWaitingDocs": "Waiting for documents",
      "dashboard.clientStatusRejectedDocs": "Replace a document",
      "dashboard.clientNoStage": "No stage set yet",
      "dashboard.clientNoDate": "No date set",
      "dashboard.clientDocsRequired": "Upload requested documents",
      "dashboard.clientDocsRequiredMeta": "{n} pending: {items}",
      "dashboard.clientRejectedDocsRequired": "Replace documents",
      "dashboard.clientRejectedDocsRequiredMeta": "{n} rejected. Check the comment and upload a new version.",
      "dashboard.clientDocsReady": "Your document side is clear",
      "dashboard.clientDocsReadyMeta": "There are no new team requests right now.",
      "dashboard.clientNextStep": "Next step",
      "dashboard.clientNextStepMeta": "Review the current case stage.",
      "dashboard.clientUpcomingAppointment": "Upcoming date",
      "dashboard.clientUpcomingAppointmentMeta": "Consulate appointment: {date}",
      "dashboard.clientMessageAction": "New message",
      "dashboard.clientMessageActionMeta": "Reply to the team in Messages.",
      "dashboard.clientNoActions": "No action is needed from you right now",
      "dashboard.clientNoActionsMeta": "We will update this block when a new request appears.",
      "dashboard.clientRequestedDocuments": "Requested documents",
      "dashboard.clientRequestedDocumentsMeta": "Upload the files in the documents section.",
      "dashboard.clientArchiveReady": "Completed package",
      "dashboard.clientArchivePending": "Completed package has not been uploaded yet",
      "dashboard.clientMoreItems": "{n} more",
    },
  };

  function ensureStaffDashboardI18n() {
    if (!window.LkI18n || !window.LkI18n.STRINGS) return;
    window.LkI18n.STRINGS.ru = {
      ...(window.LkI18n.STRINGS.ru || {}),
      ...staffDashboardI18n.ru,
    };
    window.LkI18n.STRINGS.en = {
      ...(window.LkI18n.STRINGS.en || {}),
      ...staffDashboardI18n.en,
    };
    if (typeof window.LkI18n.applyDocument === "function") {
      window.LkI18n.applyDocument(document);
    }
  }

  function ensureClientDashboardI18n() {
    if (!window.LkI18n || !window.LkI18n.STRINGS) return;
    window.LkI18n.STRINGS.ru = {
      ...(window.LkI18n.STRINGS.ru || {}),
      ...clientDashboardI18n.ru,
    };
    window.LkI18n.STRINGS.en = {
      ...(window.LkI18n.STRINGS.en || {}),
      ...clientDashboardI18n.en,
    };
    if (typeof window.LkI18n.applyDocument === "function") {
      window.LkI18n.applyDocument(document);
    }
  }

  function isStaffUser(user) {
    const raw = user?.role?.level;
    const level = parseFloat(String(raw ?? ""));
    return Number.isFinite(level) && level <= 4;
  }

  function setDashboardMode(mode) {
    const clientNode = document.getElementById("client-dashboard");
    const staffNode = document.getElementById("staff-dashboard");
    if (clientNode) {
      clientNode.classList.toggle("hidden", mode === "staff");
    }
    if (staffNode) {
      staffNode.classList.toggle("hidden", mode !== "staff");
    }
  }

  function parseTargetDate(value) {
    const raw = String(value || "").trim();
    const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(raw);
    if (!match) return null;
    const date = new Date(
      Number(match[1]),
      Number(match[2]) - 1,
      Number(match[3])
    );
    return Number.isNaN(date.getTime()) ? null : date;
  }

  function formatTargetDate(value) {
    const date = parseTargetDate(value);
    if (!date) return t("dashboard.staffNoDate");
    const month = window.LkI18n
      ? window.LkI18n.formatMonthShort(date.getMonth())
      : String(date.getMonth() + 1);
    return `${date.getDate()} ${month} ${date.getFullYear()}`;
  }

  function daysUntilTarget(value) {
    const date = parseTargetDate(value);
    if (!date) return null;
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    date.setHours(0, 0, 0, 0);
    return Math.round((date.getTime() - today.getTime()) / 86400000);
  }

  function formatDeadlineMeta(days) {
    if (days === null) return t("dashboard.staffNoDate");
    if (days < 0) return t("dashboard.staffDeadlineOverdue");
    if (days === 0) return t("dashboard.staffDeadlineToday");
    if (days === 1) return t("dashboard.staffDeadlineTomorrow");
    return t("dashboard.staffDeadlineInDays", { n: days });
  }

  function truthyFlag(value) {
    return (
      value === true ||
      value === 1 ||
      value === "1" ||
      String(value || "").toLowerCase() === "true"
    );
  }

  function caseTimeline(caseData) {
    return Array.isArray(caseData?.timeline) ? caseData.timeline : [];
  }

  function openDocumentRequests(caseData) {
    const requests = Array.isArray(caseData?.document_requests)
      ? caseData.document_requests
      : [];
    return requests.filter(
      (item) => truthyFlag(item?.sent) && !truthyFlag(item?.fulfilled)
    );
  }

  function documentRequestName(item) {
    return (
      String(item?.name || "").trim() ||
      String(item?.title || "").trim() ||
      t("dashboard.clientDocumentsTitle")
    );
  }

  function activeTimelineStep(caseData) {
    const steps = caseTimeline(caseData);
    return (
      steps.find((step) => String(step?.status || "").toLowerCase() === "active") ||
      steps.find((step) => String(step?.status || "").toLowerCase() === "pending") ||
      [...steps].reverse().find((step) => String(step?.status || "").toLowerCase() === "completed") ||
      null
    );
  }

  function formatClientTargetDate(value) {
    const date = parseTargetDate(value);
    if (!date) return t("dashboard.clientNoDate");
    const month = window.LkI18n
      ? window.LkI18n.formatMonthShort(date.getMonth())
      : String(date.getMonth() + 1);
    return `${date.getDate()} ${month} ${date.getFullYear()}`;
  }

  function clientSummaryTile(icon, labelKey, value, toneClass = "text-primary-container") {
    return `
      <div class="rounded-[12px] bg-surface p-4 border border-outline-variant/20 min-w-0">
        <div class="flex items-center justify-between gap-3 mb-2">
          <span class="text-[10px] font-label font-bold uppercase tracking-widest text-outline">${escapeHtml(t(labelKey))}</span>
          <span class="material-symbols-outlined ${toneClass} text-[20px]">${escapeHtml(icon)}</span>
        </div>
        <p class="text-sm md:text-base font-headline font-extrabold text-on-surface leading-snug break-words">${escapeHtml(value)}</p>
      </div>
    `;
  }

  function renderClientSummary(caseData, sessionUser, badges = dashboardClientBadges) {
    const container = document.getElementById("client-case-summary");
    if (!container) return;

    const pendingDocs = openDocumentRequests(caseData);
    const rejectedDocs = Number(badges?.document_rejected_count || 0);
    const completedAt = caseData?.completed_at || caseData?.case_completed_at || null;
    const currentStep = activeTimelineStep(caseData);
    const status = completedAt
      ? t("dashboard.clientStatusCompleted")
      : rejectedDocs > 0
        ? t("dashboard.clientStatusRejectedDocs")
        : pendingDocs.length
        ? t("dashboard.clientStatusWaitingDocs")
        : t("dashboard.clientStatusActive");
    const country = String(caseData?.country || "").trim() || t("dashboard.countryNotSet");
    const stage =
      String(currentStep?.title || "").trim() || t("dashboard.clientNoStage");
    const dateLabel = formatClientTargetDate(caseData?.target_date);

    container.innerHTML = [
      clientSummaryTile(
        completedAt
          ? "verified"
          : rejectedDocs > 0
            ? "assignment_late"
            : pendingDocs.length
              ? "pending_actions"
              : "auto_awesome_motion",
        "dashboard.clientSummaryStatus",
        status,
        completedAt
          ? "text-emerald-600"
          : rejectedDocs > 0
            ? "text-red-600"
            : pendingDocs.length
              ? "text-tertiary-container"
              : "text-primary-container"
      ),
      clientSummaryTile("flag", "dashboard.clientSummaryStage", stage, "text-secondary"),
      clientSummaryTile("event", "dashboard.clientSummaryDate", dateLabel, "text-primary"),
      clientSummaryTile("public", "dashboard.clientSummaryCountry", country, "text-tertiary-container"),
    ].join("");

    void sessionUser;
  }

  function clientActionRow(icon, title, meta, href, toneClass = "text-primary-container") {
    return `
      <a href="${escapeHtml(href)}" class="flex items-start gap-3 rounded-[12px] bg-surface p-4 border border-outline-variant/20 no-underline hover:bg-surface-container-low transition-colors">
        <span class="material-symbols-outlined ${toneClass} text-[21px] mt-0.5">${escapeHtml(icon)}</span>
        <span class="min-w-0">
          <span class="block text-sm font-bold font-headline text-on-surface truncate">${escapeHtml(title)}</span>
          <span class="block text-xs text-on-surface-variant mt-1 line-clamp-2">${escapeHtml(meta)}</span>
        </span>
      </a>
    `;
  }

  function renderClientActions(caseData, conversations, sessionUser, badges = dashboardClientBadges) {
    const container = document.getElementById("client-action-list");
    if (!container) return;

    const rows = [];
    const pendingDocs = openDocumentRequests(caseData);
    const rejectedDocs = Number(badges?.document_rejected_count || 0);
    if (rejectedDocs > 0) {
      rows.push(
        clientActionRow(
          "assignment_late",
          t("dashboard.clientRejectedDocsRequired"),
          t("dashboard.clientRejectedDocsRequiredMeta", { n: rejectedDocs }),
          "./documents.html",
          "text-red-600"
        )
      );
    }

    if (pendingDocs.length) {
      const names = pendingDocs.slice(0, 2).map(documentRequestName);
      if (pendingDocs.length > 2) {
        names.push(t("dashboard.clientMoreItems", { n: pendingDocs.length - 2 }));
      }
      rows.push(
        clientActionRow(
          "upload_file",
          t("dashboard.clientDocsRequired"),
          t("dashboard.clientDocsRequiredMeta", {
            n: pendingDocs.length,
            items: names.join(", "),
          }),
          "./documents.html",
          "text-tertiary-container"
        )
      );
    }

    const days = daysUntilTarget(caseData?.target_date);
    if (days !== null && days >= 0 && days <= 14) {
      rows.push(
        clientActionRow(
          "event_upcoming",
          t("dashboard.clientUpcomingAppointment"),
          t("dashboard.clientUpcomingAppointmentMeta", {
            date: formatClientTargetDate(caseData?.target_date),
          }),
          "./documents.html",
          "text-primary"
        )
      );
    }

    const target = resolveMessageDeskTarget(sessionUser);
    const conv = findDeskConversation(conversations, target);
    const hasInbound = Boolean(
      conv && formatMessagePreviewForUi(conv.last_inbound_message)
    );
    if (hasInbound) {
      rows.push(
        clientActionRow(
          "mark_chat_unread",
          t("dashboard.clientMessageAction"),
          t("dashboard.clientMessageActionMeta"),
          "./messages.html",
          "text-secondary"
        )
      );
    }

    const currentStep = activeTimelineStep(caseData);
    if (!pendingDocs.length && currentStep) {
      rows.push(
        clientActionRow(
          "route",
          String(currentStep?.title || "").trim() || t("dashboard.clientNextStep"),
          String(currentStep?.description || "").trim() || t("dashboard.clientNextStepMeta"),
          "./dashboard.html#dashboard-timeline",
          "text-primary-container"
        )
      );
    }

    if (!rows.length) {
      container.innerHTML = `
        <div class="flex items-start gap-3 rounded-[12px] bg-surface-container-low p-4 border border-outline-variant/20">
          <span class="material-symbols-outlined text-emerald-600 text-[22px] mt-0.5">check_circle</span>
          <span>
            <span class="block text-sm font-bold font-headline text-on-surface">${escapeHtml(t("dashboard.clientNoActions"))}</span>
            <span class="block text-xs text-on-surface-variant mt-1">${escapeHtml(t("dashboard.clientNoActionsMeta"))}</span>
          </span>
        </div>
      `;
      return;
    }

    container.innerHTML = rows.join("");
  }

  function isCaseCompleted(user) {
    return Boolean(user && (user.completed_at || user.case_completed_at));
  }

  function isClientLikeUser(user) {
    const role = user?.role || {};
    const level = parseFloat(String(role.level ?? ""));
    if (Number.isFinite(level)) {
      return level > 4;
    }
    const key = String(role.key || role.role_key || "").toLowerCase();
    return !["management", "admin", "support", "moderator", "manager"].includes(key);
  }

  function clientRef(user) {
    const displayId = String(user?.display_id || "").trim().toUpperCase();
    if (/^[A-Z]{2}\d{4}$/.test(displayId)) {
      return `client=${encodeURIComponent(displayId)}`;
    }
    return `userId=${encodeURIComponent(String(user?.id || ""))}`;
  }

  function clientDisplayName(user) {
    return (
      String(user?.name || "").trim() ||
      String(user?.email || "").trim() ||
      t("dashboard.staffUnnamedClient")
    );
  }

  function initialsForUser(user) {
    const base = clientDisplayName(user);
    return base
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part.charAt(0))
      .join("")
      .toUpperCase()
      .slice(0, 2) || "CL";
  }

  function roleLabel(role) {
    if (!role) return "";
    if (window.LkI18n && role.key) {
      return window.LkI18n.roleLabel(role.key);
    }
    return role.name_ru || role.name_en || role.key || "";
  }

  function staffEmptyState(icon, textKey) {
    return `
      <div class="flex flex-col items-center justify-center gap-3 min-h-[8rem] rounded-[12px] bg-surface-container-low p-6 text-center">
        <span class="material-symbols-outlined text-4xl text-outline">${icon}</span>
        <p class="text-sm font-semibold font-headline text-on-surface-variant">${escapeHtml(t(textKey))}</p>
      </div>
    `;
  }

  function formatTimeAgo(value) {
    if (!value) return t("common.justNow");
    const date = window.LkI18n?.parseInstant(value) || new Date(value);
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
    const section = container.closest("section");
    const completedAt = caseData?.completed_at || caseData?.case_completed_at || null;
    const isCompleted = Boolean(completedAt);
    const completedBadge = document.getElementById("dashboard-case-completed-badge");
    if (completedBadge) {
      completedBadge.classList.toggle("hidden", !isCompleted);
    }
    if (section) {
      section.classList.toggle("bg-emerald-50", isCompleted);
      section.classList.toggle("border", isCompleted);
      section.classList.toggle("border-emerald-200", isCompleted);
      section.classList.toggle("ring-1", isCompleted);
      section.classList.toggle("ring-emerald-100", isCompleted);
    }

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
      .map((step, index) => {
        const status = String(step?.status || "pending");
        const title = escapeHtml(step?.title || t("dashboard.stepUntitled"));
        const description = escapeHtml(step?.description || "");
        const isLast = index === timeline.length - 1;

        const icon =
          status === "completed"
            ? `<div class="relative z-10 w-9 h-9 rounded-full bg-primary-fixed border border-primary-container/20 flex items-center justify-center shadow-[0_0_0_5px_rgba(235,239,255,0.9)]"><span class="material-symbols-outlined text-primary-container text-[18px]">check</span></div>`
            : status === "active"
              ? `<div class="relative z-10 w-9 h-9 rounded-full bg-white border-2 border-tertiary-container flex items-center justify-center shadow-[0_0_0_5px_rgba(248,250,252,0.95)]"><div class="w-2.5 h-2.5 rounded-full bg-tertiary-container"></div></div>`
              : `<div class="relative z-10 w-9 h-9 rounded-full bg-surface-container-low border border-outline-variant/40 flex items-center justify-center shadow-[0_0_0_5px_rgba(248,250,252,0.92)]"><span class="material-symbols-outlined text-outline text-[17px]">schedule</span></div>`;

        const body =
          status === "active"
            ? `<div class="bg-surface-container-low p-5 rounded-[12px] border border-primary-container/10 flex-1"><div class="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-2 mb-2"><h3 class="text-base font-semibold font-headline text-on-surface">${title}</h3><span class="inline-flex w-fit bg-tertiary-container text-on-tertiary px-2.5 py-1 rounded-md text-[10px] font-bold uppercase tracking-wider font-label">${escapeHtml(t("dashboard.currentStage"))}</span></div><p class="text-sm text-on-surface-variant font-body leading-relaxed">${description || escapeHtml(t("dashboard.noDescription"))}</p></div>`
            : `<div class="pt-1.5"><h3 class="text-base font-semibold font-headline text-on-surface">${title}</h3><p class="text-sm text-on-surface-variant font-body mt-1 leading-relaxed">${description || escapeHtml(t("dashboard.noDescription"))}</p></div>`;

        return `
          <div class="grid grid-cols-[2.25rem_minmax(0,1fr)] gap-5 relative ${status === "pending" ? "opacity-55" : ""}">
            <div class="relative flex justify-center">
              ${!isLast ? '<div class="absolute top-9 bottom-[-1.5rem] w-px bg-outline-variant/35"></div>' : ""}
              ${icon}
            </div>
            ${body}
          </div>
        `;
      })
      .join("");

    container.className = "flex flex-col gap-6 min-h-[100px]";
    container.innerHTML = rows;
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
    const pendingDocs = openDocumentRequests(caseData);
    const cards = [];

    if (pendingDocs.length) {
      const names = pendingDocs.slice(0, 3).map(documentRequestName);
      if (pendingDocs.length > 3) {
        names.push(t("dashboard.clientMoreItems", { n: pendingDocs.length - 3 }));
      }
      cards.push(`
        <a href="./documents.html" class="flex items-center justify-between p-4 bg-surface-container-low rounded-[12px] group no-underline hover:bg-surface-container transition-colors">
          <div class="flex items-center gap-4 min-w-0">
            <div class="w-10 h-10 rounded-[8px] bg-tertiary-container/15 text-tertiary-container flex items-center justify-center shrink-0">
              <span class="material-symbols-outlined">upload_file</span>
            </div>
            <div class="min-w-0">
              <p class="font-semibold text-sm font-headline text-on-surface truncate">${escapeHtml(t("dashboard.clientRequestedDocuments"))}</p>
              <p class="text-xs text-outline font-body mt-0.5 truncate">${escapeHtml(names.join(", "))}</p>
            </div>
          </div>
          <span class="material-symbols-outlined text-outline group-hover:text-primary-container transition-colors text-[20px] shrink-0">arrow_forward</span>
        </a>
      `);
    } else {
      cards.push(`
        <a href="./documents.html" class="flex items-center justify-between p-4 bg-surface-container-low rounded-[12px] group no-underline hover:bg-surface-container transition-colors">
          <div class="flex items-center gap-4 min-w-0">
            <div class="w-10 h-10 rounded-[8px] bg-emerald-50 text-emerald-600 flex items-center justify-center shrink-0">
              <span class="material-symbols-outlined">task_alt</span>
            </div>
            <div class="min-w-0">
              <p class="font-semibold text-sm font-headline text-on-surface truncate">${escapeHtml(t("dashboard.clientDocsReady"))}</p>
              <p class="text-xs text-outline font-body mt-0.5 truncate">${escapeHtml(t("dashboard.clientDocsReadyMeta"))}</p>
            </div>
          </div>
          <span class="material-symbols-outlined text-outline group-hover:text-primary-container transition-colors text-[20px] shrink-0">arrow_forward</span>
        </a>
      `);
    }

    if (!archiveUrl || !archiveName) {
      container.innerHTML = cards.join("");
      return;
    }

    const safeName = escapeHtml(archiveName);
    cards.push(`
      <div class="flex items-center justify-between p-4 bg-surface-container-low rounded-[12px] group">
        <div class="flex items-center gap-4 min-w-0">
          <div class="w-10 h-10 rounded-[8px] bg-secondary-fixed text-on-secondary-fixed flex items-center justify-center">
            <span class="material-symbols-outlined">folder_zip</span>
          </div>
          <div class="min-w-0">
            <p class="font-semibold text-sm font-headline text-on-surface truncate" title="${safeName}">${safeName}</p>
            <p class="text-xs text-outline font-body mt-0.5">${escapeHtml(t("dashboard.clientArchiveReady"))}</p>
          </div>
        </div>
        <a href="${escapeHtml(buildProtectedApiUrl(archiveUrl))}" download class="text-outline hover:text-primary-container transition-colors p-2 shrink-0" title="${escapeHtml(t("dashboard.downloadArchive"))}">
          <span class="material-symbols-outlined text-[20px]">download</span>
        </a>
      </div>
    `);
    container.innerHTML = cards.join("");
  }

  function formatMessagePreviewForUi(raw) {
    const s = String(raw ?? "").trim();
    if (!s) {
      return "";
    }
    if (s.startsWith("[[SPAINZA_MANAGER_COMPLAINT]]")) {
      return t("dashboard.complaintPreview");
    }
    if (s.startsWith("[[SPAINZA_ACCOUNT_DELETION]]")) {
      return t("chat.deletionPreview");
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

  function staffClientUsers() {
    return (Array.isArray(dashboardStaffUsers) ? dashboardStaffUsers : []).filter(
      isClientLikeUser
    );
  }

  function activeStaffUsers() {
    return staffClientUsers().filter(
      (user) => !isCaseCompleted(user)
    );
  }

  function pendingDocsCount(user) {
    return Number(user?.pending_documents_count || 0);
  }

  function sortPriorityUsers(users) {
    return [...users].sort((a, b) => {
      const pa = pendingDocsCount(a);
      const pb = pendingDocsCount(b);
      if (pa !== pb) return pb - pa;

      const da = daysUntilTarget(a?.target_date);
      const db = daysUntilTarget(b?.target_date);
      const va = da === null ? Number.POSITIVE_INFINITY : da;
      const vb = db === null ? Number.POSITIVE_INFINITY : db;
      if (va !== vb) return va - vb;

      return clientDisplayName(a).localeCompare(clientDisplayName(b));
    });
  }

  function staffAvatarHtml(user) {
    if (user?.avatar) {
      return `<img class="w-10 h-10 rounded-full object-cover shrink-0" src="${escapeHtml(user.avatar)}" alt="${escapeHtml(clientDisplayName(user))}"/>`;
    }
    return `<div class="w-10 h-10 rounded-full bg-primary-fixed text-primary-container flex items-center justify-center text-xs font-extrabold font-headline shrink-0">${escapeHtml(initialsForUser(user))}</div>`;
  }

  function renderStaffKpis() {
    const users = staffClientUsers();
    const activeUsers = activeStaffUsers();
    const upcoming = activeUsers.filter((user) => {
      const days = daysUntilTarget(user?.target_date);
      return days !== null && days >= 0 && days <= 14;
    });
    const pendingClients = activeUsers.filter((user) => pendingDocsCount(user) > 0);
    const unread =
      Number(dashboardStaffBadges?.unread_count) ||
      (Array.isArray(dashboardConversations)
        ? dashboardConversations.reduce(
            (sum, item) => sum + Number(item?.unread_count || item?.unread || 0),
            0
          )
        : 0);

    const totalNode = document.getElementById("staff-kpi-total");
    const pendingNode = document.getElementById("staff-kpi-pending-docs");
    const unreadNode = document.getElementById("staff-kpi-unread");
    const deadlinesNode = document.getElementById("staff-kpi-deadlines");
    const kpiGrid = document.getElementById("staff-kpi-grid");
    if (totalNode) totalNode.textContent = String(users.length);
    if (pendingNode) pendingNode.textContent = String(pendingClients.length);
    if (unreadNode) unreadNode.textContent = String(unread);
    if (deadlinesNode) deadlinesNode.textContent = String(upcoming.length);
    if (kpiGrid) kpiGrid.setAttribute("aria-busy", "false");
  }

  function staffStats() {
    const users = staffClientUsers();
    const activeUsers = users.filter((user) => !isCaseCompleted(user));
    const completedUsers = users.filter(isCaseCompleted);
    const pendingClients = activeUsers.filter((user) => pendingDocsCount(user) > 0);
    const noDateClients = activeUsers.filter((user) => daysUntilTarget(user?.target_date) === null);
    const overdueClients = activeUsers.filter((user) => {
      const days = daysUntilTarget(user?.target_date);
      return days !== null && days < 0;
    });
    const upcomingClients = activeUsers.filter((user) => {
      const days = daysUntilTarget(user?.target_date);
      return days !== null && days >= 0 && days <= 14;
    });
    const priorityUsers = sortPriorityUsers(activeUsers);
    return {
      users,
      activeUsers,
      completedUsers,
      pendingClients,
      noDateClients,
      overdueClients,
      upcomingClients,
      priorityUsers,
    };
  }

  function latestConversation() {
    const items = Array.isArray(dashboardConversations) ? dashboardConversations : [];
    if (!items.length) return null;
    return [...items].sort((a, b) => {
      const da = window.LkI18n?.parseInstant(conversationTime(a)) || new Date(conversationTime(a));
      const db = window.LkI18n?.parseInstant(conversationTime(b)) || new Date(conversationTime(b));
      return (db?.getTime?.() || 0) - (da?.getTime?.() || 0);
    })[0] || null;
  }

  function focusTile(icon, labelKey, value, href, toneClass = "text-primary-container") {
    return `
      <a href="${escapeHtml(href || "./clients.html")}" class="rounded-[12px] border border-outline-variant/20 bg-white/70 p-3 no-underline hover:bg-white transition-colors">
        <div class="flex items-center justify-between gap-3">
          <span class="text-[10px] font-label font-bold uppercase tracking-widest text-outline">${escapeHtml(t(labelKey))}</span>
          <span class="material-symbols-outlined text-[18px] ${toneClass}">${escapeHtml(icon)}</span>
        </div>
        <p class="mt-2 text-sm font-headline font-extrabold text-on-surface leading-snug">${escapeHtml(value)}</p>
      </a>
    `;
  }

  function renderStaffFocus() {
    const container = document.getElementById("staff-focus-list");
    if (!container) return;
    const stats = staffStats();
    const nextDeadline = stats.upcomingClients
      .map((user) => ({ user, days: daysUntilTarget(user?.target_date) }))
      .sort((a, b) => a.days - b.days)[0];
    const pendingUser = sortPriorityUsers(stats.pendingClients)[0];
    const conv = latestConversation();
    const convName =
      conv &&
      (String(conv.other_user_name || "").trim() ||
        String(conv.other_user_email || "").trim() ||
        t("dashboard.staffUnnamedClient"));
    const convRef = conv ? conv.other_user_display_id || conv.other_user_id || "" : "";

    const tiles = [
      focusTile(
        "event_upcoming",
        "dashboard.staffFocusDeadline",
        nextDeadline
          ? `${clientDisplayName(nextDeadline.user)} · ${formatDeadlineMeta(nextDeadline.days)}`
          : t("dashboard.staffNoDeadlines"),
        nextDeadline ? `./case.html?${clientRef(nextDeadline.user)}` : "./clients.html",
        "text-primary"
      ),
      focusTile(
        "pending_actions",
        "dashboard.staffFocusDocuments",
        pendingUser
          ? `${clientDisplayName(pendingUser)} · ${pendingDocsCount(pendingUser)}`
          : t("dashboard.staffNoPriority"),
        pendingUser ? `./documents.html?${clientRef(pendingUser)}` : "./clients.html",
        "text-tertiary-container"
      ),
      focusTile(
        "mark_chat_unread",
        "dashboard.staffFocusDialog",
        convName || t("dashboard.staffNoMessages"),
        conv ? `./messages.html?openUserId=${encodeURIComponent(String(convRef))}` : "./messages.html",
        "text-secondary"
      ),
      focusTile(
        "workspaces",
        "dashboard.staffFocusLoad",
        t("dashboard.staffFocusLoadValue", { n: stats.activeUsers.length }),
        "./clients.html",
        "text-primary-container"
      ),
    ];
    container.innerHTML = tiles.join("");
  }

  function importantActionRow(icon, title, meta, href, toneClass = "text-primary-container") {
    return `
      <a href="${escapeHtml(href || "./clients.html")}" class="flex items-start gap-3 rounded-[12px] bg-surface p-4 border border-outline-variant/20 no-underline hover:bg-surface-container-low transition-colors">
        <span class="material-symbols-outlined ${toneClass} text-[20px] mt-0.5">${escapeHtml(icon)}</span>
        <span class="min-w-0">
          <span class="block text-sm font-bold font-headline text-on-surface truncate">${escapeHtml(title)}</span>
          <span class="block text-xs text-on-surface-variant mt-1">${escapeHtml(meta)}</span>
        </span>
      </a>
    `;
  }

  function renderStaffImportantActions() {
    const container = document.getElementById("staff-important-actions-list");
    if (!container) return;
    const stats = staffStats();
    const rows = [];

    if (stats.overdueClients.length) {
      const user = stats.overdueClients
        .map((item) => ({ user: item, days: daysUntilTarget(item?.target_date) }))
        .sort((a, b) => a.days - b.days)[0].user;
      rows.push(
        importantActionRow(
          "warning",
          clientDisplayName(user),
          t("dashboard.staffActionOverdue", { date: formatTargetDate(user?.target_date) }),
          `./case.html?${clientRef(user)}`,
          "text-red-600"
        )
      );
    }

    if (stats.noDateClients.length) {
      const user = sortPriorityUsers(stats.noDateClients)[0];
      rows.push(
        importantActionRow(
          "event_busy",
          clientDisplayName(user),
          t("dashboard.staffActionNoDate"),
          `./case.html?${clientRef(user)}`,
          "text-amber-600"
        )
      );
    }

    if (stats.pendingClients.length) {
      const user = sortPriorityUsers(stats.pendingClients)[0];
      rows.push(
        importantActionRow(
          "fact_check",
          clientDisplayName(user),
          t("dashboard.staffActionPendingDocs", { n: pendingDocsCount(user) }),
          `./documents.html?${clientRef(user)}`,
          "text-tertiary-container"
        )
      );
    }

    if (!rows.length) {
      container.innerHTML = staffEmptyState("task_alt", "dashboard.staffNoImportantActions");
      return;
    }
    container.innerHTML = rows.slice(0, 4).join("");
  }

  function renderPriorityRow(user) {
    const ref = clientRef(user);
    const docs = pendingDocsCount(user);
    const days = daysUntilTarget(user?.target_date);
    const dateLabel = formatTargetDate(user?.target_date);
    const role = roleLabel(user?.role);
    return `
      <article class="rounded-[12px] border border-outline-variant/20 bg-surface p-4">
        <div class="flex flex-col sm:flex-row sm:items-center gap-4">
          <div class="flex items-center gap-3 min-w-0 flex-1">
            ${staffAvatarHtml(user)}
            <div class="min-w-0">
              <div class="flex flex-wrap items-center gap-2">
                <h3 class="font-headline text-sm font-extrabold text-on-surface truncate">${escapeHtml(clientDisplayName(user))}</h3>
                ${docs > 0 ? `<span class="inline-flex items-center rounded-full bg-orange-100 px-2 py-0.5 text-[10px] font-bold text-orange-700">${docs}</span>` : ""}
              </div>
              <p class="text-xs text-outline truncate">${escapeHtml(user?.email || "")}</p>
              <p class="text-xs text-on-surface-variant mt-1">${escapeHtml(role)} · ${escapeHtml(dateLabel)} · ${escapeHtml(formatDeadlineMeta(days))}</p>
            </div>
          </div>
          <div class="grid grid-cols-2 sm:flex gap-2 shrink-0">
            <a href="./case.html?${ref}" class="inline-flex items-center justify-center gap-1.5 rounded-lg bg-primary-container text-on-primary px-3 py-2 text-xs font-bold no-underline hover:opacity-90">
              <span class="material-symbols-outlined text-[16px]">folder_managed</span>${escapeHtml(t("dashboard.staffCase"))}
            </a>
            <a href="./documents.html?${ref}" class="inline-flex items-center justify-center gap-1.5 rounded-lg bg-surface-container-low text-on-surface px-3 py-2 text-xs font-bold no-underline hover:bg-surface-container">
              <span class="material-symbols-outlined text-[16px]">description</span>${escapeHtml(t("dashboard.staffDocs"))}
            </a>
            <a href="./messages.html?openUserId=${encodeURIComponent(String(user?.display_id || user?.id || ""))}" class="inline-flex items-center justify-center gap-1.5 rounded-lg bg-surface-container-low text-on-surface px-3 py-2 text-xs font-bold no-underline hover:bg-surface-container">
              <span class="material-symbols-outlined text-[16px]">chat_bubble</span>${escapeHtml(t("dashboard.staffMessages"))}
            </a>
            <a href="./notes.html?${ref}" class="inline-flex items-center justify-center gap-1.5 rounded-lg bg-surface-container-low text-on-surface px-3 py-2 text-xs font-bold no-underline hover:bg-surface-container">
              <span class="material-symbols-outlined text-[16px]">edit_note</span>${escapeHtml(t("dashboard.staffNotes"))}
            </a>
          </div>
        </div>
      </article>
    `;
  }

  function renderStaffPriorityList() {
    const container = document.getElementById("staff-priority-list");
    if (!container) return;
    const users = sortPriorityUsers(activeStaffUsers()).filter((user) => {
      const days = daysUntilTarget(user?.target_date);
      return pendingDocsCount(user) > 0 || (days !== null && days <= 14);
    });
    if (!users.length) {
      container.innerHTML = staffEmptyState("task_alt", "dashboard.staffNoPriority");
      return;
    }
    container.innerHTML = users.slice(0, 6).map(renderPriorityRow).join("");
  }

  function renderStaffDeadlines() {
    const container = document.getElementById("staff-deadline-list");
    if (!container) return;
    const users = activeStaffUsers()
      .map((user) => ({ user, days: daysUntilTarget(user?.target_date) }))
      .filter((item) => item.days !== null && item.days >= 0 && item.days <= 14)
      .sort((a, b) => a.days - b.days);

    if (!users.length) {
      container.innerHTML = staffEmptyState("event_available", "dashboard.staffNoDeadlines");
      return;
    }

    container.innerHTML = users
      .slice(0, 6)
      .map(({ user, days }) => {
        const ref = clientRef(user);
        return `
          <a href="./case.html?${ref}" class="flex items-center justify-between gap-3 rounded-[12px] bg-surface p-4 border border-outline-variant/20 no-underline hover:bg-surface-container-low transition-colors">
            <div class="min-w-0">
              <p class="text-sm font-bold font-headline text-on-surface truncate">${escapeHtml(clientDisplayName(user))}</p>
              <p class="text-xs text-outline truncate">${escapeHtml(formatTargetDate(user?.target_date))}</p>
            </div>
            <span class="shrink-0 rounded-full bg-primary-fixed px-3 py-1 text-xs font-bold text-primary-container">${escapeHtml(formatDeadlineMeta(days))}</span>
          </a>
        `;
      })
      .join("");
  }

  function conversationTime(conversation) {
    return (
      conversation?.last_message_at ||
      conversation?.last_inbound_message_time ||
      conversation?.updated_at ||
      ""
    );
  }

  function renderStaffInbox() {
    const container = document.getElementById("staff-inbox-list");
    if (!container) return;
    const items = Array.isArray(dashboardConversations) ? dashboardConversations : [];
    if (!items.length) {
      container.innerHTML = staffEmptyState("mark_chat_read", "dashboard.staffNoMessages");
      return;
    }
    const sorted = [...items].sort((a, b) => {
      const da = window.LkI18n?.parseInstant(conversationTime(a)) || new Date(conversationTime(a));
      const db = window.LkI18n?.parseInstant(conversationTime(b)) || new Date(conversationTime(b));
      return (db?.getTime?.() || 0) - (da?.getTime?.() || 0);
    });
    container.innerHTML = sorted
      .slice(0, 5)
      .map((conv) => {
        const name =
          String(conv?.other_user_name || "").trim() ||
          String(conv?.other_user_email || "").trim() ||
          t("dashboard.staffUnnamedClient");
        const text =
          formatMessagePreviewForUi(conv?.last_inbound_message || conv?.last_message || "") ||
          t("common.noMessages");
        const openRef = conv?.other_user_display_id || conv?.other_user_id || "";
        const unread = Number(conv?.unread_count || conv?.unread || 0);
        return `
          <a href="./messages.html?openUserId=${encodeURIComponent(String(openRef))}" class="flex items-start gap-3 rounded-[12px] bg-surface p-4 border border-outline-variant/20 no-underline hover:bg-surface-container-low transition-colors">
            <img class="w-9 h-9 rounded-full object-cover shrink-0" src="${escapeHtml(conv?.other_user_avatar || defaultAvatar)}" alt="${escapeHtml(name)}"/>
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2">
                <p class="text-sm font-bold font-headline text-on-surface truncate">${escapeHtml(name)}</p>
                ${unread > 0 ? `<span class="shrink-0 rounded-full bg-primary px-2 py-0.5 text-[10px] font-bold text-white">${unread > 99 ? "99+" : unread}</span>` : ""}
              </div>
              <p class="text-xs text-outline mt-0.5">${escapeHtml(formatTimeAgo(conversationTime(conv)))}</p>
              <p class="text-sm text-on-surface-variant mt-1 line-clamp-2">${escapeHtml(text)}</p>
            </div>
          </a>
        `;
      })
      .join("");
  }

  async function initStaffDashboard(user) {
    setDashboardMode("staff");
    ensureStaffDashboardI18n();
    try {
      const [usersPayload, badgesPayload, conversationsPayload] = await Promise.all([
        apiGet("/api/users").catch(() => ({ success: false, users: [] })),
        apiGet("/api/lk/nav-badges").catch(() => null),
        apiGet("/api/conversations").catch(() => []),
      ]);
      dashboardStaffUsers =
        usersPayload && usersPayload.success && Array.isArray(usersPayload.users)
          ? usersPayload.users
          : [];
      dashboardStaffBadges = badgesPayload || null;
      dashboardConversations = Array.isArray(conversationsPayload)
        ? conversationsPayload
        : [];
      renderStaffKpis();
      renderStaffFocus();
      renderStaffPriorityList();
      renderStaffDeadlines();
      renderStaffInbox();
      renderStaffImportantActions();
      if (window.LkI18n) {
        window.LkI18n.applyDocument();
      }
    } catch (error) {
      console.error("Staff dashboard load failed:", error);
      dashboardStaffUsers = [];
      dashboardStaffBadges = null;
      dashboardConversations = [];
      renderStaffKpis();
      renderStaffFocus();
      renderStaffPriorityList();
      renderStaffDeadlines();
      renderStaffInbox();
      renderStaffImportantActions();
    }
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
      if (isStaffUser(user)) {
        await initStaffDashboard(user);
        return;
      }
      setDashboardMode("client");
      ensureClientDashboardI18n();
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
      try {
        dashboardClientBadges = await apiGet("/api/lk/nav-badges");
      } catch (error) {
        dashboardClientBadges = null;
      }
      const caseData = casePayload?.case_data || null;
      renderClientSummary(caseData, user, dashboardClientBadges);
      renderClientActions(caseData, dashboardConversations, user, dashboardClientBadges);
      renderTimelineFromCase(caseData);
      renderArchiveDocument(caseData);
      renderCountry(caseData);

      bindQuickReplyHandlers();
      updateQuickReplyUiForTarget(user);

      const conversations = await apiGet("/api/conversations");
      dashboardConversations = Array.isArray(conversations) ? conversations : [];
      renderLatestMessage(dashboardConversations, user);
      renderClientActions(caseData, dashboardConversations, user, dashboardClientBadges);
    } catch (error) {
      console.error("Dashboard data load failed:", error);
    }
  }

  function refreshDashboardLocale() {
    if (dashboardSessionUser && isStaffUser(dashboardSessionUser)) {
      ensureStaffDashboardI18n();
      renderStaffKpis();
      renderStaffFocus();
      renderStaffPriorityList();
      renderStaffDeadlines();
      renderStaffInbox();
      renderStaffImportantActions();
      if (window.LkI18n) {
        window.LkI18n.applyDocument();
      }
      return;
    }
    ensureClientDashboardI18n();
    renderClientSummary(dashboardLastCaseData, dashboardSessionUser, dashboardClientBadges);
    renderClientActions(dashboardLastCaseData, dashboardConversations, dashboardSessionUser, dashboardClientBadges);
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
