from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.conf import settings # 1. Importez les settings


def _champ_image_utilisable(champ_image):
    """Vrai si le fichier image existe réellement sur le disque."""
    return bool(
        champ_image
        and getattr(champ_image, 'name', None)
        and default_storage.exists(champ_image.name)
    )


def photo_conjoint_affichage(conjoint):
    """Retourne le premier champ image utilisable pour un époux ou une épouse."""
    if not conjoint:
        return None
    for champ in (conjoint.photo_carte, conjoint.photo):
        if _champ_image_utilisable(champ):
            return champ
    rf = getattr(conjoint, 'reconnaissance_faciale', None)
    if rf and _champ_image_utilisable(rf.photo):
        return rf.photo
    return None


class Province(models.Model):
    nom = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return f"{self.nom}"

class Ville(models.Model):
    nom = models.CharField(max_length=100)
    province = models.ForeignKey(Province, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.nom} ({self.province.nom})"

# ==========================
# COMMUNE D'ENREGISTREMENT DU MARIAGE
# ==========================
class Commune(models.Model):
    code_postal_de_la_commune = models.CharField(max_length=100)
    nom = models.CharField(max_length=100)
    ville = models.ForeignKey(Ville, on_delete=models.CASCADE)
    est_mairie = models.BooleanField(
        default=False,
        help_text="Commune virtuelle « Mairie » pour les mariages célébrés à l'hôtel de ville.",
    )

    class Meta:
        verbose_name = 'Commune'
        verbose_name_plural = 'Communes'

    def __str__(self):
        if self.est_mairie:
            return f"Mairie de {self.ville.nom}"
        return f"{self.nom} ({self.ville.nom})"

# ==========================================================
# UTILISATEURS ET ROLES
# =========================================================
class Utilisateur(AbstractUser):
    ROLE_CHOICES = [
        ('operateur', 'Operateur de saisie'),
        ('officier', 'Officier Etat Civil'),
        ('bourgmestre', 'Bourgmestre'),
        ('maire', 'Maire'),
        ('hierarchie', 'Hierarchie'),
        ('conjoint', 'Conjoint'),
        ('citoyen', 'citoyen'),
    ]

    telephone = models.CharField(max_length=20, blank=True)
    nom = models.CharField(max_length=100, blank=True, help_text="Nom de famille (actes officiels).")
    post_nom = models.CharField(max_length=100, blank=True, help_text="Postnom (actes officiels).")
    prenom = models.CharField(max_length=100, blank=True, help_text="Prénom (actes officiels).")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    commune = models.ForeignKey(
        Commune, on_delete=models.CASCADE, null=True, blank=True,
        related_name='agents',
    )
    ville = models.ForeignKey(
        'Ville', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='maires',
        help_text="Ville d'affectation pour le maire (accès à toutes les communes + mairie).",
    )
    epoux_lie = models.ForeignKey(
        'Epoux', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='comptes_conjoint',
    )
    epouse_lie = models.ForeignKey(
        'Epouse', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='comptes_conjoint',
    )
    affecte_mairie = models.BooleanField(
        default=False,
        help_text="Agent affecté à la mairie (mariages célébrés à l'hôtel de ville).",
    )

    class Meta:
        verbose_name = "Utilisateur"
        verbose_name_plural = "Utilisateurs"

    def __str__(self):
        return f"{self.username} - {self.role}"

    def nom_complet_officiel(self):
        """Nom, postnom et prénom pour les actes (bourgmestre, maire, etc.)."""
        if self.nom or self.post_nom or self.prenom:
            return ' '.join(
                part for part in (self.nom, self.post_nom, self.prenom) if part
            ).strip()
        nom = (self.last_name or '').strip()
        tokens = (self.first_name or '').strip().split()
        if len(tokens) >= 2:
            postnom, prenom = tokens[0], ' '.join(tokens[1:])
        elif len(tokens) == 1:
            postnom, prenom = '', tokens[0]
        else:
            postnom, prenom = '', ''
        return ' '.join(part for part in (nom, postnom, prenom) if part).strip()

# ================================================
# EMPREINTE DIGITALE
# ===============================================
class EmpreinteDigitale(models.Model):
    doigt = models.CharField(max_length=50)
    empreinte = models.ImageField(upload_to='empreintes/')
    date_enregistrement = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.doigt


# ================================================
# RECONNAISSANCE FACIALE
# ===============================================
class ReconnaissanceFaciale(models.Model):
    photo = models.ImageField(upload_to='reconnaissance_faciales/', null=True, blank=True)
    encodage_facial = models.JSONField(null=True, blank=True)
    date_enregistrement = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Reconnaissance faciale #{self.pk}"

# ===========================================
# EPOUX
# ==========================================
class Epoux(models.Model):
    nom = models.CharField(max_length=100)
    post_nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    # Commune de résidence (différente de la commune d'enregistrement)
    commune_residence = models.ForeignKey(Commune, on_delete=models.SET_NULL, null=True)
    piece_identite = models.CharField(max_length=100)
    numero_piece = models.CharField(max_length=100, unique=True)
    photo_carte = models.ImageField(upload_to='cartes_identite/', null=True, blank=True)
    telephone = models.CharField(max_length=20)
    empreinte_digitale = models.OneToOneField(EmpreinteDigitale, on_delete=models.SET_NULL, null=True, blank=True)
    reconnaissance_faciale = models.OneToOneField(
        ReconnaissanceFaciale, on_delete=models.SET_NULL, null=True, blank=True
    )

    profession = models.CharField(max_length=150, null=True, blank=True)
    nom_pere = models.CharField(max_length=100, null=True, blank=True)
    nom_mere = models.CharField(max_length=100, null=True, blank=True)
    date_naissance = models.DateField(null=True, blank=True)
    lieu_naissance = models.CharField(max_length=150, null=True, blank=True)
    nationalite = models.CharField(max_length=100, null=True, blank=True)
    numero_parcelle = models.CharField(max_length=150, null=True, blank=True)
    cellule = models.CharField(max_length=150, null=True, blank=True)
    quartier = models.CharField(max_length=150, null=True, blank=True)
    ville_origine = models.CharField(max_length=150, null=True, blank=True)
    date_delivrance = models.DateField(null=True, blank=True) # CORRIGÉ : DateField avec majuscule
    lieu_delivrance = models.CharField(max_length=150, null=True, blank=True)
    photo = models.ImageField(upload_to='photos/epoux/', blank=True, null=True)

    @property
    def photo_affichage(self):
        return photo_conjoint_affichage(self)

    def verifier_si_deja_mariee(self):
        # 1. Si aucune empreinte n'est fournie, on ne peut pas faire cette vérification
        if not self.empreinte_digitale:
            return False
            
        # 2. On cherche si un mariage actif existe déjà pour cette empreinte exacte
        # On passe par la relation : mariage -> epoux -> empreinte_digitale
        query = Mariage.objects.filter(
            epoux__empreinte_digitale=self.empreinte_digitale, 
            statut='actif'
        )
        
        # 3. Si l'époux existe déjà (mode modification), on exclut son propre mariage actuel
        if self.pk:
            query = query.exclude(epoux=self)
            
        return query.exists()

    def clean(self):
        # Cette vérification fonctionne maintenant à l'ajout ET à la modification
        if self.verifier_si_deja_mariee():
            raise ValidationError("Cette empreinte digitale est déjà liée à un époux ayant un mariage actif.")

# ===========================================
# EPOUSE
# ==========================================
class Epouse(models.Model):
    nom = models.CharField(max_length=100)
    post_nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    # Commune de résidence (différente de la commune d'enregistrement)
    commune_residence = models.ForeignKey(Commune, on_delete=models.SET_NULL, null=True)
    piece_identite = models.CharField(max_length=100)
    numero_piece = models.CharField(max_length=100, unique=True)
    photo_carte = models.ImageField(upload_to='cartes_identite/', null=True, blank=True)
    telephone = models.CharField(max_length=20)
    empreinte_digitale = models.OneToOneField(EmpreinteDigitale, on_delete=models.SET_NULL, null=True, blank=True)
    reconnaissance_faciale = models.OneToOneField(
        ReconnaissanceFaciale, on_delete=models.SET_NULL, null=True, blank=True
    )

    profession = models.CharField(max_length=150, null=True, blank=True)
    nom_pere = models.CharField(max_length=100, null=True, blank=True)
    nom_mere = models.CharField(max_length=100, null=True, blank=True)
    date_naissance = models.DateField(null=True, blank=True)
    lieu_naissance = models.CharField(max_length=150, null=True, blank=True)
    nationalite = models.CharField(max_length=100, null=True, blank=True)
    numero_parcelle = models.CharField(max_length=150, null=True, blank=True)
    cellule = models.CharField(max_length=150, null=True, blank=True)
    quartier = models.CharField(max_length=150, null=True, blank=True)
    ville_origine = models.CharField(max_length=150, null=True, blank=True)
    date_delivrance = models.DateField(null=True, blank=True) # CORRIGÉ : DateField avec majuscule
    lieu_delivrance = models.CharField(max_length=150, null=True, blank=True)
    photo = models.ImageField(upload_to='photos/epouse/', blank=True, null=True)

    @property
    def photo_affichage(self):
        return photo_conjoint_affichage(self)

    def verifier_si_deja_mariee(self):
        # 1. Si aucune empreinte n'est fournie, on ne peut pas faire cette vérification
        if not self.empreinte_digitale:
            return False
            
        # 2. On cherche si un mariage actif existe déjà pour cette empreinte exacte
        query = Mariage.objects.filter(
            epouse__empreinte_digitale=self.empreinte_digitale,
            statut='actif'
        )
        
        # 3. Si l'épouse existe déjà (mode modification), on exclut son propre mariage actuel
        if self.pk:
            query = query.exclude(epouse=self)
            
        return query.exists()

    def clean(self):
        # Cette vérification fonctionne maintenant à l'ajout ET à la modification
        if self.verifier_si_deja_mariee():
            raise ValidationError("Cette empreinte digitale est déjà liée à une épouse ayant un mariage actif.")

# ==================================
# DOSSIER DE MARIAGE
# ==================================
class Dossier(models.Model):
    STATUS_CHOICES = [
        ('en_attente', 'En attente'),
        ('en_cours', 'En cours'),
        ('valide', 'Validé'),
        ('rejete', 'Rejeté'),
    ]
    numero_dossier = models.CharField(max_length=50, unique=True)

   
    # La commune où le dossier est physiquement déposé
    commune_enregistrement = models.ForeignKey(
        Commune, 
        on_delete=models.CASCADE, 
        related_name='dossiers_enregistres',
        null=True,  # Permet aux anciens dossiers de ne pas avoir de commune en BDD
        blank=True  # Permet de laisser le champ vide dans les formulaires si besoin
    )
    epoux = models.ForeignKey(Epoux, on_delete=models.CASCADE, related_name='dossiers_epoux', null=True, blank=True)
    epouse = models.ForeignKey(Epouse, on_delete=models.CASCADE, related_name='dossiers_epouse', null=True, blank=True)

    date_depot = models.DateField(null=True, blank=True)
    objet = models.CharField(max_length=255, null=True, blank=True)
    statut = models.CharField(max_length=20, choices=STATUS_CHOICES, default='en_attente')
    utilisateur = models.ForeignKey(Utilisateur, on_delete=models.CASCADE)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_mise_a_jour = models.DateTimeField(auto_now=True)
    celebre_a_mairie = models.BooleanField(
        default=False,
        help_text="Mariage célébré à la mairie (hôtel de ville) plutôt qu'en commune.",
    )

    def __str__(self):
        return self.numero_dossier


# ==================================
# PAIEMENT DES FRAIS DE DOSSIER
# ==================================
class Paiement(models.Model):
    TYPE_PAIEMENT = [
        ('avance', 'Avance'),
        ('totalite', 'Totalité'),
    ]

    dossier = models.ForeignKey(Dossier, on_delete=models.CASCADE, related_name='paiements')
    montant_total_du = models.DecimalField(max_digits=10, decimal_places=2, help_text="Le coût total fixé pour le dossier")
    montant_paye = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Montant versé")
    type_paiement = models.CharField(max_length=20, choices=TYPE_PAIEMENT, default='avance')
    date_paiement = models.DateTimeField(auto_now_add=True)
    preuve_paiement = models.FileField(upload_to='paiements/recus/', blank=True, null=True)
    agent_recouvreur = models.ForeignKey(Utilisateur, on_delete=models.SET_NULL, null=True)

    @property
    def reste_a_payer(self):
        """Calcule automatiquement le solde restant pour ce paiement spécifique."""
        return self.montant_total_du - self.montant_paye

    def __str__(self):
        return f"Paiement {self.type_paiement} - Dossier {self.dossier.numero_dossier}"

    class Meta:
        verbose_name = "Paiement"
        verbose_name_plural = "Paiements"


class CaisseCommune(models.Model):
    commune = models.OneToOneField('Commune', on_delete=models.CASCADE, related_name='caisse')
    solde_actuel = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    derniere_mise_a_jour = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Caisse {self.commune.nom} : {self.solde_actuel} $"

class MouvementCaisse(models.Model):
    TYPE_MOUVEMENT = [
        ('entree', 'Entrée'),
        ('sortie', 'Sortie'),
    ]

    caisse = models.ForeignKey(CaisseCommune, on_delete=models.CASCADE, related_name='mouvements')
    type_mouvement = models.CharField(max_length=10, choices=TYPE_MOUVEMENT, default='entree')
    motif = models.CharField(max_length=200, blank=True)
    dossier = models.ForeignKey('Dossier', on_delete=models.CASCADE, null=True, blank=True)
    paiement = models.ForeignKey(
        Paiement, on_delete=models.SET_NULL, null=True, blank=True, related_name='mouvements_caisse'
    )
    montant = models.DecimalField(max_digits=10, decimal_places=2)
    montant_total_du = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    montant_paye = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    date_mouvement = models.DateTimeField(auto_now_add=True)
    agent = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    class Meta:
        verbose_name = 'Mouvement de caisse'
        verbose_name_plural = 'Mouvements de caisse'
        ordering = ['-date_mouvement']

    def __str__(self):
        sens = '+' if self.type_mouvement == 'entree' else '−'
        return f"{sens}{self.montant} $ — {self.motif or self.get_type_mouvement_display()}"

    @property
    def montant_net(self):
        if self.type_mouvement == 'sortie':
            return -self.montant
        return self.montant

    @property
    def montant_restant(self):
        if self.montant_total_du is not None and self.montant_paye is not None:
            return self.montant_total_du - self.montant_paye
        return None


# ====================================================
# DOCUMENTS
# ====================================================
class Document(models.Model):
    TYPE_DOCUMENT = [
        ('piece_identite', 'Piece identité'),
        ('acte_naissance', 'Acte naissance'),
        ('photo', 'Photo'),
        ('certificat', 'Certificat'),
    ]
    type_document = models.CharField(max_length=100, choices=TYPE_DOCUMENT)
    fichier = models.FileField(upload_to='documents/')
    date_upload = models.DateTimeField(auto_now_add=True)
    dossier = models.ForeignKey(Dossier, on_delete=models.CASCADE, related_name='documents')

    def __str__(self):
        return self.type_document

# ==============================
# TEMOINS
# ==============================
class Temoin(models.Model):
    # La liaison indispensable vers le dossier (optionnelle ici)
    dossier = models.ForeignKey('Dossier', on_delete=models.CASCADE, related_name='temoins', null=True, blank=True)
    # Pour savoir s'il vient du côté de l'époux ou de l'épouse
    provenance = models.CharField(max_length=10, choices=[('EPOUX', 'Époux'), ('EPOUSE', 'Épouse')], null=True, blank=True)
    
    nom = models.CharField(max_length=100)
    postnom = models.CharField(max_length=100, blank=True, null=True)
    prenom = models.CharField(max_length=100, blank=True, null=True)
    numero_piece = models.CharField(max_length=100, blank=True, null=True) # Retrait de unique=True pour éviter les conflits à vide
    photo = models.ImageField(upload_to='photos/temoins/', blank=True, null=True) # Rendu optionnel pour la pré-saisie
    telephone = models.CharField(max_length=20, blank=True, null=True)

    date_naissance = models.DateField(blank=True, null=True)
    adresse = models.CharField(max_length=255, blank=True, null=True)
    piece_identite = models.CharField(max_length=100, blank=True, null=True)
    date_delivrance = models.DateField(blank=True, null=True)
    lieu_delivrance = models.CharField(max_length=150, blank=True, null=True)
    empreinte_digitale = models.OneToOneField('EmpreinteDigitale', on_delete=models.SET_NULL, null=True, blank=True)
    reconnaissance_faciale = models.OneToOneField(
        'ReconnaissanceFaciale', on_delete=models.SET_NULL, null=True, blank=True
    )

    def __str__(self):
        return f"{self.nom} {self.prenom} ({self.provenance})"

# ===========================
# MARIAGE 
# ===========================
class Mariage(models.Model):
    STATUS_MARIAGE = [
        ('actif', 'Mariage Actif'),
        ('divorce', 'Divorcé')
    ]
    numero_acte = models.CharField(max_length=50, unique=True)
    date_mariage = models.DateField()
    lieu_mariage = models.CharField(max_length=150)
    regime_matrimonial = models.CharField(max_length=100)
    dossier = models.OneToOneField(Dossier, on_delete=models.CASCADE)
    agent = models.ForeignKey(Utilisateur, on_delete=models.SET_NULL, null=True)
    epoux = models.ForeignKey(Epoux, on_delete=models.CASCADE)
    epouse = models.ForeignKey(Epouse, on_delete=models.CASCADE)
    temoins = models.ManyToManyField(Temoin)
    date_enregistrement = models.DateTimeField(auto_now_add=True)
    remarque = models.TextField(blank=True)
    statut = models.CharField(max_length=20, choices=STATUS_MARIAGE, default='actif')

    def clean(self):
        # Vérification seulement lors de la création d'un nouveau mariage (pas de PK)
        if not self.pk:
            if self.epoux.verifier_si_deja_mariee():
                raise ValidationError("L'epoux possede deja un mariage actif.")
            if self.epouse.verifier_si_deja_mariee():
                raise ValidationError("L'epouse possede deja un mariage actif.")

    def __str__(self):
        return self.numero_acte 

# ==========================
# DIVORCE
# ==========================
class Divorce(models.Model):
    numero_divorce = models.CharField(max_length=50, unique=True)
    mariage = models.OneToOneField(Mariage, on_delete=models.CASCADE)
    date_divorce = models.DateField()
    motif = models.TextField()
    decision_justice = models.FileField(upload_to='divorces/')
    agent_validation = models.ForeignKey(Utilisateur, on_delete=models.SET_NULL, null=True)
    date_enregistrement = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # Met à jour automatiquement le statut du mariage lié
        self.mariage.statut = 'divorce'
        self.mariage.save()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.numero_divorce


# ==========================
# PROFIL CITOYEN (pré-enregistrement)
# ==========================
class ProfilCitoyen(models.Model):
    SEXE_CHOICES = [('M', 'Masculin'), ('F', 'Féminin')]

    utilisateur = models.OneToOneField(
        Utilisateur, on_delete=models.CASCADE, related_name='profil_citoyen',
    )
    nom = models.CharField(max_length=100)
    post_nom = models.CharField(max_length=100, blank=True)
    prenom = models.CharField(max_length=100, blank=True)
    telephone = models.CharField(max_length=20, blank=True)
    numero_piece = models.CharField(max_length=50, blank=True)
    date_naissance = models.DateField(null=True, blank=True)
    lieu_naissance = models.CharField(max_length=150, blank=True)
    sexe = models.CharField(max_length=1, choices=SEXE_CHOICES, blank=True)
    nationalite = models.CharField(max_length=100, default='Congolaise')
    profession = models.CharField(max_length=100, blank=True)
    photo = models.ImageField(upload_to='citoyens/photos/', blank=True, null=True)
    date_mise_a_jour = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.nom} {self.post_nom} {self.prenom}".strip()


# ==========================
# CAPTURE MOBILE (téléphone / empreinte)
# ==========================
class SessionCaptureMobile(models.Model):
    TYPE_CAPTURE = [
        ('empreinte', 'Empreinte digitale'),
        ('photo', 'Photo / reconnaissance faciale'),
    ]
    CONTEXTE_CHOICES = [
        ('dossier_verif', 'Vérification dossier'),
        ('mariage', 'Mariage'),
        ('divorce', 'Divorce'),
    ]

    token = models.CharField(max_length=64, unique=True, db_index=True)
    agent = models.ForeignKey(Utilisateur, on_delete=models.CASCADE, related_name='sessions_capture')
    type_capture = models.CharField(max_length=20, choices=TYPE_CAPTURE)
    role_verif = models.CharField(max_length=10, blank=True)
    contexte = models.CharField(max_length=30, choices=CONTEXTE_CHOICES, default='dossier_verif')
    fichier = models.FileField(upload_to='capture_mobile/', blank=True, null=True)
    image_base64 = models.TextField(blank=True)
    consomme = models.BooleanField(default=False)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_expiration = models.DateTimeField()

    def __str__(self):
        return f"Capture {self.token[:8]}… ({self.type_capture})"