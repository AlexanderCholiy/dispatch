from rest_framework.pagination import LimitOffsetPagination


class IncidentReportPagination(LimitOffsetPagination):
    default_limit = 50
    max_limit = 1_000
    min_limit = 1


class CommentPagination(LimitOffsetPagination):
    default_limit = 50
    max_limit = 1_000
    min_limit = 1
