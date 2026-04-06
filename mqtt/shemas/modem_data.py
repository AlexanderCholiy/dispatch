import base64
from datetime import date, datetime, time
from typing import Any, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from mqtt.services.parse_aops import ParseAops
from mqtt.services.parse_gps_coordinate import parse_gps_coordinate
from mqtt.shemas.aops import AopsData


class GpsRawData(BaseModel):
    """Координаты из MongoDB."""

    lat: Optional[str] = Field(None, description='Широта (N/S)')
    longt: Optional[str] = Field(None, description='Долгота (E/W)')


class GpsData(BaseModel):
    """Координаты в десятичном формате."""

    lat: float = Field(..., description='Широта (Decimal Degrees)')
    lon: float = Field(..., description='Долгота (Decimal Degrees)')


class ModemData(BaseModel):
    """Данные модема для валидации и нормализации информации из MongoDB."""

    model_config = ConfigDict(extra='ignore', populate_by_name=True)

    # Основная информация об устройстве:
    macaddress: str = Field(..., description='MAC-адрес контроллера')
    sysversion: Optional[str] = Field(None, description='Версия контроллера')
    appversion: Optional[str] = Field(
        None, description='Версия прошивки контроллера'
    )
    modemversion: Optional[str] = Field(None, description='Версия модема')
    modemappversion: Optional[str] = Field(
        None, description='Версия прошивки модема'
    )

    gps_raw: Optional[GpsRawData] = Field(
        None, alias='gps', description='Сырые GPS координаты'
    )
    gps: Optional[GpsData] = Field(
        None, description='Координаты в десятичном формате'
    )

    date_str: str = Field(
        ..., alias='date', description='Дата регистрации (строка DD.MM.YYYY)'
    )
    time_str: str = Field(
        ..., alias='time', description='Время регистрации (строка HH:MM:SS)'
    )
    event_datetime: datetime = Field(
        datetime.now(), description='Дата и время регистрации'
    )

    # Команды диагностики сети:
    ati_raw: Optional[str] = Field(
        None, alias='ati', description='Ответ на команду ATI'
    )
    cpsi_raw: Optional[str] = Field(
        None, alias='cpsi', description='Статус сети CPSI'
    )
    creg_raw: Optional[str] = Field(
        None, alias='creg', description='Регистрация CREG'
    )
    cgmr_raw: Optional[str] = Field(
        None, alias='cgmr', description='Версия CGMR'
    )
    cimi_raw: Optional[str] = Field(
        None, alias='cimi', description='IMEI CIMI'
    )
    csq_raw: Optional[str] = Field(
        None, alias='csq', description='Качество сигнала CSQ'
    )
    cops_raw: Optional[str] = Field(
        None, alias='cops', description='Оператор COPS'
    )
    cnsmod_raw: Optional[str] = Field(
        None, alias='cnsmod', description='Режим CNSMOD'
    )
    cpol_raw: Optional[str] = Field(
        None, alias='cnetci', description='Список сетей CPOL'
    )
    cnetci_raw: Optional[str] = Field(
        None, alias='cnetci', description='Инфо ячейки CNETCI'
    )
    aops_raw: Optional[str] = Field(
        None, alias='aops', description='Сырые данные AOPS'
    )
    aops: Optional[AopsData] = Field(
        None, description='Структурированные данные AOPS'
    )

    def __str__(self) -> str:
        return (
            f'MAC: {self.macaddress} ({self.event_datetime})'
        )

    @field_validator('macaddress')
    @classmethod
    def validate_mac(cls, v: str) -> str:
        if not v or not isinstance(v, str):
            raise ValueError('Не валидный MAC адрес')
        return v.replace(' ', '').upper()

    @field_validator('*', mode='before')
    @classmethod
    def strip_all_strings(cls, value):
        if isinstance(value, str):
            return value.strip() or None
        return value

    @staticmethod
    def _safe_base64_decode(value: str) -> Optional[str]:
        """
        Безопасное декодирование Base64 с автокоррекцией padding.
        Возвращает None, если декодирование невозможно.
        """
        if not value:
            return None

        try:
            clean_val = ''.join(value.split())

            missing_padding = len(clean_val) % 4
            if missing_padding:
                clean_val += '=' * (4 - missing_padding)

            decoded_bytes = base64.b64decode(clean_val, validate=True)
            return decoded_bytes.decode('utf-8').strip()
        except KeyboardInterrupt:
            raise
        except Exception:
            return None

    @field_validator('gps', 'aops', mode='before')
    @classmethod
    def skip_manual_fields_validation(cls, value: Any):
        if isinstance(value, (GpsData, AopsData)):
            return value
        return None

    @model_validator(mode='after')
    def process_and_decode_fields(self):
        date_val = self.date_str
        time_val = self.time_str

        if not date_val or not time_val:
            raise ValueError(
                f'Отсутствуют дата или время: {date_val}, {time_val}'
            )

        try:
            day, month, year = map(int, date_val.split('.'))
            h, m, s = map(int, time_val.split(':'))
            parsed_date = date(year, month, day)
            parsed_time = time(h, m, s)
            self.event_datetime = datetime.combine(parsed_date, parsed_time)
        except (ValueError, IndexError) as e:
            raise ValueError(f'Ошибка формата даты/времени: {e}') from e

        if self.gps_raw:
            lat_raw = self.gps_raw.lat
            lon_raw = self.gps_raw.longt

            lat_dec = parse_gps_coordinate(lat_raw, is_latitude=True)
            lon_dec = parse_gps_coordinate(lon_raw, is_latitude=False)

            self.gps = (
                None
                if lat_dec is None or lon_dec is None
                else GpsData(lat=lat_dec, lon=lon_dec)
            )

        else:
            self.gps = None

        b64_fields = (
            'ati_raw', 'cpsi_raw', 'creg_raw', 'cgmr_raw', 'cimi_raw',
            'csq_raw', 'cops_raw', 'cnsmod_raw', 'cpol_raw', 'cnetci_raw',
            'aops_raw',
        )

        for field_name in b64_fields:
            raw_value = getattr(self, field_name)
            decoded_text = self._safe_base64_decode(raw_value)
            setattr(self, field_name, decoded_text)

        self.aops = ParseAops(self.aops_raw).parse_aops_string()

        return self
