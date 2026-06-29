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
    managerNotes: [],
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
            ? 'bg-green-50 text-green-900 border-green-200'
            : 'bg-slate-50 text-slate-800 border-slate-200';
    const icon = variant === 'error' ? 'error' : variant === 'success' ? 'check_circle' : 'info';
    root.innerHTML = `
        <div class="pointer-events-auto flex items-start gap-3 rounded-2xl border px-4 py-3 text-sm font-semibold shadow-lg ${colors}">
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

function parsePaymentTerms(rawValue) {
    const raw = String(rawValue || '').trim();
    const empty = { case_price: '', payment_model: '', amount_paid: '' };
    if (!raw) return empty;
    try {
        const parsed = JSON.parse(raw);
        if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
            return {
                case_price: String(parsed.case_price || ''),
                payment_model: String(parsed.payment_model || ''),
                amount_paid: String(parsed.amount_paid || ''),
            };
        }
    } catch {
        // Legacy payment notes are kept as the payment model text.
    }
    return { ...empty, payment_model: raw };
}

function serializePaymentTerms(els) {
    return JSON.stringify({
        case_price: els.casePrice?.value || '',
        payment_model: els.paymentModel?.value || '',
        amount_paid: els.amountPaid?.value || '',
    });
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
        notesList: document.getElementById('manager-notes-list'),
        casePrice: document.getElementById('case-price'),
        paymentModel: document.getElementById('payment-model'),
        amountPaid: document.getElementById('amount-paid'),
        checklist: document.getElementById('checklist-list'),
        checklistProgress: document.getElementById('checklist-progress'),
        newChecklist: document.getElementById('new-checklist-item'),
        addChecklist: document.getElementById('add-checklist-item'),
        historyBtn: document.getElementById('history-btn'),
        historyModal: document.getElementById('history-modal'),
        closeHistory: document.getElementById('close-history-modal'),
        history: document.getElementById('history-log-list'),
    };
}

function setDirty(value) {
    notesState.dirty = Boolean(value);
    const { dirty } = getNotesEls();
    if (dirty) dirty.classList.toggle('hidden', !notesState.dirty);
}

function parseManagerNotes(rawValue, fallbackUpdatedAt) {
    const raw = String(rawValue || '').trim();
    if (!raw) return [];
    try {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed)) {
            return parsed
                .filter((item) => item && typeof item === 'object')
                .map((item, index) => ({
                    id: String(item.id || `note_${index}_${Date.now()}`),
                    text: String(item.text || '').trim(),
                    created_at: item.created_at || fallbackUpdatedAt || new Date().toISOString(),
                    updated_at: item.updated_at || item.created_at || fallbackUpdatedAt || null,
                }))
                .filter((item) => item.text);
        }
    } catch {
        // Legacy plain text is converted to one interactive note.
    }
    return [{
        id: `legacy_${Date.now()}`,
        text: raw,
        created_at: fallbackUpdatedAt || new Date().toISOString(),
        updated_at: fallbackUpdatedAt || null,
    }];
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
        general_notes: JSON.stringify(notesState.managerNotes),
        risk_notes: '',
        payment_notes: serializePaymentTerms(els),
        priority: 'normal',
        next_contact_at: null,
        checklist,
    };
}

function renderManagerNotes() {
    const { notesList } = getNotesEls();
    if (!notesList) return;
    if (!notesState.managerNotes.length) {
        notesList.innerHTML = `
            ${renderAddNoteCard()}
            <div class="notes-soft-card notes-sticky-card rounded-2xl border-dashed p-6 text-center">
                <span class="material-symbols-outlined text-4xl text-slate-300">sticky_note_2</span>
                <p class="mt-2 text-sm font-semibold text-slate-500">${notesEscape(nt('notes.emptyNotes'))}</p>
            </div>
        `;
        return;
    }
    notesList.innerHTML = [
        renderAddNoteCard(),
        ...notesState.managerNotes.map((note, index) => `
        <article data-manager-note data-note-index="${index}" class="notes-soft-card notes-sticky-card rounded-2xl p-4">
            <div class="mb-3 flex items-start justify-between gap-3">
                <div class="min-w-0">
                    <p class="text-xs font-bold uppercase tracking-wider text-slate-400">${notesEscape(nt('notes.noteCardTitle', { n: index + 1 }))}</p>
                    <p class="mt-0.5 text-xs font-semibold text-slate-400">${notesEscape(formatNotesDateTime(note.updated_at || note.created_at))}</p>
                </div>
                <button type="button" data-remove-note class="shrink-0 rounded-xl border border-slate-200 bg-white p-2 text-slate-400 transition hover:border-red-200 hover:bg-red-50 hover:text-red-600" aria-label="${notesEscape(nt('common.delete'))}">
                    <span class="material-symbols-outlined text-[18px]">delete</span>
                </button>
            </div>
            <textarea data-note-text class="notes-field min-h-[126px] resize-y border-slate-100 bg-white/90">${notesEscape(note.text)}</textarea>
        </article>
    `)
    ].join('');
}

function renderAddNoteCard() {
    return `
        <article class="notes-soft-card notes-add-card rounded-2xl p-4">
            <div class="mb-3 flex items-center gap-2">
                <span class="flex h-9 w-9 items-center justify-center rounded-xl bg-blue-50 text-blue-600">
                    <span class="material-symbols-outlined text-[20px]">add</span>
                </span>
                <div class="min-w-0">
                    <p class="text-sm font-extrabold text-slate-800 font-manrope">${notesEscape(nt('notes.addNoteLabel'))}</p>
                    <p class="text-xs font-semibold text-slate-400">${notesEscape(nt('notes.addNoteHint'))}</p>
                </div>
            </div>
            <textarea id="new-manager-note" class="notes-field min-h-[104px] resize-y border-slate-100 bg-white/90" data-i18n-placeholder="notes.addNotePlaceholder" placeholder="${notesEscape(nt('notes.addNotePlaceholder'))}" rows="4"></textarea>
            <button id="add-manager-note" type="button" class="mt-3 inline-flex min-h-10 w-full items-center justify-center gap-2 rounded-xl bg-primary px-4 py-2 text-sm font-bold text-white transition hover:-translate-y-0.5 hover:opacity-95">
                <span class="material-symbols-outlined text-[18px]">add</span>
                <span>${notesEscape(nt('notes.addNote'))}</span>
            </button>
        </article>
    `;
}

function renderChecklist() {
    const els = getNotesEls();
    const items = Array.isArray(notesState.notes?.checklist) ? notesState.notes.checklist : [];
    if (!els.checklist) return;
    els.checklist.innerHTML = items.map((item, index) => `
        <div data-checklist-row data-checklist-id="${notesEscape(item.id || `item_${index}`)}" class="flex items-start gap-3 rounded-xl border border-slate-200 bg-slate-50/80 p-3">
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
    root.innerHTML = history.map((item) => {
        const editor = item.editor || {};
        const name = editor.name || editor.email || 'System';
        const action = window.LkI18n?.translateCaseHistoryAction
            ? window.LkI18n.translateCaseHistoryAction(item.action)
            : item.action;
        return `
            <div class="rounded-xl border border-slate-100 bg-slate-50/60 p-4">
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

    notesState.managerNotes = parseManagerNotes(notes.general_notes, notes.updated_at);
    const paymentTerms = parsePaymentTerms(notes.payment_notes);
    if (els.casePrice) els.casePrice.value = paymentTerms.case_price;
    if (els.paymentModel) els.paymentModel.value = paymentTerms.payment_model;
    if (els.amountPaid) els.amountPaid.value = paymentTerms.amount_paid;
    renderManagerNotes();
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
    [els.casePrice, els.paymentModel, els.amountPaid].forEach((node) => {
        node?.addEventListener('input', () => setDirty(true));
        node?.addEventListener('change', () => setDirty(true));
    });
    els.save?.addEventListener('click', () => saveNotes());
    document.addEventListener('click', (event) => {
        const addButton = event.target?.closest?.('#add-manager-note');
        if (!addButton) return;
        const noteInput = document.getElementById('new-manager-note');
        const text = (noteInput?.value || '').trim();
        if (!text) return;
        notesState.managerNotes.unshift({
            id: `note_${Date.now()}`,
            text,
            created_at: new Date().toISOString(),
            updated_at: null,
        });
        if (noteInput) noteInput.value = '';
        renderManagerNotes();
        setDirty(true);
    });
    document.addEventListener('keydown', (event) => {
        if (!event.target?.matches?.('#new-manager-note')) return;
        if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
            event.preventDefault();
            document.getElementById('add-manager-note')?.click();
        }
    });
    els.notesList?.addEventListener('input', (event) => {
        if (!event.target?.matches?.('[data-note-text]')) return;
        const row = event.target.closest('[data-manager-note]');
        const index = Number.parseInt(row?.getAttribute('data-note-index') || '-1', 10);
        if (index < 0 || !notesState.managerNotes[index]) return;
        notesState.managerNotes[index].text = event.target.value;
        notesState.managerNotes[index].updated_at = new Date().toISOString();
        setDirty(true);
    });
    els.notesList?.addEventListener('click', (event) => {
        const btn = event.target?.closest?.('[data-remove-note]');
        if (!btn) return;
        const row = btn.closest('[data-manager-note]');
        const index = Number.parseInt(row?.getAttribute('data-note-index') || '-1', 10);
        if (index < 0 || !notesState.managerNotes[index]) return;
        notesState.managerNotes.splice(index, 1);
        renderManagerNotes();
        setDirty(true);
    });
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
    els.historyBtn?.addEventListener('click', () => {
        els.historyModal?.classList.remove('hidden');
        els.historyModal?.classList.add('flex');
    });
    els.closeHistory?.addEventListener('click', () => {
        els.historyModal?.classList.add('hidden');
        els.historyModal?.classList.remove('flex');
    });
    els.historyModal?.addEventListener('click', (event) => {
        if (event.target === els.historyModal) {
            els.historyModal.classList.add('hidden');
            els.historyModal.classList.remove('flex');
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
