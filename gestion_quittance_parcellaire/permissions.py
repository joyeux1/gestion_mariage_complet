"""Filtrage géographique des quittances parcellaires selon le rôle utilisateur."""

from mariage.permissions_commune import appliquer_filtre_perimetre_geographique


def filtrer_quittances_par_acces(user, queryset=None):
    """Quittances limitées au périmètre géographique de l'utilisateur."""
    from .models import QuittanceParcellaire

    if queryset is None:
        queryset = QuittanceParcellaire.objects.select_related(
            'parcelle', 'commune__ville__province',
        )
    return appliquer_filtre_perimetre_geographique(user, queryset, 'commune')


def libelle_perimetre_quittances(user):
    from mariage.permissions_commune import libelle_perimetre_dashboard
    return libelle_perimetre_dashboard(user)
