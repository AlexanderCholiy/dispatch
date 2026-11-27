import re


def _extract_field(body: str, field_name: str) -> str:
    """
    Извлекает значение поля вида 'Field: value' из plain text письма Zabbix.
    """
    pattern = rf"^\s*{re.escape(field_name)}\s*:\s*(.+?)\s*$"
    match = re.search(pattern, body, re.IGNORECASE | re.MULTILINE)
    return match.group(1).strip() if match else "не указано"


def build_zabbix_comment(subject: str, body: str) -> str:
    """
    Анализирует тему и тело письма из Zabbix и возвращает текст комментария.
    """
    subj = (subject or "").strip()
    text = body or ""

    # Контакты ответственных (замените на актуальные)
    CONTACTS = {
        "problem": "support-l2@example.com",
        "recovery": "monitoring-log@example.com",
        "update": "support-l2@example.com",
        "discovery": "netops@example.com",
        "autoreg": "sysadmin@example.com",
        "fallback": "helpdesk@example.com",
    }

    # 1. Проблема (Problem: {EVENT.NAME})
    if subj.startswith("Problem:"):
        problem_name = subj.removeprefix("Problem:").strip()
        host = _extract_field(text, "Host")
        severity = _extract_field(text, "Severity")
        opdata = _extract_field(text, "Operational data")

        return (
            f"🚨 Zabbix: Проблема {problem_name}\n\n"
            f"• Хост: {host}\n"
            f"• Важность: {severity}\n"
            f"• Данные: {opdata}\n"
            f"\n✉️ Куда обращаться: {CONTACTS['problem']}"
        )

    # 2. Восстановление (Resolved in {EVENT.DURATION}: {EVENT.NAME})
    elif subj.startswith("Resolved in "):
        # Разделяем "Resolved in 5m: High CPU" по первому двоеточию
        header_part, _, problem_name = subj.partition(":")
        duration = header_part.removeprefix("Resolved in ").strip()
        host = _extract_field(text, "Host")

        return (
            f"✅ Zabbix: Восстановлено {problem_name.strip()}\n\n"
            f"• Хост: {host}\n"
            f"• Длительность сбоя: {duration}\n"
            f"\n✉️ Куда обращаться (для уточнений): {CONTACTS['recovery']}"
        )

    # 3. Обновление проблемы (Updated problem in {EVENT.AGE}: {EVENT.NAME})
    elif subj.startswith("Updated problem in "):
        header_part, _, problem_name = subj.partition(":")
        age = header_part.removeprefix("Updated problem in ").strip()
        status = _extract_field(text, "Current problem status")
        ack = _extract_field(text, "Acknowledged")

        return (
            f"🔄 Zabbix: Обновление {problem_name.strip()}\n\n"
            f"• Возраст проблемы: {age}\n"
            f"• Текущий статус: {status} (Подтверждено: {ack})\n"
            f"\n✉️ Куда обращаться: {CONTACTS['update']}"
        )

    # 4. Обнаружение
    # (Discovery: {DISCOVERY.DEVICE.STATUS} {DISCOVERY.DEVICE.IPADDRESS})
    elif subj.startswith("Discovery:"):
        details = subj.removeprefix("Discovery:").strip()
        rule = _extract_field(text, "Discovery rule")
        service = _extract_field(text, "Device service name")

        return (
            f"🔍 Zabbix: Обнаружение в сети {details}\n\n"
            f"• Правило: {rule}\n"
            f"• Сервис: {service}\n"
            f"\n✉️ Куда обращаться: {CONTACTS['discovery']}"
        )

    # 5. Авторегистрация (Autoregistration: {HOST.HOST})
    elif subj.startswith("Autoregistration:"):
        host_name = subj.removeprefix("Autoregistration:").strip()
        host_ip = _extract_field(text, "Host IP")

        return (
            f"🆕 Zabbix: Авторегистрация {host_name}\n\n"
            f"• IP-адрес: {host_ip}\n"
            f"\n✉️ Куда обращаться: {CONTACTS['autoreg']}"
        )

    # 6. Fallback-случай (нестандартное письмо)
    else:
        return (
            f"⚠️ Zabbix: Нераспознанное уведомление\n\n"
            f"• Тема письма: {subj or 'без темы'}\n"
            f"• Требуется ручной разбор обращения.\n"
            f"\n✉️ Дежурный контакт: {CONTACTS['fallback']}"
        )
