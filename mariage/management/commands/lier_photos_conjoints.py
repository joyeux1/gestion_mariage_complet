from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand

from mariage.models import Dossier, Epoux, Epouse, photo_conjoint_affichage


class Command(BaseCommand):
    help = (
        "Associe une photo de carte aux conjoints des dossiers qui n'en ont pas encore "
        "(utilise les images déjà présentes dans media/cartes_identite/)."
    )

    def handle(self, *args, **options):
        dossier_dir = Path(settings.MEDIA_ROOT) / 'cartes_identite'
        images = sorted(
            list(dossier_dir.glob('*.jpg'))
            + list(dossier_dir.glob('*.JPG'))
            + list(dossier_dir.glob('*.jpeg'))
            + list(dossier_dir.glob('*.png'))
        )
        if not images:
            self.stderr.write(
                self.style.ERROR(
                    f"Aucune image dans {dossier_dir}. "
                    "Ajoutez des photos dans media/cartes_identite/ ou créez un dossier avec des fichiers."
                )
            )
            return

        conjoints_ids = set()
        from django.db.models import Q

        for dossier in Dossier.objects.filter(
            Q(epoux__isnull=False) | Q(epouse__isnull=False)
        ):
            if dossier.epoux_id:
                conjoints_ids.add(('epoux', dossier.epoux_id))
            if dossier.epouse_id:
                conjoints_ids.add(('epouse', dossier.epouse_id))

        epoux_ids = [cid for kind, cid in conjoints_ids if kind == 'epoux']
        epouse_ids = [cid for kind, cid in conjoints_ids if kind == 'epouse']

        nb = 0
        idx = 0
        for epoux in Epoux.objects.filter(pk__in=epoux_ids).order_by('pk'):
            if photo_conjoint_affichage(epoux):
                continue
            image = images[idx % len(images)]
            idx += 1
            with image.open('rb') as f:
                epoux.photo_carte.save(image.name, File(f), save=True)
            nb += 1
            self.stdout.write(f"  Epoux #{epoux.pk} ({epoux.nom}) <- {image.name}")

        for epouse in Epouse.objects.filter(pk__in=epouse_ids).order_by('pk'):
            if photo_conjoint_affichage(epouse):
                continue
            image = images[idx % len(images)]
            idx += 1
            with image.open('rb') as f:
                epouse.photo_carte.save(image.name, File(f), save=True)
            nb += 1
            self.stdout.write(f"  Epouse #{epouse.pk} ({epouse.nom}) <- {image.name}")

        self.stdout.write(self.style.SUCCESS(f"{nb} photo(s) associée(s). Rechargez /dossiers/."))
