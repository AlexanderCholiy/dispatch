import os
import re
from pathlib import Path

from django.conf import settings

from core.constants import DATA_DIR

MSYS_MODEMS_PER_PAGE = 100
MSYS_STATUSES_PER_PAGE = 100
MSYS_POLES_PER_PAGE = 100

NORMAL_POLES_CACHE_TIMEOUT = 900  # 15 мин

UNDEFINED_POLE_CASE = 'undefined'

MONITORING_EQUIPMENT_CACHE_TTL = 900  # БД мониторинга медленная
MONITORING_EQUIPMENT_CACHE_KEY = 'monitoring_equipment'
CHUNKED_MONITORING_QS = 1000

MAX_MODEM_IP_LEN = 40

MAX_NEW_RHU_NOTIFICATION = 1000

TOP_N_NEAREST_POLES = 3

GPS_NUMBER_DECIMAL_PLACES = 5

COORDINATE_PATTERN = re.compile(r'^-?\d+(\.\d+)?$')

FACTORY_EXCLUSION_RADIUS = 750  # метров
MAX_MIN_LEN_BETWEEN_MODEM_AND_POLE = 1500  # метров
TRETHHOLD_RATIO_BETWEEN_MODEM_AND_POLE = 1.5  # 50% от дистанции до главной

MONITORING_CHUNK_SIZE = 1000

NOTIFY_NEW_POLE_EMAILS = [
    email.strip()
    for email in os.getenv('NOTIFY_NEW_POLE_EMAILS').split(',')
    if email.strip()
]

NOTIFY_NEW_POLE_LOCK_KEY = 'lock_notify_pole_up'
NOTIFY_NEW_POLE_LOCK_TIMEOUT = 3600

# Объекты Paas:
MQTT_PAAS_HOST = os.getenv('MQTT_PAAS_HOST')
MQTT_PAAS_PORT = int(os.getenv('MQTT_PAAS_PORT', 1883))
MQTT_PAAS_TOPIC = os.getenv('MQTT_PAAS_TOPIC')
MQTT_PAAS_USER = os.getenv('MQTT_PAAS_USER')
MQTT_PAAS_PSWD = os.getenv('MQTT_PAAS_PSWD')

# SMS контроллер с РВР:
SMS_RVR_LOCK_KEY = 'lock_sms_rvr'
SMS_RVR_LOCK_TIMEOUT = 3600
SMS_RVR_CONTROLLER_HOST = os.getenv('SMS_RVR_CONTROLLER_HOST')
SMS_RVR_CONTROLLER_PSWD = os.getenv('SMS_RVR_CONTROLLER_PSWD')
SMS_RVR_DIR = Path(DATA_DIR) / 'monitoring' / 'rvr_sms'

SMS_RVR_TMP_FILE = Path(DATA_DIR) / 'tmp' / 'monitoring_rvr_sms.tmp'
SMS_RVR_CSV_FILE = (
    Path(settings.MEDIA_ROOT) / 'monitoring_cache' / 'monitoring_rvr_sms.csv'
)
