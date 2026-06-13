from django.db import migrations, models


def migrer_identite_depuis_django(apps, schema_editor):
    Utilisateur = apps.get_model('mariage', 'Utilisateur')
    for user in Utilisateur.objects.all():
        if user.nom or user.prenom:
            continue
        nom = (user.last_name or '').strip()
        tokens = (user.first_name or '').strip().split()
        if len(tokens) >= 2:
            user.post_nom = tokens[0]
            user.prenom = ' '.join(tokens[1:])
        elif len(tokens) == 1:
            user.prenom = tokens[0]
        if nom:
            user.nom = nom
        if nom or user.prenom or user.post_nom:
            user.save(update_fields=['nom', 'post_nom', 'prenom'])


class Migration(migrations.Migration):

    dependencies = [
        ('mariage', '0010_mouvementcaisse_motif_paiement_sortie'),
    ]

    operations = [
        migrations.AddField(
            model_name='utilisateur',
            name='nom',
            field=models.CharField(blank=True, help_text='Nom de famille (actes officiels).', max_length=100),
        ),
        migrations.AddField(
            model_name='utilisateur',
            name='post_nom',
            field=models.CharField(blank=True, help_text='Postnom (actes officiels).', max_length=100),
        ),
        migrations.AddField(
            model_name='utilisateur',
            name='prenom',
            field=models.CharField(blank=True, help_text='Prénom (actes officiels).', max_length=100),
        ),
        migrations.RunPython(migrer_identite_depuis_django, migrations.RunPython.noop),
    ]
