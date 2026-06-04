from django.urls import path
from django.views.generic import RedirectView
from . import views
from .views import BourgmestreDashboardView, DossierSyntheseView, QuickSearchView

urlpatterns = [
    # ====================
    # DASHBOARD
    # ====================
    # Le chemin vide '' signifie que c'est la page par défaut de l'application
    path('', views.DashboardView.as_view(), name='dashboard'),
    path('dashboard/api/stats/', views.DashboardStatsAPIView.as_view(), name='dashboard_stats_api'),
    path('dashboard/bourgmestre/', BourgmestreDashboardView.as_view(), name='bourgmestre_dashboard'),
    path('dashboard/bourgmestre/api/stats/', views.BourgmestreStatsAPIView.as_view(), name='bourgmestre_stats_api'),

    # ==========================
    # 1. ACCUEIL ET CONFIGURATION
    # ==========================
    path('communes/', views.CommuneListView.as_view(), name='commune_list'),
    path('communes/nouveau/', views.CommuneCreateView.as_view(), name='commune_create'),

    # ==========================
    # 2. LES CONJOINTS
    # ==========================
    path('epoux/', views.EpouxListView.as_view(), name='epoux_list'),
    path('epoux/nouveau/', views.EpouxCreateView.as_view(), name='epoux_create'),
    
    path('epouses/', views.EpouseListView.as_view(), name='epouse_list'),
    path('epouses/nouveau/', views.EpouseCreateView.as_view(), name='epouse_create'),

    # ==========================
    # 3. GESTION DES DOSSIERS
    # ==========================
    path('dossiers/', views.DossierListView.as_view(), name='dossier_list'),
    path('dossiers/nouveau/', views.DossierCreateView.as_view(), name='dossier_create'),
    path('dossiers/api/verifier-conjoint/', views.DossierVerificationAntiPolygamieAPIView.as_view(), name='dossier_verifier_conjoint'),
    path('dossiers/document/nouveau/', views.DocumentCreateView.as_view(), name='document_create'),
    path('dossiers/paiement/nouveau/', views.PaiementCreateView.as_view(), name='paiement_create'),
    path('dossiers/<int:pk>/modifier/', views.dossier_edit_view, name='dossier_edit'),

    # ==========================
    # 4. LES TÉMOINS
    # ==========================
    path('temoins/', views.TemoinListView.as_view(), name='temoin_list'),
    path('temoins/nouveau/', views.TemoinCreateView.as_view(), name='temoin_create'),

    # ==========================
    # 5. LE MARIAGE (ACTES)
    # ==========================
    path('mariages/', views.MariageListView.as_view(), name='mariage_list'),
    path('mariages/api/recherche-dossier/', views.DossierRechercheMariageAPIView.as_view(), name='mariage_recherche_dossier'),
    path('mariages/api/recherche-faciale/', views.DossierRechercheFacialeMariageAPIView.as_view(), name='mariage_recherche_faciale'),
    path('mariages/api/enregistrer-acte/', views.MariageEnregistrerActeAPIView.as_view(), name='mariage_enregistrer_acte'),
    path('mariages/<int:pk>/', views.MariageDetailView.as_view(), name='mariage_detail'),
    path('mariages/<int:pk>/acte/', views.MariageDetailView.as_view(), name='visualiser_acte_pdf'),
    path('mariages/<int:pk>/acte/embed/', views.MariageActeEmbedView.as_view(), name='visualiser_acte_embed'),
    path('mariages/nouveau/', views.MariageCreateView.as_view(), name='mariage_create'),
    path('mariages/<int:pk>/modifier/', views.MariageUpdateView.as_view(), name='mariage_update'),

    # ==========================
    # 6. RUPTURE ET BIOMÉTRIE
    # ==========================
    path('divorces/', views.DivorceListView.as_view(), name='divorce_list'),
    path('divorces/api/recherche-nominative/', views.MariageRechercheDivorceNominativeAPIView.as_view(), name='divorce_recherche_nominative'),
    path('divorces/api/recherche-empreinte/', views.MariageRechercheDivorceEmpreinteAPIView.as_view(), name='divorce_recherche_empreinte'),
    path('divorces/api/recherche-faciale/', views.MariageRechercheDivorceFacialeAPIView.as_view(), name='divorce_recherche_faciale'),
    path('divorces/api/enregistrer/', views.DivorceEnregistrerAPIView.as_view(), name='divorce_enregistrer'),
    path('divorces/<int:pk>/acte/', views.ActeDivorceDetailView.as_view(), name='acte_divorce_detail'),
    path('divorce/nouveau/', views.DivorceCreateView.as_view(), name='divorce_create'),
    path('empreinte/', RedirectView.as_view(pattern_name='empreinte_create', permanent=False)),
    path('empreinte/nouveau/', views.EmpreinteCreateView.as_view(), name='empreinte_create'),


    # Nouvelle route pour l'enregistrement rapide
    path('dossiers/synthese/', DossierSyntheseView.as_view(), name='dossier_synthese'),

    # =================
    # barre de recherche
    # ===================
    path('recherche-rapide/', QuickSearchView.as_view(), name='quick_search'),



]
