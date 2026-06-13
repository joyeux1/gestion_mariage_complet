from django.test import TestCase

from mariage.models import Commune, Province, Utilisateur, Ville
from mariage.roles import ROLES_ACCES_NATIONAL, ROLES_ACCES_PROVINCE

from .models import Parcelle, QuittanceParcellaire
from .permissions import filtrer_quittances_par_acces


class QuittanceFiltrageGeographiqueTests(TestCase):
    def setUp(self):
        self.province_a = Province.objects.create(nom='Kinshasa')
        self.province_b = Province.objects.create(nom='Katanga')
        ville_a = Ville.objects.create(nom='Kinshasa-Ville', province=self.province_a)
        ville_b = Ville.objects.create(nom='Lubumbashi', province=self.province_b)
        self.commune_a = Commune.objects.create(
            nom='Gombe', code_postal_de_la_commune='001', ville=ville_a,
        )
        self.commune_b = Commune.objects.create(
            nom='Kenya', code_postal_de_la_commune='002', ville=ville_b,
        )
        parcelle_a = Parcelle.objects.create(
            numero_cadastre='CAD-001',
            proprietaire='Dupont',
            adresse='Av. du Commerce',
            commune=self.commune_a,
        )
        parcelle_b = Parcelle.objects.create(
            numero_cadastre='CAD-002',
            proprietaire='Martin',
            adresse='Rue Principale',
            commune=self.commune_b,
        )
        QuittanceParcellaire.objects.create(
            parcelle=parcelle_a, montant='100.00', periode='2024',
            date='2024-06-01', commune=self.commune_a,
        )
        QuittanceParcellaire.objects.create(
            parcelle=parcelle_b, montant='200.00', periode='2024',
            date='2024-06-01', commune=self.commune_b,
        )
        self.gouverneur = Utilisateur.objects.create_user(
            username='gov_test',
            password='test',
            role='gouverneur',
            province_affectation=self.province_a,
        )
        self.president = Utilisateur.objects.create_user(
            username='pres_test',
            password='test',
            role='president',
        )

    def test_gouverneur_voit_uniquement_sa_province(self):
        qs = filtrer_quittances_par_acces(self.gouverneur)
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().commune, self.commune_a)

    def test_president_voit_toutes_les_quittances(self):
        qs = filtrer_quittances_par_acces(self.president)
        self.assertEqual(qs.count(), 2)
