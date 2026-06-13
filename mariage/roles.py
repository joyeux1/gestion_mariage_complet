"""Constantes et helpers pour les rôles d'autorité (remplacement de « hiérarchie »)."""

ROLES_ACCES_NATIONAL = frozenset({
    'PRESIDENT',
    'AGENT_PRESIDENT',
    'PREMIER_MINISTRE',
    'AGENT_PREMIER_MINISTRE',
    'MINISTRE_NATIONAL',
    'AGENT_MINISTRE_NATIONAL',
})

ROLES_ACCES_PROVINCE = frozenset({
    'GOUVERNEUR',
    'AGENT_GOUVERNEUR',
})

ROLES_AUTORITE = ROLES_ACCES_NATIONAL | ROLES_ACCES_PROVINCE

ROLES_AUTORITE_LISTE = sorted(ROLES_AUTORITE)


def role_utilisateur_upper(user):
    return (getattr(user, 'role', None) or '').upper()


def est_autorite_nationale(user):
    return role_utilisateur_upper(user) in ROLES_ACCES_NATIONAL


def est_autorite_provinciale(user):
    return role_utilisateur_upper(user) in ROLES_ACCES_PROVINCE


def est_autorite(user):
    return role_utilisateur_upper(user) in ROLES_AUTORITE
