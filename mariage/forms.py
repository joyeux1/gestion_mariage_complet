from django import forms
from .models import (
    Commune, Utilisateur, Epoux, Epouse, Dossier, 
    Paiement, Document, Temoin, Mariage, Divorce, EmpreinteDigitale
)

# ==========================================
# 1. CONFIGURATION ET UTILISATEURS
# ==========================================
class CommuneForm(forms.ModelForm):
    class Meta:
        model = Commune
        fields = '__all__'

class UtilisateurForm(forms.ModelForm):
    class Meta:
        model = Utilisateur
        fields = ['username', 'email', 'telephone', 'role', 'commune', 'password']
        widgets = {
            'password': forms.PasswordInput(),
        }

# ==========================================
# 2. CONJOINTS (Époux & Épouse)
# ==========================================
class EpouxForm(forms.ModelForm):
    class Meta:
        model = Epoux
        fields = '__all__'
        widgets = {
            'date_naissance': forms.DateInput(attrs={'type': 'date'}),
            'date_delivrance': forms.DateInput(attrs={'type': 'date'}),
        }

class EpouseForm(forms.ModelForm):
    class Meta:
        model = Epouse
        fields = '__all__'
        widgets = {
            'date_naissance': forms.DateInput(attrs={'type': 'date'}),
            'date_delivrance': forms.DateInput(attrs={'type': 'date'}),
        }

# ==========================================
# 3. DOSSIER, DOCUMENTS ET PAIEMENT
# ==========================================
class DossierForm(forms.ModelForm):
    class Meta:
        model = Dossier
        fields = ['numero_dossier', 'date_depot', 'objet', 'statut', 'utilisateur', 'commune_enregistrement']
        widgets = {
            'date_depot': forms.DateInput(attrs={'type': 'date'}),
        }

class DocumentForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ['type_document', 'fichier', 'dossier']

class PaiementForm(forms.ModelForm):
    class Meta:
        model = Paiement
        fields = ['dossier', 'montant_total_du', 'montant_paye', 'type_paiement', 'preuve_paiement', 'agent_recouvreur']

# ==========================================
# 4. TÉMOINS ET MARIAGE
# ==========================================
class TemoinForm(forms.ModelForm):
    class Meta:
        model = Temoin
        fields = '__all__'
        widgets = {
            'date_naissance': forms.DateInput(attrs={'type': 'date'}),
            'date_delivrance': forms.DateInput(attrs={'type': 'date'}),
        }

class MariageForm(forms.ModelForm):
    class Meta:
        model = Mariage
        fields = [
            'numero_acte', 'date_mariage', 'lieu_mariage', 'regime_matrimonial', 
            'dossier', 'agent', 'epoux', 'epouse', 'temoins', 'remarque', 'statut'
        ]
        widgets = {
            'date_mariage': forms.DateInput(attrs={'type': 'date'}),
            'temoins': forms.CheckboxSelectMultiple(), # Permet de cocher plusieurs témoins facilement
        }

# ==========================================
# 5. DIVORCE
# ==========================================
class DivorceForm(forms.ModelForm):
    class Meta:
        model = Divorce
        fields = '__all__'
        widgets = {
            'date_divorce': forms.DateInput(attrs={'type': 'date'}),
        }

# ==========================================
# BIOMÉTRIE (Empreinte Digitale)
# ==========================================
# dans une logique de production, on ne saisit généralement pas une empreinte 
# "à la main" via un formulaire classique ; elle provient souvent d'un capteur.
# Cependant, pour que  l'interface soit complète et que l'on puisse uploader 
# des scans ou gérer les enregistrements biométriques,
# ==========================================
class EmpreinteDigitaleForm(forms.ModelForm):
    class Meta:
        model = EmpreinteDigitale
        fields = ['doigt', 'empreinte']
        widgets = {
            'doigt': forms.TextInput(attrs={'placeholder': 'Ex: Index droit'}),
        }
