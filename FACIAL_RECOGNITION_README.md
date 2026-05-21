# Guide Complet : Reconnaissance Faciale

## 🎯 Vue d'ensemble

Votre système de gestion de mariage dispose maintenant d'une **double authentification biométrique** :
- ✅ Empreinte digitale (existant)
- ✅ Reconnaissance faciale (nouveau)

---

## 📦 Installation

### 1. Installer les dépendances

```bash
pip install -r requirements.txt
```

### 2. Dépendances système

**Linux/Ubuntu:**
```bash
sudo apt-get install libdlib-dev python3-dev
```

**macOS:**
```bash
brew install dlib cmake
```

---

## 🗄️ Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

---

## 🎨 Utilisation du service

### Extraire un encodage facial

```python
from mariage.services_biometrie import ReconnaissanceFacialeService

encodage = ReconnaissanceFacialeService.extraire_encodage_facial('photo.jpg')
```

### Comparer deux visages

```python
matches = ReconnaissanceFacialeService.comparer_visages(encodage1, encodage2)
if matches:
    print("Même personne!")
```

### Valider une photo

```python
validation = ReconnaissanceFacialeService.valider_visage('photo.jpg')
if validation['is_valide']:
    print("Photo valide")
else:
    print(f"Erreur: {validation['raison']}")
```

---

## 📊 Modèles créés

### ReconnaissanceFaciale
- `photo` : Image du visage
- `encodage_facial` : Vecteur 128D en JSON
- `is_valide` : Statut de validité
- `date_enregistrement` : Date d'ajout

### Modifications Epoux/Epouse
- `reconnaissance_faciale` : OneToOneField vers ReconnaissanceFaciale
- `verifier_biometrie_complete()` : Vérifie empreinte + facial

---

## ✅ Status

✅ Models créés  
✅ Service implémenté  
✅ Admin enrichi  
✅ Dépendances ajoutées  
⏳ Vues à implémenter  
⏳ Templates à créer  

---

**Branche : `feature/facial-recognition`**
