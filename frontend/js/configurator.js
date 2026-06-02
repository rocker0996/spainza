/**
 * Шаблоны кейсов: таймлайн и чек-лист документов по визовым путям (для автозаполнения новых кейсов).
 */

const API_BASE =
    window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
        ? 'http://localhost:5000/api'
        : '/api';

function t(key, params) {
    return window.LkI18n ? window.LkI18n.t(key, params) : key;
}

function redirectToLogin() {
    window.location.href = '/frontend/login.html';
}

let loggedInUser = null;
let templateIndex = [];
let selectedVisaType = null;
/** @type {object | null} */
let serverTemplate = null;
let draftDirty = false;

function defaultTimeline() {
    return [
        {
            order: 1,
            title: 'Первичная консультация и стратегия',
            duration_label: '1 нед.',
            description: 'Оценка оснований, сроки и доступ в портал клиента.',
        },
        {
            order: 2,
            title: 'Сбор документов и перевод',
            duration_label: '3–4 нед.',
            description: 'Загрузка файлов клиентом, апостили и присяжные переводы.',
        },
        {
            order: 3,
            title: 'Подача и сопровождение',
            duration_label: '2–3 мес.',
            description: 'Подготовка пакета, подача в органы, ответы на запросы.',
        },
    ];
}

function defaultDocumentItems() {
    return [
        {
            name: 'Действующий загранпаспорт',
            description: 'Срок действия не менее 1 года после подачи.',
            required: true,
            priority: 'normal',
        },
        {
            name: 'Банковские выписки (6 месяцев)',
            description: 'Подтверждение достаточного дохода.',
            required: true,
            priority: 'normal',
        },
        {
            name: 'Справка о несудимости',
            description: 'С апостилем и переводом по странам проживания за 5 лет.',
            required: true,
            priority: 'normal',
        },
    ];
}

async function loadSessionUser() {
    const response = await fetch(`${API_BASE}/user`, {
        credentials: 'include',
    });
    if (response.status === 401) {
        localStorage.removeItem('token');
        redirectToLogin();
        return null;
    }
    const data = await response.json();
    if (!data.success) {
        alert(t('configurator.profileLoadFailed'));
        return null;
    }
    loggedInUser = data;
    return data;
}

async function loadTemplateIndex() {
    const response = await fetch(`${API_BASE}/case-templates`, {
        credentials: 'include',
    });
    if (
        response.status === 403 ||
        (typeof window.shouldRedirectLkAccessDenied === 'function' &&
            window.shouldRedirectLkAccessDenied(response, null))
    ) {
        if (typeof window.redirectLkAccessDenied === 'function') {
            window.redirectLkAccessDenied();
        } else {
            window.location.replace(window.LK_NOT_FOUND_URL || './404.html');
        }
        return;
    }
    if (!response.ok) {
        templateIndex = [];
        return;
    }
    const data = await response.json();
    templateIndex = data.templates || [];
}

async function loadTemplate(visaType) {
    const response = await fetch(`${API_BASE}/case-templates/${encodeURIComponent(visaType)}`, {
        credentials: 'include',
    });
    if (!response.ok) {
        serverTemplate = null;
        return null;
    }
    const data = await response.json();
    serverTemplate = data.template || null;
    return serverTemplate;
}

function visaLabelFromMeta(meta) {
    if (!meta) return '';
    const key = meta.visa_type;
    if (window.LkI18n && key) {
        const localized = window.LkI18n.visaLabel(key);
        if (localized && localized !== key) {
            return localized;
        }
    }
    const loc = window.LkI18n
        ? window.LkI18n.getLocale()
        : (loggedInUser && loggedInUser.locale) || 'ru';
    return loc === 'en'
        ? meta.label_en || meta.label_ru || key
        : meta.label_ru || meta.label_en || key;
}

function renderVisaList() {
    const container = document.getElementById('visa-type-list');
    if (!container) return;

    if (!templateIndex.length) {
        container.innerHTML = `
            <div class="rounded-xl border border-outline-variant/30 bg-surface-container-low p-4 text-sm text-on-surface-variant">
                ${t('configurator.noVisaPaths')}
            </div>`;
        return;
    }

    container.innerHTML = templateIndex
        .map((meta) => {
            const key = meta.visa_type;
            const active = key === selectedVisaType;
            const saved = meta.has_saved_template;
            return `
            <button type="button" data-visa="${escapeAttr(key)}"
                class="text-left w-full rounded-xl p-4 border transition-all hover:-translate-y-0.5 ${
                    active
                        ? 'bg-surface-container-lowest border-primary-container shadow-md ring-1 ring-primary-container/20'
                        : 'bg-surface-container-lowest border-transparent hover:border-outline-variant/30 opacity-90 hover:opacity-100'
                }">
                <div class="flex justify-between items-start gap-2 mb-1">
                    <h3 class="font-headline font-semibold ${active ? 'text-primary' : 'text-on-surface'}">${escapeHtml(
                        visaLabelFromMeta(meta)
                    )}</h3>
                    <span class="shrink-0 text-[10px] font-bold uppercase px-2 py-0.5 rounded-full ${
                        saved
                            ? 'bg-secondary-container/40 text-on-secondary-container'
                            : 'bg-surface-variant text-on-surface-variant'
                    }">${saved ? t('configurator.statusSaved') : t('configurator.statusDraft')}</span>
                </div>
            </button>`;
        })
        .join('');

    container.querySelectorAll('button[data-visa]').forEach((btn) => {
        btn.addEventListener('click', () => selectVisaType(btn.getAttribute('data-visa')));
    });
}

function escapeHtml(s) {
    return String(s)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

function escapeAttr(s) {
    return escapeHtml(s).replace(/'/g, '&#39;');
}

function normalizeDraftFromServer(t) {
    const timeline = (t.timeline && t.timeline.length ? t.timeline : defaultTimeline()).map((step, i) => ({
        order: Number(step.order) || i + 1,
        title: step.title || '',
        duration_label: step.duration_label || '',
        description: step.description || '',
    }));
    const document_items = (
        t.document_items && t.document_items.length ? t.document_items : defaultDocumentItems()
    ).map((d) => ({
        name: d.name || '',
        description: d.description || '',
        required: !!d.required,
        priority: d.priority || 'normal',
    }));
    return {
        title: t.title || '',
        public_description: t.public_description || '',
        processing_fee_eur: t.processing_fee_eur ?? '',
        duration_months: t.duration_months ?? '',
        timeline,
        document_items,
    };
}

async function selectVisaType(visaType) {
    if (!visaType) return;
    if (draftDirty) {
        const ok = confirm(t('configurator.unsavedConfirm'));
        if (!ok) return;
    }
    selectedVisaType = visaType;
    draftDirty = false;
    await loadTemplateIndex();
    await loadTemplate(visaType);
    const base = serverTemplate && serverTemplate.visa_type ? serverTemplate : { visa_type: visaType };
    const draft = normalizeDraftFromServer(base);
    fillEditorForm(draft);
    renderVisaList();
    updateEditorHeader(visaType);
}

function fillEditorForm(draft) {
    const titleEl = document.getElementById('tpl-title');
    const descEl = document.getElementById('tpl-public-description');
    const feeEl = document.getElementById('tpl-fee');
    const monthsEl = document.getElementById('tpl-months');
    if (titleEl) titleEl.value = draft.title;
    if (descEl) descEl.value = draft.public_description;
    if (feeEl) feeEl.value = draft.processing_fee_eur === '' || draft.processing_fee_eur == null ? '' : draft.processing_fee_eur;
    if (monthsEl) monthsEl.value = draft.duration_months === '' || draft.duration_months == null ? '' : draft.duration_months;
    renderTimelineEditor(draft.timeline);
    renderDocumentsEditor(draft.document_items);
}

function updateEditorHeader(visaType) {
    const meta = templateIndex.find((t) => t.visa_type === visaType);
    const label = meta ? visaLabelFromMeta(meta) : visaType;
    const h = document.getElementById('editor-title');
    const sub = document.getElementById('editor-subtitle');
    if (h) h.textContent = t('configurator.templateFor', { label });
    if (sub) sub.textContent = t('configurator.templateSub');
    const updated = document.getElementById('tpl-updated-at');
    if (updated && serverTemplate && serverTemplate.updated_at) {
        updated.textContent = t('configurator.savedAt', { date: serverTemplate.updated_at });
        updated.classList.remove('hidden');
    } else if (updated) {
        updated.textContent = '';
        updated.classList.add('hidden');
    }
}

function collectDraftFromForm() {
    const timeline = [];
    document.querySelectorAll('[data-timeline-row]').forEach((row, i) => {
        timeline.push({
            order: i + 1,
            title: row.querySelector('[data-field="title"]')?.value?.trim() || '',
            duration_label: '',
            description: row.querySelector('[data-field="description"]')?.value?.trim() || '',
        });
    });

    const document_items = [];
    document.querySelectorAll('[data-doc-row]').forEach((row) => {
        document_items.push({
            name: row.querySelector('[data-field="name"]')?.value?.trim() || '',
            description: row.querySelector('[data-field="description"]')?.value?.trim() || '',
            required: row.querySelector('[data-field="required"]')?.checked || false,
            priority: row.querySelector('[data-field="priority"]')?.value || 'normal',
        });
    });

    return {
        title: document.getElementById('tpl-title')?.value?.trim() || '',
        public_description: document.getElementById('tpl-public-description')?.value?.trim() || '',
        processing_fee_eur: document.getElementById('tpl-fee')?.value,
        duration_months: document.getElementById('tpl-months')?.value,
        timeline,
        document_items,
    };
}

function renderTimelineEditor(timeline) {
    const container = document.getElementById('timeline-editor');
    if (!container) return;
    const sorted = [...timeline].sort((a, b) => a.order - b.order);
    container.innerHTML = sorted
        .map(
            (step, i) => `
        <div data-timeline-row class="bg-surface-container-low rounded-xl p-4 border border-transparent focus-within:border-primary-container/40">
            <div class="flex flex-wrap gap-2 items-center justify-between mb-3">
                <span class="text-[10px] font-bold text-on-surface-variant uppercase">${t('configurator.stepN', { n: i + 1 })}</span>
                <div class="flex gap-1">
                    <button type="button" data-move-timeline="${i}" data-dir="-1" class="p-1 rounded-lg hover:bg-surface-container text-on-surface-variant" title="${t('configurator.moveUp')}">
                        <span class="material-symbols-outlined text-[18px]">arrow_upward</span>
                    </button>
                    <button type="button" data-move-timeline="${i}" data-dir="1" class="p-1 rounded-lg hover:bg-surface-container text-on-surface-variant" title="${t('configurator.moveDown')}">
                        <span class="material-symbols-outlined text-[18px]">arrow_downward</span>
                    </button>
                    <button type="button" data-del-timeline="${i}" class="p-1 rounded-lg hover:bg-error-container/30 text-error" title="${t('configurator.remove')}">
                        <span class="material-symbols-outlined text-[18px]">delete</span>
                    </button>
                </div>
            </div>
            <div class="space-y-3">
                <div>
                    <label class="block text-[10px] font-semibold text-on-surface-variant uppercase mb-1">${t('configurator.fieldTitle')}</label>
                    <input data-field="title" type="text" value="${escapeAttr(step.title)}"
                        class="w-full bg-surface-container-lowest rounded-lg px-3 py-2 text-sm border-0 focus:ring-1 focus:ring-primary" />
                </div>
                <div>
                    <label class="block text-[10px] font-semibold text-on-surface-variant uppercase mb-1">${t('configurator.fieldDescription')}</label>
                    <textarea data-field="description" rows="2"
                        class="w-full bg-surface-container-lowest rounded-lg px-3 py-2 text-sm border-0 focus:ring-1 focus:ring-primary resize-y min-h-[4.5rem]">${escapeHtml(
                            step.description
                        )}</textarea>
                </div>
            </div>
        </div>`
        )
        .join('');

    container.querySelectorAll('[data-move-timeline]').forEach((btn) => {
        btn.addEventListener('click', () => {
            const idx = parseInt(btn.getAttribute('data-move-timeline'), 10);
            const dir = parseInt(btn.getAttribute('data-dir'), 10);
            moveTimelineRow(idx, dir);
        });
    });
    container.querySelectorAll('[data-del-timeline]').forEach((btn) => {
        btn.addEventListener('click', () => {
            const idx = parseInt(btn.getAttribute('data-del-timeline'), 10);
            deleteTimelineRow(idx);
        });
    });
    container.querySelectorAll('input, textarea').forEach((el) => {
        el.addEventListener('input', () => {
            draftDirty = true;
        });
    });
}

function moveTimelineRow(index, delta) {
    const d = collectDraftFromForm();
    const arr = d.timeline.sort((a, b) => a.order - b.order);
    const j = index + delta;
    if (j < 0 || j >= arr.length) return;
    const tmp = arr[index];
    arr[index] = arr[j];
    arr[j] = tmp;
    arr.forEach((row, i) => {
        row.order = i + 1;
    });
    draftDirty = true;
    renderTimelineEditor(arr);
}

function deleteTimelineRow(index) {
    const d = collectDraftFromForm();
    const arr = d.timeline.sort((a, b) => a.order - b.order);
    if (arr.length <= 1) {
        alert(t('configurator.needOneStep'));
        return;
    }
    arr.splice(index, 1);
    arr.forEach((row, i) => {
        row.order = i + 1;
    });
    draftDirty = true;
    renderTimelineEditor(arr);
}

function addTimelineStep() {
    const d = collectDraftFromForm();
    const next = (d.timeline.length ? Math.max(...d.timeline.map((t) => t.order)) : 0) + 1;
    d.timeline.push({
        order: next,
        title: t('configurator.newStep'),
        duration_label: '',
        description: '',
    });
    d.timeline.sort((a, b) => a.order - b.order);
    draftDirty = true;
    renderTimelineEditor(d.timeline);
}

function renderDocumentsEditor(items) {
    const container = document.getElementById('documents-editor');
    if (!container) return;
    container.innerHTML = items
        .map(
            (doc, i) => `
        <div data-doc-row class="flex flex-col md:flex-row md:items-stretch gap-3 bg-surface-container-low rounded-lg p-3">
            <div class="flex-1 flex flex-col gap-2 min-w-0 min-h-[8.5rem] md:min-h-[7rem]">
                <input data-field="name" type="text" value="${escapeAttr(doc.name)}"
                    class="w-full shrink-0 bg-surface-container-lowest rounded-lg px-3 py-2 text-sm font-semibold border-0 focus:ring-1 focus:ring-primary" placeholder="${t('configurator.docNamePlaceholder')}" />
                <textarea data-field="description" rows="3"
                    class="w-full flex-1 min-h-[5rem] md:min-h-0 basis-0 bg-surface-container-lowest rounded-lg px-3 py-2 text-xs text-on-surface-variant border-0 focus:ring-1 focus:ring-primary resize-y"
                    placeholder="${t('configurator.fieldDescription')}">${escapeHtml(doc.description)}</textarea>
            </div>
            <div class="flex flex-row md:flex-col gap-3 shrink-0 items-center md:items-start md:pt-0 md:pb-0">
                <label class="flex items-center gap-2 text-xs font-semibold text-on-surface cursor-pointer">
                    <input data-field="required" type="checkbox" ${doc.required ? 'checked' : ''} class="rounded border-outline-variant text-primary focus:ring-primary" />
                    ${t('configurator.required')}
                </label>
                <select data-field="priority" class="text-xs rounded-lg bg-surface-container-lowest px-2 py-2 border-0 focus:ring-1 focus:ring-primary">
                    <option value="normal" ${doc.priority === 'normal' ? 'selected' : ''}>${t('configurator.priorityNormal')}</option>
                    <option value="urgent" ${doc.priority === 'urgent' ? 'selected' : ''}>${t('configurator.priorityUrgent')}</option>
                    <option value="optional" ${doc.priority === 'optional' ? 'selected' : ''}>${t('configurator.priorityOptional')}</option>
                </select>
                <button type="button" data-del-doc="${i}" class="p-2 rounded-lg hover:bg-error-container/20 text-error" title="${t('configurator.remove')}">
                    <span class="material-symbols-outlined text-[20px]">delete</span>
                </button>
            </div>
        </div>`
        )
        .join('');

    container.querySelectorAll('[data-del-doc]').forEach((btn) => {
        btn.addEventListener('click', () => {
            const idx = parseInt(btn.getAttribute('data-del-doc'), 10);
            const d = collectDraftFromForm();
            d.document_items.splice(idx, 1);
            draftDirty = true;
            renderDocumentsEditor(d.document_items);
        });
    });
    container.querySelectorAll('input, textarea, select').forEach((el) => {
        el.addEventListener('change', () => {
            draftDirty = true;
        });
        el.addEventListener('input', () => {
            draftDirty = true;
        });
    });
}

function addDocumentRow() {
    const d = collectDraftFromForm();
    d.document_items.push({
        name: '',
        description: '',
        required: true,
        priority: 'normal',
    });
    draftDirty = true;
    renderDocumentsEditor(d.document_items);
}

async function saveTemplate() {
    if (!selectedVisaType) return;
    const body = collectDraftFromForm();
    const payload = {
        title: body.title,
        public_description: body.public_description,
        processing_fee_eur: body.processing_fee_eur === '' ? null : body.processing_fee_eur,
        duration_months: body.duration_months === '' ? null : body.duration_months,
        timeline: body.timeline.filter((t) => t.title || t.description || t.duration_label),
        document_items: body.document_items.filter((d) => d.name || d.description),
    };

    if (!payload.timeline.length) {
        alert(t('configurator.needTimeline'));
        return;
    }

    const response = await fetch(`${API_BASE}/case-templates/${encodeURIComponent(selectedVisaType)}`, {
        method: 'PUT',
        credentials: 'include',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok || !data.success) {
        alert(data.error || t('configurator.saveFailed'));
        return;
    }
    serverTemplate = data.template;
    draftDirty = false;
    await loadTemplateIndex();
    renderVisaList();
    updateEditorHeader(selectedVisaType);
    const toast = document.getElementById('cfg-toast');
    if (toast) {
        toast.textContent = t('configurator.saveOk');
        toast.classList.remove('hidden');
        setTimeout(() => toast.classList.add('hidden'), 3200);
    }
}

async function discardDraft() {
    if (!selectedVisaType) return;
    draftDirty = false;
    await loadTemplate(selectedVisaType);
    const base = serverTemplate && serverTemplate.visa_type ? serverTemplate : { visa_type: selectedVisaType };
    fillEditorForm(normalizeDraftFromServer(base));
    updateEditorHeader(selectedVisaType);
}

async function initConfigurator() {
    const u = await loadSessionUser();
    if (!u) return;

    await loadTemplateIndex();
    renderVisaList();

    if (templateIndex.length) {
        const first = templateIndex[0].visa_type;
        selectedVisaType = first;
        await loadTemplate(first);
        const base = serverTemplate && serverTemplate.visa_type ? serverTemplate : { visa_type: first };
        fillEditorForm(normalizeDraftFromServer(base));
        updateEditorHeader(first);
        renderVisaList();
    } else {
        document.getElementById('editor-root')?.classList.add('opacity-50', 'pointer-events-none');
    }

    document.getElementById('btn-save-template')?.addEventListener('click', saveTemplate);
    document.getElementById('btn-discard-template')?.addEventListener('click', discardDraft);
    document.getElementById('btn-add-timeline')?.addEventListener('click', addTimelineStep);
    document.getElementById('btn-add-document')?.addEventListener('click', addDocumentRow);

    const helpModal = document.getElementById('cfg-help-modal');
    const openHelp = () => helpModal?.classList.remove('hidden');
    const closeHelp = () => helpModal?.classList.add('hidden');
    document.getElementById('cfg-help-open')?.addEventListener('click', openHelp);
    document.getElementById('cfg-help-close')?.addEventListener('click', closeHelp);
    helpModal?.addEventListener('click', (e) => {
        if (e.target === helpModal) closeHelp();
    });
}

window.addEventListener('lk-locale-change', () => {
    if (window.LkI18n) {
        window.LkI18n.applyDocument();
    }
    renderVisaList();
    if (selectedVisaType) {
        const draft = collectDraftFromForm();
        renderTimelineEditor(draft.timeline);
        renderDocumentsEditor(draft.document_items);
        updateEditorHeader(selectedVisaType);
    }
});

document.addEventListener('DOMContentLoaded', initConfigurator);
