from datetime import datetime
from typing import Optional

from incidents.constants import SLA_BUFFER


def is_data_changed(
    old_value: Optional[datetime], new_value: Optional[datetime]
) -> bool:
    if old_value is None and new_value is None:
        return False
    if old_value is None or new_value is None:
        return True

    norm_old = old_value.replace(second=0, microsecond=0)
    norm_new = new_value.replace(second=0, microsecond=0)

    diff = abs((norm_new - norm_old))

    return diff > SLA_BUFFER
