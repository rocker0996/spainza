/**
 * Case management page - Dynamic client case loading and management
 */

const API_BASE = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
    ? 'http://localhost:5000/api'
    : '/api';

function t(key, params) {
    return window.LkI18n ? window.LkI18n.t(key, params) : key;
}

function translateCaseHistoryAction(action) {
    return window.LkI18n && window.LkI18n.translateCaseHistoryAction
        ? window.LkI18n.translateCaseHistoryAction(action)
        : action;
}

function getCaseLocale() {
    return window.LkI18n ? window.LkI18n.getLocale() : 'ru';
}

function pickCasePlural(n, keyOne, keyFew, keyMany) {
    if (getCaseLocale() === 'en') {
        return n === 1 ? t(keyOne) : t(keyFew);
    }
    const mod10 = n % 10;
    const mod100 = n % 100;
    if (mod10 === 1 && mod100 !== 11) return t(keyOne);
    if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return t(keyFew);
    return t(keyMany);
}

// Global state
let currentUserId = null;
let currentUser = null;
let loggedInUser = null; // Current logged-in user (manager/admin)
let availableVisaTypes = []; // Visa types that logged-in user can assign
let caseData = {
    visaType: 'digital_nomad',
    targetDate: '',
    country: '',
    archiveFileName: null,
    archiveFileId: null,
    archiveDownloadUrl: null,
    timeline: [],
    documentRequests: [],
    /** true = не подставлять шаблон таймлайна с сервера */
    timelineManual: false,
    /** true = не подставлять шаблон чек-листа документов */
    documentRequestsManual: false,
};
let isEditMode = false;
let draggedElement = null;
/** Не вызывать автосохранение при программной установке #visa-type (иначе уходит пустой кейс до шаблона). */
let suppressVisaSelectSave = false;

function escapeHtmlCase(value) {
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

/** Высота textarea по содержимому: стартует с ~1 строки, растёт при вводе (потолок — часть окна). */
function autosizeCaseStepTextarea(el) {
    if (!el || el.tagName !== "TEXTAREA" || !el.classList.contains("case-step-autosize")) {
        return;
    }
    const maxH = Math.round(window.innerHeight * 0.42);
    const minH = 40;
    el.style.overflowY = "hidden";
    el.style.height = `${minH}px`;
    const sh = el.scrollHeight;
    const target = Math.min(Math.max(sh, minH), maxH);
    el.style.height = `${target}px`;
    el.style.overflowY = sh > maxH ? "auto" : "hidden";
}

function autosizeAllCaseStepTextareas() {
    document.querySelectorAll("#timeline-container textarea.case-step-autosize").forEach(autosizeCaseStepTextarea);
}

let caseTimelineAutosizeResizeTimer = 0;
function bindCaseTimelineTextareaAutosizeOnce() {
    const tl = document.getElementById("timeline-container");
    if (!tl || tl.dataset.caseAutosizeBound === "1") {
        return;
    }
    tl.dataset.caseAutosizeBound = "1";
    tl.addEventListener("input", (e) => {
        const t = e.target;
        if (t && t.matches && t.matches("textarea.case-step-autosize")) {
            autosizeCaseStepTextarea(t);
        }
    });
    window.addEventListener("resize", () => {
        window.clearTimeout(caseTimelineAutosizeResizeTimer);
        caseTimelineAutosizeResizeTimer = window.setTimeout(autosizeAllCaseStepTextareas, 120);
    });
}

let caseToastTimer = null;
let lastEditModeHintAt = 0;
let editModeHintResetTimer = null;

/** @param {"success"|"error"|"info"} variant */
function showCaseToast(message, variant = "info") {
    const el = document.getElementById("case-toast");
    if (!el || !message) {
        return;
    }
    const panelBase =
        "pointer-events-auto flex items-start gap-3 rounded-2xl px-4 py-3 shadow-lg border text-sm font-semibold ";
    const panelClass =
        variant === "success"
            ? panelBase + "bg-green-50 text-green-900 border-green-200"
            : variant === "error"
              ? panelBase + "bg-red-50 text-red-900 border-red-200"
              : panelBase + "bg-slate-50 text-slate-800 border-slate-200";
    const icon =
        variant === "success" ? "check_circle" : variant === "error" ? "error" : "info";
    const iconColor =
        variant === "success"
            ? "text-green-600"
            : variant === "error"
              ? "text-red-600"
              : "text-blue-600";
    el.innerHTML =
        `<div class="${panelClass}"><span class="material-symbols-outlined shrink-0 ${iconColor}">${icon}</span><span class="flex-1 leading-snug">${escapeHtmlCase(message)}</span></div>`;
    el.classList.remove("hidden");
    if (caseToastTimer) {
        clearTimeout(caseToastTimer);
    }
    caseToastTimer = setTimeout(() => {
        el.classList.add("hidden");
        el.innerHTML = "";
        caseToastTimer = null;
    }, 4200);
}

function showEnableEditModeToast() {
    const now = Date.now();
    if (now - lastEditModeHintAt < 1200) {
        return;
    }
    lastEditModeHintAt = now;

    showCaseToast(
        t('case.viewModeOnly'),
        'info'
    );

    const toggleLabel = document.getElementById('edit-mode-toggle')?.closest('label');
    if (!toggleLabel) {
        return;
    }

    toggleLabel.classList.add('ring-2', 'ring-blue-300', 'ring-offset-2', 'ring-offset-slate-50', 'animate-pulse');
    if (editModeHintResetTimer) {
        clearTimeout(editModeHintResetTimer);
    }
    editModeHintResetTimer = setTimeout(() => {
        toggleLabel.classList.remove('ring-2', 'ring-blue-300', 'ring-offset-2', 'ring-offset-slate-50', 'animate-pulse');
        editModeHintResetTimer = null;
    }, 1800);
}

function ruDocumentsWordForm(n) {
    return pickCasePlural(n, "case.docWord1", "case.docWord2", "case.docWord5");
}

/**
 * @param {{ title: string, message: string, confirmText?: string, danger?: boolean }} options
 * @returns {Promise<boolean>}
 */
function showCaseConfirm(options) {
    const title = options.title || t("common.confirm");
    const message = options.message || "";
    const confirmText = options.confirmText || t("common.confirm");
    const danger = Boolean(options.danger);
    return new Promise((resolve) => {
        const existing = document.getElementById("case-generic-confirm-modal");
        if (existing) {
            existing.remove();
        }

        const modal = document.createElement("div");
        modal.id = "case-generic-confirm-modal";
        modal.className = "modal show";
        modal.style.zIndex = "1050";
        const dangerClass = danger
            ? "bg-red-600 hover:bg-red-700 text-white"
            : "bg-blue-600 hover:bg-blue-700 text-white";
        modal.innerHTML = `
        <div class="bg-white rounded-2xl p-6 max-w-md w-full mx-4 shadow-2xl">
            <h3 class="font-manrope text-lg font-bold text-slate-800 mb-2">${escapeHtmlCase(title)}</h3>
            <p class="text-sm text-slate-600 font-body whitespace-pre-wrap">${escapeHtmlCase(message)}</p>
            <div class="flex gap-3 mt-6">
                <button type="button" data-case-confirm="0" class="flex-1 px-4 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 font-manrope font-bold text-sm rounded-xl transition-colors">${t("common.cancel")}</button>
                <button type="button" data-case-confirm="1" class="flex-1 px-4 py-2.5 font-manrope font-bold text-sm rounded-xl transition-colors ${dangerClass}">${escapeHtmlCase(confirmText)}</button>
            </div>
        </div>`;

        document.body.appendChild(modal);

        function finish(ok) {
            modal.remove();
            resolve(ok);
        }

        modal.addEventListener("click", (e) => {
            if (e.target === modal) {
                finish(false);
                return;
            }
            const btn = e.target.closest("[data-case-confirm]");
            if (!btn) {
                return;
            }
            finish(btn.getAttribute("data-case-confirm") === "1");
        });
    });
}

function buildProtectedApiUrl(relativeUrl) {
    const normalized = String(relativeUrl || '').trim();
    if (!normalized) {
        return '';
    }
    return normalized.startsWith('/') ? normalized : `/${normalized}`;
}

/**
 * Redirect to login if not authenticated
 */
function redirectToLogin() {
    window.location.href = '/frontend/login.html';
}

/**
 * Resolve client user id from URL: ?client=AA1234 (preferred) or legacy ?userId=123
 */
async function resolveCasePageTargetUserId() {
    const urlParams = new URLSearchParams(window.location.search);
    const clientRaw = (urlParams.get('client') || '').trim().toUpperCase();
    const legacy = urlParams.get('userId');

    if (clientRaw && /^[A-Z]{2}\d{4}$/.test(clientRaw)) {
        try {
            const response = await fetch(
                `${API_BASE}/lk/case-client/resolve?client=${encodeURIComponent(clientRaw)}`,
                {
                    credentials: 'include',
                }
            );
            const data = await response.json().catch(() => ({}));
            if (!response.ok || !data.success || data.user_id == null) {
                if (response.status === 403 || data.error === 'access denied') {
                    if (typeof window.redirectLkAccessDenied === "function") {
                        window.redirectLkAccessDenied();
                    } else {
                        window.location.replace("/frontend/lk/404.html");
                    }
                    return null;
                }
                const msg =
                    data.error === 'user not found' || response.status === 404
                        ? t('documents.clientNotFound')
                        : t('case.toast.openCaseFailed');
                showCaseToast(msg, 'error');
                return null;
            }
            try {
                const nu = new URL(window.location.href);
                nu.searchParams.set('client', data.display_id || clientRaw);
                nu.searchParams.delete('userId');
                window.history.replaceState(null, '', nu.pathname + nu.search);
            } catch (e) {
                /* ignore */
            }
            return String(data.user_id);
        } catch (e) {
            showCaseToast(t('case.toast.openCaseFailed'), 'error');
            return null;
        }
    }

    if (legacy && /^\d+$/.test(String(legacy).trim())) {
        return String(legacy).trim();
    }
    return null;
}

/**
 * Load logged-in user data
 */
async function loadLoggedInUser() {
    try {
        console.log('Loading logged-in user...');
        const response = await fetch(`${API_BASE}/user`, {
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        if (!response.ok) {
            console.error('Failed to load logged-in user:', response.status);
            return null;
        }

        const data = await response.json();
        console.log('Logged-in user response:', data);
        
        // API returns data directly, not data.user
        if (data.success) {
            // Normalize the structure - add role_key at top level for easier access
            loggedInUser = {
                ...data,
                role_key: data.role?.key || 'client'
            };
            
            // Store available visa types for this user
            availableVisaTypes = data.assignable_visa_types || [];
            console.log('Available visa types for user:', availableVisaTypes);
            
            console.log('Normalized logged-in user:', loggedInUser);
            return loggedInUser;
        }
        return null;
    } catch (error) {
        console.error('Error loading logged-in user:', error);
        return null;
    }
}

/**
 * Load user data from API
 */
async function loadUserData(userId) {
    try {
        const response = await fetch(`${API_BASE}/users/${userId}`, {
            method: 'GET',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        if (response.status === 401) {
            localStorage.removeItem('token');
            redirectToLogin();
            return null;
        }

        if (response.status === 403) {
            if (typeof window.redirectLkAccessDenied === "function") {
                window.redirectLkAccessDenied();
            } else {
                window.location.replace("/frontend/lk/404.html");
            }
            return null;
        }

        if (!response.ok) {
            throw new Error('Failed to load user data');
        }

        const data = await response.json();
        return data.success ? data.user : null;
    } catch (error) {
        console.error('Error loading user data:', error);
        showCaseToast(t("case.toast.loadUserFailed"), "error");
        return null;
    }
}

/**
 * Render available visa types in the select dropdown
 */
function renderVisaTypeOptions() {
    const visaSelect = document.getElementById('visa-type');
    if (!visaSelect) return;
    
    // Clear existing options
    visaSelect.innerHTML = '';
    
    const locale = getCaseLocale();
    const labelKey = locale === 'en' ? 'label_en' : 'label_ru';
    
    // Add available visa types
    if (availableVisaTypes.length === 0) {
        // Fallback: if no visa types available, show a disabled message
        const option = document.createElement('option');
        option.value = '';
        option.textContent = t('case.noVisaPaths');
        option.disabled = true;
        option.selected = true;
        visaSelect.appendChild(option);
        visaSelect.disabled = true;
        console.warn('No visa types available for this user role');
    } else {
        // Add each available visa type
        availableVisaTypes.forEach(visaType => {
            const option = document.createElement('option');
            option.value = visaType.value;
            const i18nLabel = window.LkI18n ? window.LkI18n.visaLabel(visaType.value) : '';
            option.textContent =
                (locale === 'en' && i18nLabel) ||
                visaType[labelKey] ||
                visaType.label_ru ||
                visaType.value;
            visaSelect.appendChild(option);
        });
        
        // Текущая программа клиента должна оставаться в caseData — не подменяем первым пунктом списка.
        if (caseData.visaType && availableVisaTypes.some((vt) => vt.value === caseData.visaType)) {
            visaSelect.value = caseData.visaType;
        } else if (caseData.visaType) {
            const opt = document.createElement('option');
            opt.value = caseData.visaType;
            const roleLabel = window.LkI18n
                ? window.LkI18n.visaLabel(caseData.visaType) || caseData.visaType
                : caseData.visaType;
            opt.textContent = t('case.currentClientRole', { type: roleLabel });
            visaSelect.appendChild(opt);
            visaSelect.value = caseData.visaType;
        } else if (availableVisaTypes.length > 0) {
            visaSelect.value = availableVisaTypes[0].value;
        }
        
        console.log('Rendered visa type options:', availableVisaTypes.length);
    }
}

/**
 * Update page header with user information
 */
function updatePageHeader(user) {
    if (!user) return;

    // Update page title
    document.title = t('case.pageTitle', { name: user.name || user.email });

    // Update header with user name
    const headerTitle = document.getElementById('case-title');
    if (headerTitle) {
        headerTitle.textContent = t('case.headerTitle', { name: user.name || user.email });
    }

    // Update case number badge
    const caseBadge = document.getElementById('case-number');
    if (caseBadge) {
        caseBadge.textContent = `Case #${String(user.id).padStart(6, '0')}`;
    }

    // Не трогаем caseData.visaType здесь: это визовый путь/роль программы из case_data и профиля (bootstrap).
}

/**
 * Load user's case data
 */
async function loadCaseData(userId) {
    try {
        const response = await fetch(`${API_BASE}/case-data/${userId}`, {
            method: 'GET',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        if (!response.ok) {
            console.log('No case data found for user');
            return null;
        }

        const data = await response.json();
        return data.success ? data.case_data : null;
    } catch (error) {
        console.error('Error loading case data:', error);
        return null;
    }
}

async function fetchCaseTemplate(visaType, clientUserId) {
    if (!visaType) return null;
    try {
        let url = `${API_BASE}/case-templates/${encodeURIComponent(visaType)}`;
        if (clientUserId) {
            url += `?for_client_user_id=${encodeURIComponent(clientUserId)}`;
        }
        const response = await fetch(url, {
            credentials: 'include',
        });
        if (response.status === 403 || response.status === 401) return null;
        const data = await response.json();
        if (data.success && data.template) return data.template;
    } catch (e) {
        console.warn('fetchCaseTemplate failed', e);
    }
    return null;
}

function mapTemplateTimelineToCase(steps) {
    const sorted = [...steps].sort((a, b) => (Number(a.order) || 0) - (Number(b.order) || 0));
    return sorted.map((s, i) => {
        const duration = String(s.duration_label || '').trim();
        const desc = String(s.description || '').trim();
        let fullDesc = desc;
        if (duration) {
            fullDesc = desc ? `Срок: ${duration}\n\n${desc}` : `Срок: ${duration}`;
        }
        return {
            id: i + 1,
            title: s.title || `Шаг ${i + 1}`,
            description: fullDesc,
            status: i === 0 ? 'active' : 'pending',
        };
    });
}

function mapTemplateDocsToCase(items) {
    return items.map((it, i) => {
        const required = !!it.required;
        return {
            id: i + 1,
            name: it.name || 'Документ',
            description: String(it.description || ''),
            checked: false,
            priority: it.priority || 'normal',
            sent: required,
            isDefault: true,
        };
    });
}

/**
 * Таймлайн и документы: при отсутствии «ручного» флага всегда подставляется актуальный шаблон;
 * после ручных правок соответствующая часть не перезаписывается шаблоном.
 */
async function bootstrapCaseEditors(loadedCaseData) {
    const timelineManual = !!(loadedCaseData && loadedCaseData.timeline_manual);
    const documentRequestsManual = !!(loadedCaseData && loadedCaseData.document_requests_manual);
    caseData.timelineManual = timelineManual;
    caseData.documentRequestsManual = documentRequestsManual;

    if (loadedCaseData && loadedCaseData.target_date) {
        caseData.targetDate = loadedCaseData.target_date;
        const targetDate = document.getElementById('target-date');
        if (targetDate) targetDate.value = loadedCaseData.target_date;
        syncTargetDatePlaceholder();
    }

    if (loadedCaseData) {
        caseData.country = String(loadedCaseData.country || '').trim();
        const countryInput = document.getElementById('case-country-input');
        if (countryInput) {
            countryInput.value = caseData.country;
        }
        caseData.archiveFileName = loadedCaseData.archive_file_name || null;
        caseData.archiveFileId = loadedCaseData.archive_file_id || null;
        caseData.archiveDownloadUrl = loadedCaseData.archive_download_url || null;
    }

    const clientRoleKey = (currentUser && currentUser.role && currentUser.role.key) || '';
    const storedVisaType = (loadedCaseData && loadedCaseData.visa_type) || '';
    caseData.visaType = clientRoleKey || storedVisaType || caseData.visaType;

    const needTemplateFetch = !timelineManual || !documentRequestsManual;
    let tpl = null;
    if (needTemplateFetch) {
        tpl = await fetchCaseTemplate(caseData.visaType, currentUserId);
    }

    if (!timelineManual) {
        if (tpl && tpl.timeline && tpl.timeline.length > 0) {
            caseData.timeline = mapTemplateTimelineToCase(tpl.timeline);
        } else {
            caseData.timeline = [];
        }
    } else {
        caseData.timeline =
            loadedCaseData && Array.isArray(loadedCaseData.timeline) ? loadedCaseData.timeline : [];
    }

    if (!documentRequestsManual) {
        if (tpl && tpl.document_items && tpl.document_items.length > 0) {
            caseData.documentRequests = mapTemplateDocsToCase(tpl.document_items);
        } else {
            caseData.documentRequests = [];
        }
    } else {
        caseData.documentRequests =
            loadedCaseData && Array.isArray(loadedCaseData.document_requests)
                ? loadedCaseData.document_requests
                : [];
    }

    suppressVisaSelectSave = true;
    try {
        renderVisaTypeOptions();
        const visaTypeSelect = document.getElementById('visa-type');
        if (visaTypeSelect && caseData.visaType) {
            visaTypeSelect.value = caseData.visaType;
        }
    } finally {
        suppressVisaSelectSave = false;
    }
    updateCountryBadge();
    updateArchiveStatus();

    renderTimeline();
    renderDocumentRequests();

    const prevTimeline =
        loadedCaseData && Array.isArray(loadedCaseData.timeline) ? loadedCaseData.timeline : [];
    const prevDocs =
        loadedCaseData && Array.isArray(loadedCaseData.document_requests)
            ? loadedCaseData.document_requests
            : [];
    const tplHadContent =
        tpl &&
        (((tpl.timeline || []).length > 0) || ((tpl.document_items || []).length > 0));
    const persistNeeded =
        (!timelineManual || !documentRequestsManual) &&
        (JSON.stringify(caseData.timeline) !== JSON.stringify(prevTimeline) ||
            JSON.stringify(caseData.documentRequests) !== JSON.stringify(prevDocs) ||
            caseData.visaType !== storedVisaType ||
            (needTemplateFetch && tplHadContent));

    if (persistNeeded) {
        await saveCaseData();
    }
}

function updateCaseArchiveFileLabel() {
    const archiveInput = document.getElementById('case-archive');
    const nameEl = document.getElementById('case-archive-filename');
    if (!archiveInput || !nameEl) return;
    const file = archiveInput.files && archiveInput.files[0];
    if (file) {
        nameEl.removeAttribute('data-i18n');
        nameEl.textContent = file.name;
    } else {
        nameEl.setAttribute('data-i18n', 'case.archiveNoFile');
        nameEl.textContent = t('case.archiveNoFile');
    }
    const pickBtn = document.getElementById('case-archive-pick-btn');
    if (pickBtn) {
        pickBtn.textContent = t('case.archiveChooseFile');
    }
}

function setupCaseArchiveFilePicker() {
    const archiveInput = document.getElementById('case-archive');
    const pickBtn = document.getElementById('case-archive-pick-btn');
    if (!archiveInput) return;

    if (pickBtn) {
        pickBtn.addEventListener('click', () => archiveInput.click());
    }

    archiveInput.addEventListener('change', async () => {
        const selectedFile = archiveInput.files && archiveInput.files[0];
        updateCaseArchiveFileLabel();
        if (!selectedFile) return;

        try {
            await uploadCaseArchive(selectedFile);
        } catch (error) {
            console.error('Error uploading case archive:', error);
            showCaseToast(t('case.toast.archiveFailed', { error: error.message }), "error");
        } finally {
            archiveInput.value = '';
            updateCaseArchiveFileLabel();
        }
    });

    updateCaseArchiveFileLabel();
}

function updateArchiveStatus() {
    const statusElement = document.getElementById('case-archive-status');
    if (!statusElement) return;

    if (caseData.archiveDownloadUrl && caseData.archiveFileName) {
        const safeFileName = escapeHtml(caseData.archiveFileName);
        statusElement.innerHTML = `${t('case.currentArchive')} <a href="${escapeHtml(buildProtectedApiUrl(caseData.archiveDownloadUrl))}" target="_blank" class="text-blue-600 hover:text-blue-700 underline">${safeFileName}</a>`;
        return;
    }

    statusElement.textContent = t('case.archiveEmpty');
}

function updateCountryBadge() {
    const countryBadge = document.getElementById('case-country-badge');
    if (!countryBadge) return;
    countryBadge.textContent = caseData.country || t('clients.notSpecified');
}

function escapeHtml(value) {
    return String(value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

async function uploadCaseArchive(file) {
    if (!currentUserId) {
        throw new Error('missing userId');
    }

    const formData = new FormData();
    formData.append('archive', file);

    const response = await fetch(`${API_BASE}/case-data/${currentUserId}/archive`, {
        method: 'POST',
        credentials: 'include',
        body: formData
    });

    const data = await response.json();
    if (!response.ok || !data.success) {
        throw new Error(data.error || 'Не удалось загрузить архив');
    }

    caseData.archiveFileName = data.archive_file_name || file.name;
    caseData.archiveFileId = data.archive_file_id || null;
    caseData.archiveDownloadUrl = data.archive_download_url || null;
    updateArchiveStatus();
    showSaveNotification();
}

/**
 * Render timeline steps
 */
function renderTimeline() {
    const container = document.getElementById('timeline-container');
    if (!container) return;

    container.innerHTML = caseData.timeline.map((step, index) => {
        const statusClasses = {
            completed: {
                wrap: 'border-l-emerald-500 bg-white border-y border-r border-slate-200',
                select: 'bg-emerald-50 text-emerald-900 border border-emerald-200/80',
            },
            active: {
                wrap: 'border-l-blue-600 bg-gradient-to-br from-white via-white to-blue-50/50 border-y border-r border-blue-100 shadow-md shadow-blue-600/8',
                select: 'bg-blue-600 text-white border border-blue-600',
            },
            pending: {
                wrap: 'border-l-slate-300 bg-slate-50/90 border-y border-r border-slate-200',
                select: 'bg-white text-slate-700 border border-slate-200',
            },
        };

        const classes = statusClasses[step.status] || statusClasses.pending;
        const titleEsc = escapeHtmlCase(step.title);
        const descEsc = escapeHtmlCase(step.description || '');
        const ro = isEditMode ? '' : 'readonly';
        const dis = isEditMode ? '' : 'disabled';
        const dragTitle = isEditMode ? t('case.dragReorder') : '';

        return `
            <div class="min-w-0" data-step-id="${step.id}">
                <div class="min-w-0 overflow-hidden rounded-2xl border-l-4 p-4 sm:p-5 ${classes.wrap}">
                    <div class="flex min-w-0 flex-nowrap items-center justify-between gap-3">
                        <div class="flex min-w-0 flex-nowrap items-center gap-2">
                            <span class="inline-flex h-9 min-w-[2rem] shrink-0 items-center justify-center rounded-lg bg-slate-100 px-2 font-manrope text-xs font-bold text-slate-600" title="${t('case.stepOrder')}">${index + 1}</span>
                            <span class="font-manrope text-[10px] font-bold uppercase tracking-widest text-slate-400 whitespace-nowrap">${t('case.stepN')}</span>
                        </div>
                        <div
                            class="drag-handle hidden h-10 w-10 shrink-0 cursor-grab items-center justify-center rounded-xl border border-slate-200 bg-white text-slate-400 shadow-sm transition hover:border-slate-300 hover:bg-slate-50 hover:text-slate-600 active:cursor-grabbing md:flex ${isEditMode ? '' : 'pointer-events-none opacity-40'}"
                            title="${dragTitle}"
                        >
                            <span class="material-symbols-outlined text-[20px]">drag_indicator</span>
                        </div>
                    </div>
                    <div class="mt-3 flex min-w-0 flex-nowrap items-stretch gap-2 sm:mt-4">
                        <div class="min-w-0 flex-1 self-center overflow-hidden">
                            <label class="sr-only" for="step-status-${step.id}">${t('case.stepStatus')}</label>
                            <select
                                id="step-status-${step.id}"
                                class="case-step-status box-border h-10 w-full min-w-0 max-w-full cursor-pointer rounded-xl py-0 pl-3 pr-8 font-manrope text-xs font-bold uppercase tracking-wide shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500/30 ${classes.select}"
                                ${dis}
                                onchange="updateStepStatus(${step.id}, this.value)"
                            >
                                <option value="completed" ${step.status === 'completed' ? 'selected' : ''}>${t('case.stepCompleted')}</option>
                                <option value="active" ${step.status === 'active' ? 'selected' : ''}>${t('case.stepActive')}</option>
                                <option value="pending" ${step.status === 'pending' ? 'selected' : ''}>${t('case.stepPending')}</option>
                            </select>
                        </div>
                        ${
                            isEditMode
                                ? `<button type="button" class="inline-flex h-10 w-10 shrink-0 items-center justify-center self-center rounded-xl border border-slate-200 bg-white text-slate-400 transition hover:border-red-200 hover:bg-red-50 hover:text-red-600" onclick="deleteStep(${step.id})" title="${t('case.deleteStep')}">
                                    <span class="material-symbols-outlined text-[20px]">delete</span>
                                </button>`
                                : ''
                        }
                    </div>
                    <label class="mb-1.5 mt-4 block font-manrope text-[11px] font-bold uppercase tracking-wider text-slate-400" for="step-title-${step.id}">${t('case.stepTitleLabel')}</label>
                    <textarea
                        id="step-title-${step.id}"
                        class="case-step-textarea case-step-title case-step-autosize mb-3"
                        rows="1"
                        placeholder="${t('case.stepTitlePlaceholder')}"
                        ${ro}
                        onchange="updateStepTitle(${step.id}, this.value)"
                    >${titleEsc}</textarea>
                    <label class="mb-1.5 block font-manrope text-[11px] font-bold uppercase tracking-wider text-slate-400" for="step-desc-${step.id}">${t('case.stepDescLabel')}</label>
                    <textarea
                        id="step-desc-${step.id}"
                        class="case-step-textarea case-step-autosize font-body text-slate-700"
                        rows="1"
                        placeholder="${t('case.stepDescPlaceholder')}"
                        ${ro}
                        onchange="updateStepDescription(${step.id}, this.value)"
                    >${descEsc}</textarea>
                </div>
            </div>
        `;
    }).join('');

    if (isEditMode) {
        setupDragAndDrop();
    }

    bindCaseTimelineTextareaAutosizeOnce();
    window.requestAnimationFrame(() => {
        autosizeAllCaseStepTextareas();
    });
}

/**
 * Setup drag and drop for timeline steps
 */
function setupDragAndDrop() {
    const steps = document.querySelectorAll('[data-step-id]');
    
    steps.forEach(step => {
        // Only allow dragging when drag handle is grabbed
        const dragHandle = step.querySelector('.drag-handle');
        if (dragHandle) {
            dragHandle.addEventListener('mousedown', () => {
                step.setAttribute('draggable', 'true');
            });
            dragHandle.addEventListener('mouseup', () => {
                step.setAttribute('draggable', 'false');
            });
        }
        
        step.addEventListener('dragstart', handleDragStart);
        step.addEventListener('dragover', handleDragOver);
        step.addEventListener('drop', handleDrop);
        step.addEventListener('dragend', handleDragEnd);
    });
}

function handleDragStart(e) {
    // Only allow drag if it's actually draggable
    if (this.getAttribute('draggable') !== 'true') {
        e.preventDefault();
        return;
    }
    draggedElement = this;
    this.style.opacity = '0.4';
    e.dataTransfer.effectAllowed = 'move';
}

function handleDragOver(e) {
    if (e.preventDefault) {
        e.preventDefault();
    }
    e.dataTransfer.dropEffect = 'move';
    return false;
}

function handleDrop(e) {
    if (e.stopPropagation) {
        e.stopPropagation();
    }

    if (draggedElement !== this) {
        const draggedId = parseInt(draggedElement.getAttribute('data-step-id'));
        const targetId = parseInt(this.getAttribute('data-step-id'));
        
        const draggedIndex = caseData.timeline.findIndex(s => s.id === draggedId);
        const targetIndex = caseData.timeline.findIndex(s => s.id === targetId);
        
        // Swap positions
        const temp = caseData.timeline[draggedIndex];
        caseData.timeline[draggedIndex] = caseData.timeline[targetIndex];
        caseData.timeline[targetIndex] = temp;
        
        markTimelineManual();
        renderTimeline();
        showSaveNotification();
    }

    return false;
}

function handleDragEnd(e) {
    this.style.opacity = '1';
}

/**
 * Update step title
 */
function markTimelineManual() {
    caseData.timelineManual = true;
}

function markDocumentRequestsManual() {
    caseData.documentRequestsManual = true;
}

function updateStepTitle(stepId, newTitle) {
    const step = caseData.timeline.find(s => s.id === stepId);
    if (step) {
        step.title = newTitle;
        markTimelineManual();
        showSaveNotification();
    }
}

/**
 * Update step description
 */
function updateStepDescription(stepId, newDescription) {
    const step = caseData.timeline.find(s => s.id === stepId);
    if (step) {
        step.description = newDescription;
        markTimelineManual();
        showSaveNotification();
    }
}

/**
 * Update step status
 */
function updateStepStatus(stepId, newStatus) {
    const step = caseData.timeline.find(s => s.id === stepId);
    if (step) {
        step.status = newStatus;
        markTimelineManual();
        renderTimeline();
        showSaveNotification();
    }
}

/**
 * Delete step
 */
function deleteStep(stepId) {
    if (!isEditMode) {
        showEnableEditModeToast();
        return;
    }
    showCaseConfirm({
        title: t("case.deleteStepTitle"),
        message: t("case.deleteStepMessage"),
        confirmText: t("documents.card.delete"),
        danger: true,
    }).then((ok) => {
        if (!ok) {
            return;
        }
        caseData.timeline = caseData.timeline.filter(s => s.id !== stepId);
        markTimelineManual();
        renderTimeline();
        showSaveNotification();
    });
}

/**
 * Add new step
 */
function addNewStep() {
    if (!isEditMode) {
        showEnableEditModeToast();
        return;
    }
    const newId = Math.max(...caseData.timeline.map(s => s.id), 0) + 1;
    caseData.timeline.push({
        id: newId,
        title: t('case.newStep'),
        description: '',
        status: 'pending'
    });
    markTimelineManual();
    renderTimeline();
    showSaveNotification();
}

/**
 * Get priority badge HTML
 */
function getPriorityBadge(priority) {
    const badges = {
        urgent: `<span class="inline-block px-2 py-0.5 bg-red-50 text-red-600 text-[10px] font-bold rounded uppercase">${t('case.priorityUrgentBadge')}</span>`,
        optional: `<span class="inline-block px-2 py-0.5 bg-slate-50 text-slate-400 text-[10px] font-bold rounded uppercase">${t('case.priorityOptionalBadge')}</span>`,
        normal: ''
    };
    return badges[priority] || '';
}

/**
 * Render document requests
 */
function renderDocumentRequests() {
    const container = document.getElementById('document-requests-list');
    if (!container) return;

    caseData.documentRequests.forEach((d) => {
        if (d.sent) {
            d.checked = false;
        }
    });

    container.innerHTML = caseData.documentRequests.map(doc => {
        const isSent = doc.sent || false;
        const isDefault = doc.isDefault || false;
        const canDelete = !isDefault && isEditMode;
        const checkboxOrSpacer = isSent
            ? `<span class="mt-1 shrink-0 w-[18px] h-[18px] flex items-center justify-center" aria-hidden="true"><span class="material-symbols-outlined text-[18px] text-green-600">check</span></span>`
            : `<input
                class="mt-1 rounded border-slate-300 text-blue-600 focus:ring-blue-500 cursor-pointer"
                type="checkbox"
                ${doc.checked ? 'checked' : ''}
                ${!isEditMode ? 'disabled' : ''}
                onchange="toggleDocumentRequest(${doc.id}, this.checked)"
            />`;

        return `
        <div class="flex items-start gap-3 p-3 rounded-xl min-w-0 ${isSent ? 'bg-green-50 border-2 border-green-200' : 'hover:bg-slate-50 border border-transparent hover:border-slate-200'} transition-colors group">
            ${checkboxOrSpacer}
            <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2 flex-wrap">
                    <span class="block text-sm font-bold ${isSent ? 'text-green-700' : 'text-slate-800'} ${!isSent ? 'group-hover:text-blue-600' : ''} transition-colors font-manrope break-words">${doc.name}</span>
                    ${getPriorityBadge(doc.priority || 'normal')}
                    ${isSent ? `<span class="inline-block px-2 py-0.5 bg-green-600 text-white text-[10px] font-bold rounded uppercase">${t('case.sentBadge')}</span>` : ''}
                </div>
                <span class="block text-xs ${isSent ? 'text-green-600' : 'text-slate-500'} mt-0.5 break-words">${doc.description}</span>
            </div>
            ${canDelete ? `
                <button onclick="deleteDocumentRequest(${doc.id})" class="flex-shrink-0 p-1.5 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors" title="${t('documents.card.delete')}">
                    <span class="material-symbols-outlined text-[18px]">delete</span>
                </button>
            ` : ''}
            ${isSent && isEditMode ? `
                <button onclick="recallDocumentRequest(${doc.id})" class="flex-shrink-0 px-3 py-1 text-xs font-bold text-orange-600 hover:bg-orange-50 rounded-lg transition-colors" title="${t('case.recallRequestTitle')}">
                    ${t('case.recallRequest')}
                </button>
            ` : ''}
        </div>
    `;
    }).join('');

    updateSendButtonText();
}

/**
 * Open add document modal
 */
function openAddDocModal() {
    if (!isEditMode) {
        showEnableEditModeToast();
        return;
    }
    const modal = document.getElementById('add-doc-modal');
    if (modal) {
        modal.classList.add('show');
        // Clear inputs
        document.getElementById('doc-title-input').value = '';
        document.getElementById('doc-description-input').value = '';
        document.querySelector('input[name="doc-priority"][value="normal"]').checked = true;
        const titleErr = document.getElementById('doc-title-error');
        if (titleErr) {
            titleErr.classList.add('hidden');
        }
    }
}

/**
 * Close add document modal
 */
function closeAddDocModal() {
    const modal = document.getElementById('add-doc-modal');
    if (modal) {
        modal.classList.remove('show');
    }
}

/**
 * Save custom document
 */
function saveCustomDocument() {
    if (!isEditMode) {
        showEnableEditModeToast();
        return;
    }
    const title = document.getElementById('doc-title-input').value.trim();
    const description = document.getElementById('doc-description-input').value.trim();
    const priority = document.querySelector('input[name="doc-priority"]:checked').value;
    const titleErr = document.getElementById('doc-title-error');

    if (!title) {
        if (titleErr) {
            titleErr.classList.remove('hidden');
        }
        document.getElementById('doc-title-input')?.focus();
        return;
    }
    if (titleErr) {
        titleErr.classList.add('hidden');
    }
    
    const newId = Math.max(...caseData.documentRequests.map(d => d.id), 0) + 1;
    caseData.documentRequests.push({
        id: newId,
        name: title,
        description: description || t('common.noDescription'),
        checked: false,
        priority: priority,
        sent: false,
        isDefault: false
    });
    
    markDocumentRequestsManual();
    renderDocumentRequests();
    closeAddDocModal();
    showSaveNotification();
}

/**
 * Toggle document request
 */
function toggleDocumentRequest(docId, checked) {
    if (!isEditMode) {
        showEnableEditModeToast();
        return;
    }
    const doc = caseData.documentRequests.find(d => d.id === docId);
    if (doc && doc.sent) {
        return;
    }
    if (doc) {
        doc.checked = checked;
        markDocumentRequestsManual();
        updateSendButtonText();
        showSaveNotification();
    }
}

function ruDocRequestWordForm(n) {
    return pickCasePlural(n, "case.requestWord1", "case.requestWord2", "case.requestWord5");
}

/**
 * Link to client documents list from case page (?client= display id).
 */
function setupViewClientDocumentsLink() {
    const link = document.getElementById('view-client-documents-btn');
    if (!link) {
        return;
    }

    const urlClient = (new URLSearchParams(window.location.search).get('client') || '')
        .trim()
        .toUpperCase();
    let clientId = /^[A-Z]{2}\d{4}$/.test(urlClient) ? urlClient : '';

    if (!clientId && currentUser && currentUser.display_id) {
        const did = String(currentUser.display_id).trim().toUpperCase();
        if (/^[A-Z]{2}\d{4}$/.test(did)) {
            clientId = did;
        }
    }

    if (clientId) {
        link.href = `./documents.html?client=${encodeURIComponent(clientId)}`;
        link.style.display = '';
    } else {
        link.style.display = 'none';
    }
}

/**
 * Update send button text with count
 */
function updateSendButtonText() {
    const pendingCount = caseData.documentRequests.filter((d) => d.checked && !d.sent).length;
    const btnText = document.getElementById('send-btn-text');
    if (btnText) {
        btnText.textContent =
            pendingCount > 0
                ? t("case.sendRequestsCount", {
                      n: pendingCount,
                      word: ruDocRequestWordForm(pendingCount),
                  })
                : t("case.sendRequests");
    }
}

/**
 * Delete document request
 */
function deleteDocumentRequest(docId) {
    if (!isEditMode) {
        showEnableEditModeToast();
        return;
    }
    const doc = caseData.documentRequests.find(d => d.id === docId);
    if (!doc) return;

    if (doc.sent) {
        showCaseToast(t("case.cannotDeleteSent"), "error");
        return;
    }

    showCaseConfirm({
        title: t("case.deleteRequestTitle"),
        message: t("case.deleteRequestMessage", { name: doc.name }),
        confirmText: t("documents.card.delete"),
        danger: true,
    }).then((ok) => {
        if (!ok) {
            return;
        }
        caseData.documentRequests = caseData.documentRequests.filter(d => d.id !== docId);
        markDocumentRequestsManual();
        renderDocumentRequests();
        showSaveNotification();
    });
}

/**
 * Recall document request
 */
function recallDocumentRequest(docId) {
    if (!isEditMode) {
        showEnableEditModeToast();
        return;
    }
    const doc = caseData.documentRequests.find(d => d.id === docId);
    if (!doc) return;

    showCaseConfirm({
        title: t("case.recallRequestTitle"),
        message: t("case.recallRequestMessage", { name: doc.name }),
        confirmText: t("case.recallRequest"),
        danger: true,
    }).then((ok) => {
        if (!ok) {
            return;
        }
        doc.sent = false;
        doc.checked = false;
        markDocumentRequestsManual();
        renderDocumentRequests();
        showSaveNotification();
    });
}

/**
 * Send document requests
 */
function sendDocumentRequests() {
    if (!isEditMode) {
        showEnableEditModeToast();
        return;
    }
    const checkedDocs = caseData.documentRequests.filter(d => d.checked && !d.sent);
    if (checkedDocs.length === 0) {
        showCaseToast(t("case.selectDocToSend"), "error");
        return;
    }

    checkedDocs.forEach((doc) => {
        doc.sent = true;
        doc.checked = false;
    });

    markDocumentRequestsManual();
    renderDocumentRequests();
    showSaveNotification();

    const n = checkedDocs.length;
    showCaseToast(
        t("case.sentToClient", { n, word: ruDocumentsWordForm(n) }),
        "success"
    );
    console.log('Sent document requests:', checkedDocs);
}

/**
 * Toggle edit mode
 */
function toggleEditMode(enabled) {
    if (!enabled) {
        closeAddDocModal();
    }
    isEditMode = enabled;
    renderTimeline();
    renderDocumentRequests();

    const visaSelect = document.getElementById('visa-type');
    const targetDate = document.getElementById('target-date');
    const countryInput = document.getElementById('case-country-input');
    const archiveInput = document.getElementById('case-archive');

    if (visaSelect) visaSelect.disabled = !enabled;
    if (targetDate) targetDate.disabled = !enabled;
    if (countryInput) countryInput.disabled = !enabled;
    if (archiveInput) archiveInput.disabled = !enabled;

    const addStepBtn = document.getElementById('add-step-btn');
    if (addStepBtn) {
        addStepBtn.disabled = !enabled;
        addStepBtn.classList.toggle('opacity-50', !enabled);
        addStepBtn.classList.toggle('cursor-not-allowed', !enabled);
        addStepBtn.classList.toggle('pointer-events-none', !enabled);
    }

    const sendBtn = document.getElementById('send-doc-requests-btn');
    if (sendBtn) {
        sendBtn.disabled = !enabled;
        sendBtn.classList.toggle('opacity-50', !enabled);
        sendBtn.classList.toggle('cursor-not-allowed', !enabled);
        sendBtn.classList.toggle('pointer-events-none', !enabled);
    }

    const addDocBtn = document.getElementById('add-custom-doc-btn');
    if (addDocBtn) {
        addDocBtn.disabled = !enabled;
        addDocBtn.classList.toggle('opacity-50', !enabled);
        addDocBtn.classList.toggle('cursor-not-allowed', !enabled);
        addDocBtn.classList.toggle('pointer-events-none', !enabled);
    }

    ['referral', 'manager'].forEach((prefix) => {
        const idInput = document.getElementById(`${prefix}-id-input`);
        if (idInput) {
            idInput.disabled = !enabled;
        }
        const inputContainer = document.getElementById(`${prefix}-input-container`);
        if (inputContainer) {
            inputContainer.querySelectorAll('button').forEach((btn) => {
                btn.disabled = !enabled;
            });
        }
        const display = document.getElementById(`${prefix}-display`);
        if (display && !display.classList.contains('hidden')) {
            display.querySelectorAll('button').forEach((btn) => {
                btn.disabled = !enabled;
            });
        }
    });

    if (enabled) {
        const toggleLabel = document.getElementById('edit-mode-toggle')?.closest('label');
        if (toggleLabel) {
            toggleLabel.classList.remove('ring-2', 'ring-blue-300', 'ring-offset-2', 'ring-offset-slate-50', 'animate-pulse');
        }
    }
}

function setupViewModeInterceptors() {
    const attemptSelector = [
        '#visa-type',
        '#target-date',
        '#case-country-input',
        '#case-archive',
        '#add-step-btn',
        '#send-doc-requests-btn',
        '#add-custom-doc-btn',
        '#timeline-container textarea',
        '#timeline-container select',
        '#timeline-container .drag-handle',
        '#document-requests-list input[type="checkbox"]',
        '#referral-id-input',
        '#manager-id-input',
        '#referral-input-container button',
        '#manager-input-container button',
        '#referral-display button',
        '#manager-display button'
    ].join(', ');

    const onAttempt = (event) => {
        if (isEditMode) {
            return;
        }
        if (event.target?.closest('#edit-mode-toggle')) {
            return;
        }
        if (event.target?.closest(attemptSelector)) {
            showEnableEditModeToast();
        }
    };

    document.addEventListener('pointerdown', onAttempt, true);
    document.addEventListener('focusin', onAttempt, true);
}

/**
 * Show save notification
 */
function showSaveNotification() {
    // Auto-save after 1 second of inactivity
    if (window.saveTimeout) {
        clearTimeout(window.saveTimeout);
    }
    window.saveTimeout = setTimeout(() => {
        saveCaseData();
    }, 1000);
}

/**
 * Save case data to server
 */
async function saveCaseData() {
    if (!currentUserId) {
        console.error('Cannot save: missing userId', { currentUserId });
        return;
    }

    try {
        const payload = {
            visa_type: caseData.visaType,
            target_date: caseData.targetDate,
            country: caseData.country,
            timeline: caseData.timeline,
            document_requests: caseData.documentRequests,
            referral_id: caseData.referralId || null,
            manager_id: caseData.managerId || null,
            timeline_manual: !!caseData.timelineManual,
            document_requests_manual: !!caseData.documentRequestsManual,
        };
        
        console.log('Saving case data:', payload);
        
        const response = await fetch(`${API_BASE}/case-data/${currentUserId}`, {
            method: 'PUT',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });

        console.log('Save response status:', response.status);

        if (!response.ok) {
            const errorText = await response.text();
            console.error('Save failed:', errorText);
            throw new Error(`Failed to save case data: ${response.status} ${errorText}`);
        }

        const data = await response.json();
        console.log('Save response data:', data);
        
        if (data.success) {
            console.log('Case data saved successfully');
        }
    } catch (error) {
        console.error('Error saving case data:', error);
        showCaseToast(t('case.toast.saveFailed', { error: error.message }), "error");
    }
}

/**
 * Add a history entry (removed - now handled by backend)
 */
function addHistoryEntry(action, details = '') {
    // History is now tracked automatically by the backend
    console.log('📝 History will be tracked by backend:', action, details);
}

/**
 * Load and display assigned managers
 */
async function loadAssignedManagers(loadedCaseData) {
    console.log('📋 loadAssignedManagers called with:', loadedCaseData);
    
    if (!loadedCaseData) {
        console.log('⚠️ No case data provided');
        return;
    }
    
    // Load referral if exists
    if (loadedCaseData.referral_id) {
        console.log('👤 Loading referral with ID:', loadedCaseData.referral_id);
        caseData.referralId = loadedCaseData.referral_id;
        try {
            const response = await fetch(`${API_BASE}/users/${loadedCaseData.referral_id}`, {
                credentials: 'include',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            if (response.ok) {
                const data = await response.json();
                console.log('✅ Referral loaded:', data.user);
                displayAssignedManager(data.user, 'referral');
            } else {
                console.error('❌ Failed to load referral:', response.status);
            }
        } catch (error) {
            console.error('❌ Error loading referral:', error);
        }
    } else {
        console.log('ℹ️ No referral_id in case data');
    }
    
    // Load manager if exists
    if (loadedCaseData.manager_id) {
        console.log('👤 Loading manager with ID:', loadedCaseData.manager_id);
        caseData.managerId = loadedCaseData.manager_id;
        try {
            const response = await fetch(`${API_BASE}/users/${loadedCaseData.manager_id}`, {
                credentials: 'include',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            if (response.ok) {
                const data = await response.json();
                console.log('✅ Manager loaded:', data.user);
                displayAssignedManager(data.user, 'manager');
            } else {
                console.error('❌ Failed to load manager:', response.status);
            }
        } catch (error) {
            console.error('❌ Error loading manager:', error);
        }
    } else {
        console.log('ℹ️ No manager_id in case data');
    }
}

/**
 * Initialize case management page
 */
async function initializeCasePage() {
    currentUserId = await resolveCasePageTargetUserId();

    if (!currentUserId) {
        showCaseToast(t('case.toast.noUserId'), "error");
        setTimeout(() => {
            window.location.href = "/frontend/lk/clients.html";
        }, 600);
        return;
    }

    // Show loading state
    console.log(`Loading case for user ID: ${currentUserId}`);

    // Load logged-in user (manager/admin who is viewing the case) FIRST
    // This is important because we need their permissions to render visa types
    loggedInUser = await loadLoggedInUser();
    console.log('Logged-in user:', loggedInUser);
    
    if (!loggedInUser) {
        console.error('Failed to load logged-in user');
        redirectToLogin();
        return;
    }

    // Load user data (client whose case is being managed)
    currentUser = await loadUserData(currentUserId);
    if (currentUser) {
        updatePageHeader(currentUser);
        setupViewClientDocumentsLink();

        try {
            const p = new URLSearchParams(window.location.search);
            if (p.get('userId') && currentUser.display_id) {
                const did = String(currentUser.display_id).trim().toUpperCase();
                if (/^[A-Z]{2}\d{4}$/.test(did)) {
                    const nu = new URL(window.location.href);
                    nu.searchParams.set('client', did);
                    nu.searchParams.delete('userId');
                    window.history.replaceState(null, '', nu.pathname + nu.search);
                }
            }
        } catch (e) {
            /* ignore */
        }

        // Load case data
        const loadedCaseData = await loadCaseData(currentUserId);

        await bootstrapCaseEditors(loadedCaseData);
        await loadAssignedManagers(loadedCaseData);

        const editToggle = document.getElementById('edit-mode-toggle');
        const editEnabled = editToggle ? editToggle.checked : false;
        toggleEditMode(editEnabled);

        // History is now managed by backend
    }
}

/**
 * Initialize page on load
 */
document.addEventListener('DOMContentLoaded', () => {
    bindCaseTimelineTextareaAutosizeOnce();
    initializeCasePage();
    setupViewModeInterceptors();
    bindCaseManagerDisplayIdInputs();

    // Setup edit mode toggle
    const editToggle = document.getElementById('edit-mode-toggle');
    if (editToggle) {
        editToggle.addEventListener('change', (e) => {
            toggleEditMode(e.target.checked);
        });
    }

    // Setup add step button
    const addStepBtn = document.getElementById('add-step-btn');
    if (addStepBtn) {
        addStepBtn.addEventListener('click', addNewStep);
    }

    // Setup send document requests button
    const sendBtn = document.getElementById('send-doc-requests-btn');
    if (sendBtn) {
        sendBtn.addEventListener('click', sendDocumentRequests);
    }

    setupViewClientDocumentsLink();
    
    // Setup add custom document button
    const addDocBtn = document.getElementById('add-custom-doc-btn');
    if (addDocBtn) {
        addDocBtn.addEventListener('click', openAddDocModal);
    }

    // Setup visa type change
    const visaSelect = document.getElementById('visa-type');
    if (visaSelect) {
        visaSelect.addEventListener('change', (e) => {
            if (suppressVisaSelectSave) {
                return;
            }
            caseData.visaType = e.target.value;
            showSaveNotification();
        });
    }

    // Setup target date change
    const targetDate = document.getElementById('target-date');
    if (targetDate) {
        targetDate.addEventListener('change', (e) => {
            caseData.targetDate = e.target.value;
            syncTargetDatePlaceholder();
            showSaveNotification();
        });
        targetDate.addEventListener('input', syncTargetDatePlaceholder);
        syncTargetDatePlaceholder();
    }

    // Setup country change
    const countryInput = document.getElementById('case-country-input');
    if (countryInput) {
        countryInput.addEventListener('input', (e) => {
            caseData.country = String(e.target.value || '').trim();
            updateCountryBadge();
            showSaveNotification();
        });
    }

    setupCaseArchiveFilePicker();
    
    // Setup logout button
    const logoutBtn = document.getElementById('logout-btn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', (e) => {
            e.preventDefault();
            localStorage.removeItem('token');
            redirectToLogin();
        });
    }
    
    // Setup history button
    const historyBtn = document.getElementById('history-btn');
    if (historyBtn) {
        historyBtn.addEventListener('click', openHistoryModal);
    }

    window.addEventListener('lk-locale-change', () => {
        if (window.LkI18n) {
            window.LkI18n.applyDocument();
        }
        if (currentUser) {
            updatePageHeader(currentUser);
        }
        renderVisaTypeOptions();
        renderTimeline();
        renderDocumentRequests();
        updateArchiveStatus();
        updateCaseArchiveFileLabel();
        syncTargetDatePlaceholder();
        updateCountryBadge();
        document.querySelectorAll('[data-public-id]').forEach((el) => {
            const id = el.dataset.publicId;
            if (id) {
                el.textContent = t('case.managerPublicId', { id });
            }
        });
        const historyModal = document.getElementById('history-modal');
        if (historyModal && !historyModal.classList.contains('hidden')) {
            loadCaseHistory();
        }
    });
});

/**
 * History modal functions
 */
function openHistoryModal() {
    console.log('🔓 Opening history modal...');
    const modal = document.getElementById('history-modal');
    console.log('Modal element:', modal);
    
    if (modal) {
        console.log('Modal classes before:', modal.className);
        modal.classList.remove('hidden');
        modal.classList.add('flex');
        console.log('Modal classes after:', modal.className);
        console.log('Modal display style:', window.getComputedStyle(modal).display);
        loadCaseHistory();
    } else {
        console.error('❌ History modal element not found!');
    }
}

function closeHistoryModal() {
    const modal = document.getElementById('history-modal');
    if (modal) {
        modal.classList.add('hidden');
        modal.classList.remove('flex');
    }
}

async function loadCaseHistory() {
    console.log('📜 Loading case history from API...');
    
    const container = document.getElementById('history-log-list');
    if (!container) {
        console.error('❌ History container not found');
        return;
    }
    
    container.innerHTML = `<p class="text-sm text-slate-500">${t('case.historyLoading')}</p>`;
    
    try {
        const response = await fetch(`${API_BASE}/case-history/${currentUserId}`, {
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        if (!response.ok) {
            throw new Error('Failed to load history');
        }
        
        const data = await response.json();
        const historyItems = data.history || [];
        
        console.log('📋 Loaded history items:', historyItems.length);
        
        if (historyItems.length === 0) {
            container.innerHTML = `<p class="text-sm text-slate-500">${t('case.historyEmpty')}</p>`;
            return;
        }
        
        container.innerHTML = historyItems.map(item => {
            const icon = getHistoryIcon(item.action);
            const editorName = item.editor?.name || item.editor?.email || t('common.manager');
            const editorNameEsc = escapeHtmlCase(editorName);
            const editorAvatar = item.editor?.avatar;
            const actionLabel = translateCaseHistoryAction(item.action);
            const actionEsc = escapeHtmlCase(actionLabel);
            const detailsRaw = item.details
                ? (window.LkI18n && window.LkI18n.translateCaseHistoryDetails
                    ? window.LkI18n.translateCaseHistoryDetails(item.details)
                    : item.details)
                : '';
            const detailsEsc = detailsRaw ? escapeHtmlCase(detailsRaw) : '';

            return `
                <div class="flex gap-4 p-4 bg-slate-50 rounded-xl">
                    <div class="flex-shrink-0">
                        ${editorAvatar
                            ? `<img src="${escapeHtmlCase(editorAvatar)}" alt="${editorNameEsc}" class="w-10 h-10 rounded-full object-cover" />`
                            : `<div class="w-10 h-10 rounded-full ${icon.bg} flex items-center justify-center">
                                <span class="material-symbols-outlined text-[20px] ${icon.color}">${icon.name}</span>
                               </div>`
                        }
                    </div>
                    <div class="flex-1 min-w-0">
                        <div class="flex items-start justify-between gap-2">
                            <div class="min-w-0">
                                <p class="font-manrope font-bold text-sm text-slate-800">${actionEsc}</p>
                                ${detailsEsc ? `<p class="text-xs text-slate-500 mt-1.5 whitespace-pre-wrap break-words leading-relaxed">${detailsEsc}</p>` : ''}
                            </div>
                            <span class="text-xs text-slate-400 whitespace-nowrap shrink-0">${formatTimeAgo(new Date(item.created_at))}</span>
                        </div>
                        <p class="text-xs text-slate-400 mt-2">${t('case.history.byUser', { name: editorNameEsc })}</p>
                    </div>
                </div>
            `;
        }).join('');
        
        console.log('✅ History rendered');
    } catch (error) {
        console.error('❌ Error loading history:', error);
        container.innerHTML = `<p class="text-sm text-red-500">${t('case.historyError')}</p>`;
    }
}

function getHistoryIcon(action) {
    if (action.includes('создан')) {
        return { name: 'add_circle', bg: 'bg-green-100', color: 'text-green-600' };
    } else if (action.includes('График')) {
        return { name: 'route', bg: 'bg-blue-100', color: 'text-blue-600' };
    } else if (action.includes('документ')) {
        return { name: 'description', bg: 'bg-orange-100', color: 'text-orange-600' };
    } else if (action.includes('менеджер') || action.includes('реферал')) {
        return { name: 'person_add', bg: 'bg-purple-100', color: 'text-purple-600' };
    } else if (action.includes('визовый путь')) {
        return { name: 'edit', bg: 'bg-blue-100', color: 'text-blue-600' };
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

function syncTargetDatePlaceholder() {
    const input = document.getElementById("target-date");
    const ph = document.getElementById("target-date-placeholder");
    if (!input || !ph) return;
    const hasValue = Boolean(String(input.value || "").trim());
    ph.textContent = t("case.datePlaceholder");
    ph.classList.toggle("hidden", hasValue);
    input.classList.toggle("text-transparent", !hasValue);
}

/**
 * Manager assignment functions
 */
function getUserInitials(name) {
    if (!name) return '??';
    const parts = name.split(' ');
    if (parts.length >= 2) {
        return (parts[0][0] + parts[1][0]).toUpperCase();
    }
    return name.substring(0, 2).toUpperCase();
}

function normalizeCaseManagerDisplayIdInput(raw) {
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

function isCompletePublicDisplayIdCase(value) {
    return /^[A-Z]{2}\d{4}$/.test(String(value || ""));
}

function bindCaseManagerDisplayIdInputs() {
    ["manager-id-input", "referral-id-input"].forEach((id) => {
        const el = document.getElementById(id);
        if (!el) {
            return;
        }
        const sync = () => {
            const next = normalizeCaseManagerDisplayIdInput(el.value);
            if (el.value !== next) {
                el.value = next;
            }
        };
        el.addEventListener("input", sync);
        el.addEventListener("blur", sync);
        el.addEventListener("keydown", (event) => {
            if (event.key === "Enter") {
                event.preventDefault();
                if (id === "manager-id-input") {
                    void assignManager();
                } else {
                    void assignReferral();
                }
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
            const cur = normalizeCaseManagerDisplayIdInput(el.value);
            const letterCount = (cur.match(/^[A-Z]*/) || [""])[0].length;
            if (event.key.length === 1) {
                if (letterCount < 2) {
                    if (!/[A-Za-z]/.test(event.key)) {
                        event.preventDefault();
                    }
                } else if (!/[0-9]/.test(event.key)) {
                    event.preventDefault();
                }
            }
        });
    });
}

async function fetchStaffUserByDisplayForCase(displayToken, errorField) {
    if (!currentUserId) {
        showManagerError(errorField, "Нет доступа");
        return null;
    }
    const cid = parseInt(String(currentUserId), 10);
    if (!Number.isFinite(cid) || cid < 1) {
        showManagerError(errorField, "Некорректный кейс");
        return null;
    }
    try {
        const url = `${API_BASE}/users/lookup-by-display?display_id=${encodeURIComponent(
            displayToken
        )}&for_case_user_id=${encodeURIComponent(String(cid))}`;
        const response = await fetch(url, {
            credentials: 'include',
        });
        let data = {};
        try {
            data = await response.json();
        } catch {
            data = {};
        }
        if (!response.ok) {
            if (response.status === 404) {
                showManagerError(errorField, "Пользователь с таким номером не найден");
            } else if (response.status === 403) {
                showManagerError(
                    errorField,
                    "Недостаточно прав или нельзя назначить этого пользователя"
                );
            } else {
                showManagerError(errorField, data.error || "Ошибка запроса");
            }
            return null;
        }
        return data.user || null;
    } catch (error) {
        console.error(error);
        showManagerError(errorField, "Ошибка сети");
        return null;
    }
}

async function applyAssignedManagerUser(user, role) {
    const errorField = role === "referral" ? "referral" : "manager";
    const userRoleKey = (user.role && user.role.key ? String(user.role.key) : "").toLowerCase().trim();
    const allowedRoles = ["management", "admin", "moderator", "manager"];
    if (!allowedRoles.includes(userRoleKey)) {
        showManagerError(
            errorField,
            `Пользователь должен быть менеджером или выше (текущая роль: ${userRoleKey || "не указана"})`
        );
        return;
    }
    displayAssignedManager(user, role);
    if (role === "referral") {
        caseData.referralId = user.id;
    } else {
        caseData.managerId = user.id;
    }
    await saveCaseData();
}

async function assignReferral() {
    if (!isEditMode) {
        showEnableEditModeToast();
        return;
    }
    const input = document.getElementById("referral-id-input");
    const token = normalizeCaseManagerDisplayIdInput(input.value);

    if (!isCompletePublicDisplayIdCase(token)) {
        showManagerError("referral", "Введите публичный номер: 2 латинские буквы и 4 цифры");
        return;
    }

    const user = await fetchStaffUserByDisplayForCase(token, "referral");
    if (!user) {
        return;
    }
    try {
        await applyAssignedManagerUser(user, "referral");
    } catch (error) {
        console.error("Error assigning referral manager:", error);
        showManagerError("referral", "Ошибка назначения менеджера");
    }
}

async function assignManager() {
    if (!isEditMode) {
        showEnableEditModeToast();
        return;
    }
    const input = document.getElementById("manager-id-input");
    const token = normalizeCaseManagerDisplayIdInput(input.value);

    if (!isCompletePublicDisplayIdCase(token)) {
        showManagerError("manager", "Введите публичный номер: 2 латинские буквы и 4 цифры");
        return;
    }

    const user = await fetchStaffUserByDisplayForCase(token, "manager");
    if (!user) {
        return;
    }
    try {
        await applyAssignedManagerUser(user, "manager");
    } catch (error) {
        console.error("Error assigning manager:", error);
        showManagerError("manager", "Ошибка назначения менеджера");
    }
}

function displayAssignedManager(user, role) {
    console.log('👤 displayAssignedManager called:', { user, role });
    const prefix = role === 'referral' ? 'referral' : 'manager';
    
    // Hide input, show display
    const inputContainer = document.getElementById(`${prefix}-input-container`);
    const displayContainer = document.getElementById(`${prefix}-display`);
    const avatarEl = document.getElementById(`${prefix}-avatar`);
    const nameEl = document.getElementById(`${prefix}-name`);
    const emailEl = document.getElementById(`${prefix}-email`);
    
    console.log('🔍 DOM elements found:', {
        inputContainer: !!inputContainer,
        displayContainer: !!displayContainer,
        avatarEl: !!avatarEl,
        nameEl: !!nameEl,
        emailEl: !!emailEl
    });
    
    if (!inputContainer || !displayContainer || !avatarEl || !nameEl || !emailEl) {
        console.error('❌ Missing DOM elements for', prefix);
        return;
    }
    
    inputContainer.classList.add('hidden');
    displayContainer.classList.remove('hidden');
    displayContainer.classList.add('flex');
    
    // Update display elements - show photo if available, otherwise initials
    if (user.avatar) {
        console.log('🖼️ Setting avatar image for user:', user.name || user.email);
        avatarEl.innerHTML = `<img src="${user.avatar}" alt="${user.name}" class="w-full h-full object-cover" />`;
    } else {
        const initials = getUserInitials(user.name || user.email);
        console.log('🔤 Setting initials:', initials, 'for user:', user.name || user.email);
        avatarEl.textContent = initials;
    }
    
    nameEl.textContent = user.name || t('clients.noName');
    emailEl.textContent = user.email || '';

    const pubEl = document.getElementById(`${prefix}-public-id`);
    if (pubEl) {
        const pub = user.display_id ? String(user.display_id).trim().toUpperCase() : '';
        if (pub) {
            pubEl.dataset.publicId = pub;
            pubEl.textContent = t('case.managerPublicId', { id: pub });
            pubEl.classList.remove('hidden');
        } else {
            pubEl.textContent = '';
            pubEl.classList.add('hidden');
        }
    }

    console.log('✅ Manager display updated');
    
    // Clear input and error
    document.getElementById(`${prefix}-id-input`).value = '';
    hideManagerError(prefix);
}

function clearReferral() {
    clearManagerRole('referral');
}

function clearManager() {
    clearManagerRole('manager');
}

function clearManagerRole(role) {
    if (!isEditMode) {
        showEnableEditModeToast();
        return;
    }
    const prefix = role === 'referral' ? 'referral' : 'manager';
    
    // Show input, hide display
    const displayEl = document.getElementById(`${prefix}-display`);
    const inputEl = document.getElementById(`${prefix}-input-container`);
    
    if (displayEl) {
        displayEl.classList.add('hidden');
        displayEl.classList.remove('flex');
    }
    if (inputEl) {
        inputEl.classList.remove('hidden');
    }

    const pubEl = document.getElementById(`${prefix}-public-id`);
    if (pubEl) {
        pubEl.textContent = '';
        pubEl.classList.add('hidden');
    }

    // Clear from case data and set to null (backend will add history entry)
    if (role === 'referral') {
        caseData.referralId = null;
    } else {
        caseData.managerId = null;
    }
    showSaveNotification();
}

function showManagerError(role, message) {
    const errorEl = document.getElementById(`${role}-error`);
    errorEl.textContent = message;
    errorEl.classList.remove('hidden');
}

function hideManagerError(role) {
    const errorEl = document.getElementById(`${role}-error`);
    errorEl.classList.add('hidden');
}

// Make functions globally available
window.updateStepTitle = updateStepTitle;
window.updateStepDescription = updateStepDescription;
window.updateStepStatus = updateStepStatus;
window.deleteStep = deleteStep;
window.toggleDocumentRequest = toggleDocumentRequest;
window.deleteDocumentRequest = deleteDocumentRequest;
window.recallDocumentRequest = recallDocumentRequest;
window.assignReferral = assignReferral;
window.assignManager = assignManager;
window.clearReferral = clearReferral;
window.clearManager = clearManager;
window.openAddDocModal = openAddDocModal;
window.closeAddDocModal = closeAddDocModal;
window.saveCustomDocument = saveCustomDocument;
window.openHistoryModal = openHistoryModal;
window.closeHistoryModal = closeHistoryModal;
