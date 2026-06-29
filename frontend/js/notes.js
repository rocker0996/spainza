/**
 * Staff-only internal notes for a client case.
 */

const NOTES_API_BASE = (function resolveApiBase() {
    if (window.API_BASE_URL) return String(window.API_BASE_URL).replace(/\/+$/, '');
    if (window.location.protocol === 'file:') return 'http://localhost:5000/api';
    return '/api';
})();

const notesState = {
    userId: null,
    displayId: '',
    user: null,
    caseData: null,
    notes: null,
    dirty: false,
    saving: false,
};

function nt(key, params) {
    return window.LkI18n ? window.LkI18n.t(key, params) : key;
}

function notesEscape(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function notesToast(message, variant = 'info') {
    const root = document.getElementById('notes-toast');
    if (!root || !message) return;
    const colors = variant === 'error'
        ? 'bg-red-50 text-red-900 border-red-200'
        : variant === 'success'
            ? 'bg-emerald-50 text-emerald-900 border-emerald-200'
            : 'bg-slate-50 text-slate-800 border-slate-200';
    const icon = variant === 'error' ? 'error' : variant === 'success' ? 'check_circle' : 'info';
    root.innerHTML = `
        <div class="flex items-start gap-3 rounded-2xl border px-4 py-3 text-sm font-semibold shadow-lg ${colors}">
            <span class="material-symbols-outlined shrink-0 text-[20px]">${icon}</span>
            <span class="leading-snug">${notesEscape(message)}</span>
        </div>
    `;
    root.classList.remove('hidden');
    window.clearTimeout(notesToast.timer);
    notesToast.timer = window.setTimeout(() => {
        root.classList.add('hidden');
        root.innerHTML = '';
    }, 3600);
}

function getNotesParam(name) {
    return new URLSearchParams(window.location.search).get(name) || '';
}

async function notesFetch(path, options = {}) {
    const response = await fetch(`${NOTES_API_BASE}${path}`, {
        credentials: 'include',
        headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
        ...options,
    });
    const data = await response.json().catch(() => ({}));
    if (response.status === 401) {
        window.location.href = '/frontend/login.html';
        throw new Error('unauthorized');
    }
    if (
        response.status === 403 ||
        (typeof window.shouldRedirectLkAccessDenied === 'function' &&
            window.shouldRedirectLkAccessDenied(response, data))
    ) {
        if (typeof window.redirectLkAccessDenied === 'function') {
            window.redirectLkAccessDenied();
        }
        throw new Error('access denied');
    }
    if (!response.ok || data.success === false) {
        throw new Error(data.error || 'request_failed');
    }
    return data;
}

async function resolveNotesClient() {
    const publicId = getNotesParam('client').trim().toUpperCase();
    const userIdRaw = getNotesParam('userId').trim();
    if (publicId) {
        const data = await notesFetch(`/lk/case-client/resolve?client=${encodeURIComponent(publicId)}`);
        notesState.userId = Number(data.user_id);
        notesState.displayId = data.display_id || publicId;
        return;
    }
    const parsed = Number.parseInt(userIdRaw, 10);
    if (parsed > 0) {
        notesState.userId = parsed;
        return;
    }
    throw new Error('missing_client');
}

function notesClientQuery() {
    if (notesState.displayId) return `client=${encodeURIComponent(notesState.displayId)}`;
    return `userId=${encodeURIComponent(String(notesState.userId))}`;
}

function formatNotesDateTime(value) {
    if (!value) return '-';
    if (window.LkI18n?.formatLocalDateTime) return window.LkI18n.formatLocalDateTime(value);
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '-';
    return date.toLocaleString();
}

function instantToDatetimeLocal(value) {
    if (!value) return '';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '';
    const pad = (n) => String(n).padStart(2, '0');
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function datetimeLocalToInstant(value) {
    if (!value) return null;
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return null;
    return date.toISOString();
}

function getNotesEls() {
    return {
        loading: document.getElementById('notes-loading'),
        content: document.getElementById('notes-content'),
        title: document.getElementById('notes-title'),
        subtitle: document.getElementById('notes-subtitle'),
        caseNumber: document.getElementById('notes-case-number'),
        caseLink: document.getElementById('notes-case-link'),
        documentsLink: document.getElementById('notes-documents-link'),
        save: document.getElementById('notes-save-btn'),
        dirty: document.getElementById('notes-dirty-badge'),
        general: document.getElementById('general-notes'),
        risk: document.getElementById('risk-notes'),
        payment: document.getElementById('payment-notes'),
        priority: document.getElementById('priority'),
        nextContact: document.getElementById('next-contact-at'),
        checklist: document.getElementById('checklist-list'),
        checklistProgress: document.getElementById('checklist-progress'),
        newChecklist: document.getElementById('new-checklist-item'),
        addChecklist: document.getElementById('add-checklist-item'),
        updatedAt: document.getElementById('notes-updated-at'),
        updatedBy: document.getElementById('notes-updated-by'),
        visaRoute: document.getElementById('notes-visa-route'),
        history: document.getElementById('notes-history-list'),
    };
}

function setDirty(value) {
    notesState.dirty = Boolean(value);
    const { dirty } = getNotesEls();
    if (dirty) dirty.classList.toggle('hidden', !notesState.dirty);
}

function collectNotesPayload() {
    const els = getNotesEls();
    const checklist = Array.from(els.checklist?.querySelectorAll('[data-checklist-row]') || [])
        .map((row) => ({
            id: row.getAttribute('data-checklist-id') || '',
            label: row.querySelector('[data-checklist-label]')?.textContent?.trim() || '',
            checked: Boolean(row.querySelector('[data-checklist-check]')?.checked),
        }))
        .filter((item) => item.label);
    return {
        general_notes: els.general?.value || '',
        risk_notes: els.risk?.value || '',
        payment_notes: els.payment?.value || '',
        priority: els.priority?.value || 'normal',
        next_contact_at: datetimeLocalToInstant(els.nextContact?.value || ''),
        checklist,
    };
}

function renderChecklist() {
    const els = getNotesEls();
    const items = Array.isArray(notesState.notes?.checklist) ? notesState.notes.checklist : [];
    if (!els.checklist) return;
    els.checklist.innerHTML = items.map((item, index) => `
        <div data-checklist-row data-checklist-id="${notesEscape(item.id || `item_${index}`)}" class="flex items-start gap-3 rounded-xl border border-slate-100 bg-slate-50/70 p-3">
            <input data-checklist-check type="checkbox" ${item.checked ? 'checked' : ''} class="mt-0.5 h-5 w-5 rounded border-slate-300 text-primary focus:ring-primary"/>
            <div class="min-w-0 flex-1">
                <p data-checklist-label class="text-sm font-semibold text-slate-800">${notesEscape(item.label)}</p>
            </div>
            <button type="button" data-remove-checklist class="rounded-lg p-1 text-slate-400 transition hover:bg-white hover:text-red-600" aria-label="${notesEscape(nt('common.delete'))}">
                <span class="material-symbols-outlined text-[18px]">close</span>
            </button>
        </div>
    `).join('');
    const done = items.filter((item) => item.checked).length;
    if (els.checklistProgress) els.checklistProgress.textContent = `${done}/${items.length}`;
}

function renderHistory(history) {
    const { history: root } = getNotesEls();
    if (!root) return;
    if (!Array.isArray(history) || !history.length) {
        root.innerHTML = `<p class="text-sm text-slate-500">${notesEscape(nt('case.historyEmpty'))}</p>`;
        return;
    }
    root.innerHTML = history.slice(0, 8).map((item) => {
        const editor = item.editor || {};
        const name = editor.name || editor.email || 'System';
        const action = window.LkI18n?.translateCaseHistoryAction
            ? window.LkI18n.translateCaseHistoryAction(item.action)
            : item.action;
        return `
            <div class="rounded-xl border border-slate-100 bg-slate-50/60 p-3">
                <div class="mb-1 flex items-start justify-between gap-3">
                    <p class="text-sm font-bold text-slate-800">${notesEscape(action)}</p>
                    <span class="shrink-0 text-[11px] font-semibold text-slate-400">${notesEscape(formatNotesDateTime(item.created_at))}</span>
                </div>
                <p class="text-xs font-semibold text-slate-500">${notesEscape(name)}</p>
                ${item.details ? `<p class="mt-1 text-xs text-slate-500">${notesEscape(item.details)}</p>` : ''}
            </div>
        `;
    }).join('');
}

function renderNotes() {
    const els = getNotesEls();
    const user = notesState.user || {};
    const caseData = notesState.caseData || {};
    const notes = notesState.notes || {};
    const name = user.name || user.email || nt('clients.noName');
    const did = notesState.displayId || user.display_id || `#${notesState.userId}`;
    notesState.displayId = notesState.displayId || user.display_id || '';

    if (els.title) els.title.textContent = name;
    if (els.subtitle) {
        const email = user.email ? ` · ${user.email}` : '';
        els.subtitle.textContent = `${nt('notes.subtitle')} ${email}`;
    }
    if (els.caseNumber) els.caseNumber.textContent = did;
    const query = notesClientQuery();
    if (els.caseLink) els.caseLink.href = `./case.html?${query}`;
    if (els.documentsLink) els.documentsLink.href = `./documents.html?${query}`;

    if (els.general) els.general.value = notes.general_notes || '';
    if (els.risk) els.risk.value = notes.risk_notes || '';
    if (els.payment) els.payment.value = notes.payment_notes || '';
    if (els.priority) els.priority.value = notes.priority || 'normal';
    if (els.nextContact) els.nextContact.value = instantToDatetimeLocal(notes.next_contact_at);
    if (els.updatedAt) els.updatedAt.textContent = formatNotesDateTime(notes.updated_at);
    if (els.updatedBy) els.updatedBy.textContent = notes.updated_by_name || notes.updated_by_email || '-';
    if (els.visaRoute) {
        const role = caseData.visa_type || user.role?.key || '';
        els.visaRoute.textContent = window.LkI18n?.visaLabel ? window.LkI18n.visaLabel(role) : role || '-';
    }
    renderChecklist();
    setDirty(false);
}

async function loadNotesPage() {
    const els = getNotesEls();
    try {
        await resolveNotesClient();
        const [userData, caseData, notesData, historyData] = await Promise.all([
            notesFetch(`/users/${notesState.userId}`),
            notesFetch(`/case-data/${notesState.userId}`),
            notesFetch(`/case-notes/${notesState.userId}`),
            notesFetch(`/case-history/${notesState.userId}`),
        ]);
        notesState.user = userData.user || null;
        notesState.caseData = caseData.case_data || null;
        notesState.notes = notesData.notes || null;
        renderNotes();
        renderHistory(historyData.history || []);
        els.loading?.classList.add('hidden');
        els.content?.classList.remove('hidden');
    } catch (error) {
        if (String(error.message || '') === 'access denied') return;
        els.loading?.classList.remove('hidden');
        if (els.loading) {
            els.loading.innerHTML = `
                <span class="material-symbols-outlined text-5xl text-red-300">error</span>
                <p class="mt-3 font-semibold text-red-700">${notesEscape(nt('notes.loadFailed'))}</p>
            `;
        }
    }
}

async function saveNotes() {
    if (!notesState.userId || notesState.saving) return;
    const els = getNotesEls();
    notesState.saving = true;
    if (els.save) els.save.disabled = true;
    try {
        const data = await notesFetch(`/case-notes/${notesState.userId}`, {
            method: 'PUT',
            body: JSON.stringify(collectNotesPayload()),
        });
        notesState.notes = data.notes;
        renderNotes();
        const historyData = await notesFetch(`/case-history/${notesState.userId}`);
        renderHistory(historyData.history || []);
        notesToast(nt('notes.saved'), 'success');
    } catch {
        notesToast(nt('notes.saveFailed'), 'error');
    } finally {
        notesState.saving = false;
        if (els.save) els.save.disabled = false;
    }
}

function bindNotesEvents() {
    const els = getNotesEls();
    [els.general, els.risk, els.payment, els.priority, els.nextContact].forEach((node) => {
        node?.addEventListener('input', () => setDirty(true));
        node?.addEventListener('change', () => setDirty(true));
    });
    els.save?.addEventListener('click', () => saveNotes());
    els.checklist?.addEventListener('change', (event) => {
        if (!event.target?.matches?.('[data-checklist-check]')) return;
        const index = Array.from(els.checklist.querySelectorAll('[data-checklist-row]')).indexOf(
            event.target.closest('[data-checklist-row]')
        );
        if (index >= 0 && notesState.notes?.checklist?.[index]) {
            notesState.notes.checklist[index].checked = Boolean(event.target.checked);
            renderChecklist();
            setDirty(true);
        }
    });
    els.checklist?.addEventListener('click', (event) => {
        const btn = event.target?.closest?.('[data-remove-checklist]');
        if (!btn) return;
        const row = btn.closest('[data-checklist-row]');
        const rows = Array.from(els.checklist.querySelectorAll('[data-checklist-row]'));
        const index = rows.indexOf(row);
        if (index >= 0 && notesState.notes?.checklist) {
            notesState.notes.checklist.splice(index, 1);
            renderChecklist();
            setDirty(true);
        }
    });
    els.addChecklist?.addEventListener('click', () => {
        const label = (els.newChecklist?.value || '').trim();
        if (!label) return;
        if (!notesState.notes) notesState.notes = {};
        if (!Array.isArray(notesState.notes.checklist)) notesState.notes.checklist = [];
        notesState.notes.checklist.push({
            id: `custom_${Date.now()}`,
            label,
            checked: false,
        });
        els.newChecklist.value = '';
        renderChecklist();
        setDirty(true);
    });
    els.newChecklist?.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') {
            event.preventDefault();
            els.addChecklist?.click();
        }
    });
    window.addEventListener('beforeunload', (event) => {
        if (!notesState.dirty) return;
        event.preventDefault();
        event.returnValue = '';
    });
    window.addEventListener('lk-locale-change', () => {
        if (window.LkI18n) window.LkI18n.applyDocument();
        renderNotes();
    });
}

let notesPageBooted = false;

function bootNotesPage() {
    if (notesPageBooted) return;
    if (!window.getLkCurrentUser?.()) return;
    notesPageBooted = true;
    bindNotesEvents();
    loadNotesPage();
}

window.addEventListener('lk-user-ready', bootNotesPage);
document.addEventListener('DOMContentLoaded', () => {
    if (window.getLkCurrentUser?.()) bootNotesPage();
});
