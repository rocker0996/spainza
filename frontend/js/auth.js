// Minimal login flow for /ru/login.html.
(function () {
  const form = document.getElementById("login-form");
  if (!form) {
    return;
  }
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

  const errorBox = document.getElementById("login-error");

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (errorBox) {
      errorBox.textContent = "";
    }

    const email = String(document.getElementById("email")?.value || "").trim();
    const password = String(document.getElementById("password")?.value || "");

    try {
      let response = null;
      let data = null;
      let requestError = null;
      for (const baseUrl of apiBases) {
        try {
          response = await fetch(baseUrl + "/login", {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({ email, password }),
          });

          const responseText = await response.text();
          data = responseText ? JSON.parse(responseText) : {};
          requestError = null;
          break;
        } catch (error) {
          requestError = error;
        }
      }

      if (requestError) {
        throw new Error("Cannot reach API. Check backend at http://localhost:5000");
      }
      if (!response.ok || !data.success) {
        throw new Error(data.error || "Login failed");
      }

      // Backend token field is expected here.
      localStorage.setItem("token", data.token || "");
      window.location.href = "/lk/dashboard.html";
    } catch (error) {
      if (errorBox) {
        errorBox.textContent = error.message || "Login error";
      }
    }
  });
})();
