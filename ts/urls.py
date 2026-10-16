from django.urls import path

from . import views

app_name = 'ts'

urlpatterns = [
    path(
        'pole-autocomplete/',
        views.PoleAutocomplete.as_view(),
        name='pole_autocomplete'
    ),
    path(
        'bs-autocomplete/',
        views.BaseStationAutocomplete.as_view(),
        name='bs_autocomplete'
    ),
    path(
        'vols-autocomplete/',
        views.VolesAutocomplete.as_view(),
        name='vols_autocomplete'
    ),
]
