# Site Information and Legal Pages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish accurate 2026 Digital Nomad information, correctly scope UGE, and align the RU/EN legal and cookie copy with the application’s current behavior.

**Architecture:** Keep the existing static HTML structure and change only user-visible copy. Add one focused Python `unittest` file that treats the paired RU/EN pages and cookie banner as public-content contracts.

**Tech Stack:** Static HTML, vanilla JavaScript, Python `unittest`.

## Global Constraints

- Do not modify any `gold.html` page.
- Keep Russian and English public copy semantically synchronized.
- Do not invent a legal name, NIF/CIF, postal address, registration record, or other missing operator identity.
- Use the effective date 20 July 2026 / 20 июля 2026 года.
- Preserve unrelated user changes and existing page markup.

---

### Task 1: Add public-content regression tests

**Files:**
- Create: `tests/test_public_information_accuracy.py`
- Test: `tests/test_public_information_accuracy.py`

**Interfaces:**
- Consumes: UTF-8 contents of the RU/EN public pages and `frontend/js/cookie-consent.js`.
- Produces: content-contract tests for the requested facts and policies.

- [ ] **Step 1: Write failing tests**

Create a `unittest.TestCase` that asserts both locales contain the 2026 annual and monthly Digital Nomad amounts, the SMI percentages, the recognized education categories, the UGE/Extranjería/consulate routing, the effective dates, `google_oauth_state`, `spainza.cookieConsent.v1`, seven-day and ten-minute retention descriptions, and banner text stating that only necessary cookies are currently used. Assert the old amounts and optional-analytics banner copy are absent.

- [ ] **Step 2: Run the test and verify RED**

Run: `python -m unittest tests.test_public_information_accuracy -v`

Expected: assertion failures for the old Digital Nomad amounts, universal UGE wording, missing dates/cookie names, and optional analytics banner text.

- [ ] **Step 3: Keep the failing test as the acceptance contract**

Do not weaken assertions during implementation; update production copy to satisfy them.

### Task 2: Correct Digital Nomad and UGE copy

**Files:**
- Modify: `frontend/ru/nomad.html`
- Modify: `frontend/en/nomad.html`
- Modify: `frontend/ru/process.html`
- Modify: `frontend/en/process.html`
- Modify: `frontend/ru/services.html`
- Modify: `frontend/en/services.html`
- Test: `tests/test_public_information_accuracy.py`

**Interfaces:**
- Consumes: 2026 SMI thresholds and Law 14/2013 routing requirements from the approved design.
- Produces: accurate paired public copy.

- [ ] **Step 1: Update Digital Nomad thresholds**

State €34,188/year (about €2,849/month), €12,820.50/year (about €1,068.38/month), and €4,273.50/year (about €356.13/month), label them 200%/75%/25% of SMI, and say they change when SMI changes.

- [ ] **Step 2: Update qualification copy**

Replace “prestigious university” with a recognized university, vocational-training institution, or business school, or at least three years of documented professional experience.

- [ ] **Step 3: Scope UGE correctly**

On general pages, state that the competent authority depends on the route: UGE for Law 14/2013 procedures and Extranjería or a Spanish consulate for other procedures. Retain UGE references inside the Digital Nomad service card.

- [ ] **Step 4: Run the focused tests**

Run: `python -m unittest tests.test_public_information_accuracy -v`

Expected: Digital Nomad and routing assertions pass; legal/cookie assertions remain failing until Task 3.

### Task 3: Align legal pages and cookie notice

**Files:**
- Modify: `frontend/ru/terms-of-service.html`
- Modify: `frontend/en/terms-of-service.html`
- Modify: `frontend/ru/privacy-policy.html`
- Modify: `frontend/en/privacy-policy.html`
- Modify: `frontend/ru/cookie-policy.html`
- Modify: `frontend/en/cookie-policy.html`
- Modify: `frontend/js/cookie-consent.js`
- Test: `tests/test_public_information_accuracy.py`

**Interfaces:**
- Consumes: cookie behavior from `backend/routes/auth.py`, `shared/layout.js`, `frontend/js/lk.js`, `frontend/js/login.js`, and `frontend/js/cookie-consent.js`.
- Produces: publication-ready legal dates and implementation-accurate storage disclosures.

- [ ] **Step 1: Add visible dates**

Add “Редакция и дата вступления в силу: 20 июля 2026 года” and “Version and effective date: 20 July 2026” near the introduction of all six legal pages.

- [ ] **Step 2: Correct the cookie inventory**

Document `access_token` (HttpOnly, SameSite=Lax, Secure over HTTPS, up to seven days), `google_oauth_state` (HttpOnly, SameSite=None over HTTPS and Lax locally, Secure over HTTPS, up to ten minutes and removed after OAuth), `currentUserProfile`, `currentUserProfileSavedAt`, `spainza.language`, `userLocale`, `spainza.cookieConsent.v1`, legacy `token`, and session `manager_invite_token`.

- [ ] **Step 3: Correct retention and third-party wording**

Distinguish cookie expiry, logout/deletion, sessionStorage tab lifetime, and localStorage persistence. Keep the absence of third-party analytics/advertising statement and disclose Google Fonts, UI CDNs, and Telegram technical-data processing without claiming consent-gated loading.

- [ ] **Step 4: Correct the consent banner**

Remove “optional analytics” and “accept all” implications. State that Spainza currently uses necessary technologies for login, security, preferences, and remembering the notice; provide a single acknowledgement action while retaining the policy link.

- [ ] **Step 5: Run focused tests to GREEN**

Run: `python -m unittest tests.test_public_information_accuracy -v`

Expected: all tests pass.

### Task 4: Full verification

**Files:**
- Verify: all files changed in Tasks 1–3.

**Interfaces:**
- Consumes: completed content changes.
- Produces: verification evidence and a clean scoped diff.

- [ ] **Step 1: Run the project test suite**

Run: `npm.cmd test`

Expected: exit code 0 with no failed tests.

- [ ] **Step 2: Check HTML text and diff hygiene**

Run: `git diff --check` and inspect `git diff -- frontend tests`.

Expected: no whitespace errors, no unrelated changes, and no modification to any `gold.html` file.

- [ ] **Step 3: Verify excluded pages**

Run: `git diff --name-only | rg "gold\.html"`

Expected: no output.
