"""Permissions, menus et redirections selon le rôle utilisateur."""
from django.urls import reverse

ROLES_PORTAIL_PUBLIC = ('CONJOINT', 'CITOYEN')
ROLES_AGENT_COMMUNE = ('OPERATEUR', 'OFFICIER', 'BOURGMESTRE')
ROLES_AGENT_MAIRIE = ('OPERATEUR', 'OFFICIER')  # avec affecte_mairie=True


def role_utilisateur(user):
    if not user or not user.is_authenticated:
        return ''
    if user.is_superuser:
        return 'HIERARCHIE'
    return (getattr(user, 'role', None) or '').upper()


def est_portail_public(user):
    return role_utilisateur(user) in ROLES_PORTAIL_PUBLIC


def url_accueil_utilisateur(user):
    """URL de redirection après connexion."""
    role = role_utilisateur(user)
    mapping = {
        'MAIRE': 'dashboard_maire',
        'HIERARCHIE': 'dashboard_hierarchie',
        'CONJOINT': 'portal_conjoint',
        'CITOYEN': 'portal_citoyen',
        'OPERATEUR': 'dossier_list',
    }
    name = mapping.get(role, 'dashboard')
    try:
        return reverse(name)
    except Exception:
        return reverse('dashboard')


def _item(url_name, label, icon, active_keys=None):
    return {
        'url_name': url_name,
        'label': label,
        'icon': icon,
        'active_keys': active_keys or [url_name],
    }


def menu_navigation(user):
    """Éléments du menu latéral selon le rôle."""
    if not user or not user.is_authenticated:
        return []

    role = role_utilisateur(user)

    if role == 'CITOYEN':
        return [
            _item('portal_citoyen', 'Statistiques publiques', 'bi-bar-chart', ['portal_citoyen']),
            _item('profil_citoyen_edit', 'Mon profil civil', 'bi-person-vcard', ['profil_citoyen']),
        ]

    if role == 'CONJOINT':
        return [
            _item('portal_conjoint', 'Mon acte de mariage', 'bi-file-earmark-heart', ['portal_conjoint']),
        ]

    if role == 'MAIRE':
        return [
            _item('dashboard_maire', 'Tableau de bord — Mairie', 'bi-building', ['dashboard_maire']),
            _item('dossier_list', 'Dossiers (ville)', 'bi-folder-fill', ['dossier']),
            _item('mariage_list', 'Mariages (ville)', 'bi-heart-fill', ['mariage']),
            _item('divorce_list', 'Divorces (national)', 'bi-heartbreak-fill', ['divorce']),
            _item('bourgmestre_dashboard', 'Caisses communales', 'bi-cash-coin', ['bourgmestre']),
        ]

    if role == 'HIERARCHIE':
        return [
            _item('dashboard_hierarchie', 'Tableau de bord — Hiérarchie', 'bi-globe2', ['dashboard_hierarchie']),
            _item('dossier_list', 'Dossiers', 'bi-folder-fill', ['dossier']),
            _item('mariage_list', 'Mariages', 'bi-heart-fill', ['mariage']),
            _item('divorce_list', 'Divorces', 'bi-heartbreak-fill', ['divorce']),
            _item('bourgmestre_dashboard', 'Caisses (toutes communes)', 'bi-cash-coin', ['bourgmestre']),
        ]

    if role == 'OPERATEUR':
        return [
            _item('dossier_list', 'Dossiers', 'bi-folder-fill', ['dossier']),
            _item('bourgmestre_dashboard', 'Caisse de la commune', 'bi-cash-coin', ['bourgmestre']),
        ]

    # Officier, Bourgmestre (commune)
    items = [
        _item('dashboard', 'Tableau de bord', 'bi-speedometer2', ['dashboard']),
        _item('dossier_list', 'Dossiers', 'bi-folder-fill', ['dossier']),
        _item('mariage_list', 'Mariage', 'bi-heart-fill', ['mariage']),
        _item('divorce_list', 'Divorce', 'bi-heartbreak-fill', ['divorce']),
        _item('bourgmestre_dashboard', 'Caisse de la commune', 'bi-cash-coin', ['bourgmestre']),
    ]
    return items


def urls_interdites_par_role():
    """URL names interdits par rôle (redirection si accès direct)."""
    return {
        'OPERATEUR': {
            'dashboard', 'mariage_list', 'mariage_create', 'mariage_detail',
            'mariage_update', 'divorce_list', 'divorce_create', 'acte_divorce_detail',
            'commune_list', 'commune_create', 'epoux_list', 'epouse_list',
        },
        'CITOYEN': None,  # tout sauf portail
        'CONJOINT': None,
    }


def utilisateur_peut_acceder_vue(user, url_name):
    """Vérifie si l'utilisateur peut accéder à une vue nommée."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    role = role_utilisateur(user)

    if role in ROLES_PORTAIL_PUBLIC:
        allowed = {i['url_name'] for i in menu_navigation(user)}
        allowed.add('logout')
        return url_name in allowed or url_name.startswith('portal_') or url_name.startswith('profil_')

    interdits = urls_interdites_par_role().get(role, set())
    if interdits and url_name in interdits:
        return False

    if role == 'MAIRE':
        return url_name not in {'commune_create', 'dossier_create'} or url_name in {
            i['url_name'] for i in menu_navigation(user)
        }

    return True


def ville_utilisateur(user):
    """Ville de périmètre pour le maire."""
    if user.ville_id:
        return user.ville
    if user.commune_id:
        return user.commune.ville
    return None


def communes_perimetre_maire(user):
    from .models import Commune
    ville = ville_utilisateur(user)
    if not ville:
        return Commune.objects.none()
    return Commune.objects.filter(ville=ville).select_related('ville__province')


def mairie_commune_ville(ville):
    """Commune virtuelle « Mairie » pour une ville."""
    from .models import Commune
    if not ville:
        return None
    mairie, _ = Commune.objects.get_or_create(
        ville=ville,
        est_mairie=True,
        defaults={
            'nom': f"Mairie de {ville.nom}",
            'code_postal_de_la_commune': 'MAIRIE',
        },
    )
    return mairie
