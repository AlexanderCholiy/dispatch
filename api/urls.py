from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import IncidentReportViewSet, StatisticReportViewSet

router = DefaultRouter()
router.register(
    'report/incidents', IncidentReportViewSet, basename='incidents_report'
)
router.register(
    'report/statistics', StatisticReportViewSet, basename='statistics_report'
)

urlpatterns = [
    path('', include(router.urls)),
    path('auth/', include('djoser.urls')),
    path('auth/', include('djoser.urls.jwt')),
]
