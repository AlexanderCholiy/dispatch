from django.urls import path

from . import views

app_name = 'emails'

urlpatterns = [
    path('', views.emails_list, name='emails_list'),
    path(
        '<int:email_id>/download-all/',
        views.download_email_attachments,
        name='download_email_attachments'
    ),
    path(
        '<int:email_id>/',
        views.email_detail,
        name='email_detail'
    ),
]
