from typing import Optional

from pydantic import BaseModel, Field, model_validator


class CellInfo(BaseModel):
    """Информация о ячейке сети."""

    index: int = Field(..., description='Индекс ячейки')

    # Общие идентификаторы
    mcc_mnc: Optional[str] = Field(None, description='MCC-MNC код оператора')
    cellid: Optional[int] = Field(None, description='Уникальный ID ячейки')

    # LTE (4G) параметры
    tac: Optional[int] = Field(
        None, description='TAC (Tracking Area Code) - только для LTE'
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
        None, description='PCI (Physical Cell ID) - LTE'
    )
    earfcn: Optional[int] = Field(
        None,
        description=(
            'EARFCN (E-UTRA Absolute Radio Frequency Channel Number) - '
            'уникальный номер частоты для LTE'
        )
    )

    # UMTS (3G) параметры
    lac: Optional[int] = Field(
        None, description='LAC (Location Area Code) - только для 3G'
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
        None, description='PSC (Primary Scrambling Code) - только для 3G'
    )

    # GSM (2G) параметры
    bsic: Optional[int] = Field(
        None,
        description='BSIC (Base station ID code) - код базовой станции 2G'
    )
    rssi: Optional[int] = Field(
        None,
        description=(
            'RSSI (Received Signal Strength Indicator) - уровень сигнала 2G'
        )
    )

    # Общие/Дополнительные
    freq: Optional[int] = Field(
        None, description='Arfcn or Uarfcn or Earfcn - частота'
    )
    net_type: Optional[str] = Field(None, description='Тип сети (2G, 3G, 4G)')


class OperatorEntry(BaseModel):
    """Запись об операторе из списка CPOL/AOPS."""

    index: int = Field(..., description='Индекс в списке')
    status: Optional[int] = Field(
        None, description='Статус (0=не выбран, 1=выбран, 2=доступен)'
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
