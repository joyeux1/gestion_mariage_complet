from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    Province, Utilisateur, Commune, Mariage, EmpreinteDigitale,
    Epoux, Epouse, Dossier, Paiement, Document, Temoin, Divorce, Ville,
    ProfilCitoyen, SessionCaptureMobile,
)

# ==========================================================
# CONFIGURATION DE L'UTILISATEUR (Basé sur le système Django)
# ==========================================================
@admin.register(Utilisateur)
class UtilisateurAdmin(UserAdmin):
    list_display = (
        'username', 'role', 'commune', 'ville', 'affecte_mairie',
        'epoux_lie', 'epouse_lie', 'is_staff',
    )
    list_filter = ('role', 'affecte_mairie', 'commune', 'ville')
    search_fields = ('username', 'first_name', 'last_name', 'nom', 'post_nom', 'prenom', 'email')
    fieldsets = UserAdmin.fieldsets + (
        ('Informations complémentaires', {
            'fields': (
                'nom', 'post_nom', 'prenom',
                'telephone', 'role', 'commune', 'ville', 'affecte_mairie',
                'epoux_lie', 'epouse_lie',
            ),
        }),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Informations complémentaires', {
            'fields': (
                'nom', 'post_nom', 'prenom',
                'telephone', 'role', 'commune', 'ville', 'affecte_mairie',
            ),
        }),
    )

# ==========================================================
# GESTION DES DOSSIERS (Avec Documents et Paiements liés)
# ==========================================================
class DocumentInline(admin.TabularInline):
    model = Document
    extra = 1

class PaiementInline(admin.TabularInline):
    model = Paiement
    extra = 1

@admin.register(Dossier)
class DossierAdmin(admin.ModelAdmin):
    list_display = ('numero_dossier', 'objet', 'statut', 'commune_enregistrement', 'date_creation')
    list_filter = ('statut', 'commune_enregistrement')
    search_fields = ('numero_dossier', 'objet')
    inlines = [DocumentInline, PaiementInline]

# ==========================================================
# GESTION DES ÉPOUX ET ÉPOUSES (Avec Empreintes)
# ==========================================================
@admin.register(Epoux)
class EpouxAdmin(admin.ModelAdmin):
    list_display = ('nom', 'prenom', 'telephone', 'ville_origine')
    search_fields = ('nom', 'prenom', 'numero_piece')

@admin.register(Epouse)
class EpouseAdmin(admin.ModelAdmin):
    list_display = ('nom', 'prenom', 'telephone', 'ville_origine')
    search_fields = ('nom', 'prenom', 'numero_piece')

# ==========================================================
# LE MARIAGE ET LE DIVORCE
# ==========================================================
@admin.register(Mariage)
class MariageAdmin(admin.ModelAdmin):
    list_display = ('numero_acte', 'epoux', 'epouse', 'date_mariage', 'statut')
    list_filter = ('statut', 'regime_matrimonial')
    search_fields = ('numero_acte', 'epoux__nom', 'epouse__nom')
    date_hierarchy = 'date_mariage' # Ajoute une barre de navigation temporelle

@admin.register(Divorce)
class DivorceAdmin(admin.ModelAdmin):
    list_display = ('numero_divorce', 'mariage', 'date_divorce')
    search_fields = ('numero_divorce',)

# ==========================================================
# AUTRES MODÈLES (Enregistrement simple)
# ==========================================================
admin.site.register(Province)
admin.site.register(Ville)
admin.site.register(Commune)
admin.site.register(EmpreinteDigitale)
admin.site.register(Temoin)
admin.site.register(ProfilCitoyen)
admin.site.register(SessionCaptureMobile)
