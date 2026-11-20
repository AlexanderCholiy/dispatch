import email
from email import policy
from email.message import Message

from core.loggers import email_logger


def _has_text_part(container: Message) -> bool:
    """Проверяет, есть ли в письме (рекурсивно) хотя бы одна text/* часть."""
    if not container.is_multipart():
        return (container.get_content_type() or '').startswith('text/')
    return any(_has_text_part(part) for part in container.get_payload())


def strip_attachments(raw_msg_bytes: bytes, email_msg_id: str) -> bytes:
    """
    Возвращает .eml без файловых вложений.

    Удаляются:
      * части с Content-Disposition: attachment (любой тип, включая картинки,
        прикреплённые как файл);
      * части message/rfc822 (вложенные письма).

    Сохраняются:
      * inline-картинки и картинки без Content-Disposition (подписи, логотипы,
        иллюстрации в теле письма) — чтобы не ломать HTML-вёрстку и
        cid:-ссылки;
      * все текстовые части (text/plain, text/html).

    Если после удаления в письме не остаётся ни одной text/* части,
    возвращается оригинал (чтобы не получить письмо без тела).

    При любой ошибке логирует её и возвращает оригинальные байты,
    чтобы не потерять письмо.
    """
    if not raw_msg_bytes:
        return raw_msg_bytes

    try:
        # policy.default — чтобы корректно разбирались encoded-words и MIME
        msg = email.message_from_bytes(raw_msg_bytes, policy=policy.default)

        if not msg.is_multipart():
            # Вложений нет — возвращаем оригинал как есть
            return raw_msg_bytes

        def _is_attachment(part) -> bool:
            if part.is_multipart():
                return False

            cd = (part.get_content_disposition() or '').lower()
            ct = (part.get_content_type() or '').lower()

            # Вложенное письмо — всегда файл
            if ct == 'message/rfc822':
                return True

            # Явно прикреплённый файл — удаляем (в т.ч. картинку-файл)
            if cd == 'attachment':
                return True

            # Картинки без attachment (inline / без disposition) — часть тела
            if ct.startswith('image/'):
                return False

            return False

        def _prune(container) -> None:
            payload = container.get_payload()
            if not isinstance(payload, list):
                return

            kept = []
            for part in payload:
                if _is_attachment(part):
                    continue
                if part.is_multipart():
                    _prune(part)
                    inner = part.get_payload()
                    # Пропускаем контейнеры, которые опустели после чистки
                    if isinstance(inner, list) and not inner:
                        continue
                kept.append(part)

            container.set_payload(kept)

        _prune(msg)

        # Защита от письма без тела: если все текстовые части удалились —
        # отдаём оригинал
        if not _has_text_part(msg):
            email_logger.debug(
                f'После удаления вложений в письме "{email_msg_id}" не '
                'осталось текстовых частей — сохраняем оригинал'
            )
            return raw_msg_bytes

        # policy.SMTP + refold_source='none' — чтобы не падать на
        # HeaderWriteError: folded header contains newline
        return msg.as_bytes(policy=policy.SMTP.clone(refold_source='none'))

    except Exception:
        email_logger.exception(
            f'Ошибка при удалении вложений из письма "{email_msg_id}" — '
            'сохраняем оригинал'
        )
        return raw_msg_bytes
