"""
Service de biométrie avancée pour la reconnaissance faciale.
Utilise la librairie 'face-recognition' pour traiter les images faciales.
"""
import json

from django.core.exceptions import ValidationError


def _import_face_recognition():
    try:
        import face_recognition
        return face_recognition
    except ImportError as exc:
        raise ValidationError(
            "Le module face_recognition n'est pas installé ou incompatible. "
            "Utilisez Python 3.12 (pas 3.14), activez l'environnement virtuel "
            "« environnement_virtuel », puis exécutez : pip install -r requirements.txt "
            "(sous Windows : dlib-bin remplace dlib, sans compilateur C++)."
        ) from exc


def _import_numpy():
    try:
        import numpy as np
        return np
    except ImportError as exc:
        raise ValidationError(
            "Le module numpy n'est pas installé. Exécutez : pip install numpy"
        ) from exc


class ReconnaissanceFacialeService:
    """
    Service centralisé pour la gestion de la reconnaissance faciale.
    Fournit des méthodes pour :
    - Extraire des encodages faciaux
    - Comparer des visages
    - Valider la qualité des photos
    - Détecter les fraudes par doublon facial
    """

    DISTANCE_TOLERANCE = 0.6
    MODEL = 'hog'
    MAX_IMAGE_SIDE = 640

    @staticmethod
    def _redimensionner_pil(pil):
        """Réduit les grandes images avant détection (HOG est coûteux)."""
        from PIL import Image
        w, h = pil.size
        limite = ReconnaissanceFacialeService.MAX_IMAGE_SIDE
        if max(w, h) <= limite:
            return pil
        echelle = limite / max(w, h)
        return pil.resize(
            (int(w * echelle), int(h * echelle)),
            Image.Resampling.LANCZOS,
        )

    @staticmethod
    def _pil_vers_rgb_numpy(pil):
        np = _import_numpy()
        from PIL import ImageOps
        pil = ImageOps.exif_transpose(pil)
        pil = pil.convert('RGB')
        pil = ReconnaissanceFacialeService._redimensionner_pil(pil)
        return np.ascontiguousarray(np.asarray(pil), dtype=np.uint8)

    @staticmethod
    def _verifier_compatibilite_numpy():
        """dlib / face_recognition ne supportent pas numpy 2.x."""
        np = _import_numpy()
        major = int(str(np.__version__).split('.')[0])
        if major >= 2:
            raise ValidationError(
                "numpy 2.x est incompatible avec la reconnaissance faciale (dlib). "
                "Dans l'environnement virtuel : pip install \"numpy>=1.24.3,<2.0\""
            )

    @staticmethod
    def _charger_image_rgb(image_source):
        """Charge une image en tableau numpy RGB uint8 (compatible dlib)."""
        ReconnaissanceFacialeService._verifier_compatibilite_numpy()
        try:
            from PIL import Image
        except ImportError as exc:
            raise ValidationError(
                "Le module Pillow n'est pas installé. Exécutez : pip install Pillow"
            ) from exc

        import io

        if hasattr(image_source, 'read'):
            image_source.seek(0)
            raw = image_source.read()
            image_source.seek(0)
            if not raw:
                raise ValidationError("Fichier image vide.")
            try:
                pil = Image.open(io.BytesIO(raw))
                return ReconnaissanceFacialeService._pil_vers_rgb_numpy(pil)
            except ValidationError:
                raise
            except Exception as exc:
                raise ValidationError(f"Image illisible : {exc}") from exc
        try:
            pil = Image.open(str(image_source))
            return ReconnaissanceFacialeService._pil_vers_rgb_numpy(pil)
        except Exception as exc:
            raise ValidationError(f"Image illisible : {exc}") from exc

    @staticmethod
    def _localiser_visages(image, face_recognition):
        """Détection rapide : upsample léger, agrandissement si image petite."""
        np = _import_numpy()

        for upsample in (1, 2):
            locations = face_recognition.face_locations(
                image,
                model=ReconnaissanceFacialeService.MODEL,
                number_of_times_to_upsample=upsample,
            )
            if locations:
                return locations, image

        h, w = image.shape[:2]
        if max(h, w) < 480:
            try:
                import cv2
                scale = 480 / max(h, w)
                resized = cv2.resize(
                    image,
                    (int(w * scale), int(h * scale)),
                    interpolation=cv2.INTER_LINEAR,
                )
                resized = np.ascontiguousarray(resized, dtype=np.uint8)
                locations = face_recognition.face_locations(
                    resized,
                    model=ReconnaissanceFacialeService.MODEL,
                    number_of_times_to_upsample=1,
                )
                if locations:
                    return locations, resized
            except ImportError:
                pass

        return [], image

    @staticmethod
    def extraire_encodage_facial(image_path):
        """Extrait l'encodage facial d'une image (128 dimensions)."""
        face_recognition = _import_face_recognition()

        try:
            image = ReconnaissanceFacialeService._charger_image_rgb(image_path)
            face_locations, image_travail = ReconnaissanceFacialeService._localiser_visages(
                image, face_recognition
            )

            if not face_locations:
                raise ValidationError(
                    "Aucun visage détecté sur la photo. Assurez-vous que le visage est "
                    "bien visible, éclairé et centré, puis réessayez."
                )

            if len(face_locations) > 1:
                raise ValidationError("Plusieurs visages détectés. Une seule personne par photo.")

            encodages = face_recognition.face_encodings(image_travail, face_locations)
            return encodages[0] if encodages else None

        except ValidationError:
            raise
        except Exception as e:
            raise ValidationError(f"Erreur lors de l'extraction faciale: {str(e)}")

    @staticmethod
    def comparer_visages(encodage1, encodage2):
        """Compare deux encodages faciaux - retourne True si même personne"""
        np = _import_numpy()
        try:
            distance = np.linalg.norm(encodage1 - encodage2)
            return distance < ReconnaissanceFacialeService.DISTANCE_TOLERANCE
        except Exception as e:
            raise ValidationError(f"Erreur lors de la comparaison: {str(e)}")

    @staticmethod
    def valider_visage(image_path):
        """Valide la qualité et la clarté d'une photo"""
        face_recognition = _import_face_recognition()
        try:
            image = ReconnaissanceFacialeService._charger_image_rgb(image_path)
            face_locations = face_recognition.face_locations(
                image, model=ReconnaissanceFacialeService.MODEL
            )

            if not face_locations:
                return {'is_valide': False, 'raison': 'Aucun visage détecté'}

            if len(face_locations) > 1:
                return {'is_valide': False, 'raison': 'Plusieurs visages détectés'}

            top, right, bottom, left = face_locations[0]
            face_width = right - left
            face_height = bottom - top
            face_area = face_width * face_height

            if face_area < 10000:
                return {'is_valide': False, 'raison': 'Visage trop petit'}

            return {'is_valide': True, 'raison': 'Photo valide'}

        except Exception as e:
            return {'is_valide': False, 'raison': f'Erreur: {str(e)}'}

    @staticmethod
    def detecter_visage_similar(nouveau_encodage, encodages_existants_list):
        """Détecte si un visage correspond à un dans la base"""
        np = _import_numpy()
        meilleure_distance = float('inf')
        meilleure_correspondance = None

        for encodage_existant in encodages_existants_list:
            try:
                distance = np.linalg.norm(nouveau_encodage - encodage_existant)
                if distance < meilleure_distance:
                    meilleure_distance = distance
                    meilleure_correspondance = encodage_existant
            except Exception:
                continue

        trouve = meilleure_distance < ReconnaissanceFacialeService.DISTANCE_TOLERANCE

        return {
            'trouve': trouve,
            'distance': float(meilleure_distance),
            'seuil': ReconnaissanceFacialeService.DISTANCE_TOLERANCE
        }

    @staticmethod
    def encoder_json(encodage_array):
        """Encode un array numpy en JSON pour stockage BD"""
        return json.dumps(encodage_array.tolist())

    @staticmethod
    def decoder_json(encodage_json):
        """Décode un encodage JSON en numpy array"""
        np = _import_numpy()
        if encodage_json is None:
            return None
        if isinstance(encodage_json, str):
            return np.array(json.loads(encodage_json))
        if isinstance(encodage_json, list):
            return np.array(encodage_json)
        return None

    @staticmethod
    def distance_visages(encodage1, encodage2):
        """Distance euclidienne entre deux encodages (plus bas = plus similaire)."""
        np = _import_numpy()
        return float(np.linalg.norm(encodage1 - encodage2))

    @staticmethod
    def meilleure_correspondance(nouveau_encodage, candidats):
        """
        candidats: liste de dicts {'id', 'encodage', 'meta'}
        Retourne le candidat le plus proche ou None.
        """
        np = _import_numpy()
        meilleure = None
        meilleure_distance = float('inf')

        for candidat in candidats:
            enc = candidat.get('encodage')
            if enc is None:
                continue
            try:
                distance = float(np.linalg.norm(nouveau_encodage - enc))
            except Exception:
                continue
            if distance < meilleure_distance:
                meilleure_distance = distance
                meilleure = {**candidat, 'distance': distance}

        if meilleure and meilleure_distance < ReconnaissanceFacialeService.DISTANCE_TOLERANCE:
            meilleure['correspondance'] = True
            return meilleure

        if meilleure:
            meilleure['correspondance'] = False
        return meilleure
