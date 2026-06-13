# Generated manually for mouvements caisse communale

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mariage', '0009_alter_commune_options_commune_est_mairie_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='mouvementcaisse',
            name='type_mouvement',
            field=models.CharField(
                choices=[('entree', 'Entrée'), ('sortie', 'Sortie')],
                default='entree',
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name='mouvementcaisse',
            name='motif',
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name='mouvementcaisse',
            name='paiement',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='mouvements_caisse',
                to='mariage.paiement',
            ),
        ),
        migrations.AddField(
            model_name='mouvementcaisse',
            name='montant_total_du',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name='mouvementcaisse',
            name='montant_paye',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        migrations.AlterField(
            model_name='mouvementcaisse',
            name='dossier',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to='mariage.dossier',
            ),
        ),
        migrations.AlterModelOptions(
            name='mouvementcaisse',
            options={
                'ordering': ['-date_mouvement'],
                'verbose_name': 'Mouvement de caisse',
                'verbose_name_plural': 'Mouvements de caisse',
            },
        ),
    ]
