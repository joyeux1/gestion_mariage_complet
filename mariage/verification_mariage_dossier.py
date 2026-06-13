"""Vérification en 2 étapes pour identifier un dossier non validé (commune de l'agent)."""
import base64

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db.models import Q

from .models import Dossier, Epouse, Epoux, photo_conjoint_affichage
from .recherche_mariage_dossier import (
    _trouver_conjoints_par_empreinte_dossier,
    catalogue_encodages_faciaux_dossiers,
    queryset_dossiers_eligibles_mariage,
    serialiser_dossier_mariage_recherche,
)
from .services_biometrie import ReconnaissanceFacialeService
from .verification_dossier import _post_nom_conjoint

MARIAGE_VERIF_SESSION_KEY = 'mariage_dossier_verif'


def etat_verif_defaut():
    return {
        'type': None,
        'epoux_ok': False,
        'epouse_ok': False,
        'dossier_id': None,
        'dossier_numero': None,
    }


def lire_etat_verif(session):
    etat = session.get(MARIAGE_VERIF_SESSION_KEY)
    if not etat:
        return etat_verif_defaut()
    base = etat_verif_defaut()
    base.update(etat)
    return base


def sauver_etat_verif(session, etat):
    session[MARIAGE_VERIF_SESSION_KEY] = etat
    session.modified = True


def reinitialiser_verif(session):
    session.pop(MARIAGE_VERIF_SESSION_KEY, None)


def verif_complete(etat):
    return bool(etat.get('epoux_ok') and etat.get('epouse_ok') and etat.get('dossier_id'))


def _dossier_pour_conjoint(user, conjoint, est_epoux):
    qs = queryset_dossiers_eligibles_mariage(user)
    if est_epoux:
        return qs.filter(epoux=conjoint).first()
    return qs.filter(epouse=conjoint).first()


def _serialiser_match_dossier(conjoint, est_epoux, dossier):
    img = photo_conjoint_affichage(conjoint)
    post_nom = _post_nom_conjoint(conjoint)
    return {
        'est_epoux': est_epoux,
        'nom_complet': f'{conjoint.nom} {post_nom} {conjoint.prenom}'.strip(),
        'photo_profil': img.url if img else None,
        'photo_carte': conjoint.photo_carte.url if conjoint.photo_carte else None,
        'numero_dossier': dossier.numero_dossier,
        'dossier_statut': dossier.statut,
        'dossier_statut_label': dossier.get_statut_display(),
        'dossier': serialiser_dossier_mariage_recherche(dossier),
    }


def _valider_dossier_etape(role, dossier, etat):
    if not dossier:
        return {
            'ok': False,
            'message': 'Aucun dossier non validé de votre commune pour cette personne.',
        }

    role_label = 'Époux' if role == 'epoux' else 'Épouse'
    if role == 'epoux':
        etat['epoux_ok'] = True
        etat['dossier_id'] = dossier.pk
        etat['dossier_numero'] = dossier.numero_dossier
        conjoint = dossier.epoux
        est_epoux = True
    else:
        if not etat.get('epoux_ok'):
            raise ValidationError('Validez d\'abord l\'époux (étape 1/2).')
        if etat.get('dossier_id') and etat['dossier_id'] != dossier.pk:
            return {
                'ok': False,
                'message': (
                    f'⛔ {role_label} sur un autre dossier (N° {dossier.numero_dossier}). '
                    f'Les deux doivent figurer sur le même dossier '
                    f'(N° {etat.get("dossier_numero", "—")}).'
                ),
                'match': _serialiser_match_dossier(
                    dossier.epouse if role == 'epouse' else dossier.epoux,
                    role == 'epoux',
                    dossier,
                ),
            }
        etat['epouse_ok'] = True
        etat['dossier_id'] = dossier.pk
        etat['dossier_numero'] = dossier.numero_dossier
        conjoint = dossier.epouse
        est_epoux = False

    return {
        'ok': True,
        'message': (
            f'{role_label} identifié — dossier N° {dossier.numero_dossier} '
            f'({"étape 2 : vérifiez l'épouse" if role == "epoux" else "couple confirmé"})'
        ),
        'match': _serialiser_match_dossier(conjoint, est_epoux, dossier),
        'dossier': serialiser_dossier_mariage_recherche(dossier),
    }


def verifier_empreinte(user, role, fichier, etat):
    role_label = 'Époux' if role == 'epoux' else 'Épouse'
    if not fichier:
        raise ValidationError(f"Scan d'empreinte requis pour l'{role_label.lower()}.")

    conjoints = _trouver_conjoints_par_empreinte_dossier(fichier)
    for conjoint, est_epoux in conjoints:
        if (role == 'epoux' and not est_epoux) or (role == 'epouse' and est_epoux):
            continue
        dossier = _dossier_pour_conjoint(user, conjoint, est_epoux)
        if dossier:
            resultat = _valider_dossier_etape(role, dossier, etat)
            if resultat.get('ok'):
                resultat['empreinte_nom'] = fichier.name
            return resultat

    return {
        'ok': False,
        'message': (
            f'Aucun dossier non validé de votre commune pour cette empreinte ({role_label}).'
        ),
    }


def verifier_nominatif(user, role, nom, postnom, prenom, etat):
    role_label = 'Époux' if role == 'epoux' else 'Épouse'
    nom = (nom or '').strip()
    if not nom:
        raise ValidationError(f'Le nom est obligatoire pour identifier l\'{role_label.lower()}.')

    qs = queryset_dossiers_eligibles_mariage(user)
    filtre = Q(epoux__nom__iexact=nom) if role == 'epoux' else Q(epouse__nom__iexact=nom)
    if postnom:
        filtre &= (
            Q(epoux__post_nom__iexact=postnom)
            if role == 'epoux'
            else Q(epouse__post_nom__iexact=postnom)
        )
    if prenom:
        filtre &= (
            Q(epoux__prenom__iexact=prenom)
            if role == 'epoux'
            else Q(epouse__prenom__iexact=prenom)
        )
    dossier = qs.filter(filtre).first()
    if dossier:
        return _valider_dossier_etape(role, dossier, etat)

    identite = f'{nom} {postnom or ""} {prenom or ""}'.strip()
    return {
        'ok': False,
        'message': (
            f'Aucun dossier non validé de votre commune pour {identite}.'
        ),
    }


def verifier_nominatif_selection(user, role, personne_id, est_epoux, etat):
    if est_epoux:
        conjoint = Epoux.objects.filter(pk=personne_id).first()
    else:
        conjoint = Epouse.objects.filter(pk=personne_id).first()

    if not conjoint:
        raise ValidationError('Personne introuvable.')

    dossier = _dossier_pour_conjoint(user, conjoint, est_epoux)
    if not dossier:
        role_label = 'Époux' if role == 'epoux' else 'Épouse'
        return {
            'ok': False,
            'message': f'{role_label} sans dossier non validé dans votre commune.',
        }
    return _valider_dossier_etape(role, dossier, etat)


def verifier_facial(user, role, image_base64, etat):
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
        content_file = ContentFile(image_data, name='verif_mariage.jpg')
        encodage_capture = ReconnaissanceFacialeService.extraire_encodage_facial(content_file)
    except ValidationError:
        raise
    except (base64.binascii.Error, ValueError) as exc:
        raise ValidationError('Image faciale invalide.') from exc

    catalogue = []
    for item in catalogue_encodages_faciaux_dossiers(user):
        if item['role'] != role:
            continue
        dossier = item['dossier']
        catalogue.append({
            'id': f'{dossier.pk}-{role}',
            'encodage': item['encodage'],
            'meta': item,
        })

    if not catalogue:
        return {
            'ok': False,
            'message': 'Aucun visage enregistré sur les dossiers non validés de votre commune.',
        }

    correspondance = ReconnaissanceFacialeService.meilleure_correspondance(
        encodage_capture, catalogue
    )
    if not correspondance or not correspondance.get('correspondance'):
        return {
            'ok': False,
            'message': 'Aucun dossier de votre commune ne correspond à ce visage.',
        }

    dossier = correspondance['meta']['dossier']
    resultat = _valider_dossier_etape(role, dossier, etat)
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
            f'dossier N° {dossier.numero_dossier}.'
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
