from datetime import datetime
from enum import IntEnum, StrEnum
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class NetType(StrEnum):
    GSM = '2G'
    UMTS = '3G'
    LTE = '4G'


class CellBar(IntEnum):
    NOT_BARED = 0
    BARED = 1


class Operator(BaseModel):
    """Запись об операторе из списка CPOL/AOPS."""

    operator_code: str = Field(
        ..., description='Operator code'
    )
    operator_name: Optional[str] = Field(
        None, description='Operator name in long String'
    )
    operator_st_name: Optional[str] = Field(
        None, description='Operator name in short String'
    )


class Cell(BaseModel):
    cellid: int = Field(
        ..., ge=0, description='Cell ID'
    )
    operator: Operator = Field(
        ..., description='Operator'
    )
    rat: NetType = Field(..., description='Network type')
    lac: Optional[int] = Field(
        None, ge=0, description='Location Area Code'
    )
    tac: Optional[int] = Field(
        None, ge=0, description='Tracking Area Code'
    )
    freq: Optional[int] = Field(
        None, ge=0, description='Arfcn or Uarfcn or Earfcn'
    )
    bsic: Optional[int] = Field(
        None, ge=0, description='Base station ID code'
    )
    psc: Optional[int] = Field(
        None, ge=0, description='Primary Scrambling Code'
    )
    pci: Optional[int] = Field(
        None, ge=0, description='Physical Cell ID'
    )
    event_datetime: datetime = Field(
        ..., description='Дата и время регистрации'
    )

    @model_validator(mode='after')
    def check_lac_or_tac(self) -> 'Cell':
        if self.lac is None and self.tac is None:
            raise ValueError(
                'Хотя бы одно поле lac или tac должно быть заполнено'
            )
        return self


class CellMeasure(BaseModel):
    cell: Cell = Field(
        ..., description='Cell'
    )
    index: int = Field(
        ..., ge=0, description='Item ID in result list'
    )
    rssi: Optional[int] = Field(
        None, description='Received Signal Strength Indicator'
    )
    rxlev: Optional[int] = Field(
        None, description='Received Signal Level'
    )
    c1: Optional[int] = Field(
        None, description='Cell selection criterion'
    )
    cba: Optional[CellBar] = Field(
        None, description='Cell Bar indicator'
    )
    rscp: Optional[int] = Field(
        None, description='Received signal Code power'
    )
    ecno: Optional[int] = Field(
        None,
        description=(
            'Ratio of energy per modulating bit to the noise spectral density'
        )
    )
    rsrp: Optional[int] = Field(
        None, description='Reference Signal Received Power'
    )
    rsrq: Optional[int] = Field(
        None, description='Reference Signal Received Quality'
    )
    event_datetime: datetime = Field(
        ..., description='Дата и время регистрации'
    )
