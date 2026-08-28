import math
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from typing import Optional, TypedDict

from django.core.cache import cache
from django.db.models import Case, DateTimeField, F, Max, Q, QuerySet, When
from django.utils import timezone

from core.loggers import default_logger
from emails.models import EmailMessage
from incidents.constants import (
    CACHE_SIMILAR_INCIDENTS_PREFIX,
    CACHE_SIMILAR_INCIDENTS_TTL,
    MAX_INCIDENT_LINKS,
    MAX_SIMILAR_INCIDENTS_CANDIDATES,
    MAX_SIMILAR_INCIDENTS_THRESHOLD,
    MAX_SIMILAR_INCIDENTS_WINDOW_TTL,
    REFRESH_CACHE_INFO_SIMILAR_INCIDENTS_TTL,
    TOTAL_CATEGORIES,
    SimilarFactor,
)
from incidents.models import Incident, IncidentStatusHistory


class IncidentSimilarity(TypedDict):
    candidate_id: int
    candidate_str: str
    status_name: Optional[str]
    status_type_css: Optional[str]
    status_date: Optional[datetime]
    cat_names: list[str]
    incident_type_str: Optional[str]
    probability: float
    reasons: list[str]
    seconds_diff: float


class IncidentSimilarityService:
    """Сервис для поиска похожих инцидентов."""

    @staticmethod
    def _get_text_similarity(text1: str, text2: str) -> float:
        if not text1 or not text2:
            return 0.0

        t1 = ' '.join(str(text1).lower().split())
        t2 = ' '.join(str(text2).lower().split())
        if t1 == t2:
            return 1.0

        return SequenceMatcher(None, t1, t2).ratio()

    @staticmethod
    def _calculate_time_decay_weight(seconds_passed: float) -> float:
        """
        Вычисляет вес на основе прошедших секунд с использованием
        экспоненциального затухания для плавного снижения.
        """
        if seconds_passed <= 0:
            return 1.0

        # Обязательно >= 1
        # 1.0 — очень плавный спад (вес долго держится высоким).
        # 3.0 — быстрый спад (важны только очень свежие инциденты).
        decay_factor = 1.5

        ratio = seconds_passed / MAX_SIMILAR_INCIDENTS_WINDOW_TTL

        weight = math.exp(-decay_factor * ratio)
        if weight > 1:
            default_logger.warning(f'Вес {weight} > 1')

        return weight

    def _build_query_filters(
        self, incident: Incident, now: datetime
    ) -> QuerySet[Incident]:
        """
        Формирует выборку ближайших похожих инцидентов ("соседей") с обеих
        сторон (из прошлого и из будущего) относительно целевого инцидента.

        Логика определения временной оси (target_date):
        - Для открытых инцидентов: используется дата начала (`incident_date`).
        - Для закрытых инцидентов: используется дата закрытия
        (`incident_finish_date`).
        - Защита от багов: если инцидент закрыт, но дата закрытия отсутствует
        (None), в качестве защитного механизма используется дата начала
        (`incident_date`).

        Опорная точка (ref_date) текущего инцидента:
        - Если текущий инцидент закрыт (и есть дата финиша) ->
        `incident_finish_date`.
        - Если текущий инцидент открыт (или данные повреждены) ->
        переданное время `now`.

        Структура и состав возвращаемой выборки (QuerySet):
        Результат состоит из двух непересекающихся частей (плеч),
        объединенных через UNION ALL:
        """
        base_candidates = Incident.objects.filter(
            Q(is_incident_finish=False)
            | Q(is_incident_finish=True, pole__isnull=False)
        ).exclude(
            id=incident.id
        ).select_related(
            'pole',
            'base_station',
            'incident_type',
            'incident_subtype',
            'rvr_priority',
        ).prefetch_related(
            'categories',
        )

        is_closed = incident.is_incident_finish
        window_delta = timedelta(seconds=MAX_SIMILAR_INCIDENTS_WINDOW_TTL)
        half_limit = MAX_SIMILAR_INCIDENTS_CANDIDATES // 2

        # Опорная точка:
        ref_date = (
            incident.incident_finish_date
            if is_closed and incident.incident_finish_date
            else now
        )

        base_candidates = base_candidates.annotate(
            target_date=Case(
                When(
                    is_incident_finish=True,
                    incident_finish_date__isnull=False,
                    then=F('incident_finish_date'),
                ),
                default=F('incident_date'),
                output_field=DateTimeField(),
            )
        )
        base_candidates = base_candidates.exclude(target_date__isnull=True)

        min_date = ref_date - window_delta
        max_date = ref_date + window_delta

        # ПЛЕЧО «В ПРОШЛОЕ» (ближайшие, которые <= ref_date):
        past_candidates = (
            base_candidates
            .filter(target_date__gte=min_date, target_date__lte=ref_date)
            .order_by('-target_date', '-id')[:half_limit]
        )

        # ПЛЕЧО «В БУДУЩЕЕ» (ближайшие, которые > ref_date):
        future_candidates = (
            base_candidates
            .filter(target_date__gt=ref_date, target_date__lte=max_date)
            .order_by('target_date', 'id')[:half_limit]
        )

        # Объединение через UNION (дубликатов в выборке уже нет):
        return past_candidates.union(future_candidates, all=True)

    def _refresh_data(
        self, results: list[IncidentSimilarity]
    ) -> list[IncidentSimilarity]:
        """Актуализация данных, полученных из кеша."""
        if not results:
            return []

        candidate_ids = [item['candidate_id'] for item in results]

        candidates_qs = (
            Incident.objects.filter(id__in=candidate_ids)
            .select_related(
                'pole',
                'base_station',
                'incident_type',
                'incident_subtype',
                'rvr_priority',
            ).prefetch_related('categories')
        )

        candidates_map = {c.id: c for c in candidates_qs}

        last_status_ids = IncidentStatusHistory.objects.filter(
            incident_id__in=candidate_ids
        ).values('incident_id').annotate(
            max_id=Max('id')
        ).values_list('max_id', flat=True)

        last_statuses_qs = IncidentStatusHistory.objects.filter(
            id__in=list(last_status_ids)
        ).select_related('status__status_type')

        last_statuses_map = {h.incident_id: h for h in last_statuses_qs}

        updated_results: list[IncidentSimilarity] = []

        for item in results:
            cid = item['candidate_id']
            candidate = candidates_map.get(cid)

            if not candidate:
                continue

            history_obj = last_statuses_map.get(cid)
            status_name = history_obj.status.name if history_obj else None
            status_type_css = (
                history_obj.status.status_type.css_class
                if history_obj else None
            )
            status_date = history_obj.insert_date if history_obj else None

            cat_names = sorted(
                [cat.name for cat in candidate.categories.all()],
                key=str.lower
            )

            incident_type_str = (
                candidate.incident_type.name
                if candidate.incident_type else None
            )

            updated_item = {
                **item,
                'candidate_str': str(candidate),
                'status_name': status_name,
                'status_type_css': status_type_css,
                'status_date': status_date,
                'cat_names': cat_names,
                'incident_type_str': incident_type_str
            }
            updated_results.append(updated_item)

        return updated_results

    def find_similar(self, incident: Incident) -> list[IncidentSimilarity]:
        cache_key = f'{CACHE_SIMILAR_INCIDENTS_PREFIX}_{incident.id}'
        refresh_cache_key = f'{cache_key}_refreshed'

        cached_result = cache.get(cache_key)

        if cached_result is not None:
            refreshed = cache.get(refresh_cache_key)
            if refreshed is not None:
                return refreshed

            refreshed_data = self._refresh_data(cached_result)
            cache.set(
                refresh_cache_key,
                refreshed_data,
                REFRESH_CACHE_INFO_SIMILAR_INCIDENTS_TTL
            )
            return refreshed_data

        now = timezone.now()

        candidates = self._build_query_filters(incident, now)

        candidate_ids = list(candidates.values_list('id', flat=True))

        if not candidate_ids:
            return []

        all_emails_qs = (
            EmailMessage.objects.filter(
                email_incident__in=candidate_ids
            )
            .only(
                'email_subject', 'email_from', 'email_incident_id'
            ).order_by('email_date', 'id')
        )

        emails_map: dict[int, EmailMessage] = {}
        processed_incidents = set()

        for email in all_emails_qs:
            inc_id = email.email_incident_id

            if inc_id in processed_incidents:
                continue

            emails_map[inc_id] = email
            processed_incidents.add(inc_id)

            if len(processed_incidents) == len(candidate_ids):
                break

        incident_categories_ids = set(
            incident.categories.values_list('id', flat=True)
        )

        incident_first_email: Optional[EmailMessage] = (
            incident.email_messages.only(
                'email_subject', 'email_from'
            )
            .order_by('email_date', 'id').first()
        )

        last_status_ids = IncidentStatusHistory.objects.filter(
            incident_id__in=candidate_ids
        ).values('incident_id').annotate(
            max_id=Max('id')
        ).values_list('max_id', flat=True)

        last_statuses_qs = IncidentStatusHistory.objects.filter(
            id__in=list(last_status_ids)
        ).select_related('status__status_type')

        last_statuses_map: dict[int, IncidentStatusHistory] = {
            h.incident_id: h for h in last_statuses_qs
        }

        results = []

        for candidate in candidates:
            seconds_diff = 0.0
            total_score = 0.0
            reasons = []

            if (
                incident.is_incident_finish
                and incident.incident_finish_date
                and candidate.is_incident_finish
            ):
                seconds_diff = abs(
                    (
                        incident.incident_finish_date
                        - candidate.incident_finish_date
                    ).total_seconds()
                )
            elif (
                not incident.is_incident_finish
                and not candidate.is_incident_finish
            ):
                seconds_diff = abs(
                    (incident.incident_date - candidate.incident_date)
                    .total_seconds()
                )
            elif (
                incident.is_incident_finish
                and incident.incident_finish_date
                and not candidate.is_incident_finish
            ):
                seconds_diff = abs(
                    (incident.incident_finish_date - candidate.incident_date)
                    .total_seconds()
                )
            elif (
                not incident.is_incident_finish
                and candidate.is_incident_finish
                and candidate.incident_finish_date
            ):
                seconds_diff = abs(
                    (candidate.incident_finish_date - incident.incident_date)
                    .total_seconds()
                )

            time_weight = self._calculate_time_decay_weight(seconds_diff)
            if time_weight == 0:
                continue

            # Схожесть признаков:
            if (
                incident.pole
                and candidate.pole
                and incident.pole == candidate.pole
            ):
                total_score += SimilarFactor.pole * time_weight
                reasons.append('Одинаковая опора')

            if (
                incident.base_station
                and candidate.base_station
                and incident.base_station == candidate.base_station
            ):
                total_score += SimilarFactor.bs * time_weight
                reasons.append('Одинаковая базовая станция')

            if (
                incident.incident_type
                and candidate.incident_type
                and incident.incident_type == candidate.incident_type
            ):
                total_score += SimilarFactor.incident_type * time_weight
                reasons.append('Одинаковый тип проблемы')

            if (
                incident.incident_subtype
                and candidate.incident_subtype
                and incident.incident_subtype == candidate.incident_subtype
            ):
                total_score += SimilarFactor.incident_sub_type * time_weight
                reasons.append('Одинаковый подтип проблемы')

            if (
                incident.rvr_priority
                and candidate.rvr_priority
                and incident.rvr_priority == candidate.rvr_priority
            ):
                total_score += SimilarFactor.rvr_priority * time_weight
                reasons.append('Одинаковый приоритет РВР')

            candidate_cat_ids = {cat.id for cat in candidate.categories.all()}
            if incident_categories_ids and candidate_cat_ids:
                intersection_count = len(
                    incident_categories_ids.intersection(candidate_cat_ids)
                )
                if intersection_count > 0:
                    cat_score = SimilarFactor.categories * (
                        intersection_count / len(TOTAL_CATEGORIES)
                    )
                    total_score += cat_score * time_weight
                    reasons.append(
                        f'Общие категории ({intersection_count} шт.)'
                    )

            candidate_first_email = emails_map.get(candidate.id)

            if candidate_first_email and incident_first_email:
                subject_sim = self._get_text_similarity(
                    incident_first_email.email_subject or '',
                    candidate_first_email.email_subject or ''
                )
                if subject_sim > MAX_SIMILAR_INCIDENTS_THRESHOLD:
                    total_score += (
                        SimilarFactor.incident_email_subject
                        * subject_sim * time_weight
                    )
                    reasons.append('Похожая тема первого письма')

                if (
                    incident_first_email.email_from == (
                        candidate_first_email.email_from
                    )
                ):
                    total_score += (
                        SimilarFactor.incident_email_from * time_weight
                    )
                    reasons.append('Одинаковый заявитель')

            history_obj = last_statuses_map.get(candidate.id)
            status_name = history_obj.status.name if history_obj else None
            status_type_css = (
                history_obj.status.status_type.css_class
                if history_obj else None
            )
            status_date = history_obj.insert_date if history_obj else None

            cat_names = sorted(
                [cat.name for cat in candidate.categories.all()], key=str.lower
            )

            if (
                MAX_SIMILAR_INCIDENTS_THRESHOLD > 0
                and total_score < MAX_SIMILAR_INCIDENTS_THRESHOLD
            ):
                continue

            incident_type_str = (
                candidate.incident_type.name
                if candidate.incident_type else None
            )

            results.append({
                'candidate_str': str(candidate),
                'candidate_id': candidate.id,
                'incident_type_str': incident_type_str,
                'status_name': status_name,
                'status_type_css': status_type_css,
                'status_date': status_date,
                'cat_names': cat_names,
                'probability': round(min(total_score, 1), 2),
                'reasons': reasons,
                'seconds_diff': seconds_diff,
            })

        results.sort(key=lambda x: (-x['probability'], x['seconds_diff']))
        results = results[:MAX_INCIDENT_LINKS]

        cache.set(cache_key, results, timeout=CACHE_SIMILAR_INCIDENTS_TTL)

        return results


incident_similarity_service = IncidentSimilarityService()
