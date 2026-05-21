"""
Service de biométrie avancée pour la reconnaissance faciale.
Utilise la librairie 'face-recognition' pour traiter les images faciales.
"""
import face_recognition
import cv2
import numpy as np
from django.core.files.base import ContentFile
from PIL import Image
import io
import json
from django.core.exceptions import ValidationError


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

    @staticmethod
    def extraire_encodage_facial(image_path):
        """Extrait l'encodage facial d'une image (128 dimensions)"""
        try:
            image = face_recognition.load_image_file(str(image_path))
            face_locations = face_recognition.face_locations(image, model=ReconnaissanceFacialeService.MODEL)
            
            if not face_locations:
                raise ValidationError("Aucun visage détecté sur la photo.")
            
            if len(face_locations) > 1:
                raise ValidationError("Plusieurs visages détectés. Une seule personne par photo.")
            
            encodages = face_recognition.face_encodings(image, face_locations)
            return encodages[0] if encodages else None

        except ValidationError:
            raise
        except Exception as e:
            raise ValidationError(f"Erreur lors de l'extraction faciale: {str(e)}")

    @staticmethod
    def comparer_visages(encodage1, encodage2):
        """Compare deux encodages faciaux - retourne True si même personne"""
        try:
            distance = np.linalg.norm(encodage1 - encodage2)
            return distance < ReconnaissanceFacialeService.DISTANCE_TOLERANCE
        except Exception as e:
            raise ValidationError(f"Erreur lors de la comparaison: {str(e)}")

    @staticmethod
    def valider_visage(image_path):
        """Valide la qualité et la clarté d'une photo"""
        try:
            image = face_recognition.load_image_file(str(image_path))
            face_locations = face_recognition.face_locations(image, model=ReconnaissanceFacialeService.MODEL)
            
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
        meilleure_distance = float('inf')
        meilleure_correspondance = None
        
        for encodage_existant in encodages_existants_list:
            try:
                distance = np.linalg.norm(nouveau_encodage - encodage_existant)
                if distance < meilleure_distance:
                    meilleure_distance = distance
                    meilleure_correspondance = encodage_existant
            except:
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
        if isinstance(encodage_json, str):
            return np.array(json.loads(encodage_json))
        return None
