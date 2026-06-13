"""Vérification anti-polygamie stricte lors de l'ouverture d'un dossier."""
import base64
import hashlib
import json

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.urls import reverse

from .models import (
    Dossier,
    EmpreinteDigitale,
    Epoux,
    Epouse,
    Mariage,
    photo_conjoint_affichage,
)
from .services_biometrie import ReconnaissanceFacialeService

DOSSIER_VERIF_SESSION_KEY = 'dossier_anti_polygamie_verif'


def etat_verif_defaut():
    return {
        'type': None,
        'epoux_ok': False,
        'epouse_ok': False,
        'empreinte_epoux': '',
        'empreinte_epouse': '',
        'identite_epoux': {},
        'identite_epouse': {},
        'empreinte_b64_epoux': '',
        'empreinte_b64_epouse': '',
        'empreinte_nom_epoux': '',
        'empreinte_nom_epouse': '',
        'photo_b64_epoux': '',
        'photo_b64_epouse': '',
    }


def lire_etat_verif(session):
    etat = session.get(DOSSIER_VERIF_SESSION_KEY)
    if not etat:
        return etat_verif_defaut()
    base = etat_verif_defaut()
    base.update(etat)
    return base


def sauver_etat_verif(session, etat):
    session[DOSSIER_VERIF_SESSION_KEY] = etat
    session.modified = True


def reinitialiser_verif(session):
    session.pop(DOSSIER_VERIF_SESSION_KEY, None)


def reinitialiser_epoux_verif(session):
    """Annule uniquement la validation de l'époux (étape 1) pour permettre une nouvelle saisie."""
    etat = lire_etat_verif(session)
    etat['epoux_ok'] = False
    etat['identite_epoux'] = {}
    etat['empreinte_epoux'] = ''
    etat['empreinte_b64_epoux'] = ''
    etat['empreinte_nom_epoux'] = ''
    etat['photo_b64_epoux'] = ''
    sauver_etat_verif(session, etat)
    return etat


def verif_complete(etat):
    return bool(etat.get('epoux_ok') and etat.get('epouse_ok'))


def _url_image(champ_image):
    if champ_image and getattr(champ_image, 'name', None) and default_storage.exists(champ_image.name):
        return champ_image.url
    return None


def _mariage_actif_pour_conjoint(conjoint, est_epoux):
    """Mariage avec acte produit encore en vigueur (non divorcé)."""
    if not conjoint:
        return None
    if est_epoux:
        return (
            Mariage.objects.filter(epoux=conjoint, statut='actif')
            .exclude(numero_acte='')
            .select_related('dossier__commune_enregistrement', 'epouse', 'epoux')
            .first()
        )
    return (
        Mariage.objects.filter(epouse=conjoint, statut='actif')
        .exclude(numero_acte='')
        .select_related('dossier__commune_enregistrement', 'epoux', 'epouse')
        .first()
    )


def _conjoint_a_mariage_actif(conjoint, est_epoux):
    return _mariage_actif_pour_conjoint(conjoint, est_epoux) is not None


def _post_nom_conjoint(conjoint):
    return getattr(conjoint, 'post_nom', '') or getattr(conjoint, 'postnom', '') or ''


def serialiser_personne_blocante(conjoint, est_epoux, mariage=None, dossier=None):
    """Données JSON pour affichage JS (photo, carte, acte)."""
    img_affichage = photo_conjoint_affichage(conjoint)
    photo_profil = _url_image(conjoint.photo)
    photo_carte = _url_image(conjoint.photo_carte)
    if not photo_profil and img_affichage:
        url_affichage = _url_image(img_affichage)
        if url_affichage and url_affichage != photo_carte:
            photo_profil = url_affichage

    post_nom = _post_nom_conjoint(conjoint)
    data = {
        'est_epoux': est_epoux,
        'nom_complet': f"{conjoint.nom} {post_nom} {conjoint.prenom}".strip(),
        'nom': conjoint.nom,
        'postnom': post_nom,
        'prenom': conjoint.prenom,
        'photo_profil': photo_profil,
        'photo_carte': photo_carte,
        'numero_piece': conjoint.numero_piece,
        'mariage_actif': False,
        'numero_acte': None,
        'date_mariage': None,
        'lieu_mariage': None,
        'statut_mariage': None,
        'acte_url': None,
        'acte_pdf_url': None,
        'dossier_numero': None,
        'dossier_statut': None,
        'dossier_statut_label': None,
    }

    if mariage and mariage.statut == 'actif':
        data.update({
            'mariage_actif': True,
            'numero_acte': mariage.numero_acte,
            'date_mariage': mariage.date_mariage.isoformat() if mariage.date_mariage else None,
            'lieu_mariage': mariage.lieu_mariage,
            'statut_mariage': mariage.get_statut_display(),
            'acte_url': reverse('mariage_detail', args=[mariage.pk]),
            'acte_pdf_url': reverse('visualiser_acte_pdf', args=[mariage.pk]),
        })
        if mariage.dossier:
            data['dossier_numero'] = mariage.dossier.numero_dossier
            data['dossier_statut'] = mariage.dossier.statut
            data['dossier_statut_label'] = mariage.dossier.get_statut_display()

    if dossier:
        data['dossier_numero'] = dossier.numero_dossier
        data['dossier_statut'] = dossier.statut
        data['dossier_statut_label'] = dossier.get_statut_display()

    return data


def _message_blocage(conjoint, est_epoux, mariage, role_label):
    post_nom = _post_nom_conjoint(conjoint)
    identite = f"{conjoint.nom} {post_nom} {conjoint.prenom}".strip()
    return (
        f"⛔ {role_label} — {identite} possède encore un mariage actif "
        f"(Acte N° {mariage.numero_acte}). Cette personne doit d'abord divorcer "
        f"avant de pouvoir se remarier. Ouverture de dossier refusée."
    )


def evaluer_conjoint_enregistre(conjoint, est_epoux, role_label):
    """
    Bloque uniquement si la personne figure sur un acte de mariage encore actif
    (union validée, non divorcée). Les dossiers non actés ou les divorces ne bloquent pas.
    """
    if not conjoint:
        return None

    mariage = _mariage_actif_pour_conjoint(conjoint, est_epoux)
    if mariage:
        return {
            'ok': False,
            'message': _message_blocage(conjoint, est_epoux, mariage, role_label),
            'match': serialiser_personne_blocante(conjoint, est_epoux, mariage=mariage),
        }

    return None


def _catalogue_encodages_faciaux(role):
    """Visages des personnes ayant un acte de mariage encore actif (selon le rôle vérifié)."""
    candidats = []
    if role == 'epoux':
        qs = (
            Epoux.objects.filter(mariage__statut='actif')
            .exclude(mariage__numero_acte='')
            .distinct()
            .select_related('reconnaissance_faciale')
        )
        for epoux in qs.iterator():
            enc = _encodage_facial_conjoint(epoux)
            if enc is not None:
                candidats.append({'conjoint': epoux, 'est_epoux': True, 'encodage': enc})
    elif role == 'epouse':
        qs = (
            Epouse.objects.filter(mariage__statut='actif')
            .exclude(mariage__numero_acte='')
            .distinct()
            .select_related('reconnaissance_faciale')
        )
        for epouse in qs.iterator():
            enc = _encodage_facial_conjoint(epouse)
            if enc is not None:
                candidats.append({'conjoint': epouse, 'est_epoux': False, 'encodage': enc})
    return candidats


def _persister_encodage_facial_conjoint(conjoint, encodage):
    """Enregistre l'encodage en base pour éviter de recalculer à chaque vérification."""
    if conjoint is None or encodage is None:
        return
    from .models import ReconnaissanceFaciale

    enc_json = json.loads(ReconnaissanceFacialeService.encoder_json(encodage))
    rf = getattr(conjoint, 'reconnaissance_faciale', None)
    if rf:
        if not rf.encodage_facial:
            rf.encodage_facial = enc_json
            rf.save(update_fields=['encodage_facial'])
        return
    rf = ReconnaissanceFaciale.objects.create(encodage_facial=enc_json)
    type(conjoint).objects.filter(pk=conjoint.pk).update(reconnaissance_faciale=rf)


def _encodage_facial_conjoint(conjoint, persister=True):
    if not conjoint:
        return None
    rf = getattr(conjoint, 'reconnaissance_faciale', None)
    if rf and rf.encodage_facial:
        return ReconnaissanceFacialeService.decoder_json(rf.encodage_facial)
    img = photo_conjoint_affichage(conjoint)
    if not img or not img.name or not default_storage.exists(img.name):
        return None
    try:
        with default_storage.open(img.name, 'rb') as fichier:
            enc = ReconnaissanceFacialeService.extraire_encodage_facial(fichier)
        if persister and enc is not None:
            _persister_encodage_facial_conjoint(conjoint, enc)
        return enc
    except ValidationError:
        return None


def _trouver_conjoints_par_empreinte(fichier, role):
    """
    Recherche par empreinte : ne retient que les personnes avec un acte de mariage actif
    (table Epoux pour role=epoux, table Epouse pour role=epouse).
    """
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

        if role == 'epoux':
            epoux = Epoux.objects.filter(empreinte_digitale=empreinte).first()
            if epoux and _conjoint_a_mariage_actif(epoux, True):
                trouves.append((epoux, True))
        elif role == 'epouse':
            epouse = Epouse.objects.filter(empreinte_digitale=empreinte).first()
            if epouse and _conjoint_a_mariage_actif(epouse, False):
                trouves.append((epouse, False))

    return trouves


def verifier_empreinte(role, fichier):
    role_label = 'Futur époux' if role == 'epoux' else 'Future épouse'
    if not fichier:
        raise ValidationError(f"Scan d'empreinte requis pour le {role_label.lower()}.")

    nom_fichier = fichier.name
    conjoints = _trouver_conjoints_par_empreinte(fichier, role)

    if not conjoints:
        return {
            'ok': True,
            'message': (
                f"{role_label} vérifié — aucun acte de mariage actif associé à cette empreinte "
                f"(personne libre de se marier ou empreinte inconnue)."
            ),
            'empreinte_nom': nom_fichier,
        }

    for conjoint, est_epoux in conjoints:
        blocage = evaluer_conjoint_enregistre(conjoint, est_epoux, role_label)
        if blocage:
            blocage['empreinte_nom'] = nom_fichier
            return blocage

    return {
        'ok': True,
        'message': (
            f"{role_label} vérifié — empreinte reconnue sans union active enregistrée "
            f"(mariage divorcé ou sans acte en vigueur)."
        ),
        'empreinte_nom': nom_fichier,
    }


def _trouver_conjoints_nominatif(nom, postnom, prenom, role):
    nom = (nom or '').strip()
    postnom = (postnom or '').strip()
    prenom = (prenom or '').strip()
    if role == 'epoux':
        qs = Epoux.objects.filter(nom__iexact=nom)
    else:
        qs = Epouse.objects.filter(nom__iexact=nom)
    if postnom:
        qs = qs.filter(post_nom__iexact=postnom)
    if prenom:
        qs = qs.filter(prenom__iexact=prenom)
    if role == 'epoux':
        return [(e, True) for e in qs]
    return [(e, False) for e in qs]


def verifier_nominatif(role, nom, postnom, prenom):
    role_label = 'Futur époux' if role == 'epoux' else 'Future épouse'
    nom = (nom or '').strip()
    if not nom:
        raise ValidationError(f"Le nom est obligatoire pour vérifier le {role_label.lower()}.")

    conjoints = _trouver_conjoints_nominatif(nom, postnom, prenom, role)
    identite = {'nom': nom, 'postnom': postnom, 'prenom': prenom}

    if not conjoints:
        return {
            'ok': True,
            'message': f"{role_label} vérifié — identité absente du système (aucun antécédent bloquant).",
            'identite': identite,
        }

    for conjoint, est_epoux in conjoints:
        blocage = evaluer_conjoint_enregistre(conjoint, est_epoux, role_label)
        if blocage:
            blocage['identite'] = identite
            return blocage

    return {
        'ok': True,
        'message': (
            f"{role_label} vérifié — identité connue mais sans mariage actif "
            f"(personne divorcée ou sans union active)."
        ),
        'identite': identite,
    }


def verifier_nominatif_selection(role, personne_id, est_epoux, est_profil_citoyen=False):
    """Vérification après sélection dans la liste nominative."""
    from .models import Epouse, Epoux, ProfilCitoyen

    role_label = 'Futur époux' if role == 'epoux' else 'Future épouse'

    if est_profil_citoyen:
        profil = ProfilCitoyen.objects.filter(pk=personne_id).first()
        if not profil:
            raise ValidationError('Personne introuvable dans les profils citoyens.')
        identite = {
            'nom': profil.nom,
            'postnom': profil.post_nom or '',
            'prenom': profil.prenom or '',
            'numero_piece': profil.numero_piece or '',
            'profil_citoyen_id': profil.pk,
        }
        return {
            'ok': True,
            'message': (
                f"{role_label} vérifié — profil citoyen « {profil.nom} {profil.prenom} » "
                f"(données préenregistrées pour le jour du mariage)."
            ),
            'identite': identite,
        }

    if est_epoux:
        conjoint = Epoux.objects.filter(pk=personne_id).first()
    else:
        conjoint = Epouse.objects.filter(pk=personne_id).first()

    if not conjoint:
        raise ValidationError('Personne introuvable. Choisissez une entrée dans la liste.')

    post_nom = _post_nom_conjoint(conjoint)
    identite = {
        'nom': conjoint.nom,
        'postnom': post_nom,
        'prenom': conjoint.prenom or '',
        'numero_piece': conjoint.numero_piece or '',
    }

    blocage = evaluer_conjoint_enregistre(conjoint, est_epoux, role_label)
    if blocage:
        blocage['identite'] = identite
        return blocage

    return {
        'ok': True,
        'message': (
            f"{role_label} vérifié — {conjoint.nom} {post_nom} "
            f"(identité connue, sans mariage actif)."
        ),
        'identite': identite,
    }


def verifier_facial(role, image_base64):
    role_label = 'Futur époux' if role == 'epoux' else 'Future épouse'
    if not image_base64:
        raise ValidationError(f"Capturez la photo du {role_label.lower()} avant de vérifier.")

    original_b64 = image_base64
    try:
        payload = image_base64
        if ';base64,' in payload:
            payload = payload.split(';base64,', 1)[1]
        elif ',' in payload:
            payload = payload.split(',', 1)[1]
        image_data = base64.b64decode(payload, validate=True)
        content_file = ContentFile(image_data, name='verif_dossier.jpg')
        encodage_capture = ReconnaissanceFacialeService.extraire_encodage_facial(content_file)
    except ValidationError:
        raise
    except (base64.binascii.Error, ValueError) as exc:
        raise ValidationError('Image faciale invalide.') from exc

    catalogue = []
    for item in _catalogue_encodages_faciaux(role):
        catalogue.append({
            'id': item['conjoint'].pk,
            'encodage': item['encodage'],
            'meta': item,
        })

    if not catalogue:
        return {
            'ok': True,
            'message': (
                f"{role_label} vérifié — aucun visage d'union active enregistré "
                f"dans le système (aucun acte de mariage actif à comparer)."
            ),
            'photo_base64': original_b64,
        }

    correspondance = ReconnaissanceFacialeService.meilleure_correspondance(
        encodage_capture, catalogue
    )

    if correspondance and correspondance.get('correspondance'):
        meta = correspondance['meta']
        conjoint = meta['conjoint']
        est_epoux = meta['est_epoux']
        blocage = evaluer_conjoint_enregistre(conjoint, est_epoux, role_label)
        if blocage:
            confiance = max(
                0,
                min(
                    100,
                    int((1 - correspondance['distance'] / ReconnaissanceFacialeService.DISTANCE_TOLERANCE) * 100),
                ),
            )
            blocage['match']['confiance_facial'] = confiance
            return blocage

        confiance = max(
            0,
            min(
                100,
                int((1 - correspondance['distance'] / ReconnaissanceFacialeService.DISTANCE_TOLERANCE) * 100),
            ),
        )
        return {
            'ok': True,
            'message': (
                f"{role_label} vérifié — visage reconnu (confiance {confiance} %) "
                f"sans acte de mariage actif."
            ),
            'photo_base64': original_b64,
        }

    return {
        'ok': True,
        'message': (
            f"{role_label} vérifié — visage non reconnu parmi les unions actives ; "
            f"aucun acte de mariage en vigueur détecté."
        ),
        'photo_base64': original_b64,
    }


def appliquer_resultat_verif(etat, type_verif, role, resultat):
    if not etat.get('type'):
        etat['type'] = type_verif
    elif etat['type'] != type_verif:
        raise ValidationError(
            'Utilisez le même mode de vérification pour l\'époux et l\'épouse.'
        )

    if role == 'epoux':
        etat['epoux_ok'] = True
        if resultat.get('empreinte_nom'):
            etat['empreinte_epoux'] = resultat['empreinte_nom']
        if resultat.get('identite'):
            etat['identite_epoux'] = resultat['identite']
        if resultat.get('empreinte_b64'):
            etat['empreinte_b64_epoux'] = resultat['empreinte_b64']
            etat['empreinte_nom_epoux'] = resultat.get('empreinte_nom', '')
        if resultat.get('photo_base64'):
            etat['photo_b64_epoux'] = resultat['photo_base64']
    else:
        if not etat.get('epoux_ok'):
            raise ValidationError(
                'Vous devez d\'abord vérifier le futur époux avant l\'épouse.'
            )
        etat['epouse_ok'] = True
        if resultat.get('empreinte_nom'):
            etat['empreinte_epouse'] = resultat['empreinte_nom']
        if resultat.get('identite'):
            etat['identite_epouse'] = resultat['identite']
        if resultat.get('empreinte_b64'):
            etat['empreinte_b64_epouse'] = resultat['empreinte_b64']
            etat['empreinte_nom_epouse'] = resultat.get('empreinte_nom', '')
        if resultat.get('photo_base64'):
            etat['photo_b64_epouse'] = resultat['photo_base64']

    return etat
