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
    Mariage,
    MouvementCaisse,
)
from .permissions_commune import (
    acces_toutes_communes,
    filtrer_divorces_par_acces,
    filtrer_dossiers_par_acces,
    libelle_perimetre_dashboard,
    role_utilisateur,
)
from .liste_filtres import filtrer_mariages_par_acces

MOIS_FR = [
    'Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Juin',
    'Juil', 'Aoû', 'Sep', 'Oct', 'Nov', 'Déc',
]


def _querysets_perimetre(user):
    """Querysets mariages / dossiers / divorces selon le périmètre de l'utilisateur."""
    if not user or not user.is_authenticated:
        return (
            Mariage.objects.all(),
            Dossier.objects.all(),
            Divorce.objects.all(),
        )

    if role_utilisateur(user) == 'CITOYEN' or acces_toutes_communes(user):
        return (
            Mariage.objects.all(),
            Dossier.objects.all(),
            Divorce.objects.all(),
        )

    return (
        filtrer_mariages_par_acces(user),
        filtrer_dossiers_par_acces(user),
        filtrer_divorces_par_acces(user),
    )


def _evolution_mariages_mensuelle(mariages_qs):
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
            mariages_qs.filter(
                date_enregistrement__date__gte=start,
                date_enregistrement__date__lt=end,
            ).count()
        )

    return labels, data


def _variation_mariages_mois(mariages_qs):
    """Variation en % des mariages ce mois vs le mois précédent."""
    now = timezone.now()
    debut_mois = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if debut_mois.month == 1:
        debut_mois_prec = debut_mois.replace(year=debut_mois.year - 1, month=12)
    else:
        debut_mois_prec = debut_mois.replace(month=debut_mois.month - 1)

    ce_mois = mariages_qs.filter(date_enregistrement__gte=debut_mois).count()
    mois_prec = mariages_qs.filter(
        date_enregistrement__gte=debut_mois_prec,
        date_enregistrement__lt=debut_mois,
    ).count()

    if mois_prec == 0:
        return ce_mois, (100 if ce_mois else 0), 'up' if ce_mois else 'neutral'

    pct = round((ce_mois - mois_prec) / mois_prec * 100)
    direction = 'up' if pct >= 0 else 'down'
    return ce_mois, pct, direction


def _taux_succes_dossiers(dossiers_qs):
    total = dossiers_qs.count()
    if not total:
        return 0, 0, 0
    valides = dossiers_qs.filter(statut='valide').count()
    taux = round(valides / total * 100)
    return taux, valides, total


def _citoyens_perimetre(dossiers_qs):
    """Époux et épouses liés aux dossiers du périmètre."""
    epoux = dossiers_qs.exclude(epoux_id__isnull=True).values('epoux_id').distinct().count()
    epouses = dossiers_qs.exclude(epouse_id__isnull=True).values('epouse_id').distinct().count()
    return epoux + epouses


def _activites_recentes(mariages_qs, divorces_qs, limit=8):
    activites = []

    for mariage in (
        mariages_qs.select_related('epoux', 'epouse')
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
        divorces_qs.select_related('mariage__epoux', 'mariage__epouse')
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


def stats_dashboard_general(user=None):
    """Statistiques du tableau de bord filtrées selon le périmètre de l'utilisateur."""
    mariages_qs, dossiers_qs, divorces_qs = _querysets_perimetre(user)
    labels, stats_mensuelles = _evolution_mariages_mensuelle(mariages_qs)
    _, variation_pct, variation_dir = _variation_mariages_mois(mariages_qs)
    taux_succes, dossiers_valides, total_dossiers = _taux_succes_dossiers(dossiers_qs)

    return {
        'total_mariages': mariages_qs.count(),
        'mariages_actifs': mariages_qs.filter(statut='actif').count(),
        'total_divorces': divorces_qs.count(),
        'dossiers_en_cours': dossiers_qs.filter(
            statut__in=('en_attente', 'en_cours')
        ).count(),
        'dossiers_valides': dossiers_valides,
        'total_dossiers': total_dossiers,
        'total_epoux': _citoyens_perimetre(dossiers_qs),
        'taux_succes': taux_succes,
        'variation_mariages_pct': variation_pct,
        'variation_mariages_dir': variation_dir,
        'chart_labels': labels,
        'chart_data': stats_mensuelles,
        'activites_recentes': _activites_recentes(mariages_qs, divorces_qs),
        'perimetre_label': libelle_perimetre_dashboard(user) if user else '',
        'now': timezone.now(),
    }


def _recettes_sept_jours(caisse):
    """Recettes nettes par jour sur les 7 derniers jours (entrées − sorties)."""
    from django.db.models import Case, F, When

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
        .annotate(
            total=Sum(
                Case(
                    When(type_mouvement='sortie', then=-F('montant')),
                    default=F('montant'),
                )
            )
        )
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
