"""Recherche de mariages actifs pour la procédure de divorce."""
from django.db.models import Q
from django.urls import reverse

from .models import Divorce, EmpreinteDigitale, Mariage, photo_conjoint_affichage


def queryset_mariages_eligibles_divorce():
    """Mariages actifs sans divorce déjà enregistré."""
    mariages_divorces = Divorce.objects.values_list('mariage_id', flat=True)
    return (
        Mariage.objects.filter(statut='actif')
        .exclude(pk__in=mariages_divorces)
        .select_related(
            'epoux',
            'epouse',
            'dossier__commune_enregistrement__ville__province',
        )
    )


def serialiser_mariage_divorce(mariage, correspondance=None):
    commune = mariage.dossier.commune_enregistrement if mariage.dossier else None
    img_epoux = photo_conjoint_affichage(mariage.epoux)
    img_epouse = photo_conjoint_affichage(mariage.epouse)
    data = {
        'id': mariage.pk,
        'numero_acte': mariage.numero_acte,
        'date_mariage': mariage.date_mariage.isoformat() if mariage.date_mariage else None,
        'lieu_mariage': mariage.lieu_mariage,
        'regime_matrimonial': mariage.regime_matrimonial,
        'acte_url': reverse('visualiser_acte_pdf', args=[mariage.pk]),
        'epoux': {
            'nom_complet': f"{mariage.epoux.nom} {mariage.epoux.post_nom} {mariage.epoux.prenom}".strip(),
            'photo_url': img_epoux.url if img_epoux else None,
        },
        'epouse': {
            'nom_complet': f"{mariage.epouse.nom} {mariage.epouse.post_nom} {mariage.epouse.prenom}".strip(),
            'photo_url': img_epouse.url if img_epouse else None,
        },
        'lieu': {
            'commune': commune.nom if commune else '—',
            'ville': commune.ville.nom if commune else '—',
            'province': commune.ville.province.nom if commune else '—',
        },
    }
    if correspondance:
        data['correspondance'] = correspondance
    return data


def rechercher_mariages_nominatif(nom, postnom, prenom):
    qs = queryset_mariages_eligibles_divorce()
    if nom:
        qs = qs.filter(Q(epoux__nom__icontains=nom) | Q(epouse__nom__icontains=nom))
    if postnom:
        qs = qs.filter(
            Q(epoux__post_nom__icontains=postnom) | Q(epouse__post_nom__icontains=postnom)
        )
    if prenom:
        qs = qs.filter(Q(epoux__prenom__icontains=prenom) | Q(epouse__prenom__icontains=prenom))
    return [serialiser_mariage_divorce(m) for m in qs.distinct()[:15]]


def rechercher_mariages_empreinte(fichier_epoux, fichier_epouse):
    """Recherche par scan d'empreinte (nom de fichier ou upload)."""
    noms = []
    for fichier in (fichier_epoux, fichier_epouse):
        if fichier and getattr(fichier, 'name', None):
            noms.append(fichier.name.strip())

    if not noms:
        return []

    qs = queryset_mariages_eligibles_divorce()
    empreinte_ids = set()
    for nom in noms:
        for emp in EmpreinteDigitale.objects.filter(empreinte__icontains=nom):
            empreinte_ids.add(emp.pk)

    if not empreinte_ids:
        return []

    qs = qs.filter(
        Q(epoux__empreinte_digitale_id__in=empreinte_ids)
        | Q(epouse__empreinte_digitale_id__in=empreinte_ids)
    ).distinct()
    return [serialiser_mariage_divorce(m) for m in qs[:15]]
