from django.db import models


class Parcelle(models.Model):
    numero_cadastre = models.CharField(max_length=100, unique=True)
    proprietaire = models.CharField(max_length=200)
    adresse = models.CharField(max_length=255)
    commune = models.ForeignKey(
        'mariage.Commune',
        on_delete=models.CASCADE,
        related_name='parcelles',
    )

    class Meta:
        verbose_name = 'Parcelle'
        verbose_name_plural = 'Parcelles'
        ordering = ['numero_cadastre']

    def __str__(self):
        return f"{self.numero_cadastre} — {self.proprietaire}"


class QuittanceParcellaire(models.Model):
    parcelle = models.ForeignKey(
        Parcelle,
        on_delete=models.CASCADE,
        related_name='quittances',
    )
    montant = models.DecimalField(max_digits=12, decimal_places=2)
    periode = models.CharField(
        max_length=50,
        help_text="Ex. 2024, 2024-T1, année fiscale…",
    )
    date = models.DateField()
    commune = models.ForeignKey(
        'mariage.Commune',
        on_delete=models.CASCADE,
        related_name='quittances_parcellaires',
        help_text="Commune de rattachement pour le filtrage géographique.",
    )

    class Meta:
        verbose_name = 'Quittance parcellaire'
        verbose_name_plural = 'Quittances parcellaires'
        ordering = ['-date', '-pk']

    def __str__(self):
        return f"Quittance {self.parcelle.numero_cadastre} — {self.periode}"
