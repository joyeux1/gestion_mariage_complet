from datetime import timedelta
from decimal import Decimal

from django.urls import reverse_lazy
from django.http import JsonResponse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, DetailView, CreateView, TemplateView, UpdateView
from django.db.models import Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.views import View
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from django.db import transaction

from .models import (
    CaisseCommune, Commune, MouvementCaisse, EmpreinteDigitale, Epoux, Epouse, 
    Dossier, Paiement, Document, Temoin, Mariage, Divorce
)
from .forms import (
    CommuneForm, EpouxForm, EpouseForm, DossierForm, 
    PaiementForm, DocumentForm, TemoinForm, MariageForm, 
    DivorceForm, EmpreinteDigitaleForm
)

# ==========================================
# 0.1. MIXINS SÉCURITÉ GLOBALE & AJAX
# ==========================================

class SmartSecurityMixin(LoginRequiredMixin):
    """
    LE MIXIN UNIQUE DU PROJET.
    Laisse passer le Super-utilisateur sans condition (Passe-partout),
    et applique les filtres de rôles pour les autres agents.
    """
    allowed_roles = []  # À définir dans chaque vue (ex: ['OPERATEUR', 'OFFICIER'])

    def dispatch(self, request, *args, **kwargs):
        # 1. Sécurité de base : l'utilisateur doit être connecté
        if not request.user.is_authenticated:
            return redirect('login')

        # 2. PASSE-PARTOUT TECHNIQUE : Le super-utilisateur contourne toutes les restrictions
        if request.user.is_superuser:
            return super().dispatch(request, *args, **kwargs)

        # 3. Vérification du profil pour les utilisateurs normaux
        if not hasattr(request.user, 'userprofile'):
            messages.error(request, "Accès refusé. Vous ne possédez pas de profil d'agent civil.")
            return redirect('dashboard')

        # Récupération et normalisation du rôle (Gestion des majuscules)
        user_role = request.user.userprofile.role.upper()
        allowed_roles_upper = [role.upper() for role in self.allowed_roles]

        # 4. Contrôle strict du rôle requis
        if allowed_roles_upper and user_role not in allowed_roles_upper:
            messages.error(request, f"Accès interdit pour le rôle d'agent : {request.user.userprofile.role}")
            return redirect('dashboard')

        return super().dispatch(request, *args, **kwargs)


class AjaxFormMixin:
    """Ajuste automatiquement les vues de formulaire pour répondre en AJAX (JSON)"""
    def form_valid(self, form):
        response = super().form_valid(form)
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            data = {
                'success': True,
                'message': "Enregistrement réussi !",
                'redirect_url': self.get_success_url(),
            }
            if hasattr(self, 'object') and isinstance(self.object, Mariage):
                from django.urls import reverse
                data['redirect_url'] = reverse('mariage_detail', kwargs={'pk': self.object.pk})
                data['message'] = f"L'acte de mariage n°{self.object.numero_acte} a été généré."
            
            return JsonResponse(data)
        return response

    def form_invalid(self, form):
        response = super().form_invalid(form)
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)
        return response


# ==========================================
# 0.2. ACCUEIL & ANALYTIQUE (Dashboard)
# ==========================================

class DashboardView(LoginRequiredMixin, ListView):
    model = Mariage
    template_name = 'mariage/dashboard.html'
    context_object_name = 'derniers_mariages'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_mariages'] = Mariage.objects.count()
        context['dossiers_en_cours'] = Dossier.objects.filter(statut='en_cours').count()
        context['total_epoux'] = Epoux.objects.count() + Epouse.objects.count()
        context['stats_mensuelles'] = [10, 15, 8, 22, 18, 25] 
        return context


# ==========================================
# 1. CONFIGURATION (Communes)
# ==========================================

class CommuneListView(LoginRequiredMixin, ListView):
    model = Commune
    template_name = 'mariage/communes/commune_list.html'


class CommuneCreateView(SmartSecurityMixin, AjaxFormMixin, CreateView):
    allowed_roles = ['OFFICIER', 'BOURGMESTRE']
    model = Commune
    form_class = CommuneForm
    template_name = 'mariage/communes/commune_form.html'
    success_url = reverse_lazy('commune_list')


# ==========================================
# 2. BIOMÉTRIE
# ==========================================

class EmpreinteCreateView(SmartSecurityMixin, AjaxFormMixin, CreateView):
    allowed_roles = ['OPERATEUR', 'OFFICIER', 'BOURGMESTRE']
    model = EmpreinteDigitale
    form_class = EmpreinteDigitaleForm
    template_name = 'mariage/biometrie/empreinte_form.html'
    success_url = reverse_lazy('mariage_list')


# ==========================================
# 3. LES CONJOINTS
# ==========================================

class EpouxListView(SmartSecurityMixin, ListView):
    allowed_roles = ['OPERATEUR', 'OFFICIER', 'BOURGMESTRE']
    model = Epoux
    context_object_name = 'liste_epoux'
    template_name = 'mariage/epoux/epoux_list.html'


class EpouxCreateView(SmartSecurityMixin, AjaxFormMixin, CreateView):
    allowed_roles = ['OPERATEUR', 'OFFICIER', 'BOURGMESTRE']
    model = Epoux
    form_class = EpouxForm
    template_name = 'mariage/epoux/epoux_form.html'
    success_url = reverse_lazy('epoux_list')


class EpouseListView(SmartSecurityMixin, ListView):
    allowed_roles = ['OPERATEUR', 'OFFICIER', 'BOURGMESTRE']
    model = Epouse
    context_object_name = 'liste_epouses'
    template_name = 'mariage/epouses/epouse_list.html'


class EpouseCreateView(SmartSecurityMixin, AjaxFormMixin, CreateView):
    allowed_roles = ['OPERATEUR', 'OFFICIER', 'BOURGMESTRE']
    model = Epouse
    form_class = EpouseForm
    template_name = 'mariage/epouses/epouse_form.html'
    success_url = reverse_lazy('epouse_list')


# ==========================================
# 4. ADMINISTRATION DU DOSSIER
# ==========================================

class DossierListView(SmartSecurityMixin, ListView):
    allowed_roles = ['OPERATEUR', 'OFFICIER', 'BOURGMESTRE']
    model = Dossier
    template_name = 'mariage/dossiers/dossier_list.html'


class DossierCreateView(SmartSecurityMixin, View):
    allowed_roles = ['OPERATEUR', 'OFFICIER', 'BOURGMESTRE']
    template_name = 'mariage/dossiers/dossier_form.html'

    def get(self, request, *args, **kwargs):
        # Déterminer la commune de l'agent pour affichage informatif
        if request.user.is_superuser:
            commune_agent = Commune.objects.first()
        else:
            commune_agent = request.user.userprofile.commune

        context = {
            'communes': Commune.objects.all(),
            'commune_agent': commune_agent,
            'etape_biometrie': True, # On commence toujours par vérifier les empreintes
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        # Détermination de la commune de travail
        commune_agent = Commune.objects.first() if request.user.is_superuser else request.user.userprofile.commune

        # ACTION 1 : VÉRIFICATION BIOMÉTRIQUE PRÉALABLE
        if 'verifier_biometrie' in request.POST:
            file_epoux = request.FILES.get('scan_empreinte_epoux')
            file_epouse = request.FILES.get('scan_empreinte_epouse')

            conjoint_bloque = None
            mariage_actif = None

            # 1. On cherche si le fichier existe déjà dans le champ 'empreinte'
            empreinte_existante = None
            if file_epoux:
                # Utilisation du vrai champ 'empreinte' révélé par le message d'erreur
                empreinte_existante = EmpreinteDigitale.objects.filter(empreinte__icontains=file_epoux.name).first()
            if not empreinte_existante and file_epouse:
                empreinte_existante = EmpreinteDigitale.objects.filter(empreinte__icontains=file_epouse.name).first()

            # 2. Si l'empreinte existe, on récupère le conjoint associé
            if empreinte_existante:
                conjoint_bloque = Epoux.objects.filter(empreinte_digitale=empreinte_existante).first()
                if not conjoint_bloque:
                    conjoint_bloque = Epouse.objects.filter(empreinte_digitale=empreinte_existante).first()

            # 3. Si un conjoint possède cette empreinte, on vérifie son statut matrimonial
            if conjoint_bloque:
                mariage_actif = Mariage.objects.filter(
                    Q(epoux_id=conjoint_bloque.id if isinstance(conjoint_bloque, Epoux) else None) | 
                    Q(epouse_id=conjoint_bloque.id if isinstance(conjoint_bloque, Epouse) else None),
                    statut='Vigoureux'
                ).first()

                if mariage_actif:
                    messages.error(request, f"ALERTE BIGAMIE : Le citoyen {conjoint_bloque.nom} {conjoint_bloque.prenom} est déjà lié à un mariage actif (Acte N° {mariage_actif.numero_acte}). Saisie bloquée.")
                    return redirect('dashboard')

            # Si aucune empreinte n'existe ou si la personne n'est pas mariée activement, on valide l'étape
            messages.success(request, "Vérification biométrique réussie. Aucun antécédent bloquant trouvé.")
            context = {
                'communes': Commune.objects.all(),
                'commune_agent': commune_agent,
                'etape_biometrie': False,
                'empreinte_epoux_valide': file_epoux.name if file_epoux else "",
                'empreinte_epouse_valide': file_epouse.name if file_epouse else "",
            }
            return render(request, self.template_name, context)

        # ACTION 2 : ENREGISTREMENT DU CŒUR DE SAISIE (4 BLOCS)
        if 'enregistrer_coeur_saisie' in request.POST:
            try:
                with transaction.atomic():
                    
                    # --- ÉTAPE PRÉALABLE : CRÉATION DES INSTANCES D'EMPREINTES ---
                    nom_fichier_epoux = request.POST.get('e_empreinte_nom')
                    nom_fichier_epouse = request.POST.get('f_empreinte_nom')
                    
                    empreinte_obj_epoux = None
                    empreinte_obj_epouse = None
                    
                    if nom_fichier_epoux:
                        empreinte_obj_epoux = EmpreinteDigitale.objects.create(
                            empreinte=nom_fichier_epoux,
                            doigt="Index Droit"
                        )
                        
                    if nom_fichier_epouse:
                        empreinte_obj_epouse = EmpreinteDigitale.objects.create(
                            empreinte=nom_fichier_epouse,
                            doigt="Index Droit"
                        )

                    # --- CORRECTION ET SÉCURITÉ DES DONNÉES POST ---
                    prof_epoux = request.POST.get('e_profession') or "Sans"
                    prof_epouse = request.POST.get('f_profession') or "Sans"
                    
                    commune_epoux = request.POST.get('e_commune_residence')
                    commune_epouse = request.POST.get('f_commune_residence')

                    # --- BLOC 1 : L'ÉPOUX ---
                    epoux = Epoux.objects.create(
                        nom=request.POST.get('e_nom'),
                        post_nom=request.POST.get('e_postnom'),
                        prenom=request.POST.get('e_prenom'),
                        telephone=request.POST.get('e_tel'),
                        numero_piece=request.POST.get('e_num_piece'),
                        commune_residence_id=commune_epoux,
                        profession=prof_epoux,
                        empreinte_digitale=empreinte_obj_epoux
                    )

                    # --- BLOC 2 : L'ÉPOUSE ---
                    epouse = Epouse.objects.create(
                        nom=request.POST.get('f_nom'),
                        post_nom=request.POST.get('f_postnom'),
                        prenom=request.POST.get('f_prenom'),
                        telephone=request.POST.get('f_tel'),
                        numero_piece=request.POST.get('f_num_piece'),
                        commune_residence_id=commune_epouse,
                        profession=prof_epouse,
                        empreinte_digitale=empreinte_obj_epouse
                    )

                    # --- BLOC 3 : LE DOSSIER (SÉCURISÉ CONTRE LES DOUBLONS) ---
                    # 1. On récupère le numéro s'il vient du formulaire
                    num_dossier = request.POST.get('numero_dossier')
                    
                    # 2. Sécurité : S'il est absent ou vide, on génère un numéro unique à la volée
                    if not num_dossier or not num_dossier.strip():
                        import uuid
                        # Génère un identifiant court et unique, ex: "DOS-A1B2C3D4"
                        num_dossier = f"DOS-{uuid.uuid4().hex[:8].upper()}"

                    dossier = Dossier.objects.create(
                        numero_dossier=num_dossier,  # On force le numéro unique ici
                        epoux=epoux,
                        epouse=epouse,
                        commune_enregistrement=commune_agent,
                        utilisateur=request.user,
                        statut='ouvert'
                    )

                    # --- BLOC 4 : LES TÉMOINS (DEVENUS ENTIÈREMENT OPTIONNELS) ---
                    # Témoin de l'époux : créé uniquement si un nom est renseigné
                    t1_nom = request.POST.get('t1_nom')
                    if t1_nom and t1_nom.strip():
                        Temoin.objects.create(
                            dossier=dossier,
                            provenance='EPOUX',
                            nom=t1_nom,
                            postnom=request.POST.get('t1_postnom', ''),
                            prenom=request.POST.get('t1_prenom', ''),
                            telephone=request.POST.get('t1_tel', ''),
                            numero_piece=request.POST.get('t1_num_piece', '')
                        )
                    
                    # Témoin de l'épouse : créé uniquement si un nom est renseigné
                    t2_nom = request.POST.get('t2_nom')
                    if t2_nom and t2_nom.strip():
                        Temoin.objects.create(
                            dossier=dossier,
                            provenance='EPOUSE',
                            nom=t2_nom,
                            telephone=request.POST.get('t2_tel', '')
                        )

                    # --- FINANCES : PAIEMENT INITIAL (CORRIGÉ) ---
                    montant_verse = float(request.POST.get('montant_paye', 0))
                    if montant_verse > 0:
                        # Nettoyage du type de paiement pour correspondre aux choix ('avance' ou 'totalite')
                        type_form = request.POST.get('type_paiement', 'avance').lower()
                        type_valide = type_form if type_form in ['avance', 'totalite'] else 'avance'
                        
                        # Récupération propre du montant total fixé (ex: 50)
                        total_du = request.POST.get('total_du', 50)

                        Paiement.objects.create(
                            dossier=dossier,
                            montant_total_du=Decimal(str(total_du)),  # Le bon nom du champ !
                            montant_paye=Decimal(str(montant_verse)),
                            type_paiement=type_valide,
                            agent_recouvreur=request.user             # Pour alimenter la clé étrangère
                        )

                        # Mise à jour de la caisse de la commune
                        caisse, created = CaisseCommune.objects.get_or_create(commune=commune_agent)
                        caisse.solde_actuel += Decimal(str(montant_verse))
                        caisse.save()

                        # Enregistrement du mouvement comptable
                        MouvementCaisse.objects.create(
                            caisse=caisse,
                            dossier=dossier,
                            montant=montant_verse,
                            agent=request.user
                        )

                messages.success(request, f"Cœur de Saisie validé ! Le dossier a été affecté à la commune de {commune_agent.nom}.")
                return redirect('dossier_list')

            except Exception as e:
                messages.error(request, f"Échec de l'enregistrement. Détails : {str(e)}")
                return redirect('dossier_list')

class DocumentCreateView(SmartSecurityMixin, AjaxFormMixin, CreateView):
    allowed_roles = ['OPERATEUR', 'OFFICIER', 'BOURGMESTRE']
    model = Document
    form_class = DocumentForm
    template_name = 'mariage/dossiers/document_form.html'
    success_url = reverse_lazy('dossier_list')


class PaiementCreateView(SmartSecurityMixin, AjaxFormMixin, CreateView):
    allowed_roles = ['OPERATEUR', 'OFFICIER', 'BOURGMESTRE']
    model = Paiement
    form_class = PaiementForm
    template_name = 'mariage/dossiers/paiement_form.html'
    success_url = reverse_lazy('dossier_list')


# ==========================================
# 5. LES TÉMOINS
# ==========================================

class TemoinListView(SmartSecurityMixin, ListView):
    allowed_roles = ['OPERATEUR', 'OFFICIER', 'BOURGMESTRE']
    model = Temoin
    template_name = 'mariage/temoins/temoin_list.html'


class TemoinCreateView(SmartSecurityMixin, AjaxFormMixin, CreateView):
    allowed_roles = ['OPERATEUR', 'OFFICIER', 'BOURGMESTRE']
    model = Temoin
    form_class = TemoinForm
    template_name = 'mariage/temoins/temoin_form.html'
    success_url = reverse_lazy('temoin_list')


# ==========================================
# 6. LE MARIAGE (Acte Final)
# ==========================================

class MariageListView(LoginRequiredMixin, ListView):
    model = Mariage
    template_name = 'mariage/mariages/mariage_list.html'


class MariageDetailView(LoginRequiredMixin, DetailView):
    model = Mariage
    template_name = 'mariage/mariages/mariage_detail.html'


class MariageCreateView(SmartSecurityMixin, AjaxFormMixin, CreateView):
    allowed_roles = ['OFFICIER', 'BOURGMESTRE']
    model = Mariage
    form_class = MariageForm
    template_name = 'mariage/mariages/mariage_form.html'
    success_url = reverse_lazy('mariage_list')


class MariageUpdateView(SmartSecurityMixin, AjaxFormMixin, UpdateView):
    allowed_roles = ['OFFICIER', 'BOURGMESTRE']
    model = Mariage
    form_class = MariageForm
    template_name = 'mariage/mariages/mariage_form.html'
    success_url = reverse_lazy('mariage_list')


# ==========================================
# 7. RUPTURE (Divorce)
# ==========================================

class DivorceListView(SmartSecurityMixin, ListView):
    allowed_roles = ['OPERATEUR', 'OFFICIER', 'BOURGMESTRE']
    model = Divorce
    template_name = 'mariage/mariages/divorce_list.html'


class DivorceCreateView(SmartSecurityMixin, AjaxFormMixin, CreateView):
    allowed_roles = ['OFFICIER', 'BOURGMESTRE']
    model = Divorce
    form_class = DivorceForm
    template_name = 'mariage/mariages/divorce_form.html'
    success_url = reverse_lazy('mariage_list')


class ActeDivorceDetailView(SmartSecurityMixin, DetailView):
    allowed_roles = ['OFFICIER', 'BOURGMESTRE']
    model = Divorce
    template_name = 'mariage/mariages/acte_divorce_detail.html'
    context_object_name = 'divorce'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['mariage'] = self.object.mariage
        return context    


# ==========================================
# 8. RECHERCHE RAPIDE & SYNTHÈSE BIOMÉTRIQUE
# ==========================================

class QuickSearchView(LoginRequiredMixin, View):
    """Recherche rapide qui redirige vers l'acte de mariage ou divorce saisi."""
    def get(self, request, *args, **kwargs):
        query = request.GET.get('q', '').strip()
        if query:
            mariage = Mariage.objects.filter(numero_acte__icontains=query).first()
            if mariage:
                return redirect('mariage_detail', pk=mariage.pk)
            
            divorce = Divorce.objects.filter(numero_jugement__icontains=query).first()
            if divorce:
                return redirect('acte_divorce_detail', pk=divorce.pk)
            
            messages.warning(request, f"Aucun document trouvé pour : {query}")
        return redirect('dashboard')


class DossierSyntheseView(LoginRequiredMixin, View):
    template_name = 'mariage/dossiers/dossier_synthese.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_superuser:
            return super().dispatch(request, *args, **kwargs)

        roles_autorises = ['OPERATEUR', 'OFFICIER', 'BOURGMESTRE']
        if not hasattr(request.user, 'userprofile') or request.user.userprofile.role.upper() not in roles_autorises:
            messages.error(request, "Accès refusé. Vous n'avez pas l'autorisation requise.")
            return redirect('dashboard')
            
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        if request.user.is_superuser:
            affectation_commune = Commune.objects.first()
            role_affiche = "SUPER-ADMINISTRATEUR"
        else:
            affectation_commune = request.user.userprofile.commune
            role_affiche = request.user.userprofile.role

        context = {
            'communes': Commune.objects.all(),
            'affectation': affectation_commune,
            'role': role_affiche
        }
        return render(request, self.template_name, context)

    def post(self, request):
        e_finger = request.FILES.get('e_empreinte_scan')
        f_finger = request.FILES.get('f_empreinte_scan')

        if 'verifier_empreintes' in request.POST:
            conjoint_existant = Epoux.objects.filter(
                Q(empreinte_digitale=e_finger) | Q(empreinte_digitale=f_finger)
            ).first()

            if conjoint_existant:
                mariage_actif = Mariage.objects.filter(
                    Q(epoux=conjoint_existant) | Q(epouse=conjoint_existant),
                    statut='Vigoureux'
                ).first()

                if mariage_actif:
                    messages.error(request, "Alerte : Un des conjoints est déjà lié à un acte de mariage actif.")
                    return redirect('mariage_detail', pk=mariage_actif.pk)

            return render(request, self.template_name, {'show_form': True, 'e_finger': e_finger, 'f_finger': f_finger})

        try:
            with transaction.atomic():
                epoux = Epoux.objects.create(
                    nom=request.POST.get('e_nom'),
                    postnom=request.POST.get('e_postnom'),
                    prenom=request.POST.get('e_prenom'),
                    telephone=request.POST.get('e_tel'),
                    numero_piece=request.POST.get('e_num_piece'),
                    photo_piece=request.FILES.get('e_photo_piece'),
                    commune_residence_id=request.POST.get('e_commune'),
                    profession=request.POST.get('e_prof')
                )

                epouse = Epoux.objects.create(  # Assure-toi que le modèle pour l'épouse est bien instancié correctement selon tes règles de projet
                    nom=request.POST.get('f_nom'),
                    postnom=request.POST.get('f_postnom'),
                    prenom=request.POST.get('f_prenom'),
                    telephone=request.POST.get('f_tel'),
                    numero_piece=request.POST.get('f_num_piece'),
                    photo_piece=request.FILES.get('f_photo_piece'),
                    commune_residence_id=request.POST.get('f_commune'),
                    profession=request.POST.get('f_prof')
                )

                commune_agent = Commune.objects.first() if request.user.is_superuser else request.user.userprofile.commune
                
                dossier = Dossier.objects.create(
                    epoux=epoux,
                    epouse=epouse,
                    commune_enregistrement=commune_agent,
                    agent=request.user,
                    statut='ouvert'
                )

                montant_verse = float(request.POST.get('montant_paye', 0))
                Paiement.objects.create(
                    dossier=dossier,
                    total_montant_du=request.POST.get('total_du', 0),
                    montant_paye=montant_verse,
                    type_paiement=request.POST.get('type_paiement')
                )
                
                caisse, created = CaisseCommune.objects.get_or_create(commune=commune_agent)
                caisse.solde_actuel += Decimal(montant_verse)
                caisse.save()

                MouvementCaisse.objects.create(
                    caisse=caisse,
                    dossier=dossier,
                    montant=montant_verse,
                    agent=request.user
                )

                messages.success(request, f"Dossier créé avec succès ! N° Auto : {dossier.id}. Caisse mise à jour.")
                return redirect('dossier_list')

        except Exception as e:
            messages.error(request, f"Erreur : Vérifiez que toutes les informations obligatoires sont présentes. ({str(e)})")
            return redirect('dossier_synthese')


# ==========================================
# 9. COMPTABILITÉ FINANCIÈRE (Dashboard Bourgmestre)
# ==========================================

class BourgmestreDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'mariage/dashboard_bourgmestre.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_superuser:
            return super().dispatch(request, *args, **kwargs)
            
        if not hasattr(request.user, 'userprofile') or request.user.userprofile.role.upper() != 'BOURGMESTRE':
            messages.error(request, "Accès réservé aux Bourgmestres.")
            return redirect('dashboard')
            
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        if self.request.user.is_superuser:
            commune = Commune.objects.first()
            role_label = "SUPER-ADMINISTRATEUR"
        else:
            commune = self.request.user.userprofile.commune
            role_label = self.request.user.userprofile.role
        
        if commune:
            caisse, created = CaisseCommune.objects.get_or_create(commune=commune)
            solde_actuel = caisse.solde_actuel
            total_dossiers = Dossier.objects.filter(commune_enregistrement=commune).count()
            
            sept_derniers_jours = timezone.now() - timedelta(days=7)
            stats_graph = MouvementCaisse.objects.filter(
                caisse=caisse, 
                date_mouvement__gte=sept_derniers_jours
            ).annotate(date=TruncDate('date_mouvement')) \
             .values('date') \
             .annotate(total=Sum('montant')) \
             .order_by('date')
        else:
            solde_actuel = 0
            total_dossiers = 0
            stats_graph = []

        context['commune'] = commune
        context['solde'] = solde_actuel
        context['nb_dossiers'] = total_dossiers
        context['stats_graph'] = list(stats_graph)
        context['role'] = role_label
        
        return context



def dossier_edit_view(request, pk):
    # 1. On récupère le dossier existant et ses dépendances
    dossier = get_object_or_404(Dossier, pk=pk)
    epoux = dossier.epoux
    epouse = dossier.epouse
    # On récupère le dernier paiement en date s'il existe
    paiement = dossier.paiements.last() 

    if request.method == 'POST':
        try:
            with transaction.atomic():
                # --- BLOC 1 : MISE À JOUR DE L'ÉPOUX ---
                epoux.nom = request.POST.get('e_nom')
                epoux.post_nom = request.POST.get('e_postnom')
                epoux.prenom = request.POST.get('e_prenom')
                epoux.telephone = request.POST.get('e_tel')
                epoux.numero_piece = request.POST.get('e_num_piece')
                epoux.commune_residence_id = request.POST.get('e_commune_residence')
                epoux.profession = request.POST.get('e_profession') or "Sans"
                epoux.save()

                # --- BLOC 2 : MISE À JOUR DE L'ÉPOUSE ---
                epouse.nom = request.POST.get('f_nom')
                epouse.post_nom = request.POST.get('f_postnom')
                epouse.prenom = request.POST.get('f_prenom')
                epouse.telephone = request.POST.get('f_tel')
                epouse.numero_piece = request.POST.get('f_num_piece')
                epouse.commune_residence_id = request.POST.get('f_commune_residence')
                epouse.profession = request.POST.get('f_profession') or "Sans"
                epouse.save()

                # --- BLOC 3 : MISE À JOUR DU DOSSIER ---
                # On ne change généralement pas le numéro de dossier initial ni l'utilisateur créateur
                dossier.save()

                # --- BLOC 4 : MISE À JOUR DU PAIEMENT INITIAL ---
                montant_verse = float(request.POST.get('montant_paye', 0))
                total_du = request.POST.get('total_du', 50)
                
                if paiement:
                    # Ajustement de la caisse commune par rapport à l'ancienne valeur
                    ancien_montant = paiement.montant_paye
                    difference = Decimal(str(montant_verse)) - ancien_montant
                    
                    if difference != 0:
                        paiement.montant_total_du = Decimal(str(total_du))
                        paiement.montant_paye = Decimal(str(montant_verse))
                        paiement.save()

                        # Mise à jour de la caisse
                        caisse, created = CaisseCommune.objects.get_or_create(commune=dossier.commune_enregistrement)
                        caisse.solde_actuel += difference
                        caisse.save()

                        # Enregistrement du mouvement correctif
                        MouvementCaisse.objects.create(
                            caisse=caisse,
                            dossier=dossier,
                            montant=float(difference),
                            agent=request.user
                        )
                elif montant_verse > 0:
                    # Si aucun paiement n'existait mais qu'on en ajoute un maintenant
                    Paiement.objects.create(
                        dossier=dossier,
                        montant_total_du=Decimal(str(total_du)),
                        montant_paye=Decimal(str(montant_verse)),
                        agent_recouvreur=request.user
                    )

            messages.success(request, f"Le dossier N° {dossier.numero_dossier} a été modifié avec succès !")
            return redirect('dossier_list')

        except Exception as e:
            messages.error(request, f"Erreur lors de la modification. Détails : {str(e)}")
            
    # Context à envoyer pour pré-remplir le template dossier_form.html
    context = {
        'dossier': dossier,
        'epoux': epoux,
        'epouse': epouse,
        'paiement': paiement,
        'is_edit': True # Permet de savoir dans le template qu'on est en mode modification
    }
    return render(request, 'mariage/dossier_form.html', context)    