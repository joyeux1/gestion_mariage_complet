"""Recherche nationale de mariages actifs pour la procédure de divorce."""
from django.db.models import Q
from django.urls import reverse

from .models import Divorce, Mariage, photo_conjoint_affichage
from .services_biometrie import ReconnaissanceFacialeService
from .verification_dossier import (
    _catalogue_encodages_faciaux,
    _mariage_actif_pour_conjoint,
    _trouver_conjoints_par_empreinte,
)


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


def _mariage_eligible_divorce_pour_conjoint(conjoint, est_epoux):
    """Mariage actif non divorcé associé à un conjoint (recherche nationale)."""
    mariage = _mariage_actif_pour_conjoint(conjoint, est_epoux)
    if not mariage or mariage.statut != 'actif':
        return None
    if Divorce.objects.filter(mariage=mariage).exists():
        return None
    return mariage


def rechercher_mariages_empreinte(fichier_epoux, fichier_epouse):
    """Recherche nationale par empreinte (même logique biométrique que l'anti-polygamie)."""
    mariages_vus = set()
    resultats = []

    if fichier_epoux:
        for conjoint, est_epoux in _trouver_conjoints_par_empreinte(fichier_epoux, 'epoux'):
            mariage = _mariage_eligible_divorce_pour_conjoint(conjoint, est_epoux)
            if mariage and mariage.pk not in mariages_vus:
                mariages_vus.add(mariage.pk)
                resultats.append(serialiser_mariage_divorce(mariage))

    if fichier_epouse:
        for conjoint, est_epoux in _trouver_conjoints_par_empreinte(fichier_epouse, 'epouse'):
            mariage = _mariage_eligible_divorce_pour_conjoint(conjoint, est_epoux)
            if mariage and mariage.pk not in mariages_vus:
                mariages_vus.add(mariage.pk)
                resultats.append(serialiser_mariage_divorce(mariage))

    return resultats[:15]


def rechercher_mariages_facial(encodage_capture):
    """Recherche nationale par reconnaissance faciale (catalogue mariages actifs)."""
    catalogue = []
    mariages_vus = set()

    for role in ('epoux', 'epouse'):
        for item in _catalogue_encodages_faciaux(role):
            conjoint = item['conjoint']
            est_epoux = item['est_epoux']
            mariage = _mariage_eligible_divorce_pour_conjoint(conjoint, est_epoux)
            if not mariage or mariage.pk in mariages_vus:
                continue
            mariages_vus.add(mariage.pk)
            label = 'Époux' if est_epoux else 'Épouse'
            catalogue.append({
                'mariage': mariage,
                'id': f"{mariage.pk}-{role}",
                'encodage': item['encodage'],
                'meta': {
                    'role': role,
                    'role_label': label,
                    'nom_complet': f"{conjoint.nom} {conjoint.post_nom} {conjoint.prenom}".strip(),
                },
            })

    if not catalogue:
        return None, catalogue

    correspondance = ReconnaissanceFacialeService.meilleure_correspondance(
        encodage_capture, catalogue
    )
    return correspondance, catalogue
