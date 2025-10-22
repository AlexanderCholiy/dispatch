from rest_framework.pagination import LimitOffsetPagination


class IncidentReportPagination(LimitOffsetPagination):
    default_limit = 100
    max_limit = 10_000
    min_limit = 1
