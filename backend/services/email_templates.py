"""Branded HTML templates for account emails (noreply@spainza.com)."""

from __future__ import annotations

import html
from typing import Iterable

from flask import current_app


def _public_base_url() -> str:
    base = str(current_app.config.get("PUBLIC_BASE_URL") or "").rstrip("/")
    if base:
        return base
    server = str(current_app.config.get("SERVER_NAME") or "").rstrip("/")
    return server


def _logo_url() -> str | None:
    base = _public_base_url()
    if not base:
        return None
    return f"{base}/frontend/img/Logo.png"


def _paragraphs_html(paragraphs: Iterable[str]) -> str:
    parts: list[str] = []
    for paragraph in paragraphs:
        text = str(paragraph or "").strip()
        if not text:
            continue
        parts.append(
            f'<p style="margin:0 0 16px;font-size:15px;line-height:1.6;color:#3d4150;">'
            f"{html.escape(text)}</p>"
        )
    return "".join(parts)


def render_account_email_html(
    *,
    heading: str,
    paragraphs: Iterable[str],
    cta_label: str | None = None,
    cta_url: str | None = None,
    footer_note: str | None = None,
) -> str:
    """Render a Spainza-branded HTML email with inline styles for client compatibility."""
    logo_url = _logo_url()
    if logo_url:
        brand_block = (
            f'<img src="{html.escape(logo_url, quote=True)}" alt="Spainza" '
            'width="140" height="auto" style="display:block;border:0;max-width:140px;height:auto;" />'
        )
    else:
        brand_block = (
            '<span style="font-size:22px;font-weight:800;color:#0052ff;letter-spacing:-0.02em;">'
            "Spainza</span>"
        )

    cta_html = ""
    if cta_label and cta_url:
        safe_url = html.escape(cta_url, quote=True)
        safe_label = html.escape(cta_label)
        cta_html = f"""
          <table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:28px 0 8px;">
            <tr>
              <td align="center" bgcolor="#0052ff" style="border-radius:12px;background:linear-gradient(135deg,#0052ff 0%,#003ec7 100%);">
                <a href="{safe_url}" target="_blank" rel="noopener noreferrer"
                   style="display:inline-block;padding:14px 28px;font-size:15px;font-weight:700;color:#ffffff;text-decoration:none;border-radius:12px;">
                  {safe_label}
                </a>
              </td>
            </tr>
          </table>
          <p style="margin:16px 0 0;font-size:12px;line-height:1.5;color:#757682;word-break:break-all;">
            {html.escape("Если кнопка не работает, скопируйте ссылку:")}<br />
            <a href="{safe_url}" style="color:#0052ff;text-decoration:underline;">{safe_url}</a>
          </p>
        """

    footer = footer_note or (
        "Это автоматическое письмо от Spainza. "
        "Отвечать на него не нужно — ящик noreply@spainza.com не принимает входящие."
    )

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta http-equiv="X-UA-Compatible" content="IE=edge" />
  <title>{html.escape(heading)}</title>
</head>
<body style="margin:0;padding:0;background-color:#eef0f6;font-family:Inter,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#eef0f6;padding:32px 16px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width:560px;">
          <tr>
            <td align="left" style="padding:0 0 20px;">
              {brand_block}
            </td>
          </tr>
          <tr>
            <td style="background-color:#ffffff;border:1px solid #dfe1ea;border-radius:16px;padding:32px 28px;box-shadow:0 8px 30px rgba(117,118,130,0.08);">
              <h1 style="margin:0 0 20px;font-size:24px;line-height:1.25;font-weight:800;color:#191b25;letter-spacing:-0.02em;">
                {html.escape(heading)}
              </h1>
              {_paragraphs_html(paragraphs)}
              {cta_html}
            </td>
          </tr>
          <tr>
            <td style="padding:24px 8px 0;font-size:12px;line-height:1.6;color:#757682;text-align:center;">
              {html.escape(footer)}
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def verification_email_bodies(action_url: str) -> tuple[str, str]:
    text = (
        "Здравствуйте!\n\n"
        "Чтобы активировать аккаунт Spainza, откройте ссылку:\n"
        f"{action_url}\n\n"
        "Если вы не регистрировались, просто проигнорируйте это письмо."
    )
    html_body = render_account_email_html(
        heading="Подтвердите email",
        paragraphs=[
            "Здравствуйте!",
            "Спасибо за регистрацию в клиентском портале Spainza. "
            "Нажмите кнопку ниже, чтобы активировать аккаунт и получить доступ к личному кабинету.",
            "Если вы не регистрировались, просто проигнорируйте это письмо.",
        ],
        cta_label="Подтвердить email",
        cta_url=action_url,
    )
    return text, html_body


def password_reset_email_bodies(action_url: str) -> tuple[str, str]:
    text = (
        "Здравствуйте!\n\n"
        "Для смены пароля откройте ссылку и задайте новый пароль:\n"
        f"{action_url}\n\n"
        "Если вы не запрашивали восстановление, просто проигнорируйте это письмо."
    )
    html_body = render_account_email_html(
        heading="Восстановление пароля",
        paragraphs=[
            "Здравствуйте!",
            "Мы получили запрос на смену пароля для вашего аккаунта Spainza. "
            "Нажмите кнопку ниже, чтобы задать новый пароль.",
            "Ссылка действует ограниченное время. "
            "Если вы не запрашивали восстановление, просто проигнорируйте это письмо.",
        ],
        cta_label="Сменить пароль",
        cta_url=action_url,
    )
    return text, html_body


def email_change_confirmation_bodies(action_url: str) -> tuple[str, str]:
    text = (
        "Здравствуйте!\n\n"
        "Вы запросили смену email в аккаунте Spainza. "
        "Чтобы подтвердить новый адрес, откройте ссылку:\n"
        f"{action_url}\n\n"
        "Пока ссылка не подтверждена, в аккаунте остаётся прежний email.\n"
        "Если вы не запрашивали смену, просто проигнорируйте это письмо."
    )
    html_body = render_account_email_html(
        heading="Подтвердите новый email",
        paragraphs=[
            "Здравствуйте!",
            "Вы запросили смену адреса электронной почты в аккаунте Spainza. "
            "Подтвердите новый email, нажав кнопку ниже.",
            "Пока ссылка не подтверждена, в аккаунте остаётся прежний адрес. "
            "Если вы не запрашивали смену, просто проигнорируйте это письмо.",
        ],
        cta_label="Подтвердить новый email",
        cta_url=action_url,
    )
    return text, html_body


def email_changed_notification_bodies() -> tuple[str, str]:
    text = (
        "Здравствуйте!\n\n"
        "Ваш адрес электронной почты был изменен. "
        "Если это были не вы — срочно свяжитесь с поддержкой."
    )
    html_body = render_account_email_html(
        heading="Email аккаунта изменён",
        paragraphs=[
            "Здравствуйте!",
            "Адрес электронной почты, привязанный к вашему аккаунту Spainza, был изменён.",
            "Если это были не вы, срочно свяжитесь с поддержкой через личный кабинет или по адресу info@spainza.com.",
        ],
    )
    return text, html_body
