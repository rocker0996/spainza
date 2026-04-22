// Simple auth guard for /lk/* pages.
(function () {
  const loginUrl =
    window.location.protocol === "file:"
      ? "../login.html"
      : "/frontend/login.html";
  const apiBases = (function resolveApiBases() {
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
  })();

  const logoutButton = document.getElementById("logout-btn");
  if (logoutButton) {
    logoutButton.addEventListener("click", (event) => {
      event.preventDefault();
      localStorage.removeItem("token");
      window.location.href = loginUrl;
    });
  }

  const token = localStorage.getItem("token");
  if (!token) {
    window.location.href = loginUrl;
    return;
  }

  const defaultAvatar =
    "https://lh3.googleusercontent.com/aida-public/AB6AXuAWaxo2zb6eb4vAnCllT9BFKo3-B1kUyyBKnJsKOryG-83Ei1Aki_i-4mfF0Or6AXCsBHR7kzwlnxOPKVFqIuOQYwAueATj5sEaGT1oQe1FUgUdkC804wI3oYGG4WtbxobWEeFXEo-KW0e8Kiop68qXvdwdK0g3dEGiHoTcijhIPOkZaU-rRfja2RGlmSMNUar-mKZCiBJcRG0S3g-0MI5ctoY6HckcVVAGyfmSHpwDGZn9FFXCHZY2x4txr8O1i4_2QpIZuEF5FVQ";

  function resolveDisplayName(name, email) {
    if (name && String(name).trim()) {
      return String(name).trim();
    }
    if (email && String(email).includes("@")) {
      return String(email).split("@")[0];
    }
    return "Client";
  }

  function formatCreatedAt(createdAt) {
    if (!createdAt) {
      return "Member since —";
    }
    const parsedDate = new Date(createdAt);
    if (Number.isNaN(parsedDate.getTime())) {
      return "Member since —";
    }
    return "Member since " + parsedDate.toLocaleDateString();
  }

  function hasPermission(userData, permission) {
    const permissions = Array.isArray(userData.permissions) ? userData.permissions : [];
    return permissions.includes("full_access") || permissions.includes(permission);
  }

  function applyRoleDataToUi(userData) {
    const roleNameNode = document.getElementById("user-role-name");
    const roleLevelNode = document.getElementById("user-role-level");
    const roleData = userData.role || {};
    const roleName = roleData.name_ru || "Пользователь";
    const caseStatus =
      userData.case_status_ru ||
      userData.case_status ||
      userData.application_status_ru ||
      userData.application_status ||
      "Не начат";

    if (roleNameNode) {
      roleNameNode.textContent = roleName;
    }
    if (roleLevelNode) {
      roleLevelNode.textContent = String(caseStatus).trim() || "Не начат";
    }
  }

  function togglePageAccess(userData) {
    const canAccessDocuments =
      hasPermission(userData, "upload_documents") ||
      hasPermission(userData, "download_documents") ||
      hasPermission(userData, "review_documents") ||
      hasPermission(userData, "approve_documents");

    const canAccessMessages =
      hasPermission(userData, "respond_to_messages") ||
      hasPermission(userData, "communicate_with_clients");

    const canCreateApplication = hasPermission(userData, "request_role_change");

    document.querySelectorAll('a[href="./documents.html"]').forEach((link) => {
      if (!canAccessDocuments) {
        link.classList.add("hidden");
      }
    });

    document.querySelectorAll('a[href="./messages.html"]').forEach((link) => {
      if (!canAccessMessages) {
        link.classList.add("hidden");
      }
    });

    const newRequestButtons = Array.from(document.querySelectorAll("button")).filter((button) =>
      button.textContent.includes("Новая заявка")
    );
    newRequestButtons.forEach((button) => {
      if (!canCreateApplication) {
        button.classList.add("hidden");
      }
    });
  }

  function applyUserDataToUi(userData) {
    const displayName = resolveDisplayName(userData.name, userData.email);

    const titleName = document.getElementById("user-name-title");
    if (titleName) {
      titleName.textContent = displayName;
    }

    const cardName = document.getElementById("user-name-card");
    if (cardName) {
      cardName.textContent = displayName;
    }

    const email = document.getElementById("user-email");
    if (email) {
      email.textContent = userData.email || "Email unavailable";
    }

    const createdAt = document.getElementById("user-created-at");
    if (createdAt) {
      createdAt.textContent = formatCreatedAt(userData.created_at);
    }

    const avatar = document.getElementById("user-avatar");
    if (avatar) {
      avatar.src = userData.avatar || defaultAvatar;
      avatar.alt = displayName + " avatar";
    }

    applyRoleDataToUi(userData);
    togglePageAccess(userData);
  }

  async function loadCurrentUser() {
    for (const baseUrl of apiBases) {
      try {
        const response = await fetch(baseUrl + "/user", {
          method: "GET",
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        if (!response.ok) {
          continue;
        }

        const payload = await response.json();
        localStorage.setItem("currentUserProfile", JSON.stringify(payload));
        applyUserDataToUi(payload);
        return;
      } catch (error) {
        // Try next API base.
      }
    }
  }

  (async function verifySession() {
    for (const baseUrl of apiBases) {
      try {
        const response = await fetch(baseUrl + "/lk/session", {
          method: "GET",
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });
        if (!response.ok) {
          continue;
        }
        await response.json();
        await loadCurrentUser();
        return;
      } catch (error) {
        // Try next API base.
      }
    }

    localStorage.removeItem("token");
    window.location.href = loginUrl;
  })();
})();
