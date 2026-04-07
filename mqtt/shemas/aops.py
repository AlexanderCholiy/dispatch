from enum import Enum, IntEnum
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class NetType(str, Enum):
    GSM = '2G'
    UMTS = '3G'
    LTE = '4G'
    NR = '5G'


class CellInfo(BaseModel):
    """Информация о ячейке сети."""

    index: int = Field(..., description='Индекс ячейки')

    # Общие идентификаторы (cellid по алгоритмам всегда будет)
    cellid: Optional[int] = Field(
        None,
        ge=0,
        description='Уникальный ID ячейки',
    )
    mcc_mnc: Optional[str] = Field(None, description='MCC-MNC код оператора')

    # LTE (4G) параметры
    tac: Optional[int] = Field(
        None, ge=0, description='TAC (Tracking Area Code) - только для LTE'
    )
    rsrp: Optional[int] = Field(
        None,
        description=(
            'RSRP (Reference Signal Received Power) - уровень сигнала LTE'
        )
    )
    rsrq: Optional[int] = Field(
        None,
        description=(
            'RSRQ (Reference Signal Received Quality) - качество сигнала LTE'
        )
    )
    pci: Optional[int] = Field(
        None, ge=0, description='PCI (Physical Cell ID) - LTE'
    )
    earfcn: Optional[int] = Field(
        None,
        ge=0,
        description=(
            'EARFCN (E-UTRA Absolute Radio Frequency Channel Number) - '
            'уникальный номер частоты для LTE'
        )
    )

    # UMTS (3G) параметры
    lac: Optional[int] = Field(
        None, ge=0, description='LAC (Location Area Code) - только для 3G'
    )
    rscp: Optional[int] = Field(
        None,
        description='RSCP (Received signal Code power) - уровень сигнала 3G'
    )
    ecno: Optional[int] = Field(
        None,
        description=(
            'Ec/No (Ratio of energy per modulating bit to the noise spectral '
            'density) - качество сигнала 3G'
        )
    )
    psc: Optional[int] = Field(
        None, ge=0, description='PSC (Primary Scrambling Code) - только для 3G'
    )

    # GSM (2G) параметры
    bsic: Optional[int] = Field(
        None,
        ge=0,
        description='BSIC (Base station ID code) - код базовой станции 2G'
    )
    rssi: Optional[int] = Field(
        None,
        description=(
            'RSSI (Received Signal Strength Indicator) - уровень сигнала 2G'
        )
    )
    rxlev: Optional[int] = Field(
        None, description='RXLEV (Received Signal Level - 2G)'
    )
    c1: Optional[int] = Field(
        None, description='C1 (Cell selection criterion - 2G)'
    )

    # Общие/Дополнительные
    freq: Optional[int] = Field(
        None, ge=0, description='Arfcn or Uarfcn or Earfcn - частота'
    )
    net_type: Optional[NetType] = Field(None, description='Тип сети')


class OperatorStatus(IntEnum):
    FORBIDDEN = 0
    CURRENT = 1
    AVAILABLE = 2
    HOME = 3


class OperatorEntry(BaseModel):
    """Запись об операторе из списка CPOL/AOPS."""

    index: int = Field(..., ge=0, description='Индекс в списке')
    status: Optional[OperatorStatus] = Field(
        None, description='Статус оператора'
    )
    operator_code: str = Field(..., description='Код оператора')
    operator_name: Optional[str] = Field(
        None, description='Имя оператора (из заголовка AOPS)'
    )


class AopsData(BaseModel):
    """
    Структурированные данные из ответа AT-команды AOPS/CPOL.
    Содержит список найденных ячеек с параметрами сигнала и список операторов
    с их статусами.
    """

    cells: list[CellInfo] = Field(
        default_factory=list,
        description='Список найденных ячеек с качеством сигнала'
    )
    operators: list[OperatorEntry] = Field(
        default_factory=list, description='Список доступных операторов'
    )

    @model_validator(mode='after')
    def parse_raw_data(self):
        return self
