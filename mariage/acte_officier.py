"""Autorité signataire des actes (bourgmestre ou maire)."""
from django.db.models import Case, IntegerField, Value, When

from mariage.models import Utilisateur


def nom_complet_utilisateur(user):
    """Nom, postnom, prénom à partir du compte utilisateur."""
    if not user:
        return ''
    if hasattr(user, 'nom_complet_officiel'):
        return user.nom_complet_officiel()
    nom = (user.last_name or '').strip()
    tokens = (user.first_name or '').strip().split()
    if len(tokens) >= 2:
        postnom, prenom = tokens[0], ' '.join(tokens[1:])
    elif len(tokens) == 1:
        postnom, prenom = '', tokens[0]
    else:
        postnom, prenom = '', ''
    return ' '.join(part for part in (nom, postnom, prenom) if part)


def _autorite_queryset(role, **filters):
    """Bourgmestre ou maire avec identité renseignée en priorité."""
    return (
        Utilisateur.objects.filter(role=role, **filters)
        .annotate(
            priorite=Case(
                When(nom__gt='', then=Value(2)),
                When(last_name__gt='', then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            )
        )
        .order_by('-priorite', 'pk')
    )


def autorite_pour_dossier(dossier):
    """
    Retourne le bourgmestre de la commune d'enregistrement du dossier,
    ou le maire de la ville si le mariage est célébré à la mairie.
    """
    commune = getattr(dossier, 'commune_enregistrement', None)
    if not commune:
        return {
            'nom': '',
            'celebre_a_mairie': False,
            'titre_officier': "Officier de l'État Civil",
            'titre_fonction': '',
            'qualite': '',
            'utilisateur': None,
        }

    celebre_a_mairie = bool(getattr(dossier, 'celebre_a_mairie', False))
    if celebre_a_mairie:
        utilisateur = _autorite_queryset('maire', ville=commune.ville).first()
        titre_fonction = f"et Maire de la Ville de {commune.ville.nom}"
    else:
        utilisateur = _autorite_queryset('bourgmestre', commune=commune).first()
        titre_fonction = f"et Bourgmestre de la Commune de {commune.nom}"

    return {
        'nom': nom_complet_utilisateur(utilisateur) if utilisateur else '',
        'celebre_a_mairie': celebre_a_mairie,
        'titre_officier': "Officier de l'État Civil",
        'titre_fonction': titre_fonction,
        'qualite': f"Officier de l'État Civil {titre_fonction}",
        'utilisateur': utilisateur,
    }
