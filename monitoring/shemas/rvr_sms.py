from pydantic import BaseModel, field_validator
from datetime import datetime
from typing import Optional


class SMSParseSchema(BaseModel):
    phone_from: int
    phone_to: Optional[int] = None
    sent_time: Optional[datetime] = None
    received_time: Optional[datetime] = None
    answer: Optional[str] = None

    @field_validator('answer')
    @classmethod
    def validate_answer(cls, v):
        if v is None:
            return v
        if len(v) <= 1:
            raise ValueError('Ответ должен быть строкой длиной > 1')
        return v
