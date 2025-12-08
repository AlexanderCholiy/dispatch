# core/services/email.py

import os
import warnings
from email.mime.image import MIMEImage

import html2text
from django.conf import settings
from django.contrib.staticfiles import finders
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from premailer import transform

from core.constants import EMAIL_LOGO_PATH
from users.models import PendingUser, User


class EmailService:
    """Сервис для подготовки HTML-писем."""

    CSS_PATHS = [
        'css/services/base.css',
        'css/services/includes/footer.css',
    ]

    def __init__(
        self,
        template: str,
        subject: str,
        domain: str,
        context: dict,
        extra_css: list[str] | None = None,
    ):
        self.template = template
        self.subject = subject
        self.domain = domain
        self.context = context
        self.css_paths = list(self.CSS_PATHS)

        if extra_css:
            self.css_paths.extend(extra_css)

    @property
    def base_url(self) -> str:
        return f'https://{self.domain}'

    def _load_css(self) -> str:
        """Читает все CSS-файлы и объединяет в одну строку."""
        css_content = ''

        for css_path in self.CSS_PATHS:
            file = finders.find(css_path)

            if not file:
                continue

            with open(file, 'r', encoding='utf-8') as f:
                css_content += f.read() + '\n'

        return css_content

    def _load_logo(self) -> MIMEImage | None:
        """Возвращает MIMEImage логотипа, если он существует."""
        if not os.path.exists(EMAIL_LOGO_PATH):
            return None

        with open(EMAIL_LOGO_PATH, 'rb') as f:
            data = f.read()

        logo = MIMEImage(data)
        logo.add_header('Content-ID', '<logo>')
        return logo

    def build_html_email(
        self, user: User | PendingUser
    ) -> EmailMultiAlternatives:
        """
        Генерирует EmailMultiAlternatives с inline CSS, text-версией и
        логотипом.
        """
        html_content = render_to_string(self.template, self.context)

        css = self._load_css()

        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            html_inlined = transform(
                html_content,
                css_text=css,
                base_url=self.base_url,
                remove_classes=False,
                keep_style_tags=False,
            )

        text_content = html2text.html2text(html_inlined)

        email = EmailMultiAlternatives(
            subject=self.subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email],
        )

        logo = self._load_logo()
        if logo:
            email.attach(logo)

        email.attach_alternative(html_inlined, 'text/html')

        return email
