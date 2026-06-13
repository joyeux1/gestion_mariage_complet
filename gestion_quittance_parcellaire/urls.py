from django.urls import path

from . import views

app_name = 'gestion_quittance_parcellaire'

urlpatterns = [
    path('', views.QuittanceListView.as_view(), name='quittance_list'),
]
