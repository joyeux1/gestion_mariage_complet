"""Filtrage des données par commune selon le rôle de l'utilisateur."""

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
        if not user.commune_id:
            return Commune.objects.none()
        return Commune.objects.filter(
            ville_id=user.commune.ville_id
        ).select_related('ville__province').order_by('nom')
    if user.commune_id:
        return Commune.objects.filter(pk=user.commune_id).select_related('ville__province')
    return Commune.objects.none()


def filtrer_dossiers_par_acces(user, queryset=None):
    """Dossiers limités à la commune / ville / toutes communes selon le rôle."""
    from .models import Dossier

    if queryset is None:
        queryset = Dossier.objects.all()
    role = role_utilisateur(user)
    if acces_toutes_communes(user):
        return queryset
    if role == 'MAIRE':
        if not user.commune_id:
            return queryset.none()
        return queryset.filter(commune_enregistrement__ville_id=user.commune.ville_id)
    if user.commune_id:
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
