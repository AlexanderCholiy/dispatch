import email
from email import policy

from core.loggers import email_logger


def strip_attachments(raw_msg_bytes: bytes, email_msg_id: str) -> bytes:
    """
    Возвращает .eml без вложений (attachment, image/*, message/rfc822).
    При любой ошибке логирует её и возвращает оригинальные байты,
    чтобы не потерять письмо.
    """
    if not raw_msg_bytes:
        return raw_msg_bytes

    try:
        # Читаем письмо с дефолтной политикой, чтобы избежать сюрпризов с
        # кодировками
        msg = email.message_from_bytes(raw_msg_bytes, policy=policy.default)

        if not msg.is_multipart():
            # Вложений нет — возвращаем оригинал как есть
            return raw_msg_bytes

        def _is_attachment(part):
            if part.is_multipart():
                return False
            cd = part.get_content_disposition()
            ct = (part.get_content_type() or '').lower()
            return (
                cd == 'attachment'
                or ct.startswith('image/')
                or ct == 'message/rfc822'
            )

        def _prune(container):
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
                    if isinstance(inner, list) and not inner:
                        continue  # пропускаем пустые контейнеры
                kept.append(part)

            # Если это корневое письмо и мы удалили всё (такого быть не должно,
            # но на всякий случай), оставляем хотя бы один text/plain
            if not kept and container is msg:
                return

            container.set_payload(kept)

        _prune(msg)

        # Сохраняем с политикой SMTP, чтобы заголовки и тело не ломались
        return msg.as_bytes(policy=policy.SMTP)

    except Exception:
        email_logger.exception(
            f'Ошибка при удалении вложений из письма "{email_msg_id}" — '
            'сохраняем оригинал'
        )
        return raw_msg_bytes
