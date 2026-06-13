from django.contrib import admin

from .models import Parcelle, QuittanceParcellaire


@admin.register(Parcelle)
class ParcelleAdmin(admin.ModelAdmin):
    list_display = ('numero_cadastre', 'proprietaire', 'commune', 'adresse')
    list_filter = ('commune',)
    search_fields = ('numero_cadastre', 'proprietaire', 'adresse')


@admin.register(QuittanceParcellaire)
class QuittanceParcellaireAdmin(admin.ModelAdmin):
    list_display = ('parcelle', 'montant', 'periode', 'date', 'commune')
    list_filter = ('commune', 'date', 'periode')
    search_fields = ('parcelle__numero_cadastre', 'parcelle__proprietaire')
    date_hierarchy = 'date'
