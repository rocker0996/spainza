/**
 * Clients list management for clients.html
 */

const API_BASE = (function resolveApiBase() {
    if (window.API_BASE_URL) {
        return String(window.API_BASE_URL).replace(/\/+$/, '');
    }
    if (window.location.protocol === 'file:') {
        return 'http://localhost:5000/api';
    }
    return '/api';
})();

function t(key, params) {
    return window.LkI18n ? window.LkI18n.t(key, params) : key;
}

function roleLabel(role) {
    if (!role) return '—';
    if (window.LkI18n && role.key) {
        return window.LkI18n.roleLabel(role.key);
    }
    return role.name_ru || '—';
}

// Global state for sorting
let currentUsers = [];
let currentSortColumn = 'pending_action';
let currentSortDirection = 'desc';

/**
 * Redirect to login if not authenticated
 */
function redirectToLogin() {
    window.location.href = '/frontend/login.html';
}

function redirectAccessDenied() {
    if (typeof window.redirectLkAccessDenied === 'function') {
        window.redirectLkAccessDenied();
        return;
    }
    const url = window.LK_NOT_FOUND_URL || '/frontend/lk/404.html';
    window.location.replace(url);
}

/**
 * Check if user has permission to view users
 */
function hasViewUsersPermission(permissions) {
    if (!Array.isArray(permissions)) return false;
    
    const viewPermissions = [
        'full_access',
        'view_all_users',
        'view_lower_users',
        'view_assignable_users',
        'view_assigned_clients'
    ];
    
    return permissions.some(perm => viewPermissions.includes(perm));
}

/**
 * Get role badge color based on role key
 */
function getRoleBadgeColor(roleKey) {
    const colors = {
        management: 'bg-purple-100 text-purple-600',
        admin: 'bg-red-100 text-red-600',
        support: 'bg-blue-50 text-blue-700',
        moderator: 'bg-blue-100 text-blue-600',
        manager: 'bg-green-100 text-green-600',
        client: 'bg-green-50 text-green-700',
        digital_nomad: 'bg-yellow-100 text-yellow-600',
        golden_visa: 'bg-amber-100 text-amber-600',
        other: 'bg-stone-100 text-slate-600',
        user: 'bg-slate-100 text-slate-500',
    };
    return colors[roleKey] || 'bg-slate-100 text-slate-600';
}

/**
 * Get visa type badge color
 */
function getVisaTypeBadgeColor(visaType) {
    const colors = {
        'digital_nomad': 'bg-yellow-100 text-yellow-600',
        'golden_visa': 'bg-amber-100 text-amber-600',
        'citizen': 'bg-green-100 text-green-600',
        'other': 'bg-slate-100 text-slate-600'
    };
    return colors[visaType] || 'bg-slate-100 text-slate-600';
}

/**
 * Get visa type label in Russian
 */
function getVisaTypeLabel(visaType) {
    return window.LkI18n ? window.LkI18n.visaLabel(visaType) : visaType;
}

/**
 * Get user initials from name or email
 */
function getUserInitials(name, email) {
    if (name && name.trim()) {
        const parts = name.trim().split(' ');
        if (parts.length >= 2) {
            return (parts[0][0] + parts[1][0]).toUpperCase();
        }
        return name.substring(0, 2).toUpperCase();
    }
    if (email) {
        return email.substring(0, 2).toUpperCase();
    }
    return 'U';
}

/**
 * Format date to readable format
 */
function formatDate(dateString) {
    if (!dateString) return t('clients.dateUnknown');

    const date = new Date(dateString);
    const month = window.LkI18n
        ? window.LkI18n.formatMonthShort(date.getMonth())
        : date.getMonth();

    return `${date.getDate()} ${month} ${date.getFullYear()}`;
}

/** Дата из кейса (#target-date / case_data.target_date), формат YYYY-MM-DD — без сдвига по часовому поясу */
function formatConsulateTargetDate(ymd) {
    if (!ymd) return t('clients.notSpecified');
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(ymd).trim());
    if (!m) return formatDate(ymd);
    const y = parseInt(m[1], 10);
    const mo = parseInt(m[2], 10) - 1;
    const d = parseInt(m[3], 10);
    const date = new Date(y, mo, d);
    const month = window.LkI18n
        ? window.LkI18n.formatMonthShort(date.getMonth())
        : date.getMonth();
    return `${date.getDate()} ${month} ${date.getFullYear()}`;
}

function renderEmptyUsersState() {
    return `
        <div class="flex flex-col items-center gap-3 py-4">
            <span class="material-symbols-outlined text-5xl text-slate-300">group_off</span>
            <p class="font-semibold text-slate-500">${t('clients.notFound')}</p>
        </div>
    `;
}

function buildUserAvatarHtml(user, initials, sizeClass = 'w-10 h-10', extraClass = '') {
    const x = extraClass ? ` ${extraClass}` : '';
    if (user.avatar) {
        return `<img class="${sizeClass} rounded-full object-cover shrink-0${x}" src="${user.avatar}" alt="${user.name || user.email}"/>`;
    }
    return `<div class="${sizeClass} rounded-full bg-blue-100 flex items-center justify-center text-primary font-bold text-[10px] shrink-0${x}">${initials}</div>`;
}

function buildPendingDocsBadge(pendingDocsCount, variant = 'default') {
    if (pendingDocsCount <= 0) return '';
    const sizeClass =
        variant === 'compact'
            ? 'min-w-[18px] h-4 px-1 text-[9px]'
            : 'min-w-[20px] h-5 px-1.5 text-[10px]';
    return `
        <span class="pulser inline-flex items-center justify-center shrink-0 rounded-full bg-primary text-white font-bold ${sizeClass}">
            ${pendingDocsCount > 99 ? '99+' : pendingDocsCount}
        </span>
    `;
}

const MOBILE_SORT_LABELS = {
    id: 'ID',
    pending_action: () => t('clients.sortPending'),
    role: () => t('clients.sortRole'),
    target_date: () => t('clients.sortConsulate'),
    date: () => t('clients.sortRegistration'),
};

function updateMobileSortPills(column, direction) {
    document.querySelectorAll('.clients-sort-pill').forEach((pill) => {
        const col = pill.getAttribute('data-mobile-sort');
        const isActive = col === column;
        const raw = MOBILE_SORT_LABELS[col] || col;
        const base = typeof raw === 'function' ? raw() : raw;
        pill.classList.toggle('active', isActive);
        pill.textContent = isActive
            ? base + (direction === 'asc' ? ' ↑' : ' ↓')
            : base;
    });
}

/** Публичный ID в списках: две латинские буквы и четыре цифры при наличии, иначе #число */
function formatClientListId(user) {
    const d = user && user.display_id ? String(user.display_id).trim() : '';
    if (d) {
        return `#${d}`;
    }
    return `#${user.id}`;
}

/**
 * Render users table
 */
function renderUsersTable(users) {
    const tbody = document.getElementById('users-table-body');
    if (!tbody) return;

    if (!users || users.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="6" class="px-8 py-12 text-center text-slate-500">
                    ${renderEmptyUsersState()}
                </td>
            </tr>
        `;
        renderUsersCards(users);
        return;
    }

    tbody.innerHTML = users.map(user => {
        const initials = getUserInitials(user.name, user.email);
        const roleBadgeColor = getRoleBadgeColor(user.role.key);
        const pendingDocsCount = Number(user.pending_documents_count || 0);
        const pendingDocsBadge = buildPendingDocsBadge(pendingDocsCount);
        const pendingDocsBadgeCompact = buildPendingDocsBadge(pendingDocsCount, 'compact');
        
        return `
            <tr class="hover:bg-slate-50/80 transition-colors group">
                <td class="px-8 py-6 font-manrope font-bold text-slate-400">${formatClientListId(user)}</td>
                <td class="px-8 py-6">
                    <div class="flex flex-col gap-1">
                        <button type="button"
                                class="flex items-center gap-3 w-full max-w-full text-left rounded-xl -m-1 p-1 border-0 bg-transparent cursor-pointer hover:bg-slate-100/80 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/30"
                                onclick='manageCaseForUser(${user.id}, ${JSON.stringify(user.display_id || "")})'
                                title="${t('clients.openCase')}">
                        ${user.avatar
                            ? `<img class="w-10 h-10 rounded-full object-cover shrink-0 pointer-events-none" src="${user.avatar}" alt="${user.name || user.email}"/>`
                            : `<div class="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center text-primary font-bold text-xs shrink-0 pointer-events-none">${initials}</div>`
                        }
                        <div class="min-w-0 flex-1">
                            <p class="font-bold text-slate-800 flex items-center gap-2 min-w-0">
                                ${pendingDocsBadge}
                                <span class="truncate">${user.name || t('clients.noName')}</span>
                            </p>
                        </div>
                        </button>
                        <p class="text-xs text-slate-500 pl-[52px]">${user.email}</p>
                    </div>
                </td>
                <td class="px-8 py-6">
                    <span class="inline-flex items-center px-3 py-1 rounded-full ${roleBadgeColor} text-xs font-bold font-manrope">
                        ${roleLabel(user.role)}
                    </span>
                </td>
                <td class="px-8 py-6 text-sm text-slate-600">${formatConsulateTargetDate(user.target_date)}</td>
                <td class="px-8 py-6 text-sm text-slate-600">${formatDate(user.created_at)}</td>
                <td class="px-8 py-6 text-right">
                    <div class="relative">
                        <button class="p-2 rounded-xl hover:bg-white hover:shadow-sm transition-all text-slate-400 hover:text-primary"
                                onclick="toggleDropdown(event, ${user.id})">
                            <span class="material-symbols-outlined">more_vert</span>
                        </button>
                        <div class="dropdown-menu" id="dropdown-${user.id}">
                            <div class="dropdown-item" onclick='manageCaseForUser(${user.id}, ${JSON.stringify(user.display_id || "")})'>
                                <span class="material-symbols-outlined text-[20px]">folder_managed</span>
                                ${t('clients.manageCase')}
                            </div>
                            <div class="dropdown-item" onclick='viewUserDetails(${user.id}, ${JSON.stringify(user.display_id || "")})'>
                                <span class="material-symbols-outlined text-[20px]">visibility</span>
                                ${t('clients.viewDocuments')}
                                ${pendingDocsBadgeCompact}
                            </div>
                        </div>
                    </div>
                </td>
            </tr>
        `;
    }).join('');

    renderUsersCards(users);
}

/**
 * Render users as cards (mobile)
 */
function renderUsersCards(users) {
    const list = document.getElementById('users-cards-list');
    if (!list) return;

    if (!users || users.length === 0) {
        list.innerHTML = `
            <div class="bg-white rounded-2xl shadow-[0px_12px_32px_rgba(117,118,130,0.06)] p-8 text-center">
                ${renderEmptyUsersState()}
            </div>
        `;
        return;
    }

    list.innerHTML = users.map(user => {
        const initials = getUserInitials(user.name, user.email);
        const roleBadgeColor = getRoleBadgeColor(user.role.key);
        const pendingDocsCount = Number(user.pending_documents_count || 0);
        const pendingDocsBadge = buildPendingDocsBadge(pendingDocsCount);
        const pendingDocsBadgeCompact = buildPendingDocsBadge(pendingDocsCount, 'compact');
        const avatarHtml = buildUserAvatarHtml(user, initials, 'w-9 h-9', 'pointer-events-none');

        return `
            <article class="bg-white rounded-xl shadow-[0px_8px_24px_rgba(117,118,130,0.06)] p-3 active:scale-[0.995] transition-transform">
                <div class="flex items-center gap-2.5 mb-2">
                    <button type="button"
                            class="shrink-0 p-0 border-0 bg-transparent rounded-full cursor-pointer hover:opacity-90 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/30 focus-visible:ring-offset-2"
                            onclick='manageCaseForUser(${user.id}, ${JSON.stringify(user.display_id || "")})'
                            title="${t('clients.openCase')}"
                            aria-label="${t('clients.openCase')}">
                        ${avatarHtml}
                    </button>
                    <div class="flex-1 min-w-0">
                        <p class="font-bold text-slate-800 text-sm leading-tight flex items-center gap-1.5 min-w-0">
                            ${pendingDocsBadge}
                            <button type="button"
                                    class="truncate text-left p-0 border-0 bg-transparent font-bold text-slate-800 text-sm min-w-0 cursor-pointer hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/30 rounded-sm"
                                    onclick='manageCaseForUser(${user.id}, ${JSON.stringify(user.display_id || "")})'
                                    title="${t('clients.openCase')}">
                                ${user.name || t('clients.noName')}
                            </button>
                            <span class="inline-flex items-center shrink-0 px-2 py-0.5 rounded-full ${roleBadgeColor} text-[9px] font-bold font-manrope leading-none">
                                ${roleLabel(user.role)}
                            </span>
                        </p>
                        <p class="text-[11px] text-slate-500 truncate flex items-center justify-between gap-2 mt-0.5">
                            <span class="truncate">${user.email}</span>
                            <span class="shrink-0 font-manrope font-bold text-[10px] text-slate-400">${formatClientListId(user)}</span>
                        </p>
                    </div>
                </div>
                <dl class="grid grid-cols-2 gap-1.5 mb-2 text-[11px]">
                    <div class="rounded-lg bg-slate-50 px-2 py-1.5">
                        <dt class="text-[9px] font-bold uppercase tracking-wider text-slate-400 leading-none mb-0.5">${t('clients.sortConsulate')}</dt>
                        <dd class="font-semibold text-slate-700 leading-tight">${formatConsulateTargetDate(user.target_date)}</dd>
                    </div>
                    <div class="rounded-lg bg-slate-50 px-2 py-1.5">
                        <dt class="text-[9px] font-bold uppercase tracking-wider text-slate-400 leading-none mb-0.5">${t('clients.sortRegistration')}</dt>
                        <dd class="font-semibold text-slate-700 leading-tight">${formatDate(user.created_at)}</dd>
                    </div>
                </dl>
                <div class="flex gap-1.5">
                    <button type="button" class="flex-1 flex items-center justify-center gap-1 py-2 rounded-lg bg-primary/10 text-primary text-[11px] font-bold font-manrope active:scale-[0.98] transition-transform"
                            onclick='manageCaseForUser(${user.id}, ${JSON.stringify(user.display_id || "")})'>
                        <span class="material-symbols-outlined text-[16px]">folder_managed</span>
                        ${t('clients.caseBtn')}
                    </button>
                    <button type="button" class="flex-1 flex items-center justify-center gap-1 py-2 rounded-lg bg-slate-100 text-slate-700 text-[11px] font-bold font-manrope active:scale-[0.98] transition-transform"
                            onclick='viewUserDetails(${user.id}, ${JSON.stringify(user.display_id || "")})'>
                        <span class="material-symbols-outlined text-[16px]">description</span>
                        ${t('clients.docsBtn')}
                        ${pendingDocsBadgeCompact}
                    </button>
                </div>
            </article>
        `;
    }).join('');
}

/**
 * Update stats display
 */
function updateStats(users, viewerRole) {
    const totalElement = document.getElementById('total-users');
    const viewerRoleElement = document.getElementById('viewer-role');
    
    if (totalElement) {
        totalElement.textContent = users.length;
    }
    
    if (viewerRoleElement && viewerRole) {
        viewerRoleElement.textContent = roleLabel(viewerRole);
    }
}

/**
 * Load users from API
 */
async function loadUsers() {
    try {
        const response = await fetch(`${API_BASE}/users`, {
            method: 'GET',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        const data = await response.json().catch(() => ({}));

        if (response.status === 401) {
            if (typeof window.whenLkSessionReady === 'function') {
                try {
                    await window.whenLkSessionReady();
                    return loadUsers();
                } catch {
                    // session bootstrap failed — lk.js will redirect
                }
            }
            localStorage.removeItem('token');
            redirectToLogin();
            return;
        }

        if (
            response.status === 403 ||
            (typeof window.shouldRedirectLkAccessDenied === 'function' &&
                window.shouldRedirectLkAccessDenied(response, data))
        ) {
            redirectAccessDenied();
            return;
        }

        if (!response.ok) {
            throw new Error('Failed to load users');
        }

        if (data.success) {
            currentUsers = data.users;
            renderWithCurrentSort();
            updateStats(currentUsers, data.viewer_role);
        } else if (
            typeof window.isLkAccessDeniedPayload === 'function' &&
            window.isLkAccessDeniedPayload(data)
        ) {
            redirectAccessDenied();
        } else {
            console.error('Failed to load users:', data.error);
            alert(t('clients.loadError'));
        }
    } catch (error) {
        console.error('Error loading users:', error);
        alert(t('clients.connectionError'));
    }
}

/**
 * Toggle dropdown menu
 */
function toggleDropdown(event, userId) {
    event.stopPropagation();
    
    // Close all other dropdowns
    document.querySelectorAll('.dropdown-menu').forEach(menu => {
        if (menu.id !== `dropdown-${userId}`) {
            menu.classList.remove('show');
        }
    });
    
    // Toggle current dropdown
    const dropdown = document.getElementById(`dropdown-${userId}`);
    if (dropdown) {
        dropdown.classList.toggle('show');
    }
}

/**
 * Navigate to case management page for specific user
 */
function manageCaseForUser(userId, displayIdOpt) {
    const did = String(displayIdOpt || "").trim().toUpperCase();
    if (/^[A-Z]{2}\d{4}$/.test(did)) {
        window.location.href = `./case.html?client=${encodeURIComponent(did)}`;
        return;
    }
    window.location.href = `./case.html?userId=${encodeURIComponent(String(userId))}`;
}

/**
 * View user documents
 */
function viewUserDetails(userId, displayIdOpt) {
    const did = String(displayIdOpt || "").trim().toUpperCase();
    if (/^[A-Z]{2}\d{4}$/.test(did)) {
        window.location.href = `./documents.html?client=${encodeURIComponent(did)}`;
        return;
    }
    window.location.href = `./documents.html?userId=${encodeURIComponent(String(userId))}`;
}

function getSortedUsers(column, direction) {
    return [...currentUsers].sort((a, b) => {
        let valueA;
        let valueB;

        switch (column) {
            case 'id':
                valueA = a.id;
                valueB = b.id;
                break;
            case 'pending_action':
                valueA = Number(a.pending_documents_count || 0);
                valueB = Number(b.pending_documents_count || 0);
                break;
            case 'role':
                valueA = a.role.level;
                valueB = b.role.level;
                break;
            case 'target_date':
                valueA = a.target_date || '';
                valueB = b.target_date || '';
                break;
            case 'date':
                valueA = new Date(a.created_at || 0).getTime();
                valueB = new Date(b.created_at || 0).getTime();
                break;
            default:
                return 0;
        }

        let comparison = 0;
        if (valueA > valueB) comparison = 1;
        else if (valueA < valueB) comparison = -1;

        return direction === 'asc' ? comparison : -comparison;
    });
}

function renderWithCurrentSort() {
    const sortedUsers = getSortedUsers(currentSortColumn, currentSortDirection);
    updateSortIcons(currentSortColumn, currentSortDirection);
    updateMobileSortPills(currentSortColumn, currentSortDirection);
    renderUsersTable(sortedUsers);
}

/**
 * Sort table by column
 */
function sortTable(column) {
    if (currentSortColumn === column) {
        currentSortDirection = currentSortDirection === 'asc' ? 'desc' : 'asc';
    } else {
        currentSortColumn = column;
        currentSortDirection = column === 'pending_action' ? 'desc' : 'asc';
    }
    renderWithCurrentSort();
}

/**
 * Update sort icons to show current sort state
 */
function updateSortIcons(activeColumn, direction) {
    // Reset all icons
    document.querySelectorAll('.sort-icon').forEach(icon => {
        icon.textContent = 'unfold_more';
        icon.classList.remove('text-primary');
    });
    
    // Update active column icon
    const activeIcon = document.querySelector(`.sort-icon[data-sort="${activeColumn}"]`);
    if (activeIcon) {
        activeIcon.textContent = direction === 'asc' ? 'arrow_upward' : 'arrow_downward';
        activeIcon.classList.add('text-primary');
    }
}

/**
 * Close dropdowns when clicking outside
 */
function closeAllDropdowns() {
    document.querySelectorAll('.dropdown-menu').forEach(menu => {
        menu.classList.remove('show');
    });
}

/**
 * Initialize page
 */
function getAddClientModalEls() {
    return {
        modal: document.getElementById('add-client-modal'),
        closeBtn: document.getElementById('add-client-modal-close'),
        openBtn: document.getElementById('add-client-open-btn'),
        idInput: document.getElementById('add-client-by-id-input'),
        idSubmit: document.getElementById('add-client-by-id-submit'),
        idMessage: document.getElementById('add-client-by-id-message'),
        inviteUrl: document.getElementById('add-client-invite-url'),
        inviteCopy: document.getElementById('add-client-invite-copy'),
        inviteHint: document.getElementById('add-client-invite-hint'),
    };
}

function setAddClientByIdMessage(text, kind) {
    const { idMessage } = getAddClientModalEls();
    if (!idMessage) return;
    idMessage.textContent = text || '';
    idMessage.classList.remove('hidden', 'text-emerald-600', 'text-red-600', 'text-slate-600');
    if (!text) {
        idMessage.classList.add('hidden');
        return;
    }
    idMessage.classList.remove('hidden');
    if (kind === 'ok') idMessage.classList.add('text-emerald-600');
    else if (kind === 'err') idMessage.classList.add('text-red-600');
    else idMessage.classList.add('text-slate-600');
}

function openAddClientModal() {
    const { modal } = getAddClientModalEls();
    if (!modal) return;
    modal.classList.add('show');
    modal.setAttribute('aria-hidden', 'false');
    loadManagerInviteIntoModal();
}

function closeAddClientModal() {
    const { modal } = getAddClientModalEls();
    if (!modal) return;
    modal.classList.remove('show');
    modal.setAttribute('aria-hidden', 'true');
    setAddClientByIdMessage('', null);
}

let inviteLoadPromise = null;

async function loadManagerInviteIntoModal() {
    const { inviteUrl, inviteHint } = getAddClientModalEls();
    if (!inviteUrl || !inviteHint) return;

    inviteHint.textContent = t('clients.inviteLoading');
    inviteUrl.value = '';

    if (!inviteLoadPromise) {
        inviteLoadPromise = (async () => {
            const res = await fetch(`${API_BASE}/lk/manager-invite`, {
                credentials: 'include',
                headers: {
                    'Content-Type': 'application/json',
                },
            });
            const data = await res.json().catch(() => ({}));
            if (!res.ok || !data.success) {
                throw new Error(data.error || 'invite_failed');
            }
            return data;
        })();
    }

    try {
        const data = await inviteLoadPromise;
        const path = data.invite_path || '';
        const built =
            path && typeof window.location !== 'undefined' && window.location.origin
                ? `${window.location.origin}${path}`
                : data.invite_url || '';
        inviteUrl.value = built;
        inviteHint.textContent = t('clients.inviteReady');
    } catch {
        inviteHint.textContent = t('clients.inviteFailed');
        inviteLoadPromise = null;
    }
}

async function submitAddClientById() {
    const { idInput } = getAddClientModalEls();
    if (!idInput) return;

    const raw = String(idInput.value || '').trim();
    const compact = raw.toUpperCase().replace(/\s+/g, '');
    let clientPayload;
    if (/^[A-Z]{2}\d{4}$/.test(compact)) {
        clientPayload = compact;
    } else {
        const clientId = parseInt(raw, 10);
        if (!clientId || clientId < 1) {
            setAddClientByIdMessage(t('clients.invalidId'), 'err');
            return;
        }
        clientPayload = clientId;
    }

    setAddClientByIdMessage(t('clients.sending'), 'muted');

    try {
        const res = await fetch(`${API_BASE}/lk/clients/assign-by-id`, {
            method: 'POST',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ client_id: clientPayload }),
        });
        const data = await res.json().catch(() => ({}));

        if (res.ok && data.success) {
            setAddClientByIdMessage(t('clients.assignOk'), 'ok');
            idInput.value = '';
            await loadUsers();
            return;
        }

        const msg =
            data.message_ru ||
            data.error ||
            t('clients.assignFailed');
        setAddClientByIdMessage(msg, 'err');
    } catch {
        setAddClientByIdMessage(t('clients.networkError'), 'err');
    }
}

let clientsPageBooted = false;

function bootClientsPage() {
    if (clientsPageBooted) {
        return;
    }
    clientsPageBooted = true;
    if (!guardClientsPageAccess()) {
        return;
    }
    void loadUsers();
}

window.addEventListener('lk-user-ready', bootClientsPage);

window.addEventListener('lk-locale-change', () => {
    if (window.LkI18n) {
        window.LkI18n.applyDocument();
    }
    updateMobileSortPills(currentSortColumn, currentSortDirection);
    renderUsersTable(currentUsers);
});

function guardClientsPageAccess() {
    const user = typeof window.getLkCurrentUser === 'function' ? window.getLkCurrentUser() : null;
    if (user && typeof window.canAccessLkPageGate === 'function' && !window.canAccessLkPageGate(user, 'clients')) {
        redirectAccessDenied();
        return false;
    }
    return true;
}

document.addEventListener('DOMContentLoaded', () => {
    if (window.getLkCurrentUser?.()) {
        bootClientsPage();
    }

    const modalEls = getAddClientModalEls();
    if (modalEls.openBtn) {
        modalEls.openBtn.addEventListener('click', () => openAddClientModal());
    }
    if (modalEls.closeBtn) {
        modalEls.closeBtn.addEventListener('click', () => closeAddClientModal());
    }
    if (modalEls.modal) {
        modalEls.modal.addEventListener('click', (e) => {
            if (e.target === modalEls.modal) closeAddClientModal();
        });
    }
    if (modalEls.idSubmit) {
        modalEls.idSubmit.addEventListener('click', () => submitAddClientById());
    }
    if (modalEls.idInput) {
        modalEls.idInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                submitAddClientById();
            }
        });
    }
    if (modalEls.inviteCopy && modalEls.inviteUrl) {
        modalEls.inviteCopy.addEventListener('click', async () => {
            const v = modalEls.inviteUrl.value || '';
            if (!v) return;
            try {
                await navigator.clipboard.writeText(v);
                const hint = modalEls.inviteHint;
                if (hint) {
                    const prev = hint.textContent;
                    hint.textContent = t('clients.copied');
                    setTimeout(() => {
                        hint.textContent = prev;
                    }, 2000);
                }
            } catch {
                modalEls.inviteUrl.select();
                document.execCommand('copy');
            }
        });
    }
    
    // Close dropdowns when clicking outside
    document.addEventListener('click', closeAllDropdowns);

    document.querySelectorAll('.clients-sort-pill').forEach((pill) => {
        pill.addEventListener('click', () => {
            const column = pill.getAttribute('data-mobile-sort');
            if (column) sortTable(column);
        });
    });
});

// Make functions globally available for onclick handlers
window.sortTable = sortTable;
window.toggleDropdown = toggleDropdown;
window.manageCaseForUser = manageCaseForUser;
window.viewUserDetails = viewUserDetails;
window.openAddClientModal = openAddClientModal;
window.closeAddClientModal = closeAddClientModal;
