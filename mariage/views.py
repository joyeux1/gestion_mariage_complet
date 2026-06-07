import base64
import json
from datetime import timedelta
from decimal import Decimal

from django.urls import reverse, reverse_lazy
from django.http import JsonResponse
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.exceptions import ValidationError
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
    CaisseCommune, Commune, MouvementCaisse, EmpreinteDigitale, ReconnaissanceFaciale,
    Epoux, Epouse, Dossier, Paiement, Document, Temoin, Mariage, Divorce,
    photo_conjoint_affichage,
)
from .dashboard_stats import stats_dashboard_bourgmestre, stats_dashboard_general
from .liste_filtres import (
    appliquer_filtres_divorce,
    appliquer_filtres_dossier,
    appliquer_filtres_mariage,
    contexte_filtres_liste,
    filtrer_mariages_par_acces,
    filtres_actifs,
    lire_parametres_filtre,
)
from .permissions_commune import (
    commune_caisse_active,
    communes_accessibles,
    filtrer_dossiers_par_acces,
    role_utilisateur,
    utilisateur_peut_acceder_caisse,
)
from .services_biometrie import ReconnaissanceFacialeService
from .verification_dossier import (
    appliquer_resultat_verif,
    lire_etat_verif,
    reinitialiser_verif,
    sauver_etat_verif,
    verif_complete,
    verifier_empreinte,
    verifier_facial,
    verifier_nominatif,
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
        if not getattr(request.user, 'role', None):
            messages.error(request, "Accès refusé. Vous ne possédez pas de rôle d'agent civil.")
            return redirect('dashboard')

        # Récupération et normalisation du rôle (Gestion des majuscules)
        user_role = request.user.role.upper()
        allowed_roles_upper = [role.upper() for role in self.allowed_roles]

        # 4. Contrôle strict du rôle requis
        if allowed_roles_upper and user_role not in allowed_roles_upper:
            messages.error(request, f"Accès interdit pour le rôle d'agent : {request.user.get_role_display() if hasattr(request.user, 'get_role_display') else request.user.role}")
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

    def get_queryset(self):
        return (
            Mariage.objects.select_related('epoux', 'epouse')
            .order_by('-date_enregistrement')[:10]
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(stats_dashboard_general())
        return context


class DashboardStatsAPIView(LoginRequiredMixin, View):
    """API JSON pour actualisation du tableau de bord principal."""

    def get(self, request):
        stats = stats_dashboard_general()
        activites = []
        for act in stats['activites_recentes']:
            activites.append({
                'type': act['type'],
                'titre': act['titre'],
                'detail': act['detail'],
                'date_label': act['date_label'],
                'badge_class': act['badge_class'],
                'badge_label': act['badge_label'],
            })
        return JsonResponse({
            'success': True,
            'total_mariages': stats['total_mariages'],
            'mariages_actifs': stats['mariages_actifs'],
            'total_divorces': stats['total_divorces'],
            'dossiers_en_cours': stats['dossiers_en_cours'],
            'total_epoux': stats['total_epoux'],
            'taux_succes': stats['taux_succes'],
            'dossiers_valides': stats['dossiers_valides'],
            'total_dossiers': stats['total_dossiers'],
            'variation_mariages_pct': stats['variation_mariages_pct'],
            'variation_mariages_dir': stats['variation_mariages_dir'],
            'chart_labels': stats['chart_labels'],
            'chart_data': stats['chart_data'],
            'activites_recentes': activites,
            'now_label': stats['now'].strftime('%d %B %Y'),
        })


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

    def post(self, request, *args, **kwargs):
        is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'
        image_base64 = request.POST.get('image_base64', '').strip()

        if is_ajax and image_base64:
            return self._traiter_reconnaissance_faciale(request, image_base64)

        return super().post(request, *args, **kwargs)

    def _traiter_reconnaissance_faciale(self, request, image_base64):
        try:
            image_base64 = self._nettoyer_chaine_base64(image_base64)
            image_data = base64.b64decode(image_base64, validate=True)
            content_file = ContentFile(image_data, name='capture_webcam.jpg')

            encodage = ReconnaissanceFacialeService.extraire_encodage_facial(content_file)
            encodage_facial = json.loads(
                ReconnaissanceFacialeService.encoder_json(encodage)
            )

            reconnaissance = ReconnaissanceFaciale(encodage_facial=encodage_facial)
            content_file.seek(0)
            reconnaissance.photo.save('capture_webcam.jpg', content_file, save=False)
            reconnaissance.save()

            return JsonResponse({
                'success': True,
                'message': 'Reconnaissance faciale enregistrée avec succès !',
                'redirect_url': self.get_success_url(),
            })

        except ValidationError as exc:
            return JsonResponse({
                'success': False,
                'errors': {'image_base64': exc.messages},
            }, status=400)

        except (base64.binascii.Error, ValueError):
            return JsonResponse({
                'success': False,
                'errors': {'image_base64': ['Image Base64 invalide ou corrompue.']},
            }, status=400)

        except Exception as exc:
            return JsonResponse({
                'success': False,
                'errors': {'image_base64': [f'Erreur lors du traitement facial : {exc}']},
            }, status=400)

    @staticmethod
    def _nettoyer_chaine_base64(image_base64):
        if ';base64,' in image_base64:
            return image_base64.split(';base64,', 1)[1]
        if ',' in image_base64:
            return image_base64.split(',', 1)[1]
        return image_base64


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

def _decode_b64_fichier(data_b64, nom_fichier='fichier.bin'):
    if not data_b64:
        return None
    payload = data_b64
    if ';base64,' in payload:
        payload = payload.split(';base64,', 1)[1]
    elif payload.startswith('data:') and ',' in payload:
        payload = payload.split(',', 1)[1]
    try:
        raw = base64.b64decode(payload, validate=True)
    except (ValueError, base64.binascii.Error):
        return None
    return ContentFile(raw, name=nom_fichier)


def _fichiers_formulaire_avec_session(request, etat_verif):
    """Complète les fichiers manquants à partir de la session de vérification."""
    fichiers = request.FILES.copy()
    for prefix, role in (('e', 'epoux'), ('f', 'epouse')):
        if not fichiers.get(f'{prefix}_photo'):
            cf = _decode_b64_fichier(
                etat_verif.get(f'photo_b64_{role}'),
                f'photo_{role}.jpg',
            )
            if cf:
                fichiers[f'{prefix}_photo'] = cf
        if (
            not fichiers.get(f'{prefix}_scan_empreinte')
            and etat_verif.get('type') == 'empreinte'
        ):
            cf = _decode_b64_fichier(
                etat_verif.get(f'empreinte_b64_{role}'),
                etat_verif.get(f'empreinte_nom_{role}') or f'empreinte_{role}.png',
            )
            if cf:
                fichiers[f'{prefix}_scan_empreinte'] = cf
    return fichiers


def _identite_prefill(identite):
    """Identité préremplie avec clés toujours définies (évite erreurs template)."""
    identite = identite or {}
    return {
        'nom': identite.get('nom', ''),
        'postnom': identite.get('postnom', ''),
        'prenom': identite.get('prenom', ''),
    }


def _commune_agent_utilisateur(user):
    if user.commune_id:
        return user.commune
    if user.is_superuser:
        return Commune.objects.first()
    return None


def _creer_empreinte_depuis_fichier(fichier):
    if not fichier:
        return None
    return EmpreinteDigitale.objects.create(empreinte=fichier, doigt="Index Droit")


class DossierListView(SmartSecurityMixin, ListView):
    allowed_roles = ['OPERATEUR', 'OFFICIER', 'BOURGMESTRE', 'MAIRE', 'HIERARCHIE']
    model = Dossier
    template_name = 'mariage/dossiers/dossier_list.html'
    context_object_name = 'dossiers'
    limite_defaut = 10

    def get_queryset(self):
        params = lire_parametres_filtre(self.request)
        qs = Dossier.objects.select_related(
            'epoux',
            'epouse',
            'epoux__reconnaissance_faciale',
            'epouse__reconnaissance_faciale',
            'commune_enregistrement',
            'utilisateur',
        ).prefetch_related('temoins').order_by('-date_creation')
        qs = filtrer_dossiers_par_acces(self.request.user, qs)
        qs = appliquer_filtres_dossier(qs, params)
        if not filtres_actifs(params):
            qs = qs[:self.limite_defaut]
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        params = lire_parametres_filtre(self.request)
        context.update(contexte_filtres_liste(
            self.request, params, 'dossier', self.limite_defaut, self.request.user
        ))
        return context


class DossierVerificationAntiPolygamieAPIView(LoginRequiredMixin, View):
    """Vérification successive époux / épouse avant ouverture de dossier."""

    def post(self, request):
        type_verif = request.POST.get('type_verif', '').strip()
        role = request.POST.get('role', '').strip()

        if type_verif not in ('empreinte', 'nominative', 'faciale'):
            return JsonResponse(
                {'success': False, 'errors': {'type_verif': ['Mode de vérification invalide.']}},
                status=400,
            )
        if role not in ('epoux', 'epouse'):
            return JsonResponse(
                {'success': False, 'errors': {'role': ['Rôle invalide (epoux ou epouse).']}},
                status=400,
            )

        etat = lire_etat_verif(request.session)

        try:
            if type_verif == 'empreinte':
                fichier = request.FILES.get('scan_empreinte')
                resultat = verifier_empreinte(role, fichier)
            elif type_verif == 'nominative':
                resultat = verifier_nominatif(
                    role,
                    request.POST.get('nom'),
                    request.POST.get('postnom'),
                    request.POST.get('prenom'),
                )
            else:
                resultat = verifier_facial(role, request.POST.get('image_base64'))

            if not resultat.get('ok'):
                return JsonResponse({
                    'success': False,
                    'bloque': True,
                    'message': resultat['message'],
                    'match': resultat.get('match'),
                    'etat': etat,
                })

            if type_verif == 'empreinte':
                fichier = request.FILES.get('scan_empreinte')
                if fichier:
                    fichier.seek(0)
                    resultat['empreinte_b64'] = base64.b64encode(fichier.read()).decode('ascii')
                    fichier.seek(0)
            elif type_verif == 'faciale':
                resultat['photo_base64'] = request.POST.get('image_base64', '')

            etat = appliquer_resultat_verif(etat, type_verif, role, resultat)
            sauver_etat_verif(request.session, etat)

            return JsonResponse({
                'success': True,
                'message': resultat['message'],
                'role': role,
                'etat': etat,
                'complete': verif_complete(etat),
            })

        except ValidationError as exc:
            messages_list = exc.messages if hasattr(exc, 'messages') else [str(exc)]
            return JsonResponse(
                {'success': False, 'errors': {'verification': messages_list}},
                status=400,
            )
        except Exception as exc:
            return JsonResponse(
                {'success': False, 'errors': {'verification': [str(exc)]}},
                status=500,
            )


class DossierCreateView(SmartSecurityMixin, View):
    allowed_roles = ['OPERATEUR', 'OFFICIER', 'BOURGMESTRE']
    template_name = 'mariage/dossiers/dossier_form.html'

    def _contexte_formulaire(self, request, commune_agent, etat_verif):
        return {
            'communes': Commune.objects.select_related('ville__province').all(),
            'commune_agent': commune_agent,
            'etape_biometrie': not verif_complete(etat_verif),
            'verif_etat': etat_verif,
            'empreinte_epoux_valide': etat_verif.get('empreinte_epoux', ''),
            'empreinte_epouse_valide': etat_verif.get('empreinte_epouse', ''),
            'prefill_epoux': _identite_prefill(etat_verif.get('identite_epoux')),
            'prefill_epouse': _identite_prefill(etat_verif.get('identite_epouse')),
            'verif_type': etat_verif.get('type'),
            'is_edit': False,
        }

    def get(self, request, *args, **kwargs):
        commune_agent = _commune_agent_utilisateur(request.user)

        etat_verif = lire_etat_verif(request.session)
        context = self._contexte_formulaire(request, commune_agent, etat_verif)
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        commune_agent = _commune_agent_utilisateur(request.user)
        etat_verif = lire_etat_verif(request.session)

        if 'reinitialiser_verification' in request.POST:
            reinitialiser_verif(request.session)
            messages.info(request, "Vérification anti-polygamie réinitialisée.")
            return redirect('dossier_create')

        if not verif_complete(etat_verif):
            messages.error(
                request,
                "Vérification incomplète : vous devez valider successivement l'époux puis l'épouse "
                "avant d'enregistrer le dossier.",
            )
            context = self._contexte_formulaire(request, commune_agent, etat_verif)
            return render(request, self.template_name, context)

        # ACTION : ENREGISTREMENT DU CŒUR DE SAISIE (4 BLOCS)
        if 'enregistrer_coeur_saisie' in request.POST:
            fichiers = _fichiers_formulaire_avec_session(request, etat_verif)
            erreurs_photo = []
            if not fichiers.get('e_photo'):
                erreurs_photo.append("La photo du futur époux est obligatoire.")
            if not fichiers.get('f_photo'):
                erreurs_photo.append("La photo de la future épouse est obligatoire.")
            if erreurs_photo:
                for msg in erreurs_photo:
                    messages.error(request, msg)
                context = self._contexte_formulaire(request, commune_agent, etat_verif)
                return render(request, self.template_name, context)

            try:
                with transaction.atomic():

                    empreinte_obj_epoux = _creer_empreinte_depuis_fichier(
                        fichiers.get('e_scan_empreinte')
                    )
                    empreinte_obj_epouse = _creer_empreinte_depuis_fichier(
                        fichiers.get('f_scan_empreinte')
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
                        piece_identite=request.POST.get('e_piece_identite') or "Carte d'Électeur",
                        commune_residence_id=commune_epoux,
                        profession=prof_epoux,
                        empreinte_digitale=empreinte_obj_epoux
                    )
                    _maj_conjoint_modification(epoux, 'e', request.POST, fichiers)

                    # --- BLOC 2 : L'ÉPOUSE ---
                    epouse = Epouse.objects.create(
                        nom=request.POST.get('f_nom'),
                        post_nom=request.POST.get('f_postnom'),
                        prenom=request.POST.get('f_prenom'),
                        telephone=request.POST.get('f_tel'),
                        numero_piece=request.POST.get('f_num_piece'),
                        piece_identite=request.POST.get('f_piece_identite') or "Carte d'Électeur",
                        commune_residence_id=commune_epouse,
                        profession=prof_epouse,
                        empreinte_digitale=empreinte_obj_epouse
                    )
                    _maj_conjoint_modification(epouse, 'f', request.POST, fichiers)

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
                        temoin1 = Temoin.objects.create(
                            dossier=dossier,
                            provenance='EPOUX',
                            nom=t1_nom,
                            postnom=request.POST.get('t1_postnom', ''),
                            prenom=request.POST.get('t1_prenom', ''),
                            telephone=request.POST.get('t1_tel', ''),
                            numero_piece=request.POST.get('t1_num_piece', '')
                        )
                        if request.FILES.get('t1_photo_carte'):
                            temoin1.photo = request.FILES['t1_photo_carte']
                            temoin1.save()
                    
                    # Témoin de l'épouse : créé uniquement si un nom est renseigné
                    t2_nom = request.POST.get('t2_nom')
                    if t2_nom and t2_nom.strip():
                        temoin2 = Temoin.objects.create(
                            dossier=dossier,
                            provenance='EPOUSE',
                            nom=t2_nom,
                            telephone=request.POST.get('t2_tel', '')
                        )
                        if request.FILES.get('t2_photo_carte'):
                            temoin2.photo = request.FILES['t2_photo_carte']
                            temoin2.save()

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
                reinitialiser_verif(request.session)
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
# MARIAGE
# =================================

class MariageListView(LoginRequiredMixin, ListView):
    model = Mariage
    template_name = 'mariage/mariages/mariage_list.html'
    context_object_name = 'mariages'
    paginate_by = None
    limite_defaut = 10

    def get_queryset(self):
        params = lire_parametres_filtre(self.request)
        qs = (
            Mariage.objects.select_related(
                'epoux',
                'epouse',
                'epoux__reconnaissance_faciale',
                'epouse__reconnaissance_faciale',
                'dossier__commune_enregistrement__ville__province',
                'agent',
            )
            .order_by('-date_enregistrement')
        )
        qs = filtrer_mariages_par_acces(self.request.user, qs)
        qs = appliquer_filtres_mariage(qs, params)
        if not filtres_actifs(params):
            qs = qs[:self.limite_defaut]
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        params = lire_parametres_filtre(self.request)
        context.update(contexte_filtres_liste(
            self.request, params, 'mariage', self.limite_defaut, self.request.user
        ))
        return context


class MariageDetailView(LoginRequiredMixin, DetailView):
    model = Mariage
    template_name = 'mariage/mariages/mariage_detail.html'
    context_object_name = 'mariage'

    def get_queryset(self):
        return Mariage.objects.select_related(
            'epoux',
            'epouse',
            'dossier__commune_enregistrement__ville__province',
            'agent',
            'dossier',
        ).prefetch_related('temoins')


class MariageActeEmbedView(LoginRequiredMixin, DetailView):
    """Aperçu compact de l'acte, intégrable dans une iframe."""

    model = Mariage
    template_name = 'mariage/mariages/mariage_acte_embed.html'
    context_object_name = 'mariage'

    def get_queryset(self):
        return Mariage.objects.select_related(
            'epoux',
            'epouse',
            'dossier__commune_enregistrement__ville__province',
        )


def _nettoyer_image_base64(image_base64):
    if ';base64,' in image_base64:
        return image_base64.split(';base64,', 1)[1]
    if ',' in image_base64:
        return image_base64.split(',', 1)[1]
    return image_base64


def _queryset_dossiers_eligibles_mariage():
    """Dossiers utilisables pour créer un acte (sans mariage existant)."""
    dossiers_avec_acte = Mariage.objects.values_list('dossier_id', flat=True)
    return (
        Dossier.objects.filter(
            statut__in=['valide', 'en_cours', 'ouvert'],
            epoux__isnull=False,
            epouse__isnull=False,
        )
        .exclude(pk__in=dossiers_avec_acte)
        .select_related(
            'epoux',
            'epouse',
            'epoux__reconnaissance_faciale',
            'epouse__reconnaissance_faciale',
            'commune_enregistrement__ville__province',
        )
        .distinct()
    )


def _serialiser_dossier_mariage_recherche(dossier, correspondance=None):
    commune = dossier.commune_enregistrement
    img_epoux = photo_conjoint_affichage(dossier.epoux)
    img_epouse = photo_conjoint_affichage(dossier.epouse)
    data = {
        'id': dossier.pk,
        'numero_dossier': dossier.numero_dossier,
        'statut': dossier.statut,
        'statut_label': dossier.get_statut_display(),
        'epoux': {
            'nom_complet': f"{dossier.epoux.nom} {dossier.epoux.post_nom} {dossier.epoux.prenom}".strip(),
            'photo_url': img_epoux.url if img_epoux else None,
            'photo_carte': dossier.epoux.photo_carte.url if dossier.epoux.photo_carte else None,
            'photo': dossier.epoux.photo.url if dossier.epoux.photo else None,
        },
        'epouse': {
            'nom_complet': f"{dossier.epouse.nom} {dossier.epouse.post_nom} {dossier.epouse.prenom}".strip(),
            'photo_url': img_epouse.url if img_epouse else None,
            'photo_carte': dossier.epouse.photo_carte.url if dossier.epouse.photo_carte else None,
            'photo': dossier.epouse.photo.url if dossier.epouse.photo else None,
        },
        'lieu': {
            'commune': commune.nom if commune else '—',
            'ville': commune.ville.nom if commune else '—',
            'province': commune.ville.province.nom if commune else '—',
        },
    }
    if correspondance:
        data['correspondance'] = correspondance
    return data


def _encodage_facial_conjoint(conjoint):
    """Retourne l'encodage numpy d'un conjoint (BD ou photo carte/profil)."""
    if not conjoint:
        return None

    rf = getattr(conjoint, 'reconnaissance_faciale', None)
    if rf and rf.encodage_facial:
        return ReconnaissanceFacialeService.decoder_json(rf.encodage_facial)

    img = photo_conjoint_affichage(conjoint)
    if not img or not img.name or not default_storage.exists(img.name):
        return None

    try:
        with default_storage.open(img.name, 'rb') as fichier:
            return ReconnaissanceFacialeService.extraire_encodage_facial(fichier)
    except ValidationError:
        return None


class DossierRechercheMariageAPIView(LoginRequiredMixin, View):
    """Recherche de dossiers validés pour le workflow Nouveau Mariage."""

    def get(self, request):
        nom = request.GET.get('nom', '').strip()
        postnom = request.GET.get('postnom', '').strip()
        prenom = request.GET.get('prenom', '').strip()

        dossiers = _queryset_dossiers_eligibles_mariage()

        if nom:
            dossiers = dossiers.filter(
                Q(epoux__nom__icontains=nom)
                | Q(epouse__nom__icontains=nom)
            )
        if postnom:
            dossiers = dossiers.filter(
                Q(epoux__post_nom__icontains=postnom)
                | Q(epouse__post_nom__icontains=postnom)
            )
        if prenom:
            dossiers = dossiers.filter(
                Q(epoux__prenom__icontains=prenom)
                | Q(epouse__prenom__icontains=prenom)
            )

        resultats = [
            _serialiser_dossier_mariage_recherche(dossier)
            for dossier in dossiers[:15]
        ]

        return JsonResponse({'success': True, 'dossiers': resultats})


class DossierRechercheFacialeMariageAPIView(LoginRequiredMixin, View):
    """Recherche de dossiers par reconnaissance faciale (webcam ou photo)."""

    def post(self, request):
        image_base64 = request.POST.get('image_base64', '').strip()
        if not image_base64:
            return JsonResponse(
                {'success': False, 'errors': {'image_base64': ['Capturez une photo avant de lancer la recherche.']}},
                status=400,
            )

        try:
            image_base64 = _nettoyer_image_base64(image_base64)
            image_data = base64.b64decode(image_base64, validate=True)
            content_file = ContentFile(image_data, name='recherche_faciale.jpg')
            encodage_capture = ReconnaissanceFacialeService.extraire_encodage_facial(content_file)
        except ValidationError as exc:
            return JsonResponse(
                {'success': False, 'errors': {'image_base64': exc.messages}},
                status=400,
            )
        except (base64.binascii.Error, ValueError):
            return JsonResponse(
                {'success': False, 'errors': {'image_base64': ['Image invalide.']}},
                status=400,
            )
        except Exception as exc:
            return JsonResponse(
                {'success': False, 'errors': {'image_base64': [str(exc)]}},
                status=400,
            )

        candidats = []
        for dossier in _queryset_dossiers_eligibles_mariage()[:50]:
            for role, conjoint, label in (
                ('epoux', dossier.epoux, 'Époux'),
                ('epouse', dossier.epouse, 'Épouse'),
            ):
                encodage = _encodage_facial_conjoint(conjoint)
                if encodage is None:
                    continue
                candidats.append({
                    'dossier': dossier,
                    'id': f"{dossier.pk}-{role}",
                    'encodage': encodage,
                    'meta': {
                        'role': role,
                        'role_label': label,
                        'nom_complet': f"{conjoint.nom} {conjoint.post_nom} {conjoint.prenom}".strip(),
                    },
                })

        if not candidats:
            return JsonResponse({
                'success': True,
                'dossiers': [],
                'message': 'Aucune photo faciale enregistrée sur les dossiers. Ajoutez des photos de carte ou une capture biométrique.',
            })

        correspondance = ReconnaissanceFacialeService.meilleure_correspondance(
            encodage_capture, candidats
        )

        if not correspondance or not correspondance.get('correspondance'):
            distance = correspondance['distance'] if correspondance else None
            return JsonResponse({
                'success': True,
                'dossiers': [],
                'message': 'Aucun dossier ne correspond à ce visage.',
                'distance': distance,
            })

        dossier = correspondance['dossier']
        confiance = max(
            0,
            min(
                100,
                int((1 - correspondance['distance'] / ReconnaissanceFacialeService.DISTANCE_TOLERANCE) * 100),
            ),
        )
        resultat = _serialiser_dossier_mariage_recherche(
            dossier,
            correspondance={
                'role': correspondance['meta']['role'],
                'role_label': correspondance['meta']['role_label'],
                'nom_complet': correspondance['meta']['nom_complet'],
                'confiance': confiance,
                'distance': round(correspondance['distance'], 4),
            },
        )

        return JsonResponse({
            'success': True,
            'dossiers': [resultat],
            'message': (
                f"Correspondance trouvée : {correspondance['meta']['role_label']} "
                f"{correspondance['meta']['nom_complet']} (confiance {confiance} %)."
            ),
        })


class MariageEnregistrerActeAPIView(LoginRequiredMixin, View):
    """Crée un acte de mariage à partir d'un dossier validé."""

    def post(self, request):
        dossier_id = request.POST.get('dossier_id')
        numero_acte = request.POST.get('numero_acte', '').strip()
        date_mariage = request.POST.get('date_mariage')
        lieu_mariage = request.POST.get('lieu_mariage', '').strip()
        regime_matrimonial = request.POST.get('regime_matrimonial', 'Communauté de biens').strip()
        remarque = request.POST.get('remarque', '').strip()

        if not dossier_id:
            return JsonResponse(
                {'success': False, 'errors': {'dossier_id': ['Dossier requis.']}},
                status=400,
            )

        dossier = get_object_or_404(
            Dossier.objects.select_related('epoux', 'epouse', 'commune_enregistrement'),
            pk=dossier_id,
        )

        if Mariage.objects.filter(dossier=dossier).exists():
            return JsonResponse(
                {'success': False, 'errors': {'dossier_id': ['Ce dossier a déjà un acte de mariage.']}},
                status=400,
            )

        if not dossier.epoux or not dossier.epouse:
            return JsonResponse(
                {'success': False, 'errors': {'dossier_id': ['Époux et épouse requis sur le dossier.']}},
                status=400,
            )

        if not numero_acte:
            numero_acte = f"ACTE-{dossier.numero_dossier}-{timezone.now().strftime('%Y%m%d')}"

        if Mariage.objects.filter(numero_acte=numero_acte).exists():
            return JsonResponse(
                {'success': False, 'errors': {'numero_acte': ['Ce numéro d\'acte existe déjà.']}},
                status=400,
            )

        if not date_mariage:
            date_mariage = timezone.now().date()

        if not lieu_mariage and dossier.commune_enregistrement:
            lieu_mariage = f"Commune de {dossier.commune_enregistrement.nom}"

        try:
            with transaction.atomic():
                mariage = Mariage.objects.create(
                    numero_acte=numero_acte,
                    date_mariage=date_mariage,
                    lieu_mariage=lieu_mariage,
                    regime_matrimonial=regime_matrimonial,
                    dossier=dossier,
                    agent=request.user,
                    epoux=dossier.epoux,
                    epouse=dossier.epouse,
                    remarque=remarque,
                    statut='actif',
                )
                temoins = Temoin.objects.filter(dossier=dossier)
                if temoins.exists():
                    mariage.temoins.set(temoins)

                dossier.statut = 'valide'
                dossier.save(update_fields=['statut'])

            return JsonResponse({
                'success': True,
                'message': f"Acte de mariage n°{mariage.numero_acte} enregistré avec succès !",
                'redirect_url': reverse('mariage_detail', kwargs={'pk': mariage.pk}),
            })
        except ValidationError as exc:
            return JsonResponse({'success': False, 'errors': {'__all__': exc.messages}}, status=400)
        except Exception as exc:
            return JsonResponse(
                {'success': False, 'errors': {'__all__': [str(exc)]}},
                status=400,
            )


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
    template_name = 'mariage/divorces/divorce_list.html'
    context_object_name = 'divorces'
    limite_defaut = 20

    def get_queryset(self):
        params = lire_parametres_filtre(self.request)
        qs = (
            Divorce.objects.select_related(
                'mariage__epoux',
                'mariage__epouse',
                'mariage__dossier__commune_enregistrement',
            )
            .order_by('-date_enregistrement')
        )
        qs = appliquer_filtres_divorce(qs, params)
        if not filtres_actifs(params):
            qs = qs[:self.limite_defaut]
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        params = lire_parametres_filtre(self.request)
        context.update(contexte_filtres_liste(
            self.request, params, 'divorce', self.limite_defaut, self.request.user
        ))
        return context


class MariageRechercheDivorceNominativeAPIView(LoginRequiredMixin, View):
    """Recherche nominative de mariages actifs pour divorce."""

    def get(self, request):
        from .recherche_divorce import rechercher_mariages_nominatif

        nom = request.GET.get('nom', '').strip()
        postnom = request.GET.get('postnom', '').strip()
        prenom = request.GET.get('prenom', '').strip()

        if not any([nom, postnom, prenom]):
            return JsonResponse({
                'success': False,
                'errors': {'recherche': ['Saisissez au moins un critère (nom, postnom ou prénom).']},
            }, status=400)

        mariages = rechercher_mariages_nominatif(nom, postnom, prenom)
        message = None
        if not mariages:
            message = 'Aucun mariage actif ne correspond à ces critères.'
        return JsonResponse({'success': True, 'mariages': mariages, 'message': message})


class MariageRechercheDivorceEmpreinteAPIView(LoginRequiredMixin, View):
    """Recherche par empreinte digitale pour divorce."""

    def post(self, request):
        from .recherche_divorce import rechercher_mariages_empreinte

        fichier_epoux = request.FILES.get('scan_empreinte_epoux')
        fichier_epouse = request.FILES.get('scan_empreinte_epouse')

        if not fichier_epoux and not fichier_epouse:
            return JsonResponse({
                'success': False,
                'errors': {'empreinte': ['Chargez au moins une empreinte (époux ou épouse).']},
            }, status=400)

        mariages = rechercher_mariages_empreinte(fichier_epoux, fichier_epouse)
        message = None
        if not mariages:
            message = 'Aucun mariage actif identifié pour ces empreintes.'
        return JsonResponse({'success': True, 'mariages': mariages, 'message': message})


class MariageRechercheDivorceFacialeAPIView(LoginRequiredMixin, View):
    """Recherche faciale sur les mariages actifs."""

    def post(self, request):
        from .recherche_divorce import queryset_mariages_eligibles_divorce, serialiser_mariage_divorce

        image_base64 = request.POST.get('image_base64', '').strip()
        if not image_base64:
            return JsonResponse(
                {'success': False, 'errors': {'image_base64': ['Capturez une photo avant la recherche.']}},
                status=400,
            )

        try:
            image_base64 = _nettoyer_image_base64(image_base64)
            image_data = base64.b64decode(image_base64, validate=True)
            content_file = ContentFile(image_data, name='recherche_divorce_faciale.jpg')
            encodage_capture = ReconnaissanceFacialeService.extraire_encodage_facial(content_file)
        except ValidationError as exc:
            return JsonResponse(
                {'success': False, 'errors': {'image_base64': exc.messages}},
                status=400,
            )
        except (base64.binascii.Error, ValueError):
            return JsonResponse(
                {'success': False, 'errors': {'image_base64': ['Image invalide.']}},
                status=400,
            )

        candidats = []
        for mariage in queryset_mariages_eligibles_divorce()[:50]:
            for role, conjoint, label in (
                ('epoux', mariage.epoux, 'Époux'),
                ('epouse', mariage.epouse, 'Épouse'),
            ):
                encodage = _encodage_facial_conjoint(conjoint)
                if encodage is None:
                    continue
                candidats.append({
                    'mariage': mariage,
                    'id': f"{mariage.pk}-{role}",
                    'encodage': encodage,
                    'meta': {
                        'role': role,
                        'role_label': label,
                        'nom_complet': f"{conjoint.nom} {conjoint.post_nom} {conjoint.prenom}".strip(),
                    },
                })

        if not candidats:
            return JsonResponse({
                'success': True,
                'mariages': [],
                'message': 'Aucune photo faciale enregistrée sur les mariages actifs.',
            })

        correspondance = ReconnaissanceFacialeService.meilleure_correspondance(
            encodage_capture, candidats
        )

        if not correspondance or not correspondance.get('correspondance'):
            return JsonResponse({
                'success': True,
                'mariages': [],
                'message': 'Aucun mariage actif ne correspond à ce visage.',
            })

        mariage = correspondance['mariage']
        confiance = max(
            0,
            min(
                100,
                int((1 - correspondance['distance'] / ReconnaissanceFacialeService.DISTANCE_TOLERANCE) * 100),
            ),
        )
        resultat = serialiser_mariage_divorce(
            mariage,
            correspondance={
                'role': correspondance['meta']['role'],
                'role_label': correspondance['meta']['role_label'],
                'nom_complet': correspondance['meta']['nom_complet'],
                'confiance': confiance,
            },
        )
        return JsonResponse({
            'success': True,
            'mariages': [resultat],
            'message': (
                f"Correspondance : {correspondance['meta']['role_label']} "
                f"{correspondance['meta']['nom_complet']} (confiance {confiance} %)."
            ),
        })


class DivorceEnregistrerAPIView(LoginRequiredMixin, View):
    """Enregistre l'acte de divorce et annule le mariage."""

    def post(self, request):
        mariage_id = request.POST.get('mariage_id')
        date_divorce = request.POST.get('date_divorce')
        motif = (request.POST.get('motif') or '').strip()
        tribunal = (request.POST.get('tribunal') or '').strip()
        numero_divorce = (request.POST.get('numero_divorce') or '').strip()

        if not mariage_id:
            return JsonResponse(
                {'success': False, 'errors': {'mariage_id': ['Mariage requis.']}},
                status=400,
            )

        mariage = get_object_or_404(
            Mariage.objects.select_related('epoux', 'epouse', 'dossier'),
            pk=mariage_id,
            statut='actif',
        )

        if Divorce.objects.filter(mariage=mariage).exists():
            return JsonResponse(
                {'success': False, 'errors': {'mariage_id': ['Ce mariage est déjà divorcé.']}},
                status=400,
            )

        if not date_divorce:
            date_divorce = timezone.now().date()
        else:
            from django.utils.dateparse import parse_date
            parsed = parse_date(date_divorce)
            if not parsed:
                return JsonResponse(
                    {'success': False, 'errors': {'date_divorce': ['Date invalide.']}},
                    status=400,
                )
            date_divorce = parsed

        if not motif:
            motif = 'Dissolution par consentement mutuel enregistrée à l\'état civil.'

        if tribunal:
            motif = f"{motif} — Tribunal : {tribunal}"

        if not numero_divorce:
            numero_divorce = f"DIV-{timezone.now().year}-{mariage.pk:04d}"

        if Divorce.objects.filter(numero_divorce=numero_divorce).exists():
            numero_divorce = f"{numero_divorce}-{timezone.now().strftime('%H%M%S')}"

        decision_file = request.FILES.get('decision_justice')
        if not decision_file:
            decision_file = ContentFile(
                f"Décision de divorce — acte {mariage.numero_acte}".encode('utf-8'),
                name=f'decision_{numero_divorce}.txt',
            )

        try:
            with transaction.atomic():
                divorce = Divorce.objects.create(
                    numero_divorce=numero_divorce,
                    mariage=mariage,
                    date_divorce=date_divorce,
                    motif=motif,
                    decision_justice=decision_file,
                    agent_validation=request.user if request.user.is_authenticated else None,
                )
        except Exception as exc:
            return JsonResponse(
                {'success': False, 'errors': {'enregistrement': [str(exc)]}},
                status=400,
            )

        return JsonResponse({
            'success': True,
            'message': f"Acte de divorce N° {divorce.numero_divorce} enregistré. Le mariage {mariage.numero_acte} est annulé.",
            'divorce_id': divorce.pk,
            'redirect_url': reverse('acte_divorce_detail', args=[divorce.pk]),
        })


class DivorceCreateView(SmartSecurityMixin, AjaxFormMixin, CreateView):
    allowed_roles = ['OFFICIER', 'BOURGMESTRE']
    model = Divorce
    form_class = DivorceForm
    template_name = 'mariage/mariages/divorce_form.html'
    success_url = reverse_lazy('mariage_list')


class ActeDivorceDetailView(SmartSecurityMixin, DetailView):
    allowed_roles = ['OFFICIER', 'BOURGMESTRE', 'OPERATEUR']
    model = Divorce
    template_name = 'mariage/mariages/acte_divorce_detail.html'
    context_object_name = 'divorce'

    def get_queryset(self):
        return Divorce.objects.select_related(
            'mariage__epoux',
            'mariage__epouse',
            'mariage__dossier__commune_enregistrement__ville__province',
        )

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
            
            divorce = Divorce.objects.filter(numero_divorce__icontains=query).first()
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
        if not getattr(request.user, 'role', None) or request.user.role.upper() not in roles_autorises:
            messages.error(request, "Accès refusé. Vous n'avez pas l'autorisation requise.")
            return redirect('dashboard')
            
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        if request.user.is_superuser:
            affectation_commune = Commune.objects.first()
            role_affiche = "SUPER-ADMINISTRATEUR"
        else:
            affectation_commune = request.user.commune
            role_affiche = request.user.role

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

                commune_agent = Commune.objects.first() if request.user.is_superuser else request.user.commune
                
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
        if not utilisateur_peut_acceder_caisse(request.user):
            messages.error(request, "Accès réservé aux agents habilités à consulter la caisse communale.")
            return redirect('dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        communes = list(communes_accessibles(self.request.user))
        commune = commune_caisse_active(
            self.request.user,
            self.request.GET.get('commune'),
        )
        context.update(stats_dashboard_bourgmestre(commune))
        context['communes_accessibles'] = communes
        context['commune_courante'] = commune
        if self.request.user.is_superuser:
            context['role'] = 'SUPER-ADMINISTRATEUR'
        else:
            context['role'] = self.request.user.get_role_display()
        return context


class BourgmestreStatsAPIView(LoginRequiredMixin, View):
    """API JSON pour actualisation du tableau de bord caisse communale."""

    def dispatch(self, request, *args, **kwargs):
        if not utilisateur_peut_acceder_caisse(request.user):
            return JsonResponse({'success': False, 'errors': ['Accès refusé.']}, status=403)
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        commune = commune_caisse_active(request.user, request.GET.get('commune'))
        stats = stats_dashboard_bourgmestre(commune)
        return JsonResponse({
            'success': True,
            'solde': float(stats['solde']),
            'nb_dossiers': stats['nb_dossiers'],
            'nb_mariages_commune': stats['nb_mariages_commune'],
            'nb_divorces_commune': stats['nb_divorces_commune'],
            'recettes_semaine': stats['recettes_semaine'],
            'stats_graph': stats['stats_graph'],
            'commune_nom': stats['commune'].nom if stats['commune'] else '—',
            'commune_id': stats['commune'].pk if stats['commune'] else None,
            'derniere_mise_a_jour': (
                stats['derniere_mise_a_jour'].strftime('%d/%m/%Y %H:%M')
                if stats['derniere_mise_a_jour'] else '—'
            ),
        })



def _maj_conjoint_modification(conjoint, prefixe, post_data, fichiers):
    """Met à jour un époux ou une épouse depuis le formulaire de modification."""
    if not conjoint:
        return

    conjoint.nom = post_data.get(f'{prefixe}_nom', conjoint.nom)
    conjoint.post_nom = post_data.get(f'{prefixe}_postnom', conjoint.post_nom)
    conjoint.prenom = post_data.get(f'{prefixe}_prenom', conjoint.prenom)
    conjoint.telephone = post_data.get(f'{prefixe}_tel', conjoint.telephone)
    conjoint.numero_piece = post_data.get(f'{prefixe}_num_piece', conjoint.numero_piece)
    conjoint.piece_identite = post_data.get(f'{prefixe}_piece_identite', conjoint.piece_identite or "Carte d'Électeur")
    conjoint.profession = post_data.get(f'{prefixe}_profession') or conjoint.profession or 'Sans'
    conjoint.nom_pere = post_data.get(f'{prefixe}_nom_pere') or conjoint.nom_pere
    conjoint.nom_mere = post_data.get(f'{prefixe}_nom_mere') or conjoint.nom_mere
    conjoint.lieu_naissance = post_data.get(f'{prefixe}_lieu_naissance') or conjoint.lieu_naissance
    conjoint.nationalite = post_data.get(f'{prefixe}_nationalite') or conjoint.nationalite or 'Congolaise'
    conjoint.ville_origine = post_data.get(f'{prefixe}_ville_origine') or conjoint.ville_origine
    conjoint.quartier = post_data.get(f'{prefixe}_quartier') or conjoint.quartier
    conjoint.cellule = post_data.get(f'{prefixe}_cellule') or conjoint.cellule
    conjoint.numero_parcelle = post_data.get(f'{prefixe}_numero_parcelle') or conjoint.numero_parcelle
    conjoint.lieu_delivrance = post_data.get(f'{prefixe}_lieu_delivrance') or conjoint.lieu_delivrance

    commune_id = post_data.get(f'{prefixe}_commune_residence')
    if commune_id:
        conjoint.commune_residence_id = commune_id

    date_naissance = post_data.get(f'{prefixe}_date_naissance')
    if date_naissance:
        conjoint.date_naissance = date_naissance

    date_delivrance = post_data.get(f'{prefixe}_date_delivrance')
    if date_delivrance:
        conjoint.date_delivrance = date_delivrance

    if fichiers.get(f'{prefixe}_photo_carte'):
        conjoint.photo_carte = fichiers[f'{prefixe}_photo_carte']
    if fichiers.get(f'{prefixe}_photo'):
        conjoint.photo = fichiers[f'{prefixe}_photo']

    conjoint.save()


def _maj_temoin_modification(dossier, provenance, post_data, fichiers, index):
    """Crée ou met à jour un témoin lié au dossier."""
    prefix = f't{index}_'
    nom = post_data.get(f'{prefix}nom', '').strip()
    if not nom:
        return

    temoin = dossier.temoins.filter(provenance=provenance).first()
    if not temoin:
        temoin = Temoin(dossier=dossier, provenance=provenance, nom=nom)
    else:
        temoin.nom = nom

    temoin.postnom = post_data.get(f'{prefix}postnom') or temoin.postnom
    temoin.prenom = post_data.get(f'{prefix}prenom') or temoin.prenom
    temoin.telephone = post_data.get(f'{prefix}tel') or temoin.telephone
    temoin.numero_piece = post_data.get(f'{prefix}num_piece') or temoin.numero_piece
    temoin.adresse = post_data.get(f'{prefix}adresse') or temoin.adresse

    fichier_carte = fichiers.get(f'{prefix}photo_carte')
    if fichier_carte:
        temoin.photo = fichier_carte

    temoin.save()


def dossier_edit_view(request, pk):
    if not request.user.is_authenticated:
        return redirect('login')

    dossier = get_object_or_404(
        Dossier.objects.select_related(
            'epoux',
            'epouse',
            'epoux__reconnaissance_faciale',
            'epouse__reconnaissance_faciale',
            'commune_enregistrement__ville__province',
            'utilisateur',
        ).prefetch_related('temoins', 'paiements'),
        pk=pk,
    )
    epoux = dossier.epoux
    epouse = dossier.epouse
    paiement = dossier.paiements.last()

    if request.user.is_superuser:
        commune_agent = dossier.commune_enregistrement or Commune.objects.first()
    else:
        commune_agent = getattr(request.user, 'commune', None) or dossier.commune_enregistrement

    if request.method == 'POST' and 'enregistrer_coeur_saisie' in request.POST:
        try:
            with transaction.atomic():
                if epoux:
                    _maj_conjoint_modification(epoux, 'e', request.POST, request.FILES)
                if epouse:
                    _maj_conjoint_modification(epouse, 'f', request.POST, request.FILES)

                dossier.objet = request.POST.get('objet', dossier.objet) or 'mariage civil'
                dossier.statut = request.POST.get('statut', dossier.statut)
                date_depot = request.POST.get('date_depot')
                if date_depot:
                    dossier.date_depot = date_depot
                dossier.save()

                _maj_temoin_modification(dossier, 'EPOUX', request.POST, request.FILES, 1)
                _maj_temoin_modification(dossier, 'EPOUSE', request.POST, request.FILES, 2)

                montant_verse = Decimal(str(request.POST.get('montant_paye', 0) or 0))
                total_du = Decimal(str(request.POST.get('total_du', 50) or 50))
                type_paiement = request.POST.get('type_paiement', 'avance').lower()
                if type_paiement not in ('avance', 'totalite'):
                    type_paiement = 'avance'

                if paiement and dossier.commune_enregistrement:
                    difference = montant_verse - paiement.montant_paye
                    paiement.montant_total_du = total_du
                    paiement.montant_paye = montant_verse
                    paiement.type_paiement = type_paiement
                    paiement.save()

                    if difference != 0:
                        caisse, _ = CaisseCommune.objects.get_or_create(
                            commune=dossier.commune_enregistrement
                        )
                        caisse.solde_actuel += difference
                        caisse.save()
                        MouvementCaisse.objects.create(
                            caisse=caisse,
                            dossier=dossier,
                            montant=difference,
                            agent=request.user,
                        )
                elif montant_verse > 0 and dossier.commune_enregistrement:
                    Paiement.objects.create(
                        dossier=dossier,
                        montant_total_du=total_du,
                        montant_paye=montant_verse,
                        type_paiement=type_paiement,
                        agent_recouvreur=request.user,
                    )
                    caisse, _ = CaisseCommune.objects.get_or_create(
                        commune=dossier.commune_enregistrement
                    )
                    caisse.solde_actuel += montant_verse
                    caisse.save()
                    MouvementCaisse.objects.create(
                        caisse=caisse,
                        dossier=dossier,
                        montant=montant_verse,
                        agent=request.user,
                    )

            messages.success(request, f"Le dossier N° {dossier.numero_dossier} a été modifié avec succès !")
            return redirect('dossier_list')

        except Exception as e:
            messages.error(request, f"Erreur lors de la modification. Détails : {str(e)}")

    temoin_epoux = dossier.temoins.filter(provenance='EPOUX').first()
    temoin_epouse = dossier.temoins.filter(provenance='EPOUSE').first()

    context = {
        'dossier': dossier,
        'epoux': epoux,
        'epouse': epouse,
        'paiement': paiement,
        'temoin_epoux': temoin_epoux,
        'temoin_epouse': temoin_epouse,
        'is_edit': True,
        'etape_biometrie': False,
        'status_choices': Dossier.STATUS_CHOICES,
        'communes': Commune.objects.select_related('ville__province').all(),
        'commune_agent': commune_agent,
    }
    return render(request, 'mariage/dossiers/dossier_form.html', context)