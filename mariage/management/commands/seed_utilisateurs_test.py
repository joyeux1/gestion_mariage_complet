"""Crée un utilisateur de test par rôle (mot de passe : test1234)."""
from django.core.management.base import BaseCommand

from mariage.models import Commune, Mariage, Province, Utilisateur, Ville
from mariage.role_permissions import mairie_commune_ville


class Command(BaseCommand):
    help = "Crée les utilisateurs de test par rôle (mot de passe : test1234)."

    MOT_DE_PASSE = 'test1234'

    def handle(self, *args, **options):
        commune = (
            Commune.objects.filter(est_mairie=False)
            .select_related('ville')
            .order_by('pk')
            .first()
        )
        if not commune:
            self.stderr.write(self.style.ERROR('Aucune commune trouvée. Lancez seed_demo_mariage d\'abord.'))
            return

        ville = commune.ville
        mairie_commune_ville(ville)

        mariage_actif = (
            Mariage.objects.filter(statut='actif')
            .select_related('epoux', 'epouse')
            .first()
        )

        specs = [
            {
                'username': 'test_operateur',
                'first_name': 'Opérateur',
                'last_name': 'Test',
                'role': 'operateur',
                'commune': commune,
                'ville': None,
                'affecte_mairie': False,
            },
            {
                'username': 'test_officier',
                'first_name': 'Officier',
                'last_name': 'Test',
                'role': 'officier',
                'commune': commune,
                'ville': None,
                'affecte_mairie': False,
            },
            {
                'username': 'test_bourgmestre',
                'nom': 'Test',
                'post_nom': '',
                'prenom': 'Bourgmestre',
                'first_name': 'Bourgmestre',
                'last_name': 'Test',
                'role': 'bourgmestre',
                'commune': commune,
                'ville': None,
                'affecte_mairie': False,
            },
            {
                'username': 'test_maire',
                'nom': 'Test',
                'post_nom': '',
                'prenom': 'Maire',
                'first_name': 'Maire',
                'last_name': 'Test',
                'role': 'maire',
                'commune': None,
                'ville': ville,
                'affecte_mairie': False,
            },
            {
                'username': 'test_president',
                'first_name': 'Président',
                'last_name': 'Test',
                'role': 'president',
                'commune': None,
                'ville': None,
                'province_affectation': None,
                'affecte_mairie': False,
            },
            {
                'username': 'test_gouverneur',
                'first_name': 'Gouverneur',
                'last_name': 'Test',
                'role': 'gouverneur',
                'commune': None,
                'ville': None,
                'province_affectation': ville.province,
                'affecte_mairie': False,
            },
            {
                'username': 'test_operateur_mairie',
                'first_name': 'Opérateur Mairie',
                'last_name': 'Test',
                'role': 'operateur',
                'commune': commune,
                'ville': None,
                'affecte_mairie': True,
            },
            {
                'username': 'test_officier_mairie',
                'first_name': 'Officier Mairie',
                'last_name': 'Test',
                'role': 'officier',
                'commune': commune,
                'ville': None,
                'affecte_mairie': True,
            },
            {
                'username': 'test_citoyen',
                'first_name': 'Citoyen',
                'last_name': 'Test',
                'role': 'citoyen',
                'commune': None,
                'ville': None,
                'affecte_mairie': False,
            },
        ]

        if mariage_actif:
            specs.append({
                'username': 'test_conjoint_epoux',
                'first_name': 'Conjoint',
                'last_name': 'Époux',
                'role': 'conjoint',
                'commune': None,
                'ville': None,
                'affecte_mairie': False,
                'epoux_lie': mariage_actif.epoux,
                'epouse_lie': None,
            })
            specs.append({
                'username': 'test_conjoint_epouse',
                'first_name': 'Conjointe',
                'last_name': 'Épouse',
                'role': 'conjoint',
                'commune': None,
                'ville': None,
                'affecte_mairie': False,
                'epoux_lie': None,
                'epouse_lie': mariage_actif.epouse,
            })

        crees = 0
        maj = 0
        for spec in specs:
            username = spec['username']
            defaults = {
                'first_name': spec.get('first_name', ''),
                'last_name': spec.get('last_name', ''),
                'nom': spec.get('nom', spec.get('last_name', '')),
                'post_nom': spec.get('post_nom', ''),
                'prenom': spec.get('prenom', spec.get('first_name', '')),
                'email': f'{username}@test.local',
                'role': spec['role'],
                'commune': spec.get('commune'),
                'ville': spec.get('ville'),
                'province_affectation': spec.get('province_affectation'),
                'affecte_mairie': spec.get('affecte_mairie', False),
                'is_staff': False,
                'is_superuser': False,
            }
            user, created = Utilisateur.objects.get_or_create(username=username, defaults=defaults)
            if created:
                user.set_password(self.MOT_DE_PASSE)
                crees += 1
            else:
                for key, val in defaults.items():
                    setattr(user, key, val)
                user.set_password(self.MOT_DE_PASSE)
                maj += 1
            user.epoux_lie = spec.get('epoux_lie')
            user.epouse_lie = spec.get('epouse_lie')
            user.save()

        self.stdout.write(self.style.SUCCESS(
            f'Utilisateurs de test prêts ({crees} créés, {maj} mis à jour). '
            f'Commune de référence : {commune.nom} — Ville : {ville.nom}'
        ))
        self.stdout.write(f'Mot de passe pour tous : {self.MOT_DE_PASSE}')
        self.stdout.write('')
        self.stdout.write('Comptes :')
        for spec in specs:
            extra = ''
            if spec.get('affecte_mairie'):
                extra = ' (mairie)'
            elif spec.get('province_affectation'):
                extra = f' (province {spec["province_affectation"].nom})'
            elif spec.get('ville'):
                extra = f' (ville {spec["ville"].nom})'
            elif spec.get('commune'):
                extra = f' ({spec["commune"].nom})'
            self.stdout.write(f"  - {spec['username']} -> {spec['role']}{extra}")
