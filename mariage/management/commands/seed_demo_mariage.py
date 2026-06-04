from django.core.management.base import BaseCommand
from django.utils import timezone

from mariage.models import (
    Province, Ville, Commune, Utilisateur,
    Epoux, Epouse, Dossier, Mariage,
)


class Command(BaseCommand):
    help = "Crée des données de démonstration pour le registre des mariages."

    def handle(self, *args, **options):
        province, _ = Province.objects.get_or_create(nom='Nord-Kivu')
        ville, _ = Ville.objects.get_or_create(nom='Butembo', province=province)
        commune, _ = Commune.objects.get_or_create(
            nom='Bulengera',
            ville=ville,
            defaults={'code_postal_de_la_commune': '6140'},
        )

        agent = Utilisateur.objects.filter(username='joyeux').first()
        if not agent:
            agent = Utilisateur.objects.create_superuser(
                username='joyeux',
                email='joyeux@example.com',
                password='1234',
                role='officier',
            )
            agent.commune = commune
            agent.save()

        epoux, _ = Epoux.objects.get_or_create(
            numero_piece='EP-001-DEMO',
            defaults={
                'nom': 'KASEREKA',
                'post_nom': 'MBUSA',
                'prenom': 'Joyeux',
                'piece_identite': 'Carte électeur',
                'telephone': '0990000001',
                'commune_residence': commune,
                'lieu_naissance': 'Butembo',
            },
        )

        epouse, _ = Epouse.objects.get_or_create(
            numero_piece='EP-002-DEMO',
            defaults={
                'nom': 'KAVIRA',
                'post_nom': 'MASIKA',
                'prenom': 'Alliance',
                'piece_identite': 'Carte électeur',
                'telephone': '0990000002',
                'commune_residence': commune,
                'lieu_naissance': 'Beni',
            },
        )

        dossier, created_d = Dossier.objects.get_or_create(
            numero_dossier='DOS-2026-001',
            defaults={
                'commune_enregistrement': commune,
                'epoux': epoux,
                'epouse': epouse,
                'date_depot': timezone.now().date(),
                'objet': 'Demande de mariage civil',
                'statut': 'valide',
                'utilisateur': agent,
            },
        )

        if not Mariage.objects.filter(numero_acte='ACTE-2026-001').exists():
            Mariage.objects.create(
                numero_acte='ACTE-2026-001',
                date_mariage=timezone.now().date(),
                lieu_mariage=f'Commune de {commune.nom}',
                regime_matrimonial='Communauté de biens',
                dossier=dossier,
                agent=agent,
                epoux=epoux,
                epouse=epouse,
                statut='actif',
                remarque='Acte de démonstration',
            )
            self.stdout.write(self.style.SUCCESS('Acte de mariage ACTE-2026-001 créé.'))
        else:
            self.stdout.write('Acte de démonstration déjà présent.')

        dossier2, _ = Dossier.objects.get_or_create(
            numero_dossier='DOS-2026-002',
            defaults={
                'commune_enregistrement': commune,
                'epoux': epoux,
                'epouse': epouse,
                'statut': 'en_cours',
                'utilisateur': agent,
                'objet': 'Dossier en attente d\'acte',
            },
        )
        if created_d or dossier2:
            self.stdout.write(self.style.SUCCESS('Données de démonstration prêtes. Consultez /mariages/'))
