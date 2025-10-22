from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import IncidentReportViewSet

router = DefaultRouter()
router.register(
    'report/incidents', IncidentReportViewSet, basename='incidents_report'
)

urlpatterns = [
    path('', include(router.urls)),
    path('auth/', include('djoser.urls')),
    path('auth/', include('djoser.urls.jwt')),
]
