from datetime import datetime
from enum import IntEnum, StrEnum
from typing import Optional

from pydantic import BaseModel, Field, model_validator

from mqtt.constants import (
    MAX_MONGO_ID_LEN,
    CellMeasurConstraints,
)


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
        ...,
        ge=0,
        description='Cell ID',
    )
    operator: Operator = Field(
        ...,
        description='Operator',
    )
    rat: NetType = Field(
        ...,
        description='Network type',
    )
    lac: Optional[int] = Field(
        None,
        ge=0,
        description='Location Area Code',
    )
    tac: Optional[int] = Field(
        None,
        ge=0,
        description='Tracking Area Code',
    )
    freq: Optional[int] = Field(
        None,
        ge=0,
        description='Arfcn or Uarfcn or Earfcn',
    )
    bsic: Optional[int] = Field(
        None,
        ge=0,
        description='Base station ID code',
    )
    psc: Optional[int] = Field(
        None,
        ge=0,
        description='Primary Scrambling Code',
    )
    pci: Optional[int] = Field(
        None,
        ge=0,
        description='Physical Cell ID',
    )
    event_datetime: datetime = Field(
        ...,
        description='Дата и время регистрации',
    )

    @model_validator(mode='after')
    def check_lac_or_tac(self) -> 'Cell':
        if self.lac is None and self.tac is None:
            raise ValueError(
                'Хотя бы одно поле lac или tac должно быть заполнено'
            )
        return self


class CellMeasure(BaseModel):
    mongo_id: str = Field(
        ...,
        alias='mongo_id',
        min_length=MAX_MONGO_ID_LEN,
        max_length=MAX_MONGO_ID_LEN,
        description='Уникальный идентификатор документа из MongoDB (ObjectId)'
    )
    cell: Cell = Field(
        ...,
        description='Cell',
    )
    index: int = Field(
        ...,
        description='Item ID in result list',
        ge=CellMeasurConstraints.MIN_INDEX_VAL,
        le=CellMeasurConstraints.MAX_INDEX_VAL,
    )
    rssi: Optional[int] = Field(
        None,
        description='Received Signal Strength Indicator',
        ge=CellMeasurConstraints.MIN_RSSI_VAL,
        le=CellMeasurConstraints.MAX_RSSI_VAL,
    )
    rxlev: Optional[int] = Field(
        None,
        description='Received Signal Level',
        ge=CellMeasurConstraints.MIN_RXLEV_VAL,
        le=CellMeasurConstraints.MAX_RXLEV_VAL,
    )
    c1: Optional[int] = Field(
        None,
        description='Cell selection criterion',
        ge=CellMeasurConstraints.MIN_C1_VAL,
        le=CellMeasurConstraints.MAX_C1_VAL,
    )
    cba: Optional[CellBar] = Field(
        None,
        description='Cell Bar indicator',
    )
    rscp: Optional[int] = Field(
        None,
        description='Received signal Code power',
        ge=CellMeasurConstraints.MIN_RSCP_VAL,
        le=CellMeasurConstraints.MAX_RSCP_VAL,
    )
    ecno: Optional[int] = Field(
        None,
        description=(
            'Ratio of energy per modulating bit to the noise spectral density'
        ),
        ge=CellMeasurConstraints.MIN_ECNO_VAL,
        le=CellMeasurConstraints.MAX_ECNO_VAL,
    )
    rsrp: Optional[int] = Field(
        None,
        description='Reference Signal Received Power',
        ge=CellMeasurConstraints.MIN_RSRP_VAL,
        le=CellMeasurConstraints.MAX_RSRP_VAL,
    )
    rsrq: Optional[int] = Field(
        None,
        description='Reference Signal Received Quality',
        ge=CellMeasurConstraints.MIN_RSRQ_VAL,
        le=CellMeasurConstraints.MAX_RSRQ_VAL,
    )
    event_datetime: datetime = Field(
        ...,
        description='Дата и время регистрации',
    )
