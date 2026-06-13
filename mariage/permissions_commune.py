"""Filtrage des données par commune selon le rôle de l'utilisateur."""

from django.db.models import Q

from .models import Commune


def role_utilisateur(user):
    """Rôle métier réel (le superuser conserve son rôle d'affectation)."""
    return (getattr(user, 'role', None) or '').upper()


def acces_toutes_communes(user):
    """Hiérarchie, ou superuser sans commune d'affectation."""
    if role_utilisateur(user) == 'HIERARCHIE':
        return True
    return bool(user.is_superuser and not user.commune_id)


def communes_accessibles(user):
    """Communes visibles pour l'utilisateur (caisse, rapports)."""
    role = role_utilisateur(user)
    if acces_toutes_communes(user):
        return Commune.objects.select_related('ville__province').order_by('nom')
    if role == 'MAIRE':
        from .role_permissions import communes_perimetre_maire
        return communes_perimetre_maire(user)
    if user.commune_id:
        return Commune.objects.filter(pk=user.commune_id).select_related('ville__province')
    return Commune.objects.none()


def filtrer_divorces_par_acces(user, queryset=None):
    """Divorces limités au périmètre communal de l'utilisateur."""
    from .models import Divorce
    from .role_permissions import ville_utilisateur

    if queryset is None:
        queryset = Divorce.objects.all()
    role = role_utilisateur(user)
    if acces_toutes_communes(user):
        return queryset
    if role == 'MAIRE':
        ville = ville_utilisateur(user)
        if not ville:
            return queryset.none()
        return queryset.filter(mariage__dossier__commune_enregistrement__ville=ville)
    if user.commune_id:
        if getattr(user, 'affecte_mairie', False):
            mairie = Commune.objects.filter(
                ville=user.commune.ville_id, est_mairie=True
            ).first()
            if mairie:
                return queryset.filter(
                    Q(mariage__dossier__commune_enregistrement=user.commune)
                    | Q(mariage__dossier__commune_enregistrement=mairie)
                )
        return queryset.filter(
            mariage__dossier__commune_enregistrement_id=user.commune_id
        )
    return queryset.none()


def libelle_perimetre_dashboard(user):
    """Libellé du périmètre affiché sur le tableau de bord."""
    from .role_permissions import ville_utilisateur

    if not user or not user.is_authenticated:
        return ''
    role = role_utilisateur(user)
    if role == 'CITOYEN':
        return 'Statistiques nationales'
    if acces_toutes_communes(user):
        return 'Toutes les communes'
    if role == 'MAIRE':
        ville = ville_utilisateur(user)
        return f"Ville de {ville.nom}" if ville else 'Périmètre non défini'
    communes = list(communes_accessibles(user))
    if len(communes) == 1:
        return f"Commune de {communes[0].nom}"
    if len(communes) > 1:
        noms = ', '.join(c.nom for c in communes[:4])
        if len(communes) > 4:
            noms += f" (+{len(communes) - 4})"
        return f"Communes : {noms}"
    return 'Aucune commune affectée'


def filtrer_dossiers_par_acces(user, queryset=None):
    """Dossiers limités à la commune / ville / toutes communes selon le rôle."""
    from .models import Dossier
    from .role_permissions import ville_utilisateur

    if queryset is None:
        queryset = Dossier.objects.all()
    role = role_utilisateur(user)
    if acces_toutes_communes(user):
        return queryset
    if role == 'MAIRE':
        ville = ville_utilisateur(user)
        if not ville:
            return queryset.none()
        return queryset.filter(commune_enregistrement__ville=ville)
    if user.commune_id:
        if getattr(user, 'affecte_mairie', False):
            mairie = Commune.objects.filter(
                ville=user.commune.ville_id, est_mairie=True
            ).first()
            if mairie:
                return queryset.filter(
                    Q(commune_enregistrement=user.commune) | Q(commune_enregistrement=mairie)
                )
        return queryset.filter(commune_enregistrement_id=user.commune_id)
    return queryset.none()


def commune_caisse_active(user, commune_id=None):
    """Commune sélectionnée pour le tableau de bord caisse."""
    accessibles = list(communes_accessibles(user))
    if not accessibles:
        return None
    if commune_id:
        for c in accessibles:
            if c.pk == int(commune_id):
                return c
    return accessibles[0]


def utilisateur_peut_acceder_caisse(user):
    role = role_utilisateur(user)
    return role in ('HIERARCHIE', 'MAIRE', 'BOURGMESTRE', 'OFFICIER', 'OPERATEUR') or user.is_superuser


def utilisateur_peut_sortir_caisse(user):
    """Seul le bourgmestre peut retirer des fonds de la caisse communale."""
    return role_utilisateur(user) == 'BOURGMESTRE' or user.is_superuser
