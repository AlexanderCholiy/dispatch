import os
from pathlib import Path

from core.constants import TMP_DATA_DIR

BASE_URL = 'https://max.ru'

MAX_TOKEN = os.getenv('MAX_TOKEN')

MAX_CERT_DIR = Path(TMP_DATA_DIR) / 'max' / 'cert'
