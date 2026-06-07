"""Vérification anti-polygamie stricte lors de l'ouverture d'un dossier."""
import base64
import hashlib

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

STATUTS_DOSSIER_BLOQUANTS = ('en_cours', 'valide', 'ouvert')


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


def verif_complete(etat):
    return bool(etat.get('epoux_ok') and etat.get('epouse_ok'))


def _url_image(champ_image):
    if champ_image and getattr(champ_image, 'name', None) and default_storage.exists(champ_image.name):
        return champ_image.url
    return None


def _mariage_actif_pour_conjoint(conjoint, est_epoux):
    if not conjoint:
        return None
    if est_epoux:
        return (
            Mariage.objects.filter(epoux=conjoint, statut='actif')
            .select_related('dossier', 'epouse', 'epoux')
            .first()
        )
    return (
        Mariage.objects.filter(epouse=conjoint, statut='actif')
        .select_related('dossier', 'epoux', 'epouse')
        .first()
    )


def _dossier_bloquant_pour_conjoint(conjoint, est_epoux):
    """Dossier en cours / validé / ouvert sans divorce sur le mariage lié."""
    if not conjoint:
        return None
    if est_epoux:
        qs = Dossier.objects.filter(epoux=conjoint, statut__in=STATUTS_DOSSIER_BLOQUANTS)
    else:
        qs = Dossier.objects.filter(epouse=conjoint, statut__in=STATUTS_DOSSIER_BLOQUANTS)
    for dossier in qs.select_related('epoux', 'epouse'):
        mariage = Mariage.objects.filter(dossier=dossier).first()
        if mariage and mariage.statut == 'divorce':
            continue
        if mariage and mariage.statut == 'actif':
            return dossier, mariage
        if not mariage:
            return dossier, None
    return None


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


def _message_blocage(conjoint, est_epoux, mariage, dossier, role_label):
    post_nom = _post_nom_conjoint(conjoint)
    identite = f"{conjoint.nom} {post_nom} {conjoint.prenom}".strip()
    if mariage and mariage.statut == 'actif':
        return (
            f"⛔ {role_label} — {identite} possède encore un mariage actif "
            f"(Acte N° {mariage.numero_acte}). Cette personne doit d'abord divorcer "
            f"avant de pouvoir se remarier. Ouverture de dossier refusée."
        )
    if dossier:
        return (
            f"ALERTE — {role_label} : {identite} est déjà enregistré(e) dans le système "
            f"(Dossier N° {dossier.numero_dossier}, statut : {dossier.get_statut_display()}). "
            f"Ouverture refusée."
        )
    return f"ALERTE — {role_label} : {identite} ne peut pas ouvrir un nouveau dossier."


def evaluer_conjoint_enregistre(conjoint, est_epoux, role_label):
    """
    Évalue une personne déjà en base.
    Retourne None si la vérification peut passer (divorcé, jamais marié activement, etc.).
    Retourne dict {ok: False, message, match} si bloqué.
    """
    if not conjoint:
        return None

    mariage = _mariage_actif_pour_conjoint(conjoint, est_epoux)
    if mariage:
        return {
            'ok': False,
            'message': _message_blocage(conjoint, est_epoux, mariage, mariage.dossier, role_label),
            'match': serialiser_personne_blocante(conjoint, est_epoux, mariage=mariage),
        }

    dossier_info = _dossier_bloquant_pour_conjoint(conjoint, est_epoux)
    if dossier_info:
        dossier, mariage_lie = dossier_info
        if mariage_lie and mariage_lie.statut == 'actif':
            return {
                'ok': False,
                'message': _message_blocage(conjoint, est_epoux, mariage_lie, dossier, role_label),
                'match': serialiser_personne_blocante(
                    conjoint, est_epoux, mariage=mariage_lie, dossier=dossier
                ),
            }
        return {
            'ok': False,
            'message': _message_blocage(conjoint, est_epoux, None, dossier, role_label),
            'match': serialiser_personne_blocante(conjoint, est_epoux, dossier=dossier),
        }

    return None


def _catalogue_encodages_faciaux():
    candidats = []
    for epoux in Epoux.objects.select_related('reconnaissance_faciale').iterator():
        enc = _encodage_facial_conjoint(epoux)
        if enc is not None:
            candidats.append({'conjoint': epoux, 'est_epoux': True, 'encodage': enc})
    for epouse in Epouse.objects.select_related('reconnaissance_faciale').iterator():
        enc = _encodage_facial_conjoint(epouse)
        if enc is not None:
            candidats.append({'conjoint': epouse, 'est_epoux': False, 'encodage': enc})
    return candidats


def _encodage_facial_conjoint(conjoint):
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
            return ReconnaissanceFacialeService.extraire_encodage_facial(fichier)
    except ValidationError:
        return None


def _trouver_conjoints_par_empreinte(fichier):
    """Recherche par empreinte sur toute la base (toutes communes)."""
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


def verifier_empreinte(role, fichier):
    role_label = 'Futur époux' if role == 'epoux' else 'Future épouse'
    if not fichier:
        raise ValidationError(f"Scan d'empreinte requis pour le {role_label.lower()}.")

    nom_fichier = fichier.name
    conjoints = _trouver_conjoints_par_empreinte(fichier)

    if not conjoints:
        return {
            'ok': True,
            'message': f"{role_label} vérifié — personne non reconnue dans le système (aucun antécédent bloquant).",
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
            f"{role_label} vérifié — personne reconnue mais sans mariage actif ni dossier bloquant "
            f"(divorcé(e) ou jamais marié(e) activement)."
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
    for item in _catalogue_encodages_faciaux():
        catalogue.append({
            'id': item['conjoint'].pk,
            'encodage': item['encodage'],
            'meta': item,
        })

    if not catalogue:
        return {
            'ok': True,
            'message': f"{role_label} vérifié — visage inconnu du système (aucun antécédent bloquant).",
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
                f"sans mariage actif ni dossier bloquant."
            ),
            'photo_base64': original_b64,
        }

    return {
        'ok': True,
        'message': f"{role_label} vérifié — visage non reconnu ; aucun antécédent bloquant.",
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
