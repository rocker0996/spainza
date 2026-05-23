/**
 * Ранний редирект на 404 при отсутствии доступа (без defer — до lk.js и страничных скриптов).
 */
(function (global) {
  const path = global.location.pathname || "";
  const NOT_FOUND = path.includes("/lk/") ? "./404.html" : "/frontend/lk/404.html";

  global.LK_NOT_FOUND_URL = NOT_FOUND;

  global.redirectLkAccessDenied = function redirectLkAccessDenied() {
    if (path.includes("404.html")) {
      return;
    }
    global.location.replace(NOT_FOUND);
  };

  global.isLkAccessDeniedPayload = function isLkAccessDeniedPayload(data) {
    if (!data || typeof data !== "object") {
      return false;
    }
    const err = String(data.error || data.message_ru || data.message || "").toLowerCase();
    return (
      err.includes("access denied") ||
      err.includes("нет доступа") ||
      err.includes("недостаточно прав") ||
      err === "forbidden"
    );
  };

  global.shouldRedirectLkAccessDenied = function shouldRedirectLkAccessDenied(response, data) {
    if (response && response.status === 403) {
      return true;
    }
    return global.isLkAccessDeniedPayload(data);
  };
})(window);
