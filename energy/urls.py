from django.urls import path

from . import views

app_name = 'energy'

urlpatterns = [
    path('', views.energy_companies, name='energy_companies'),
]
