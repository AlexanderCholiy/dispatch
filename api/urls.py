from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views.comment import CommentViewSet
from .views.energy import AppealViewSet, ClaimViewSet
from .views.monitoring import SMSCsvExportView
from .views.reports import IncidentReportViewSet

app_name = 'api'

router = DefaultRouter()
router.register(
    'report/incidents', IncidentReportViewSet, basename='incidents_report'
)
router.register(
    'energy/claims', ClaimViewSet, basename='energy_api_claims'
)
router.register(
    'energy/appeals', AppealViewSet, basename='energy_api_appeals'
)
router.register(r'comments', CommentViewSet, basename='incident_api_comment')
router.register(
    'monitoring/rvr-sms', SMSCsvExportView, basename='monitoring_rvr_sms'
)

urlpatterns = [
    path('', include(router.urls)),
    path('auth/', include('djoser.urls')),
    path('auth/', include('djoser.urls.jwt')),
]
