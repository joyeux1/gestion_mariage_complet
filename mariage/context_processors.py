"""Context processors Django pour les templates."""
from .role_permissions import menu_navigation, role_utilisateur, url_accueil_utilisateur


def navigation_role(request):
    user = request.user
    if not user.is_authenticated:
        return {}
    return {
        'menu_items': menu_navigation(user),
        'role_utilisateur_court': role_utilisateur(user),
        'url_accueil_user': url_accueil_utilisateur(user),
    }
