import os
import re
from datetime import timedelta

from core.utils import Config

MAX_EMAIL_SUBJECT_LEN = 1024
MAX_EMAIL_LEN = 64

# В YandexTracker max 50 MB, в Exchange 20 MB:
MAX_ATTACHMENT_SIZE = 20 * 1024 * 1024
MAX_TOTAL_ATTACHMENTS_SIZE = MAX_ATTACHMENT_SIZE

# Кол-во дней через которое для не актуальных инцидентов будут удалены
# вложения:
MAX_EMAILS_ATTACHMENT_DAYS = 365

EMAILS_FILES_2_DEL_BATCH_SIZE = 500

MAX_EMAILS_INFO_CACHE_SEC = 3600

MAX_EMAIL_STATUS_LEN = 32

EMAILS_PER_PAGE = 25
PAGE_SIZE_EMAILS_CHOICES = [15, EMAILS_PER_PAGE, 50, 100]

ALLOWED_MIME_PREFIXES = {
    # Документы
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument',  # docx, xlsx, pptx
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',  # noqa: E501
    'application/vnd.ms-excel',
    'application/vnd.ms-powerpoint',
    'application/vnd.visio',  # .vsdx, .vsd
    'application/vnd.oasis.opendocument.text',  # .odt
    'application/vnd.oasis.opendocument.spreadsheet',  # .ods
    'application/vnd.oasis.opendocument.presentation',  # .odp
    'application/epub+zip',  # .epub
    'application/json',  # .json

    # Веб-страницы
    'text/html',  # .html, .htm

    # Google Workspace
    'application/vnd.google-apps',  # sheets, docs, slides, etc.

    # Текст
    'text/plain',
    'text/rtf',

    # Картинки
    'image/',  # jpg, png, gif, bmp, webp, svg

    # Видео
    'video/',  # mp4, mov, avi, mkv, webm

    # Аудио
    'audio/mpeg',  # .mp3
    'audio/wav',   # .wav
    'audio/ogg',   # .ogg

    # Архивы
    'application/zip',             # .zip
    'application/x-zip-compressed',  # .zip (браузер)
    'application/x-7z-compressed',   # .7z
    'application/x-rar-compressed',  # .rar
    'application/x-tar',           # .tar
    'application/gzip',            # .gz
    'application/x-gzip',
    'application/x-bzip2',         # .bz2
    'application/x-xz',

    # Специфические офисные форматы
    'application/vnd.ms-project',  # .mpp
    'application/vnd.ms-access',   # .mdb

    # Электронные письма
    'message/rfc822',  # стандартный MIME для .eml/.msg

    # Универсальный бинарный тип для файлов вроде .sor
    'application/octet-stream',
}

ALLOWED_EXTENSIONS = {
    # Документы
    '.pdf',  # PDF
    '.doc', '.docx',  # Word
    '.xls', '.xlsx',  # Excel
    '.ppt', '.pptx',  # PowerPoint
    '.vsd', '.vsdx',  # Visio
    '.odt',  # OpenDocument Text
    '.ods',  # OpenDocument Spreadsheet
    '.odp',  # OpenDocument Presentation
    '.epub',  # eBook
    '.json',  # JSON
    '.sor',  # GIS
    '.html', '.htm',  # HTML

    # Google Workspace (расширения, которые часто встречаются при экспорте)
    '.gsheet', '.gdoc', '.gslides', '.gdraw', '.gform',

    # Текстовые файлы
    '.txt', '.rtf',

    # Архивы
    '.zip', '.7z', '.rar', '.tar', '.gz', '.bz2',

    # Специфические офисные форматы
    '.mpp',  # MS Project
    '.mdb',  # MS Access

    # Аудио и видео (если нужно сохранять)
    '.mp3', '.wav', '.ogg',  # Аудио
    '.mp4', '.mov', '.avi', '.mkv', '.webm',  # Видео

    # Картинки
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg', '.jfif',

    # Электронные письма
    '.eml', '.msg',
}

EMAIL_RE = re.compile(
    r'^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$',
    re.IGNORECASE,
)

MIN_STACK_EMAILS_TTL = 120  # Не менять, сначала просмотеть задачу в Cellery

MAX_STACK_EMAILS_TTL = 3600

DISPATCHER_SIGNATURE = (
    'С уважением,\n'
    'Диспетчерская служба «Новые Башни»\n'
    'Тел.: +7 (911) 371-61-48'
)

EMAIL_SUBJECT_NOT_FOR_YT_CONTROLLED = 'V8ieFf'

EMAILS_BATCH_SIZE = 1000

CLEANUP_EMAILS_WITHOUT_INCIDENT_TTL = timedelta(days=90)

EMAIL_PARSER_CONFIG = {
    'PARSING_EMAIL_LOGIN': os.getenv('PARSING_EMAIL_LOGIN'),
    'PARSING_EMAIL_PSWD': os.getenv('PARSING_EMAIL_PSWD'),
    'PARSING_EMAIL_SERVER': os.getenv('PARSING_EMAIL_SERVER'),
    'PARSING_EMAIL_PORT': os.getenv('PARSING_EMAIL_PORT', 993),
    'PARSING_EMAIL_SENT_FOLDER_NAME': os.getenv('PARSING_EMAIL_SENT_FOLDER_NAME'),  # noqa: E501
}

Config.validate_env_variables(EMAIL_PARSER_CONFIG)

EMAILD_UID_CACHE_PREFIX_KEY = 'imap_uid_map__'
EMAILD_UID_CACHE_TTL = 3600 * 24 * 2
