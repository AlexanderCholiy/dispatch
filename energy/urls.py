from django.urls import path

from . import views

app_name = 'energy'

urlpatterns = [
    path('', views.energy_companies, name='energy_companies'),
    path('claims/<int:claim_id>/', views.claim_detail, name='claim_detail'),
    path('appeals/<int:appeal_id>/', views.appeal_detail, name='appeal_detail'),
]
