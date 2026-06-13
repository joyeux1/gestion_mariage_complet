"""Recherche de dossiers non validés (commune de l'agent) pour le workflow Nouveau Mariage."""
import hashlib
import itertools

from django.core.files.storage import default_storage
from django.db.models import Q

from .models import Dossier, EmpreinteDigitale, Epoux, Epouse, Mariage, photo_conjoint_affichage
from .verification_dossier import _post_nom_conjoint
from .permissions_commune import filtrer_dossiers_par_acces
from .services_biometrie import ReconnaissanceFacialeService
from .verification_dossier import _encodage_facial_conjoint


def queryset_dossiers_eligibles_mariage(user):
    """Dossiers non validés de la commune, sans acte de mariage existant."""
    dossiers_avec_acte = Mariage.objects.values_list('dossier_id', flat=True)
    qs = (
        Dossier.objects.filter(
            statut__in=['en_attente', 'en_cours'],
            epoux__isnull=False,
            epouse__isnull=False,
        )
        .exclude(pk__in=dossiers_avec_acte)
        .select_related(
            'epoux',
            'epouse',
            'epoux__reconnaissance_faciale',
            'epouse__reconnaissance_faciale',
            'commune_enregistrement__ville__province',
        )
        .distinct()
    )
    return filtrer_dossiers_par_acces(user, qs)


def _trouver_conjoints_par_empreinte_dossier(fichier):
    """Associe une empreinte scannée aux conjoints (Epoux / Epouse) correspondants."""
    fichier.seek(0)
    contenu = fichier.read()
    fichier.seek(0)
    if not contenu:
        return []

    upload_hash = hashlib.md5(contenu).hexdigest()
    nom_fichier = (fichier.name or '').lower()
    trouves = []
    empreintes_vues = set()

    for empreinte in EmpreinteDigitale.objects.exclude(empreinte='').iterator():
        if empreinte.pk in empreintes_vues:
            continue
        correspond = False
        if empreinte.empreinte and empreinte.empreinte.name:
            nom_stocke = empreinte.empreinte.name.lower()
            if nom_fichier and (
                nom_fichier in nom_stocke
                or nom_stocke.split('/')[-1] == nom_fichier
            ):
                correspond = True
            elif default_storage.exists(empreinte.empreinte.name):
                try:
                    with default_storage.open(empreinte.empreinte.name, 'rb') as stocke:
                        if hashlib.md5(stocke.read()).hexdigest() == upload_hash:
                            correspond = True
                except OSError:
                    pass
        if not correspond:
            continue
        empreintes_vues.add(empreinte.pk)

        epoux = Epoux.objects.filter(empreinte_digitale=empreinte).first()
        if epoux:
            trouves.append((epoux, True))
        epouse = Epouse.objects.filter(empreinte_digitale=empreinte).first()
        if epouse:
            trouves.append((epouse, False))

    return trouves


def rechercher_dossiers_empreinte(user, fichier_epoux=None, fichier_epouse=None):
    """Retourne les dossiers éligibles liés aux empreintes reconnues."""
    qs = queryset_dossiers_eligibles_mariage(user)
    dossier_ids = set()

    for fichier in (fichier_epoux, fichier_epouse):
        if not fichier:
            continue
        for conjoint, est_epoux in _trouver_conjoints_par_empreinte_dossier(fichier):
            filtre = {'epoux': conjoint} if est_epoux else {'epouse': conjoint}
            for dossier in qs.filter(**filtre):
                dossier_ids.add(dossier.pk)

    if not dossier_ids:
        return []

    return list(qs.filter(pk__in=dossier_ids)[:15])


def rechercher_dossiers_nominatif(user, nom, postnom, prenom):
    qs = queryset_dossiers_eligibles_mariage(user)
    if nom:
        qs = qs.filter(Q(epoux__nom__icontains=nom) | Q(epouse__nom__icontains=nom))
    if postnom:
        qs = qs.filter(
            Q(epoux__post_nom__icontains=postnom) | Q(epouse__post_nom__icontains=postnom)
        )
    if prenom:
        qs = qs.filter(
            Q(epoux__prenom__icontains=prenom) | Q(epouse__prenom__icontains=prenom)
        )
    return list(qs.distinct()[:15])


def catalogue_encodages_faciaux_dossiers(user):
    """Visages des conjoints sur dossiers non validés de la commune."""
    candidats = []
    for dossier in queryset_dossiers_eligibles_mariage(user).iterator():
        for role, conjoint, est_epoux in (
            ('epoux', dossier.epoux, True),
            ('epouse', dossier.epouse, False),
        ):
            enc = _encodage_facial_conjoint(conjoint)
            if enc is not None:
                candidats.append({
                    'dossier': dossier,
                    'role': role,
                    'est_epoux': est_epoux,
                    'conjoint': conjoint,
                    'encodage': enc,
                })
    return candidats


def serialiser_dossier_mariage_recherche(dossier, correspondance=None):
    commune = dossier.commune_enregistrement
    img_epoux = photo_conjoint_affichage(dossier.epoux)
    img_epouse = photo_conjoint_affichage(dossier.epouse)
    data = {
        'id': dossier.pk,
        'numero_dossier': dossier.numero_dossier,
        'statut': dossier.statut,
        'statut_label': dossier.get_statut_display(),
        'epoux': {
            'nom_complet': f"{dossier.epoux.nom} {dossier.epoux.post_nom} {dossier.epoux.prenom}".strip(),
            'photo_url': img_epoux.url if img_epoux else None,
            'photo_carte': dossier.epoux.photo_carte.url if dossier.epoux.photo_carte else None,
            'photo': dossier.epoux.photo.url if dossier.epoux.photo else None,
        },
        'epouse': {
            'nom_complet': f"{dossier.epouse.nom} {dossier.epouse.post_nom} {dossier.epouse.prenom}".strip(),
            'photo_url': img_epouse.url if img_epouse else None,
            'photo_carte': dossier.epouse.photo_carte.url if dossier.epouse.photo_carte else None,
            'photo': dossier.epouse.photo.url if dossier.epouse.photo else None,
        },
        'lieu': {
            'commune': commune.nom if commune else '—',
            'ville': commune.ville.nom if commune else '—',
            'province': commune.ville.province.nom if commune else '—',
        },
    }
    if correspondance:
        data['correspondance'] = correspondance
    return data


def meilleure_correspondance_faciale_dossier(user, encodage_capture):
    catalogue = []
    for item in catalogue_encodages_faciaux_dossiers(user):
        conjoint = item['conjoint']
        catalogue.append({
            'dossier': item['dossier'],
            'id': f"{item['dossier'].pk}-{item['role']}",
            'encodage': item['encodage'],
            'meta': {
                'role': item['role'],
                'role_label': 'Époux' if item['est_epoux'] else 'Épouse',
                'nom_complet': f"{conjoint.nom} {conjoint.post_nom} {conjoint.prenom}".strip(),
            },
        })

    if not catalogue:
        return None, catalogue

    correspondance = ReconnaissanceFacialeService.meilleure_correspondance(
        encodage_capture, catalogue
    )
    return correspondance, catalogue


def _url_image(champ_image):
    if champ_image and getattr(champ_image, 'name', None) and default_storage.exists(champ_image.name):
        return champ_image.url
    return None


def serialiser_personne_dossier_mariage(conjoint, est_epoux, dossier):
    post = _post_nom_conjoint(conjoint)
    img_affichage = photo_conjoint_affichage(conjoint)
    photo_carte_url = _url_image(conjoint.photo_carte)
    photo_profil_url = _url_image(conjoint.photo)
    depuis_carte = False
    if not photo_profil_url and img_affichage:
        url_affichage = _url_image(img_affichage)
        if url_affichage and url_affichage != photo_carte_url:
            photo_profil_url = url_affichage
    if photo_profil_url and photo_carte_url and photo_profil_url == photo_carte_url:
        depuis_carte = True

    conjoint_lie = ''
    if est_epoux and dossier.epouse_id:
        ep = dossier.epouse
        conjoint_lie = f'{ep.nom} {ep.post_nom} {ep.prenom}'.strip()
    elif not est_epoux and dossier.epoux_id:
        ex = dossier.epoux
        conjoint_lie = f'{ex.nom} {ex.post_nom} {ex.prenom}'.strip()

    commune = dossier.commune_enregistrement
    return {
        'id': conjoint.pk,
        'est_epoux': est_epoux,
        'nom': conjoint.nom,
        'postnom': post,
        'prenom': conjoint.prenom or '',
        'nom_complet': f'{conjoint.nom} {post} {conjoint.prenom or ""}'.strip(),
        'numero_piece': conjoint.numero_piece or '',
        'numero_dossier': dossier.numero_dossier,
        'dossier_statut': dossier.get_statut_display(),
        'conjoint_lie': conjoint_lie,
        'commune_enregistrement': commune.nom if commune else '—',
        'ville_enregistrement': commune.ville.nom if commune else '—',
        'province_enregistrement': commune.ville.province.nom if commune else '—',
        'photo_url': photo_profil_url,
        'photo_profil_url': photo_profil_url,
        'photo_carte_url': photo_carte_url,
        'photo_profil_depuis_carte': depuis_carte,
        'dossier_id': dossier.pk,
    }


def rechercher_dossiers_par_mot_cle(user, mot):
    """Dossiers non validés de la commune dont l'époux ou l'épouse correspond au mot-clé."""
    mot = (mot or '').strip()
    if not mot:
        return []

    qs = queryset_dossiers_eligibles_mariage(user)
    filtre = (
        Q(epoux__nom__icontains=mot)
        | Q(epoux__post_nom__icontains=mot)
        | Q(epoux__prenom__icontains=mot)
        | Q(epouse__nom__icontains=mot)
        | Q(epouse__post_nom__icontains=mot)
        | Q(epouse__prenom__icontains=mot)
    )
    return list(qs.filter(filtre).distinct().order_by('-date_creation')[:20])


def rechercher_personnes_nominatif(user, role, mot, permute=False):
    """Personnes figurant sur un dossier non validé de la commune."""
    est_epoux = role == 'epoux'
    Model = Epoux if est_epoux else Epouse
    dossier_qs = queryset_dossiers_eligibles_mariage(user)
    rel = 'dossiers_epoux' if est_epoux else 'dossiers_epouse'

    if not permute:
        filtre = (
            Q(nom__icontains=mot)
            | Q(post_nom__icontains=mot)
            | Q(prenom__icontains=mot)
        )
        qs = (
            Model.objects.filter(filtre, **{f'{rel}__in': dossier_qs})
            .distinct()
            .order_by('nom', 'post_nom', 'prenom')[:30]
        )
        resultats = []
        for conjoint in qs:
            if est_epoux:
                dossier = dossier_qs.filter(epoux=conjoint).first()
            else:
                dossier = dossier_qs.filter(epouse=conjoint).first()
            if dossier:
                resultats.append(serialiser_personne_dossier_mariage(conjoint, est_epoux, dossier))
        return resultats

    mots = [m for m in mot.split() if m.strip()]
    if len(mots) < 2:
        return []

    combos = set()
    if len(mots) == 2:
        a, b = mots
        combos.update([(a, b, ''), (a, '', b), (b, a, ''), ('', a, b)])
    else:
        reste = ' '.join(mots[3:]).strip()
        for trio in itertools.permutations(mots[:3]):
            prenom = trio[2]
            if reste:
                prenom = f'{prenom} {reste}'.strip()
            combos.add((trio[0], trio[1], prenom))

    resultats = []
    vus = set()
    for nom, postnom, prenom in combos:
        qs = Model.objects.filter(**{f'{rel}__in': dossier_qs}).distinct()
        if nom:
            qs = qs.filter(nom__icontains=nom)
        if postnom:
            qs = qs.filter(post_nom__icontains=postnom)
        if prenom:
            qs = qs.filter(prenom__icontains=prenom)
        for conjoint in qs[:15]:
            if conjoint.pk in vus:
                continue
            dossier = dossier_qs.filter(
                **({'epoux': conjoint} if est_epoux else {'epouse': conjoint})
            ).first()
            if dossier:
                vus.add(conjoint.pk)
                resultats.append(serialiser_personne_dossier_mariage(conjoint, est_epoux, dossier))
    return resultats[:30]
