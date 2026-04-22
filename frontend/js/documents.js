// Documents page: load user documents and handle pagination.
(function () {
  const token = localStorage.getItem("token");
  if (!token) {
    return;
  }

  const CARDS_PER_PAGE = 12;
  let currentPage = 1;
  let allDocuments = [];
  let currentUserName = "Пользователь";
  let currentUserPermissions = [];

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

  function toDisplayDate(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return "Дата не указана";
    }
    return date.toLocaleString("ru-RU", {
      day: "2-digit",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  async function fetchFromApi(path) {
    for (const baseUrl of apiBases) {
      try {
        const response = await fetch(baseUrl + path, {
          method: "GET",
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        if (!response.ok) {
          continue;
        }

        return await response.json();
      } catch (error) {
        // Try next base URL.
      }
    }

    return null;
  }

  function buildCard(documentData) {
    const statusLabel =
      documentData.status === "pending" ? "Ожидает загрузки" : "Загружено";
    const priorityLabel = documentData.is_priority ? "Срочно" : "Стандарт";
    const badgeClasses = documentData.is_priority
      ? "bg-tertiary-container/10 text-tertiary-container"
      : "bg-primary-fixed text-primary-container";

    const canModerateDocuments =
      currentUserPermissions.includes("full_access") ||
      currentUserPermissions.includes("approve_documents") ||
      currentUserPermissions.includes("review_documents");
    const canDownloadDocuments =
      canModerateDocuments ||
      currentUserPermissions.includes("download_documents");
    const actionsHtml = canModerateDocuments
      ? `
          <button id="document-approve-${documentData.id}" class="flex-1 py-3 bg-primary-container text-white rounded-xl text-sm font-bold hover:opacity-90 transition-all" type="button">Одобрить</button>
          <button id="document-reject-${documentData.id}" class="flex-1 py-3 bg-slate-50 text-error rounded-xl text-sm font-bold hover:bg-error/10 transition-all" type="button">Отклонить</button>
        `
      : canDownloadDocuments
      ? `
          <button id="document-download-${documentData.id}" class="flex-1 py-3 bg-primary-container text-white rounded-xl text-sm font-bold hover:opacity-90 transition-all" type="button">Скачать</button>
        `
      : `
          <div class="flex-1 py-3 text-center bg-slate-50 text-slate-400 rounded-xl text-xs font-semibold uppercase tracking-wide">Нет доступа</div>
        `;

    return `
      <article id="document-card-${documentData.id}" class="bg-surface-container-lowest p-6 rounded-xl shadow-[0px_20px_40px_rgba(117,118,130,0.06)] group relative overflow-hidden flex flex-col h-full border-t-4 border-tertiary-container">
        <div class="absolute top-0 right-0 mt-4 mr-4">
          <span class="${badgeClasses} text-[10px] font-bold uppercase tracking-widest px-3 py-1 rounded-full flex items-center gap-1">
            <span class="material-symbols-outlined text-xs" style="font-variation-settings: 'FILL' 1;">priority_high</span>
            ${priorityLabel}
          </span>
        </div>
        <div class="mb-6">
          <div class="w-12 h-12 bg-slate-50 rounded-xl flex items-center justify-center text-primary mb-4">
            <span class="material-symbols-outlined">${escapeHtml(documentData.icon || "description")}</span>
          </div>
          <h3 class="text-xl font-bold text-slate-800 leading-tight mb-1">${escapeHtml(documentData.title)}</h3>
          <p class="text-sm text-slate-500 font-medium">Клиент: ${escapeHtml(currentUserName)}</p>
        </div>
        <div class="flex items-center gap-4 py-4 mb-6 border-y border-slate-50">
          <div class="flex-1">
            <p class="text-[10px] uppercase tracking-wider text-slate-400 font-bold mb-1">${statusLabel}</p>
            <p class="text-sm font-semibold text-slate-700">${toDisplayDate(documentData.last_action_at)}</p>
          </div>
          <div class="flex-1">
            <p class="text-[10px] uppercase tracking-wider text-slate-400 font-bold mb-1">Тип файла</p>
            <p class="text-sm font-semibold text-slate-700">${escapeHtml(documentData.file_type)}, ${escapeHtml(documentData.file_size)}</p>
          </div>
        </div>
        <div class="flex gap-3 mt-auto">
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

  function renderDocuments() {
    const grid = document.getElementById("documents-grid");
    const summary = document.getElementById("documents-summary");
    const total = allDocuments.length;
    const totalPages = Math.max(1, Math.ceil(total / CARDS_PER_PAGE));

    if (!grid || !summary) {
      return;
    }

    if (currentPage > totalPages) {
      currentPage = totalPages;
    }

    const start = (currentPage - 1) * CARDS_PER_PAGE;
    const pageDocuments = allDocuments.slice(start, start + CARDS_PER_PAGE);

    if (!pageDocuments.length) {
      grid.innerHTML =
        '<div class="col-span-full bg-surface-container-lowest p-8 rounded-xl shadow-[0px_20px_40px_rgba(117,118,130,0.06)] text-slate-500 font-medium">Документы пока не загружены.</div>';
      summary.textContent = "Показано 0 из 0 документов";
      renderPagination(1);
      return;
    }

    grid.innerHTML = pageDocuments.map(buildCard).join("");
    summary.textContent = `Показано ${start + 1}-${Math.min(start + CARDS_PER_PAGE, total)} из ${total} документов`;
    renderPagination(totalPages);
  }

  async function initDocumentsPage() {
    const userPayload = await fetchFromApi("/user");
    if (userPayload) {
      currentUserName = userPayload.name || userPayload.email || "Пользователь";
      currentUserPermissions = Array.isArray(userPayload.permissions)
        ? userPayload.permissions
        : [];
    }

    const canAccessDocuments =
      currentUserPermissions.includes("full_access") ||
      currentUserPermissions.includes("review_documents") ||
      currentUserPermissions.includes("approve_documents") ||
      currentUserPermissions.includes("upload_documents") ||
      currentUserPermissions.includes("download_documents");
    if (!canAccessDocuments) {
      const grid = document.getElementById("documents-grid");
      const summary = document.getElementById("documents-summary");
      if (grid) {
        grid.innerHTML =
          '<div class="col-span-full bg-surface-container-lowest p-8 rounded-xl shadow-[0px_20px_40px_rgba(117,118,130,0.06)] text-slate-500 font-medium">Доступ к разделу документов ограничен для вашей роли.</div>';
      }
      if (summary) {
        summary.textContent = "Доступ ограничен";
      }
      return;
    }

    const documentsPayload = await fetchFromApi("/documents");
    allDocuments = documentsPayload?.documents || [];

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
  }

  initDocumentsPage();
})();
