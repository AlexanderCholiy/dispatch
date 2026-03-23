from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views.energy import AppealViewSet, ClaimViewSet
from .views.reports import (
    AVRContractorViewSet,
    IncidentReportViewSet,
    StatisticReportViewSet,
    DispatchViewSet,
)

router = DefaultRouter()
router.register(
    'report/incidents', IncidentReportViewSet, basename='incidents_report'
)
router.register(
    'report/statistics/avr-contractor',
    AVRContractorViewSet,
    basename='avr_contractor_statistics_report'
)
router.register(
    'report/statistics/dispatch',
    DispatchViewSet,
    basename='dispatch_statistics_report'
)
router.register(
    'report/statistics', StatisticReportViewSet, basename='statistics_report'
)
router.register(
    'energy/claims', ClaimViewSet, basename='energy_api_claims'
)
router.register(
    'energy/appeals', AppealViewSet, basename='energy_api_appeals'
)

urlpatterns = [
    path('', include(router.urls)),
    path('auth/', include('djoser.urls')),
    path('auth/', include('djoser.urls.jwt')),
]
