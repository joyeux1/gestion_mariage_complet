"""Vérification en 2 étapes (époux puis épouse) pour identifier un mariage actif à divorcer."""
import base64

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile

from .models import Divorce, Epouse, Epoux, Mariage, photo_conjoint_affichage
from .recherche_divorce import serialiser_mariage_divorce, _mariage_eligible_divorce_pour_conjoint
from .services_biometrie import ReconnaissanceFacialeService
from .verification_dossier import (
    _catalogue_encodages_faciaux,
    _encodage_facial_conjoint,
    _mariage_actif_pour_conjoint,
    _post_nom_conjoint,
    _trouver_conjoints_nominatif,
    _trouver_conjoints_par_empreinte,
    serialiser_personne_blocante,
)

DIVORCE_VERIF_SESSION_KEY = 'divorce_identification_verif'


def etat_verif_defaut():
    return {
        'type': None,
        'epoux_ok': False,
        'epouse_ok': False,
        'mariage_id': None,
        'mariage_numero_acte': None,
    }


def lire_etat_verif(session):
    etat = session.get(DIVORCE_VERIF_SESSION_KEY)
    if not etat:
        return etat_verif_defaut()
    base = etat_verif_defaut()
    base.update(etat)
    return base


def sauver_etat_verif(session, etat):
    session[DIVORCE_VERIF_SESSION_KEY] = etat
    session.modified = True


def reinitialiser_verif(session):
    session.pop(DIVORCE_VERIF_SESSION_KEY, None)


def verif_complete(etat):
    return bool(etat.get('epoux_ok') and etat.get('epouse_ok') and etat.get('mariage_id'))


def _serialiser_match_divorce(conjoint, est_epoux, mariage):
    data = serialiser_personne_blocante(conjoint, est_epoux, mariage=mariage)
    data['mariage'] = serialiser_mariage_divorce(mariage)
    return data


def _valider_mariage_etape(role, mariage, etat):
    if not mariage:
        return {
            'ok': False,
            'message': 'Aucun mariage actif éligible au divorce pour cette personne.',
        }

    role_label = 'Époux' if role == 'epoux' else 'Épouse'
    if role == 'epoux':
        etat['epoux_ok'] = True
        etat['mariage_id'] = mariage.pk
        etat['mariage_numero_acte'] = mariage.numero_acte
        conjoint = mariage.epoux
        est_epoux = True
    else:
        if not etat.get('epoux_ok'):
            raise ValidationError('Validez d\'abord l\'époux (étape 1/2).')
        if etat.get('mariage_id') and etat['mariage_id'] != mariage.pk:
            return {
                'ok': False,
                'message': (
                    f'⛔ {role_label} identifié sur un autre acte (N° {mariage.numero_acte}). '
                    f'Les deux conjoints doivent appartenir au même mariage '
                    f'(acte N° {etat.get("mariage_numero_acte", "—")}).'
                ),
                'match': _serialiser_match_divorce(
                    mariage.epouse if role == 'epouse' else mariage.epoux,
                    role == 'epoux',
                    mariage,
                ),
            }
        etat['epouse_ok'] = True
        etat['mariage_id'] = mariage.pk
        etat['mariage_numero_acte'] = mariage.numero_acte
        conjoint = mariage.epouse
        est_epoux = False

    return {
        'ok': True,
        'message': (
            f'{role_label} identifié — mariage actif N° {mariage.numero_acte} '
            f'({"étape 2 : vérifiez l'épouse" if role == "epoux" else "couple confirmé"})'
        ),
        'match': _serialiser_match_divorce(conjoint, est_epoux, mariage),
        'mariage': serialiser_mariage_divorce(mariage),
    }


def verifier_empreinte(role, fichier, etat):
    role_label = 'Époux' if role == 'epoux' else 'Épouse'
    if not fichier:
        raise ValidationError(f"Scan d'empreinte requis pour l'{role_label.lower()}.")

    conjoints = _trouver_conjoints_par_empreinte(fichier, role)
    for conjoint, est_epoux in conjoints:
        mariage = _mariage_eligible_divorce_pour_conjoint(conjoint, est_epoux)
        if mariage:
            resultat = _valider_mariage_etape(role, mariage, etat)
            if resultat.get('ok'):
                resultat['empreinte_nom'] = fichier.name
            return resultat

    return {
        'ok': False,
        'message': (
            f'Aucun mariage actif national associé à cette empreinte ({role_label}).'
        ),
    }


def verifier_nominatif(role, nom, postnom, prenom, etat):
    role_label = 'Époux' if role == 'epoux' else 'Épouse'
    nom = (nom or '').strip()
    if not nom:
        raise ValidationError(f'Le nom est obligatoire pour identifier l\'{role_label.lower()}.')

    conjoints = _trouver_conjoints_nominatif(nom, postnom, prenom, role)
    for conjoint, est_epoux in conjoints:
        mariage = _mariage_eligible_divorce_pour_conjoint(conjoint, est_epoux)
        if mariage:
            return _valider_mariage_etape(role, mariage, etat)

    identite = f'{nom} {postnom or ""} {prenom or ""}'.strip()
    return {
        'ok': False,
        'message': (
            f'Aucun mariage actif trouvé pour {identite} '
            f'— impossible de procéder au divorce sans acte référent.'
        ),
    }


def verifier_nominatif_selection(role, personne_id, est_epoux, etat):
    role_label = 'Époux' if role == 'epoux' else 'Épouse'
    if est_epoux:
        conjoint = Epoux.objects.filter(pk=personne_id).first()
    else:
        conjoint = Epouse.objects.filter(pk=personne_id).first()

    if not conjoint:
        raise ValidationError('Personne introuvable.')

    mariage = _mariage_eligible_divorce_pour_conjoint(conjoint, est_epoux)
    if not mariage:
        return {
            'ok': False,
            'message': f'{role_label} sans mariage actif éligible au divorce.',
        }
    return _valider_mariage_etape(role, mariage, etat)


def verifier_facial(role, image_base64, etat):
    role_label = 'Époux' if role == 'epoux' else 'Épouse'
    if not image_base64:
        raise ValidationError(f'Capturez la photo de l\'{role_label.lower()} avant de vérifier.')

    original_b64 = image_base64
    try:
        payload = image_base64
        if ';base64,' in payload:
            payload = payload.split(';base64,', 1)[1]
        elif ',' in payload:
            payload = payload.split(',', 1)[1]
        image_data = base64.b64decode(payload, validate=True)
        content_file = ContentFile(image_data, name='verif_divorce.jpg')
        encodage_capture = ReconnaissanceFacialeService.extraire_encodage_facial(content_file)
    except ValidationError:
        raise
    except (base64.binascii.Error, ValueError) as exc:
        raise ValidationError('Image faciale invalide.') from exc

    catalogue = []
    for item in _catalogue_encodages_faciaux(role):
        conjoint = item['conjoint']
        est_epoux = item['est_epoux']
        mariage = _mariage_eligible_divorce_pour_conjoint(conjoint, est_epoux)
        if not mariage:
            continue
        catalogue.append({
            'id': f'{mariage.pk}-{role}',
            'encodage': item['encodage'],
            'meta': {**item, 'mariage': mariage},
        })

    if not catalogue:
        return {
            'ok': False,
            'message': 'Aucun visage de mariage actif enregistré dans la base nationale.',
        }

    correspondance = ReconnaissanceFacialeService.meilleure_correspondance(
        encodage_capture, catalogue
    )
    if not correspondance or not correspondance.get('correspondance'):
        return {
            'ok': False,
            'message': 'Aucun mariage actif ne correspond à ce visage (recherche nationale).',
        }

    meta = correspondance['meta']
    mariage = meta['mariage']
    resultat = _valider_mariage_etape(role, mariage, etat)
    if resultat.get('ok'):
        confiance = max(
            0,
            min(
                100,
                int((1 - correspondance['distance'] / ReconnaissanceFacialeService.DISTANCE_TOLERANCE) * 100),
            ),
        )
        resultat['match']['confiance_facial'] = confiance
        resultat['photo_base64'] = original_b64
        resultat['message'] = (
            f'{role_label} identifié par reconnaissance faciale ({confiance} %) — '
            f'acte N° {mariage.numero_acte}.'
        )
    return resultat


def appliquer_resultat_verif(etat, type_verif, role, resultat):
    if not resultat.get('ok'):
        return etat
    if not etat.get('type'):
        etat['type'] = type_verif
    elif etat['type'] != type_verif:
        raise ValidationError(
            'Utilisez le même mode de vérification pour l\'époux et l\'épouse.'
        )
    return etat
