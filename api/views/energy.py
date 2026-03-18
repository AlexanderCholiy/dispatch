import csv
import io

from rest_framework import viewsets, permissions
from django.db.models import Prefetch, QuerySet
from http import HTTPStatus

from energy.models import Claim, ClaimStatus, ClaimAttr
from api.serializers.energy import ClaimSerializer
from rest_framework.decorators import action
from django.core.cache import cache
from energy.constants import AttrTypes
from api.utils import get_attr_mapping, is_file_fresh
from core.views import send_x_accel_file
from django.http import HttpResponse
from rest_framework.request import Request
from redis.exceptions import LockError
from pathlib import Path

from core.loggers import default_logger

from api.constants import (
    CACHE_ENERGY_CLAIMS_FILE,
    CACHE_ENERGY_TTL,
    LOCK_KEY_CACHE_ENERGY_CLAIMS_FILE,
    LOCK_ENERGY_BLOCKING_TIMEOUT_SEC,
    LOCK_ENERY_TIMEOUT_SEC,
    ENERGY_DB_CHUNK_SIZE,
    API_DATETIME_FORMAT,
)


class ClaimViewSet(viewsets.ReadOnlyModelViewSet):
    """Энергосети (заявки)"""
    permission_classes = (permissions.AllowAny,)
    serializer_class = ClaimSerializer

    def get_queryset(self):
        return Claim.objects.select_related(
            'declarant', 'company'
        ).prefetch_related(
            Prefetch(
                'claim_statuses',
                queryset=ClaimStatus.objects.order_by('-created_at'),
                to_attr='ordered_statuses'
            ),
            Prefetch(
                'claim_attrs',
                queryset=ClaimAttr.objects.select_related('attr_type')
            )
        )

    @action(detail=False, methods=['get'], url_path='export-csv')
    def export_csv(self, request: Request):
        """Выгрузка в CSV через X-Accel-Redirect с кешированием файла."""
        cache_file = CACHE_ENERGY_CLAIMS_FILE

        fresh, _ = is_file_fresh(cache_file, CACHE_ENERGY_TTL)
        if fresh:
            return send_x_accel_file(cache_file)

        try:
            with cache.lock(
                LOCK_KEY_CACHE_ENERGY_CLAIMS_FILE,
                timeout=LOCK_ENERY_TIMEOUT_SEC,
                blocking_timeout=LOCK_ENERGY_BLOCKING_TIMEOUT_SEC,
            ):
                fresh, _ = is_file_fresh(cache_file, CACHE_ENERGY_TTL)
                if fresh:
                    return send_x_accel_file(cache_file)

                self._generate_csv_file(self.get_queryset(), cache_file)
                return send_x_accel_file(cache_file)

        except LockError:
            return HttpResponse(
                'Файл все еще генерируется, попробуйте позже.',
                status=HTTPStatus.SERVICE_UNAVAILABLE
            )

    def _generate_csv_file(self, queryset: QuerySet, file_path: Path):
        tmp_file = file_path.with_suffix('.tmp')
        attr_mapping = get_attr_mapping(AttrTypes)
        attr_ids = list(attr_mapping.keys())

        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)

            with tmp_file.open('w', encoding='utf-8-sig', newline='') as f:
                writer = csv.writer(f, delimiter=';')

                headers = [
                    'id',
                    'number',
                    'declarant_name',
                    'company_name',
                    'last_status_name',
                    'last_status_created_at',
                    'last_status_date',
                ]
                for slug in attr_mapping.values():
                    headers.extend(
                        [f'{slug}_name', f'{slug}_text', f'{slug}_created_at']
                    )
                writer.writerow(headers)

                buffer = []

                for claim in queryset.iterator(
                    chunk_size=ENERGY_DB_CHUNK_SIZE
                ):
                    status = (
                        claim.ordered_statuses[0]
                        if getattr(claim, 'ordered_statuses', None) else None
                    )

                    row = [
                        claim.id,
                        claim.number,
                        claim.declarant.name,
                        claim.company.name,
                        status.name if status else '',
                        (
                            status.created_at.strftime(API_DATETIME_FORMAT)
                            if status else ''
                        ),
                        status.date if status else ''
                    ]

                    attrs_dict: dict[int, ClaimAttr] = {
                        a.attr_type.attribute_id: a
                        for a in claim.claim_attrs.all()
                    }
                    for attr_id in attr_ids:
                        attr_obj = attrs_dict.get(attr_id)
                        if attr_obj:
                            row.extend([
                                attr_obj.attr_type.name,
                                attr_obj.text or '',
                                attr_obj.created_at.strftime(
                                    API_DATETIME_FORMAT
                                )
                            ])
                        else:
                            row.extend(['', '', ''])

                    buffer.append(row)

                    if len(buffer) >= ENERGY_DB_CHUNK_SIZE:
                        writer.writerows(buffer)
                        buffer = []
                if buffer:
                    writer.writerows(buffer)

            tmp_file.replace(file_path)
        except Exception as e:
            default_logger.exception(e)
        finally:
            if tmp_file.exists():
                tmp_file.unlink()
