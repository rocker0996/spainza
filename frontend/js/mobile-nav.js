/**
 * Мобильная навигация ЛК (drawer как на dashboard.html).
 * На <body>: data-lk-nav-active="dashboard|clients|documents|configurator|messages|profile|support"
 * (getAttribute — надёжнее dataset для имён с несколькими дефисами.)
 */
const initLkMobileNav = () => {
  if (document.getElementById("mobile-nav-toggle")) return;

  const active =
    document.body.getAttribute("data-lk-nav-active") ||
    document.body.getAttribute("data-lk-nav-secondary") ||
    "";

  const mainClass = (id) =>
    id === active
      ? "-ml-5 pl-6 pr-4 py-3 flex items-center gap-4 text-primary-container bg-primary-fixed/30 rounded-r-xl border-l-4 border-primary-container transition-transform active:scale-[0.98]"
      : "flex items-center gap-4 text-outline px-6 py-3 hover:bg-surface-container-low rounded-r-xl transition-all border-l-4 border-transparent hover:border-outline-variant/30";

  const secondaryClass = (id) =>
    id === active
      ? "-ml-5 pl-6 pr-4 py-2 flex items-center gap-4 text-primary-container bg-primary-fixed/30 rounded-r-xl border-l-4 border-primary-container transition-transform active:scale-[0.98]"
      : "-ml-5 pl-6 pr-4 py-2 flex items-center gap-4 text-outline hover:bg-surface-container-low rounded-r-xl transition-all";

  const t = (key) => (window.LkI18n ? window.LkI18n.t(key) : key);

  const mainItems = [
    { id: "dashboard", href: "./dashboard.html", icon: "dashboard", labelKey: "nav.dashboard" },
    { id: "clients", href: "./clients.html", icon: "groups", labelKey: "nav.clients", gate: "clients" },
    { id: "documents", href: "./documents.html", icon: "description", labelKey: "nav.documents", gate: "documents" },
    { id: "configurator", href: "./configurator.html", icon: "rule_settings", labelKey: "nav.configurator", gate: "configurator" },
    { id: "messages", href: "./messages.html", icon: "chat_bubble", labelKey: "nav.messages", gate: "messages" },
  ];

  const style = document.createElement("style");
  style.textContent = `
    .mobile-nav-overlay { transition: opacity 260ms ease; }
    .mobile-nav-drawer { transition: transform 320ms cubic-bezier(0.22, 0.61, 0.36, 1); }
  `;
  document.head.appendChild(style);

  const el = (tag, className, attrs = {}) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    Object.entries(attrs).forEach(([k, v]) => node.setAttribute(k, v));
    return node;
  };

  const icon = (name, filled, spanClass = "material-symbols-outlined") => {
    const span = el("span", spanClass);
    if (filled) span.style.fontVariationSettings = "'FILL' 1";
    span.textContent = name;
    return span;
  };

  const secondaryLink = (href, label, iconName, id) => {
    const a = el("a", secondaryClass(id), { href });
    a.append(icon(iconName, active === id, "material-symbols-outlined text-[20px]"), document.createTextNode(label));
    return a;
  };

  // Header
  const header = el(
    "header",
    "md:hidden fixed inset-x-0 top-0 z-50 bg-surface/90 backdrop-blur-lg border-b border-outline-variant/20"
  );
  const headerInner = el("div", "px-4 py-3 flex items-center justify-between");
  const logo = el(
    "a",
    "text-2xl font-black tracking-tighter text-primary-container font-headline inline-block no-underline hover:opacity-90 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-container rounded-sm",
    { href: "./dashboard.html" }
  );
  logo.textContent = "Spainza";
  const menuToggle = el(
    "button",
    "w-10 h-10 rounded-xl bg-surface-container-low flex items-center justify-center text-outline active:scale-95 transition-transform",
    {
      type: "button",
      id: "mobile-nav-toggle",
      "aria-label": t("common.openMenu"),
      "aria-controls": "mobile-nav-drawer",
      "aria-expanded": "false",
    }
  );
  menuToggle.append(icon("menu", false, "material-symbols-outlined text-[22px]"));
  headerInner.append(logo, menuToggle);
  header.append(headerInner);

  const menuOverlay = el(
    "div",
    "mobile-nav-overlay md:hidden fixed inset-0 z-40 bg-black/35 opacity-0 pointer-events-none",
    { id: "mobile-nav-overlay" }
  );

  const menuDrawer = el(
    "aside",
    "mobile-nav-drawer md:hidden fixed top-0 left-0 h-dvh w-[84%] max-w-[320px] z-50 bg-surface-container-lowest border-r border-outline-variant/15 -translate-x-full overflow-y-auto",
    { id: "mobile-nav-drawer" }
  );

  const drawerHead = el("div", "px-5 py-4 border-b border-outline-variant/15 flex items-center justify-between");
  const drawerLogo = el(
    "a",
    "text-2xl font-black tracking-tighter text-primary-container font-headline inline-block no-underline",
    { href: "./dashboard.html" }
  );
  drawerLogo.textContent = "Spainza";
  const menuClose = el(
    "button",
    "w-9 h-9 rounded-lg bg-surface-container-low flex items-center justify-center text-outline active:scale-95 transition-transform",
    { type: "button", id: "mobile-nav-close", "aria-label": t("common.closeMenu") }
  );
  menuClose.append(icon("close", false, "material-symbols-outlined text-[20px]"));
  drawerHead.append(drawerLogo, menuClose);

  const drawerBody = el("div", "px-5 py-6 space-y-6");
  const mainNav = el("nav", "flex flex-col gap-2 font-headline text-sm font-semibold uppercase tracking-widest");
  mainItems.forEach((item) => {
    const a = el("a", mainClass(item.id), { href: item.href });
    if (item.gate) a.dataset.lkGate = item.gate;
    const ic = icon(item.icon, item.id === active);
    a.append(ic, document.createTextNode(t(item.labelKey)));
    mainNav.append(a);
  });

  const footerBlock = el("div", "pt-4 border-t border-outline-variant/15 space-y-4");
  const localeWrap = el("div");
  const localeLabel = el(
    "div",
    "text-[10px] font-semibold uppercase tracking-widest text-on-surface-variant font-label mb-2 text-center"
  );
  localeLabel.textContent = t("common.interfaceLanguage");
  const localeBtns = el("div", "flex p-1 bg-surface-container rounded-xl border border-outline-variant/20");
  const ruBtn = el("button", "flex-1 py-2 rounded-lg text-xs font-bold bg-white shadow-sm text-primary", {
    type: "button",
    "data-locale-btn": "ru",
  });
  ruBtn.textContent = t("common.langRu");
  const enBtn = el(
    "button",
    "flex-1 py-2 rounded-lg text-xs font-bold text-slate-500 hover:text-primary transition-colors",
    { type: "button", "data-locale-btn": "en" }
  );
  enBtn.textContent = t("common.langEn");
  localeBtns.append(ruBtn, enBtn);
  localeWrap.append(localeLabel, localeBtns);

  footerBlock.append(
    localeWrap,
    secondaryLink("./profile.html", t("nav.profile"), "tune", "profile"),
    secondaryLink("./support.html", t("nav.support"), "help_center", "support"),
    (() => {
      const a = el(
        "a",
        "-ml-5 pl-6 pr-4 py-2 flex items-center gap-4 text-outline hover:bg-surface-container-low rounded-r-xl transition-all mt-4",
        {
          href: "../login.html",
        }
      );
      a.append(icon("logout", false, "material-symbols-outlined text-[20px]"), document.createTextNode(t("nav.logout")));
      return a;
    })()
  );

  drawerBody.append(mainNav, footerBlock);
  menuDrawer.append(drawerHead, drawerBody);

  const mount = document.createDocumentFragment();
  mount.append(header, menuOverlay, menuDrawer);
  document.body.insertBefore(mount, document.body.firstChild);

  const openMenu = () => {
    document.body.classList.add("overflow-hidden");
    menuOverlay.classList.remove("opacity-0", "pointer-events-none");
    menuOverlay.classList.add("opacity-100");
    menuDrawer.classList.remove("-translate-x-full");
    menuDrawer.classList.add("translate-x-0");
    menuToggle.setAttribute("aria-expanded", "true");
  };

  const closeMenu = () => {
    document.body.classList.remove("overflow-hidden");
    menuOverlay.classList.add("opacity-0", "pointer-events-none");
    menuOverlay.classList.remove("opacity-100");
    menuDrawer.classList.add("-translate-x-full");
    menuDrawer.classList.remove("translate-x-0");
    menuToggle.setAttribute("aria-expanded", "false");
  };

  menuToggle.addEventListener("click", () => {
    const expanded = menuToggle.getAttribute("aria-expanded") === "true";
    if (expanded) closeMenu();
    else openMenu();
  });
  menuClose.addEventListener("click", closeMenu);
  menuOverlay.addEventListener("click", closeMenu);
  menuDrawer.querySelectorAll("a[href]").forEach((link) => {
    link.addEventListener("click", closeMenu);
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeMenu();
  });

  window.addEventListener("lk-locale-change", () => {
    localeLabel.textContent = t("common.interfaceLanguage");
    ruBtn.textContent = t("common.langRu");
    enBtn.textContent = t("common.langEn");
    menuToggle.setAttribute("aria-label", t("common.openMenu"));
    menuClose.setAttribute("aria-label", t("common.closeMenu"));
    mainNav.querySelectorAll("a[href]").forEach((link, index) => {
      const item = mainItems[index];
      if (!item) return;
      const textNode = [...link.childNodes].find((n) => n.nodeType === Node.TEXT_NODE);
      if (textNode) textNode.textContent = t(item.labelKey);
    });
    const footerLinks = footerBlock.querySelectorAll("a[href]");
    if (footerLinks[0]) footerLinks[0].lastChild.textContent = t("nav.profile");
    if (footerLinks[1]) footerLinks[1].lastChild.textContent = t("nav.support");
    const logoutLink = footerBlock.querySelector('a[href="../login.html"]');
    if (logoutLink && logoutLink.lastChild) logoutLink.lastChild.textContent = t("nav.logout");
  });
};

if (document.body) initLkMobileNav();
else document.addEventListener("DOMContentLoaded", initLkMobileNav);
