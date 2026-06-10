"""Filtres communs pour les listes dossiers, mariages et divorces."""
from django.db.models import Q

from .models import Commune, Dossier, Mariage
from .permissions_commune import filtrer_dossiers_par_acces


def lire_parametres_filtre(request):
    return {
        'date_debut': request.GET.get('date_debut', '').strip(),
        'date_fin': request.GET.get('date_fin', '').strip(),
        'nom': request.GET.get('nom', '').strip(),
        'statut': request.GET.get('statut', '').strip(),
        'numero': request.GET.get('numero', '').strip(),
        'commune': request.GET.get('commune', '').strip(),
    }


def filtres_actifs(params):
    return any(params.values())


def _filtrer_par_dates(qs, params, champ_date):
    if params['date_debut']:
        qs = qs.filter(**{f'{champ_date}__gte': params['date_debut']})
    if params['date_fin']:
        qs = qs.filter(**{f'{champ_date}__lte': params['date_fin']})
    return qs


def appliquer_filtres_dossier(qs, params):
    qs = _filtrer_par_dates(qs, params, 'date_creation__date')
    if params['statut']:
        qs = qs.filter(statut=params['statut'])
    if params['numero']:
        qs = qs.filter(numero_dossier__icontains=params['numero'])
    if params['nom']:
        nom = params['nom']
        qs = qs.filter(
            Q(epoux__nom__icontains=nom)
            | Q(epoux__post_nom__icontains=nom)
            | Q(epoux__prenom__icontains=nom)
            | Q(epouse__nom__icontains=nom)
            | Q(epouse__post_nom__icontains=nom)
            | Q(epouse__prenom__icontains=nom)
        )
    return qs.distinct()


def queryset_dossiers_liste(user, params, limite_defaut=10, limite_filtre=50):
    """Dossiers visibles pour l'utilisateur, avec filtres et limite adaptée."""
    qs = Dossier.objects.select_related(
        'epoux',
        'epouse',
        'epoux__reconnaissance_faciale',
        'epouse__reconnaissance_faciale',
        'commune_enregistrement',
        'utilisateur',
    ).prefetch_related('temoins').order_by('-date_creation')
    qs = filtrer_dossiers_par_acces(user, qs)
    qs = appliquer_filtres_dossier(qs, params)
    if filtres_actifs(params):
        qs = qs[:limite_filtre]
    else:
        qs = qs[:limite_defaut]
    return qs


def filtrer_mariages_par_acces(user, queryset=None):
    if queryset is None:
        queryset = Mariage.objects.all()
    from .permissions_commune import acces_toutes_communes, role_utilisateur

    role = role_utilisateur(user)
    if acces_toutes_communes(user):
        return queryset
    if role == 'MAIRE':
        from .role_permissions import ville_utilisateur
        ville = ville_utilisateur(user)
        if not ville:
            return queryset.none()
        return queryset.filter(dossier__commune_enregistrement__ville=ville)
    if user.commune_id:
        return queryset.filter(
            dossier__commune_enregistrement_id=user.commune_id
        )
    return queryset.none()


def appliquer_filtres_mariage(qs, params):
    qs = _filtrer_par_dates(qs, params, 'date_enregistrement__date')
    if params['statut']:
        qs = qs.filter(statut=params['statut'])
    if params['numero']:
        qs = qs.filter(numero_acte__icontains=params['numero'])
    if params['nom']:
        nom = params['nom']
        qs = qs.filter(
            Q(epoux__nom__icontains=nom)
            | Q(epoux__post_nom__icontains=nom)
            | Q(epoux__prenom__icontains=nom)
            | Q(epouse__nom__icontains=nom)
            | Q(epouse__post_nom__icontains=nom)
            | Q(epouse__prenom__icontains=nom)
        )
    return qs.distinct()


def appliquer_filtres_divorce(qs, params):
    qs = _filtrer_par_dates(qs, params, 'date_enregistrement__date')
    if params['numero']:
        qs = qs.filter(
            Q(numero_divorce__icontains=params['numero'])
            | Q(mariage__numero_acte__icontains=params['numero'])
        )
    if params['commune']:
        try:
            qs = qs.filter(
                mariage__dossier__commune_enregistrement_id=int(params['commune'])
            )
        except (TypeError, ValueError):
            pass
    if params['nom']:
        nom = params['nom']
        qs = qs.filter(
            Q(mariage__epoux__nom__icontains=nom)
            | Q(mariage__epoux__post_nom__icontains=nom)
            | Q(mariage__epoux__prenom__icontains=nom)
            | Q(mariage__epouse__nom__icontains=nom)
            | Q(mariage__epouse__post_nom__icontains=nom)
            | Q(mariage__epouse__prenom__icontains=nom)
        )
    return qs.distinct()


def contexte_filtres_liste(request, params, type_liste, limite_defaut, user=None):
    """Contexte template pour la barre de filtres."""
    from .permissions_commune import acces_toutes_communes, role_utilisateur

    actifs = filtres_actifs(params)
    ctx = {
        'filtres': params,
        'filtres_actifs': actifs,
        'limite_defaut': limite_defaut,
        'type_liste': type_liste,
    }

    if type_liste == 'dossier':
        ctx['statut_choices'] = Dossier.STATUS_CHOICES
        ctx['numero_label'] = 'N° dossier'
    elif type_liste == 'mariage':
        ctx['statut_choices'] = Mariage.STATUS_MARIAGE
        ctx['numero_label'] = 'N° acte'
    else:
        ctx['statut_choices'] = []
        ctx['numero_label'] = 'N° acte divorce / mariage'
        ctx['communes_filtre'] = Commune.objects.select_related(
            'ville__province'
        ).order_by('nom')

    if user and user.commune_id:
        ctx['filtre_commune_label'] = f"Commune : {user.commune.nom}"
    elif user and role_utilisateur(user) == 'MAIRE':
        from .role_permissions import ville_utilisateur
        ville = ville_utilisateur(user)
        ctx['filtre_commune_label'] = f"Ville : {ville.nom}" if ville else 'Ville non configurée'
    elif user and acces_toutes_communes(user):
        ctx['filtre_commune_label'] = 'Toutes les communes'
    else:
        ctx['filtre_commune_label'] = ''

    if actifs:
        ctx['sous_titre_liste'] = 'Résultats filtrés'
    elif type_liste == 'divorce':
        ctx['sous_titre_liste'] = (
            f'Affichage des {limite_defaut} derniers divorces (toutes communes)'
        )
    elif user and user.commune_id:
        ctx['sous_titre_liste'] = (
            f'Affichage des {limite_defaut} derniers enregistrements — '
            f'commune de {user.commune.nom}'
        )
    else:
        ctx['sous_titre_liste'] = (
            f'Affichage des {limite_defaut} derniers enregistrements'
        )

    return ctx
