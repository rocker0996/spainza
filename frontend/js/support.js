/**
 * Центр поддержки ЛК: FAQ, поиск, контакты (чат → сообщения, email, заказ звонка).
 */
(function () {
  var SUPPORT_EMAIL = "support@spainza.com";

  var I18N = {
    ru: {
      pageTitle: "Поддержка | Spainza",
      heroTitle: "Центр поддержки",
      heroSubtitle:
        "Найдите ответы на ваши вопросы или свяжитесь с нами.",
      searchPlaceholder: "Поиск по базе знаний...",
      faqHeading: "Частые вопросы",
      noResults: "Ничего не найдено. Попробуйте другие слова или напишите в чат.",
      guidesTitle: "Руководства",
      guidesDesc: "Подробные инструкции по платформе и процессу.",
      legalTitle: "Юридическая база",
      legalDesc: "Политика конфиденциальности и ключевые документы.",
      contactHeading: "Связаться с нами",
      contactLead: "Нужна индивидуальная помощь? Наши эксперты на связи.",
      chatTitle: "Живой чат",
      chatHint: "Время ответа: ~5 минут",
      emailTitle: "Email поддержка",
      callbackTitle: "Заказать звонок",
      callbackModalTitle: "Обратный звонок",
      callbackModalLead: "Укажите телефон и удобное время — ответим на почту или перезвоним.",
      labelName: "Имя",
      labelPhone: "Телефон",
      labelComment: "Комментарий",
      cancel: "Отмена",
      sendRequest: "Отправить запрос",
      callbackSuccess: "Откроется почтовый клиент. Если окно не появилось, напишите на ",
      callbackMailtoHint:
        "Запрос не сохраняется на сайте: откроется ваш почтовый клиент с черновиком на {email}. Мы получим обращение только после того, как вы отправите это письмо.",
    },
    en: {
      pageTitle: "Support | Spainza",
      heroTitle: "Help center",
      heroSubtitle: "Find answers or reach our expert team.",
      searchPlaceholder: "Search the knowledge base...",
      faqHeading: "Frequently asked questions",
      noResults: "No matches. Try other words or open live chat.",
      guidesTitle: "Guides",
      guidesDesc: "Platform and process walkthroughs.",
      legalTitle: "Legal",
      legalDesc: "Privacy policy and key documents.",
      contactHeading: "Contact us",
      contactLead: "Need personal help? We are here.",
      chatTitle: "Live chat",
      chatHint: "Typical reply: ~5 min",
      emailTitle: "Email support",
      callbackTitle: "Request a call",
      callbackModalTitle: "Callback request",
      callbackModalLead: "Add your phone and preferred time — we will email or call you back.",
      labelName: "Name",
      labelPhone: "Phone",
      labelComment: "Comment",
      cancel: "Cancel",
      sendRequest: "Send request",
      callbackSuccess: "Your mail app should open. If not, write to ",
      callbackMailtoHint:
        "Nothing is stored on the site: your mail app opens with a draft to {email}. We only receive it after you press send in your mail client.",
    },
  };

  /** Два раздела: иммиграция (общие принципы) и ЛК (устойчивое описание функций). */
  var FAQ = {
    ru: [
      {
        id: "immigration",
        title: "Иммиграция и процесс",
        items: [
          {
            q: "Подходит ли мне маршрут, который уже выбран в кейсе?",
            a: "Маршрут в кейсе отражает согласованную с вами стратегию. Если обстоятельства изменились (семья, работа, сроки), опишите ситуацию менеджеру в «Сообщениях» — правовую оценку и корректировку плана делает команда, а не текст в справке.",
          },
          {
            q: "Можно ли получить юридическую консультацию только из ответов в этом разделе?",
            a: "Нет. Здесь — ориентиры в общем виде. Индивидуальный исход зависит от гражданства, документов, консульства, очередей и актуальных норм. Всё, что касается вашего дела, согласуется с менеджером и юристами по факту материалов.",
          },
          {
            q: "Кто готовит список документов и в каком виде их подавать?",
            a: "Перечень, переводы, копии или оригиналы, легализация или апостиль — определяются под ваш тип дела и канал подачи. В личном кабинете вы видите запрошенные позиции; финальную «сшивку» подачи согласует команда — не ориентируйтесь на обобщённые чек-листы из интернета.",
          },
          {
            q: "Почему сроки нельзя назвать точной датой заранее?",
            a: "Сроки зависят от загрузки консульства или миграционной службы, полноты пакета, дополнительных запросов и сезона. Мы даём диапазоны и обновления по мере движения дела, но гарантировать календарную дату государственного органа нельзя.",
          },
          {
            q: "Нужны ли переводы и заверение документов?",
            a: "Обычно да: иностранные документы переводят и приводят к требованиям приёмной стороны (заверенный перевод, иногда присяжный переводчик — зависит от правил конкретной подачи). Что именно нужно вам — в списке к документам и в комментариях менеджера.",
          },
          {
            q: "Чем отличается подача через консульство от оформления уже в Испании?",
            a: "Это разные ветки процесса: где подаётся первое заявление, какие шаги до въезда и после, какие органы ведут дело. Ваш сценарий фиксируется в сопровождении; общая схема на сайте «Процесс» — для понимания этапов, а не замена персонального плана.",
          },
          {
            q: "Можно ли включить в дело членов семьи?",
            a: "Часто да, но условия (брак, дети, иждивенцы, отдельные заявления или совместный пакет) зависят от основания и маршрута. Перечень и порядок согласуется с менеджером; универсального ответа без ваших данных не существует.",
          },
          {
            q: "Что делать, если изменились законы или требования консульства?",
            a: "Нормы и практика со временем меняются. Если влияет на ваш кейс, команда сообщит, что обновить в документах или в стратегии. Справка не подменяет мониторинг дела — следите за сообщениями в ЛК.",
          },
          {
            q: "Где отслеживать ход именно иммиграционного дела?",
            a: "Официальный статус запроса в государственном органе мы не «подключаем» к сайту как к госреестру. В ЛК отображаются этапы сопровождения, запросы документов и коммуникация с командой — это рабочая картина вашего файла у нас.",
          },
        ],
      },
      {
        id: "portal",
        title: "Личный кабинет и сервис",
        items: [
          {
            q: "Как войти и что делать, если сессия сбросилась?",
            a: "Вход по логину и паролю на странице входа. Сессия привязана к токену в браузере: очистка cookie, другой браузер или режим инкогнито могут потребовать войти снова. Сохраняйте доступ к почте, указанной при регистрации.",
          },
          {
            q: "Зачем раздел «Сообщения»?",
            a: "Это основной защищённый канал переписки с менеджером: уточнения по документам, срокам, шагам. Им удобнее пользоваться, чем разрозненным мессенджером — история остаётся привязанной к делу.",
          },
          {
            q: "Как работает раздел «Документы»?",
            a: "Там отображаются запрошенные категории и ваши загрузки, статусы (на проверке, принят, нужны правки). Комментарий к статусу подсказывает, что изменить. Форматы и лимиты размера файлов зависят от настроек портала; тяжёлые архивы лучше согласовать в переписке.",
          },
          {
            q: "Документ отклонён или запрошена доработка — что делать?",
            a: "Прочитайте пояснение к статусу, внесите правки и загрузите новую версию в ту же категорию, если это доступно. Если кнопки замены нет или неясно, как исправить — напишите в «Сообщениях», приложив скрин при необходимости.",
          },
          {
            q: "Где смотреть общую картину по делу?",
            a: "На главной (дашборд) и в карточке кейса: этапы, напоминания и ссылки на связанные разделы. Набор блоков может отличаться в зависимости от роли и прав доступа.",
          },
          {
            q: "Почему у меня нет пункта меню «Клиенты» или «Документы»?",
            a: "Меню строится по роли и правам: часть разделов только для сотрудников, часть — для клиентов. Если кажется, что чего-то не хватает по делу, уточните у менеджера — возможно, нужно расширить доступ или это не предусмотрено вашим типом учётной записи.",
          },
          {
            q: "Переключатель «Русский / English» — что меняет?",
            a: "Сохраняет предпочтение языка интерфейса в браузере для страниц ЛК, где эта опция подключена (в т.ч. блоки поддержки). Юридические тексты на внешнем сайте открываются по ссылкам в выбранной локали.",
          },
          {
            q: "Безопасно ли загружать документы через ЛК?",
            a: "Файлы передаются по защищённому соединению и хранятся в рамках инфраструктуры проекта. Не передавайте пароль третьим лицам; при смене устройства выходите из сессии. Подробности обработки данных — в политике конфиденциальности на сайте.",
          },
          {
            q: "Чем «Поддержка» отличается от переписки в «Сообщениях»?",
            a: "Эта страница — справочник и быстрые действия (чат с командой через «Сообщения», email, запрос звонка). Конкретные вопросы по вашему кейсу всё равно лучше вести в «Сообщениях», чтобы ответ был привязан к контексту файла.",
          },
        ],
      },
    ],
    en: [
      {
        id: "immigration",
        title: "Immigration and process",
        items: [
          {
            q: "Is the route shown in my case the right one for me?",
            a: "It reflects the strategy agreed with you. If circumstances change (family, work, timing), describe it to your manager in Messages — legal assessment and plan updates are done by the team, not by static help text.",
          },
          {
            q: "Can this FAQ replace legal advice?",
            a: "No. These are general pointers. Outcomes depend on nationality, evidence, consulate workload, and current rules. Anything that matters for your file is confirmed against your materials by your manager and counsel.",
          },
          {
            q: "Who defines the document list and how originals are used?",
            a: "The list, translations, copies vs originals, and legalization or apostille follow your legal basis and submission channel. The portal shows requested items; the final submission package is coordinated by the team — random internet checklists are not a substitute.",
          },
          {
            q: "Why can’t you promise an exact decision date?",
            a: "Timing depends on consulate or immigration workload, completeness of the file, extra requests, and seasonality. We share ranges and updates as the case moves; no one can calendar-guarantee a government decision.",
          },
          {
            q: "Do I need translations and certified copies?",
            a: "Usually yes: foreign documents are translated and formatted to the receiving authority’s rules (sworn translator where required — depends on the route). What applies to you appears in your document list and manager notes.",
          },
          {
            q: "What is the difference between consular filing and in-Spain procedures?",
            a: "They are different paths: where the first application is lodged, pre- and post-arrival steps, and which authorities handle the case. Your scenario is defined in the engagement; the public “Process” page is for orientation, not a substitute for a personal plan.",
          },
          {
            q: "Can family members be included?",
            a: "Often yes, but conditions (marriage, children, dependants, joint vs separate filings) depend on the basis and route. The exact setup is agreed with your manager; there is no one-size-fits-all answer without your facts.",
          },
          {
            q: "What if laws or consulate rules change?",
            a: "Rules and practice evolve. If it affects your case, the team will tell you what to refresh in documents or strategy. This help page is not a substitute for ongoing case monitoring — watch your portal messages.",
          },
          {
            q: "Where do I track the immigration case itself?",
            a: "We do not wire the portal to government registries. The portal shows our service stages, document requests, and team communication — that is the operational picture of your file with us.",
          },
        ],
      },
      {
        id: "portal",
        title: "Portal and service",
        items: [
          {
            q: "How do I sign in and what if my session drops?",
            a: "Use the login page with your credentials. Sessions rely on a token in the browser: clearing cookies, another browser, or incognito may require signing in again. Keep access to the email used for registration.",
          },
          {
            q: "What is Messages for?",
            a: "It is the main secure channel with your manager: clarifications on documents, timing, and next steps. Prefer it over scattered chat apps so the history stays tied to the case.",
          },
          {
            q: "How does Documents work?",
            a: "You see requested categories and your uploads, with statuses (pending review, accepted, changes needed). Status notes explain what to fix. File formats and size limits follow portal settings; very large archives should be agreed in thread.",
          },
          {
            q: "A document was rejected or needs a fix — what should I do?",
            a: "Read the status explanation, apply the fix, and upload a new version in the same category when available. If there is no replace action or anything is unclear, write in Messages and attach a screenshot if helpful.",
          },
          {
            q: "Where is the big-picture view of my case?",
            a: "On the dashboard and the case page: stages, reminders, and links to related areas. Blocks may differ by role and permissions.",
          },
          {
            q: "Why don’t I see Clients or Documents in the menu?",
            a: "Navigation is driven by role and permissions: some areas are staff-only, others client-only. If something seems missing for your workstream, ask your manager — access may need to be expanded or may not apply to your account type.",
          },
          {
            q: "What does the Russian / English switch do?",
            a: "It stores your UI language preference in the browser for LK pages that support it (including support copy). Legal pages on the public site open in the linked locale.",
          },
          {
            q: "Is it safe to upload documents here?",
            a: "Files are sent over TLS and stored within the project’s infrastructure. Do not share your password; sign out on shared devices. Details on data handling are in the site privacy policy.",
          },
          {
            q: "How is Support different from Messages?",
            a: "This page is a knowledge base plus shortcuts (team chat via Messages, email, callback request). Case-specific questions still belong in Messages so answers stay tied to your file context.",
          },
        ],
      },
    ],
  };

  function getLocale() {
    return localStorage.getItem("userLocale") === "en" ? "en" : "ru";
  }

  function t(key) {
    var loc = I18N[getLocale()] || I18N.ru;
    return loc[key] != null ? loc[key] : key;
  }

  function siteBasePath() {
    return getLocale() === "en" ? "../en/" : "../ru/";
  }

  function setText(id, text) {
    var el = document.getElementById(id);
    if (el) {
      el.textContent = text;
    }
  }

  function applyStaticCopy() {
    document.title = t("pageTitle");
    setText("support-hero-title", t("heroTitle"));
    setText("support-hero-subtitle", t("heroSubtitle"));
    var input = document.getElementById("support-kb-search");
    if (input) {
      input.placeholder = t("searchPlaceholder");
    }
    setText("support-faq-heading", t("faqHeading"));
    setText("support-guides-title", t("guidesTitle"));
    setText("support-guides-desc", t("guidesDesc"));
    setText("support-legal-title", t("legalTitle"));
    setText("support-legal-desc", t("legalDesc"));
    setText("support-contact-heading", t("contactHeading"));
    setText("support-contact-lead", t("contactLead"));
    setText("support-chat-title", t("chatTitle"));
    setText("support-chat-hint", t("chatHint"));
    setText("support-email-title", t("emailTitle"));
    var emailLine = document.getElementById("support-email-address");
    if (emailLine) {
      emailLine.textContent = SUPPORT_EMAIL;
    }
    setText("support-callback-btn-label", t("callbackTitle"));
    setText("support-modal-title", t("callbackModalTitle"));
    setText("support-modal-lead", t("callbackModalLead"));
    var mailtoHint = document.getElementById("support-modal-mailto-hint");
    if (mailtoHint) {
      mailtoHint.textContent = String(t("callbackMailtoHint")).replace(/\{email\}/g, SUPPORT_EMAIL);
    }
    setText("support-label-name", t("labelName"));
    setText("support-label-phone", t("labelPhone"));
    setText("support-label-comment", t("labelComment"));
    var cancelBtn = document.getElementById("support-modal-cancel");
    if (cancelBtn) {
      cancelBtn.textContent = t("cancel");
    }
    var sendLabel = document.getElementById("support-modal-submit-label");
    if (sendLabel) {
      sendLabel.textContent = t("sendRequest");
    }

    var guides = document.getElementById("support-link-guides");
    var legal = document.getElementById("support-link-legal");
    if (guides) {
      guides.href = siteBasePath() + "process.html";
    }
    if (legal) {
      legal.href = siteBasePath() + "privacy-policy.html";
    }
  }

  function renderFaq() {
    var mount = document.getElementById("support-faq-mount");
    if (!mount) {
      return;
    }
    var categories = FAQ[getLocale()] || FAQ.ru;
    var html = categories
      .map(function (cat) {
        var itemsHtml = cat.items
          .map(function (item, idx) {
            var safeQ = escapeHtml(item.q);
            var safeA = escapeHtml(item.a);
            return (
              '<div class="support-faq-item border-b border-surface-variant/20 last:border-0 py-3" data-search-text="' +
              attrEscape((item.q + " " + item.a).toLowerCase()) +
              '">' +
              '<button type="button" class="support-faq-q w-full flex justify-between items-start gap-3 text-left font-body text-on-surface hover:text-primary transition-colors">' +
              '<span class="font-medium">' +
              safeQ +
              "</span>" +
              '<span class="material-symbols-outlined text-outline shrink-0 support-faq-chevron transition-transform">expand_more</span>' +
              "</button>" +
              '<div class="support-faq-a hidden mt-2 pl-0 text-sm text-on-surface-variant leading-relaxed">' +
              safeA +
              "</div>" +
              "</div>"
            );
          })
          .join("");
        return (
          '<div class="support-faq-category mb-4 last:mb-0" data-category="' +
          escapeHtml(cat.id) +
          '">' +
          '<button type="button" class="support-cat-toggle w-full flex justify-between items-center text-left pb-2 border-b border-surface-variant/30 hover:border-outline-variant/50 transition-colors">' +
          '<span class="font-headline font-medium text-lg text-on-surface group-hover:text-primary transition-colors">' +
          escapeHtml(cat.title) +
          "</span>" +
          '<span class="material-symbols-outlined text-outline support-cat-chevron transition-transform">expand_more</span>' +
          "</button>" +
          '<div class="support-cat-body hidden pt-2">' +
          itemsHtml +
          "</div>" +
          "</div>"
        );
      })
      .join("");
    mount.innerHTML = html;

    mount.querySelectorAll(".support-cat-toggle").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var block = btn.closest(".support-faq-category");
        if (!block) {
          return;
        }
        var body = block.querySelector(".support-cat-body");
        var chev = btn.querySelector(".support-cat-chevron");
        var open = body && !body.classList.contains("hidden");
        mount.querySelectorAll(".support-cat-body").forEach(function (b) {
          b.classList.add("hidden");
        });
        mount.querySelectorAll(".support-cat-chevron").forEach(function (c) {
          c.classList.remove("rotate-180");
        });
        if (!open && body) {
          body.classList.remove("hidden");
          if (chev) {
            chev.classList.add("rotate-180");
          }
        }
      });
    });

    mount.querySelectorAll(".support-faq-q").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var row = btn.closest(".support-faq-item");
        if (!row) {
          return;
        }
        var ans = row.querySelector(".support-faq-a");
        var chev = btn.querySelector(".support-faq-chevron");
        if (!ans) {
          return;
        }
        var show = ans.classList.contains("hidden");
        ans.classList.toggle("hidden", !show);
        if (chev) {
          chev.classList.toggle("rotate-180", show);
        }
      });
    });
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function attrEscape(s) {
    return String(s).replace(/"/g, "&quot;");
  }

  function filterFaq(query) {
    var q = String(query || "")
      .trim()
      .toLowerCase();
    var mount = document.getElementById("support-faq-mount");
    var empty = document.getElementById("support-faq-empty");
    if (!mount) {
      return;
    }

    if (!q) {
      mount.querySelectorAll(".support-faq-item").forEach(function (item) {
        item.classList.remove("hidden");
      });
      mount.querySelectorAll(".support-faq-category").forEach(function (cat) {
        cat.classList.remove("hidden");
        var body = cat.querySelector(".support-cat-body");
        var chev = cat.querySelector(".support-cat-chevron");
        if (body) {
          body.classList.add("hidden");
        }
        if (chev) {
          chev.classList.remove("rotate-180");
        }
      });
      if (empty) {
        empty.classList.add("hidden");
      }
      return;
    }

    var any = false;
    mount.querySelectorAll(".support-faq-category").forEach(function (cat) {
      var visibleItems = 0;
      cat.querySelectorAll(".support-faq-item").forEach(function (item) {
        var text = item.getAttribute("data-search-text") || "";
        var match = text.indexOf(q) !== -1;
        item.classList.toggle("hidden", !match);
        if (match) {
          visibleItems += 1;
        }
      });
      var catVisible = visibleItems > 0;
      cat.classList.toggle("hidden", !catVisible);
      if (catVisible) {
        any = true;
      }
      var body = cat.querySelector(".support-cat-body");
      var chev = cat.querySelector(".support-cat-chevron");
      if (catVisible && body) {
        body.classList.remove("hidden");
        if (chev) {
          chev.classList.add("rotate-180");
        }
      }
    });
    if (empty) {
      empty.classList.toggle("hidden", any);
      empty.textContent = t("noResults");
    }
  }

  function setupSearch() {
    var input = document.getElementById("support-kb-search");
    if (!input) {
      return;
    }
    input.addEventListener("input", function () {
      filterFaq(input.value);
    });
  }

  function readProfileName() {
    try {
      var raw = localStorage.getItem("currentUserProfile");
      if (!raw) {
        return "";
      }
      var p = JSON.parse(raw);
      if (p.name && String(p.name).trim()) {
        return String(p.name).trim();
      }
      if (p.email) {
        return String(p.email).split("@")[0];
      }
    } catch (e) {}
    return "";
  }

  function resetSubmitAnimation() {
    if (typeof anime === "undefined") {
      return;
    }
    var btn = document.getElementById("support-modal-submit");
    if (!btn) {
      return;
    }
    anime.remove(btn);
    var text = btn.querySelector(".support-submit-text");
    var bar = btn.querySelector(".support-submit-progress");
    var svg = btn.querySelector(".support-submit-svg");
    var path = btn.querySelector(".support-submit-check");
    ["height", "width", "minHeight", "borderRadius", "backgroundColor", "border"].forEach(function (p) {
      btn.style.removeProperty(p);
    });
    btn.classList.remove("support-submit-busy");
    btn.setAttribute("aria-busy", "false");
    if (text) {
      anime.remove(text);
      text.style.opacity = "";
    }
    if (bar) {
      anime.remove(bar);
      ["width", "height", "borderRadius", "backgroundColor"].forEach(function (p) {
        bar.style.removeProperty(p);
      });
    }
    if (svg) {
      anime.remove(svg);
      svg.style.opacity = "";
    }
    if (path) {
      anime.remove(path);
      path.style.strokeDasharray = "";
      path.style.strokeDashoffset = "";
      path.removeAttribute("stroke-dashoffset");
    }
  }

  function playSubmitAnimation(btn, onComplete) {
    var text = btn.querySelector(".support-submit-text");
    var bar = btn.querySelector(".support-submit-progress");
    var svg = btn.querySelector(".support-submit-svg");
    var path = btn.querySelector(".support-submit-check");
    var w = Math.max(btn.offsetWidth || btn.getBoundingClientRect().width, 100);
    var pathLen = 0;
    if (path && typeof path.getTotalLength === "function") {
      pathLen = path.getTotalLength();
      path.style.strokeDasharray = pathLen + " " + pathLen;
      path.setAttribute("stroke-dashoffset", String(pathLen));
    }
    var circle = 48;
    var barH = 8;

    var tl = anime.timeline({
      autoplay: true,
      complete: function () {
        window.setTimeout(function () {
          onComplete();
        }, 380);
      },
    });

    tl.add({
      targets: text,
      opacity: 0,
      duration: 200,
      easing: "easeOutQuad",
    })
      .add({
        targets: btn,
        height: barH,
        borderRadius: 9999,
        duration: 700,
        easing: "easeInOutQuad",
      })
      .add({
        targets: bar,
        width: w,
        duration: 1400,
        easing: "linear",
      })
      .add({
        targets: bar,
        width: circle,
        height: circle,
        borderRadius: circle / 2,
        backgroundColor: "#dde1ff",
        duration: 650,
        delay: 220,
        easing: "easeInOutQuad",
      });

    if (path && pathLen > 0) {
      tl.add(
        {
          targets: svg,
          opacity: 1,
          duration: 120,
          easing: "linear",
        },
        "-=420"
      );
      tl.add({
        targets: path,
        strokeDashoffset: [pathLen, 0],
        duration: 300,
        easing: "easeInOutSine",
      });
    } else if (svg) {
      tl.add(
        {
          targets: svg,
          opacity: 1,
          duration: 200,
        },
        "-=200"
      );
    }
  }

  function openModal() {
    var modal = document.getElementById("support-callback-modal");
    if (!modal) {
      return;
    }
    resetSubmitAnimation();
    modal.classList.remove("hidden");
    modal.setAttribute("aria-hidden", "false");
    var nameInput = document.getElementById("support-callback-name");
    if (nameInput && !nameInput.value) {
      nameInput.value = readProfileName();
    }
    var phoneInput = document.getElementById("support-callback-phone");
    if (phoneInput) {
      phoneInput.focus();
    }
  }

  function closeModal() {
    var modal = document.getElementById("support-callback-modal");
    if (!modal) {
      return;
    }
    modal.classList.add("hidden");
    modal.setAttribute("aria-hidden", "true");
  }

  function setupContact() {
    var chatBtn = document.getElementById("support-btn-chat");
    if (chatBtn) {
      chatBtn.addEventListener("click", function () {
        window.location.href = "./messages.html";
      });
    }
    var emailBtn = document.getElementById("support-btn-email");
    if (emailBtn) {
      emailBtn.addEventListener("click", function () {
        var subj = getLocale() === "en" ? "Spainza portal support" : "Обращение из ЛК Spainza";
        window.location.href =
          "mailto:" + SUPPORT_EMAIL + "?subject=" + encodeURIComponent(subj);
      });
    }
    var cbBtn = document.getElementById("support-btn-callback");
    if (cbBtn) {
      cbBtn.addEventListener("click", openModal);
    }
    var cancel = document.getElementById("support-modal-cancel");
    if (cancel) {
      cancel.addEventListener("click", closeModal);
    }
    var modal = document.getElementById("support-callback-modal");
    if (modal) {
      modal.addEventListener("click", function (e) {
        if (e.target === modal) {
          closeModal();
        }
      });
    }
    document.addEventListener("keydown", function (e) {
      if (e.key !== "Escape") {
        return;
      }
      var m = document.getElementById("support-callback-modal");
      if (m && !m.classList.contains("hidden")) {
        closeModal();
      }
    });
    var form = document.getElementById("support-callback-form");
    if (form) {
      form.addEventListener("submit", function (e) {
        e.preventDefault();
        var phone = (document.getElementById("support-callback-phone") || {}).value || "";
        var name = (document.getElementById("support-callback-name") || {}).value || "";
        var comment = (document.getElementById("support-callback-comment") || {}).value || "";
        if (!String(phone).trim()) {
          alert(getLocale() === "en" ? "Please enter a phone number." : "Укажите телефон.");
          return;
        }
        var submitBtn = document.getElementById("support-modal-submit");
        if (submitBtn && submitBtn.classList.contains("support-submit-busy")) {
          return;
        }
        var cancelBtn = document.getElementById("support-modal-cancel");

        function runMailtoAndClose() {
          var subj = getLocale() === "en" ? "Callback request (portal)" : "Заказ обратного звонка (ЛК)";
          var body =
            (getLocale() === "en" ? "Name: " : "Имя: ") +
            name +
            "\n" +
            (getLocale() === "en" ? "Phone: " : "Телефон: ") +
            phone +
            "\n" +
            (getLocale() === "en" ? "Comment: " : "Комментарий: ") +
            comment;
          window.location.href =
            "mailto:" +
            SUPPORT_EMAIL +
            "?subject=" +
            encodeURIComponent(subj) +
            "&body=" +
            encodeURIComponent(body);
          resetSubmitAnimation();
          if (cancelBtn) {
            cancelBtn.disabled = false;
          }
          closeModal();
        }

        if (!submitBtn || typeof anime === "undefined") {
          runMailtoAndClose();
          return;
        }

        if (cancelBtn) {
          cancelBtn.disabled = true;
        }
        submitBtn.classList.add("support-submit-busy");
        submitBtn.setAttribute("aria-busy", "true");

        playSubmitAnimation(submitBtn, runMailtoAndClose);
      });
    }
  }

  function bindLocaleRefresh() {
    document.querySelectorAll("[data-locale-btn]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        window.setTimeout(function () {
          applyStaticCopy();
          renderFaq();
          filterFaq((document.getElementById("support-kb-search") || {}).value || "");
        }, 0);
      });
    });
  }

  function init() {
    applyStaticCopy();
    renderFaq();
    setupSearch();
    setupContact();
    bindLocaleRefresh();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
