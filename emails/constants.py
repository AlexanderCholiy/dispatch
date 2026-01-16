MAX_EMAIL_SUBJECT_LEN = 1024
MAX_EMAIL_LEN = 64

MAX_ATTACHMENT_SIZE = 48 * 1024 * 1024  # (в YandexTracker max 50 MB)

# Кол-во дней через которое для не актуальных инцидентов будут удалены
# вложения:
MAX_EMAILS_ATTACHMENT_DAYS = 180

EMAILS_FILES_2_DEL_BATCH_SIZE = 500

MAX_EMAILS_INFO_CACHE_SEC = 3600

EMAILS_PER_PAGE = 100
PAGE_SIZE_EMAILS_CHOICES = [25, 50, EMAILS_PER_PAGE]

ALLOWED_MIME_PREFIXES = {
    # Документы
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument',  # docx, xlsx, pptx
    'application/vnd.ms-excel',
    'application/vnd.ms-powerpoint',
    'application/vnd.visio',  # .vsdx, .vsd
    'application/vnd.oasis.opendocument.text',  # .odt
    'application/vnd.oasis.opendocument.spreadsheet',  # .ods
    'application/vnd.oasis.opendocument.presentation',  # .odp
    'application/epub+zip',  # .epub
    'application/json',  # .json

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
    'application/x-7z-compressed',   # .7z
    'application/x-rar-compressed',  # .rar
    'application/x-tar',           # .tar
    'application/gzip',            # .gz
    'application/x-bzip2',         # .bz2

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
