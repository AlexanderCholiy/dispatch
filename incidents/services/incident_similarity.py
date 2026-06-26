import math
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from typing import Optional, TypedDict

from django.core.cache import cache
from django.db.models import Max, Q, QuerySet
from django.utils import timezone

from core.loggers import default_logger
from core.wraps import timer
from emails.models import EmailMessage
from incidents.constants import (
    CACHE_SIMILAR_INCIDENTS_PREFIX,
    CACHE_SIMILAR_INCIDENTS_TTL,
    MAX_INCIDENT_LINKS,
    MAX_SIMILAR_INCIDENTS_CANDIDATES,
    MAX_SIMILAR_INCIDENTS_THRESHOLD,
    MAX_SIMILAR_INCIDENTS_WINDOW_TTL,
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

        # 1.0 — очень плавный спад (вес долго держится высоким).
        # 3.0 — быстрый спад (важны только очень свежие инциденты).
        decay_factor = 1.5
        ratio = seconds_passed / MAX_SIMILAR_INCIDENTS_WINDOW_TTL

        weight = math.exp(-decay_factor * ratio)

        return weight

    def _build_query_filters(
        self, incident: Incident, now: datetime
    ) -> QuerySet[Incident]:
        is_closed = incident.is_incident_finish
        ref_date = (
            incident.incident_finish_date
            if is_closed else incident.incident_date
        )
        window_delta = timedelta(seconds=MAX_SIMILAR_INCIDENTS_WINDOW_TTL)

        candidates = Incident.objects.exclude(
            Q(id=incident.id) | Q(pole__isnull=True)
        )

        if is_closed:
            closed_filter = Q(
                is_incident_finish=True,
                incident_finish_date__gte=ref_date - window_delta,
                incident_finish_date__lte=ref_date + window_delta
            )
            open_filter = Q(
                is_incident_finish=False, incident_date__lte=ref_date
            )
            final_q = closed_filter | open_filter
        else:
            open_filter = Q(is_incident_finish=False, incident_date__lte=now)
            closed_filter = Q(
                is_incident_finish=True,
                incident_finish_date__gte=(
                    incident.incident_date - window_delta
                ),
                incident_finish_date__lte=incident.incident_date + window_delta
            )
            final_q = open_filter | closed_filter

        return (
            candidates.filter(final_q).order_by('-incident_date', '-id')
            [:MAX_SIMILAR_INCIDENTS_CANDIDATES]
        )

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
                'pole', 'base_station', 'incident_type', 'incident_subtype'
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

            categories_list = candidate.categories.all()

            cat_names = sorted(
                [cat.name for cat in categories_list], key=str.lower
            )

            updated_item = {
                **item,
                'candidate_str': str(candidate),
                'status_name': status_name,
                'status_type_css': status_type_css,
                'status_date': status_date,
                'cat_names': cat_names,
            }
            updated_results.append(updated_item)

        return updated_results

    @timer(default_logger)
    def find_similar(self, incident: Incident) -> list[IncidentSimilarity]:
        cache_key = f'{CACHE_SIMILAR_INCIDENTS_PREFIX}_{incident.id}'

        cached_result = cache.get(cache_key)
        if cached_result is not None:
            return self._refresh_data(cached_result)

        now = timezone.now()
        candidates_qs = self._build_query_filters(incident, now)

        candidate_ids = list(candidates_qs.values_list('id', flat=True))

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

        candidates = candidates_qs.select_related(
            'pole',
            'base_station',
            'incident_type',
            'incident_subtype',
        ).prefetch_related(
            'categories',
        )

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

            results.append({
                'candidate_str': str(candidate),
                'candidate_id': candidate.id,
                'status_name': status_name,
                'status_type_css': status_type_css,
                'status_date': status_date,
                'cat_names': cat_names,
                'probability': round(total_score, 2),
                'reasons': reasons,
                'seconds_diff': seconds_diff,
            })

        results.sort(key=lambda x: (-x['probability'], x['seconds_diff']))
        results = results[:MAX_INCIDENT_LINKS]

        cache.set(cache_key, results, timeout=CACHE_SIMILAR_INCIDENTS_TTL)

        return results


incident_similarity_service = IncidentSimilarityService()
