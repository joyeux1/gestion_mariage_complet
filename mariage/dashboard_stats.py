"""Statistiques dynamiques pour les tableaux de bord."""
from datetime import timedelta
from decimal import Decimal

from django.db.models import Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from .models import (
    CaisseCommune,
    Divorce,
    Dossier,
    Epouse,
    Epoux,
    Mariage,
    MouvementCaisse,
)

MOIS_FR = [
    'Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Juin',
    'Juil', 'Aoû', 'Sep', 'Oct', 'Nov', 'Déc',
]


def _evolution_mariages_mensuelle():
    """Nombre de mariages sur les 6 derniers mois calendaires."""
    today = timezone.localdate()
    labels = []
    data = []

    for i in range(5, -1, -1):
        month = today.month - i
        year = today.year
        while month <= 0:
            month += 12
            year -= 1
        labels.append(MOIS_FR[month - 1])
        start = today.replace(year=year, month=month, day=1)
        if month == 12:
            end = start.replace(year=year + 1, month=1, day=1)
        else:
            end = start.replace(month=month + 1, day=1)
        data.append(
            Mariage.objects.filter(
                date_enregistrement__date__gte=start,
                date_enregistrement__date__lt=end,
            ).count()
        )

    return labels, data


def _variation_mariages_mois():
    """Variation en % des mariages ce mois vs le mois précédent."""
    now = timezone.now()
    debut_mois = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if debut_mois.month == 1:
        debut_mois_prec = debut_mois.replace(year=debut_mois.year - 1, month=12)
    else:
        debut_mois_prec = debut_mois.replace(month=debut_mois.month - 1)

    ce_mois = Mariage.objects.filter(date_enregistrement__gte=debut_mois).count()
    mois_prec = Mariage.objects.filter(
        date_enregistrement__gte=debut_mois_prec,
        date_enregistrement__lt=debut_mois,
    ).count()

    if mois_prec == 0:
        return ce_mois, (100 if ce_mois else 0), 'up' if ce_mois else 'neutral'

    pct = round((ce_mois - mois_prec) / mois_prec * 100)
    direction = 'up' if pct >= 0 else 'down'
    return ce_mois, pct, direction


def _taux_succes_dossiers():
    total = Dossier.objects.count()
    if not total:
        return 0, 0, 0
    valides = Dossier.objects.filter(statut='valide').count()
    avec_mariage = Mariage.objects.count()
    taux = round(valides / total * 100)
    return taux, valides, total


def _activites_recentes(limit=8):
    activites = []

    for mariage in (
        Mariage.objects.select_related('epoux', 'epouse')
        .order_by('-date_enregistrement')[:limit]
    ):
        activites.append({
            'type': 'mariage',
            'titre': f"{mariage.epoux.nom} & {mariage.epouse.nom}",
            'detail': f"Acte n° {mariage.numero_acte}",
            'date': mariage.date_enregistrement,
            'date_label': mariage.date_enregistrement.strftime('%d/%m'),
            'url_name': 'mariage_detail',
            'url_pk': mariage.pk,
            'badge_class': 'bg-danger',
            'badge_label': 'Mariage',
        })

    for divorce in (
        Divorce.objects.select_related('mariage__epoux', 'mariage__epouse')
        .order_by('-date_enregistrement')[:limit]
    ):
        activites.append({
            'type': 'divorce',
            'titre': (
                f"{divorce.mariage.epoux.nom} & {divorce.mariage.epouse.nom}"
            ),
            'detail': f"Divorce n° {divorce.numero_divorce}",
            'date': divorce.date_enregistrement,
            'date_label': divorce.date_enregistrement.strftime('%d/%m'),
            'url_name': 'acte_divorce_detail',
            'url_pk': divorce.pk,
            'badge_class': 'bg-dark',
            'badge_label': 'Divorce',
        })

    activites.sort(key=lambda item: item['date'], reverse=True)
    return activites[:limit]


def stats_dashboard_general():
    labels, stats_mensuelles = _evolution_mariages_mensuelle()
    _, variation_pct, variation_dir = _variation_mariages_mois()
    taux_succes, dossiers_valides, total_dossiers = _taux_succes_dossiers()

    return {
        'total_mariages': Mariage.objects.count(),
        'mariages_actifs': Mariage.objects.filter(statut='actif').count(),
        'total_divorces': Divorce.objects.count(),
        'dossiers_en_cours': Dossier.objects.filter(
            statut__in=('en_attente', 'en_cours')
        ).count(),
        'dossiers_valides': dossiers_valides,
        'total_dossiers': total_dossiers,
        'total_epoux': Epoux.objects.count() + Epouse.objects.count(),
        'taux_succes': taux_succes,
        'variation_mariages_pct': variation_pct,
        'variation_mariages_dir': variation_dir,
        'chart_labels': labels,
        'chart_data': stats_mensuelles,
        'activites_recentes': _activites_recentes(),
        'now': timezone.now(),
    }


def _recettes_sept_jours(caisse):
    """Recettes par jour sur les 7 derniers jours (jours sans mouvement = 0)."""
    today = timezone.localdate()
    jours = [today - timedelta(days=i) for i in range(6, -1, -1)]
    totaux = {jour: Decimal('0.00') for jour in jours}

    mouvements = (
        MouvementCaisse.objects.filter(
            caisse=caisse,
            date_mouvement__date__gte=jours[0],
        )
        .annotate(jour=TruncDate('date_mouvement'))
        .values('jour')
        .annotate(total=Sum('montant'))
    )
    for row in mouvements:
        if row['jour'] in totaux:
            totaux[row['jour']] = row['total'] or Decimal('0.00')

    return [
        {'date': jour.strftime('%d/%m'), 'total': float(totaux[jour])}
        for jour in jours
    ]


def stats_dashboard_bourgmestre(commune):
    if not commune:
        return {
            'commune': None,
            'solde': Decimal('0.00'),
            'nb_dossiers': 0,
            'nb_mariages_commune': 0,
            'nb_divorces_commune': 0,
            'stats_graph': [],
            'recettes_semaine': 0,
            'derniere_mise_a_jour': None,
        }

    caisse, _ = CaisseCommune.objects.get_or_create(commune=commune)
    stats_graph = _recettes_sept_jours(caisse)
    recettes_semaine = sum(entry['total'] for entry in stats_graph)

    dossiers_qs = Dossier.objects.filter(commune_enregistrement=commune)
    mariages_commune = Mariage.objects.filter(dossier__commune_enregistrement=commune).count()
    divorces_commune = Divorce.objects.filter(
        mariage__dossier__commune_enregistrement=commune
    ).count()

    return {
        'commune': commune,
        'solde': caisse.solde_actuel,
        'nb_dossiers': dossiers_qs.count(),
        'nb_mariages_commune': mariages_commune,
        'nb_divorces_commune': divorces_commune,
        'stats_graph': stats_graph,
        'recettes_semaine': recettes_semaine,
        'derniere_mise_a_jour': caisse.derniere_mise_a_jour,
    }
