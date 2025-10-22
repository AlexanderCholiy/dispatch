import os

from core.constants import DATA_DIR

MAX_POLE_LEN = 32
MAX_PHONE_LEN = 11

POLES_PER_PAGE = 32
BASE_STATIONS_PER_PAGE = 32
AVR_CONTRACTORS_PER_PAGE = 32
BASE_STATION_OPERATORS_PER_PAGE = 32
REGIONS_PER_PAGE = 32
CONTRACTOR_EMAILS_PER_PAGE = 32

UNDEFINED_CASE = 'undefined'
UNDEFINED_ID = 0
UNDEFINED_EMAILS = [
    eml.strip()
    for eml in os.getenv('DEFAULT_CONTRACTOR_EMAILS', '').split(',')
    if eml.strip()
]

TS_DATA_DIR = os.path.join(DATA_DIR, 'ts')
POLES_FILE = os.path.join(TS_DATA_DIR, 'poles.json')
BASE_STATIONS_FILE = os.path.join(TS_DATA_DIR, 'base_stations.json')
AVR_FILE = os.path.join(TS_DATA_DIR, 'avr.json')

TS_POLES_TL_URL = os.getenv('TS_POLES_TL_URL')
TS_AVR_REPORT_URL = os.getenv('TS_AVR_REPORT_URL')
TS_BS_REPORT_URL = os.getenv('TS_BS_REPORT_URL')

COLUMNS_TO_KEEP_POLES_TL: list[str] = [
    'SiteId',
    'Шифр',
    'Имя БС',
    'Статус опоры',
    'Широта',
    'Долгота',
    'Высота опоры',
    'Регион',
    'Адрес',
    'Инфраструктурная компания',
    'Якорный оператор',
    'RegionRu',
]
COLUMNS_TO_KEEP_AVR_REPORT: list[str] = [
    'Подрядчик',
    'Исключен из договора',
    'Шифр опоры',
    'Контактные данные подрядчика Email',
    'Контактные данные подрядчика Телефон',
]
COLUMNS_TO_KEEP_BS_OPERATORS_REPORT: list[str] = [
    'Шифр опоры',
    'Имя БС/Оборудование',
    'Оператор',
    'Группа операторов',
]
