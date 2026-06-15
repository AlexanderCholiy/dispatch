from django.urls import path

from . import views

app_name = 'planned_work'

urlpatterns = [
    path('create/', views.create_planned_work, name='planned_work_create'),
    path('<int:pk>/', views.planned_work_detail, name='planned_work_detail'),
]
