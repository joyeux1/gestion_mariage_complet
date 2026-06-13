"""Filtres pour les actes officiels (mariage, divorce)."""
from datetime import date

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()

MOIS_FR = (
    '',
    'janvier',
    'février',
    'mars',
    'avril',
    'mai',
    'juin',
    'juillet',
    'août',
    'septembre',
    'octobre',
    'novembre',
    'décembre',
)


@register.filter
def mois_fr(value):
    if not value:
        return ''
    try:
        return MOIS_FR[value.month]
    except (AttributeError, IndexError):
        return ''


@register.filter
def age_ans(value):
    if not value:
        return ''
    today = date.today()
    ans = today.year - value.year
    if (today.month, today.day) < (value.month, value.day):
        ans -= 1
    return ans


@register.filter
def nom_complet_conjoint(conjoint):
    if not conjoint:
        return ''
    parts = [conjoint.nom, getattr(conjoint, 'post_nom', ''), conjoint.prenom]
    return ' '.join(p for p in parts if p).strip()


@register.filter
def nom_complet_temoin(temoin):
    if not temoin:
        return ''
    parts = [
        temoin.nom,
        getattr(temoin, 'postnom', '') or '',
        getattr(temoin, 'prenom', '') or '',
    ]
    return ' '.join(p for p in parts if p).strip()


@register.simple_tag
def champ_acte(value, width='medium'):
    """Valeur remplie ou pointillés (style formulaire officiel)."""
    if value not in (None, ''):
        return mark_safe(f'<span class="acte-val">{escape(str(value))}</span>')
    return mark_safe(f'<span class="acte-leader acte-leader-{width}"></span>')


@register.simple_tag
def points(width='medium'):
    """Ligne pointillée vide."""
    return mark_safe(f'<span class="acte-leader acte-leader-{width}"></span>')

@register.simple_tag
def autorite_acte(dossier):
    from mariage.acte_officier import autorite_pour_dossier
    return autorite_pour_dossier(dossier)


@register.simple_tag
def titre_officier(user):
    if not user or not user.is_authenticated:
        return "Officier de l'État Civil"
    role = (getattr(user, 'role', '') or '').lower()
    nom = user.get_full_name() or user.username
    if role == 'bourgmestre':
        return f"{nom}, Officier de l'État Civil et Bourgmestre"
    return f"{nom}, Officier de l'État Civil"
