"""Portails par rôle, capture mobile et recherche nominative."""
import base64
import itertools
import secrets
import uuid
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView

from .capture_mobile import (
    enregistrer_session_locale,
    infos_reseau_capture,
    resoudre_token_local,
    url_capture_courte,
    url_capture_directe,
)
from .dashboard_stats import stats_dashboard_bourgmestre, stats_dashboard_general
from .liste_filtres import filtrer_mariages_par_acces, lire_parametres_filtre, appliquer_filtres_dossier
from .models import (
    Commune,
    Dossier,
    Divorce,
    Epouse,
    Epoux,
    Mariage,
    ProfilCitoyen,
    SessionCaptureMobile,
    photo_conjoint_affichage,
)
from .permissions_commune import (
    communes_accessibles,
    commune_caisse_active,
    filtrer_dossiers_par_acces,
)
from .verification_dossier import _mariage_actif_pour_conjoint
from .role_permissions import (
    communes_perimetre_maire,
    est_portail_public,
    mairie_commune_ville,
    menu_navigation,
    role_utilisateur,
    url_accueil_utilisateur,
    ville_utilisateur,
)


class AccueilRedirectView(LoginRequiredMixin, View):
    """Redirection post-login selon le rôle."""

    def get(self, request):
        return redirect(url_accueil_utilisateur(request.user))


class DashboardMaireView(LoginRequiredMixin, TemplateView):
    template_name = 'mariage/portail/dashboard_maire.html'

    def dispatch(self, request, *args, **kwargs):
        if role_utilisateur(request.user) not in ('MAIRE',) and not request.user.is_superuser:
            messages.error(request, 'Accès réservé au maire.')
            return redirect('dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ville = ville_utilisateur(self.request.user)
        communes = communes_perimetre_maire(self.request.user)
        mairie = mairie_commune_ville(ville) if ville else None

        ctx['ville'] = ville
        ctx['communes'] = communes
        ctx['mairie'] = mairie
        ctx['nb_dossiers_ville'] = Dossier.objects.filter(
            commune_enregistrement__ville=ville
        ).count() if ville else 0
        ctx['nb_mariages_ville'] = Mariage.objects.filter(
            dossier__commune_enregistrement__ville=ville
        ).count() if ville else 0
        ctx['nb_mariages_mairie'] = Dossier.objects.filter(
            celebre_a_mairie=True,
            commune_enregistrement=mairie,
        ).count() if mairie else 0
        ctx['communes_accessibles'] = list(communes_accessibles(self.request.user))
        return ctx


class DashboardHierarchieView(LoginRequiredMixin, TemplateView):
    template_name = 'mariage/portail/dashboard_hierarchie.html'

    def dispatch(self, request, *args, **kwargs):
        if role_utilisateur(request.user) not in ('HIERARCHIE',) and not request.user.is_superuser:
            messages.error(request, 'Accès réservé à la hiérarchie.')
            return redirect('dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        stats = stats_dashboard_general()
        ctx.update(stats)
        ctx['communes'] = Commune.objects.select_related('ville__province').order_by('ville__nom', 'nom')
        ctx['nb_communes'] = ctx['communes'].count()
        return ctx


class PortalConjointView(LoginRequiredMixin, TemplateView):
    template_name = 'mariage/portail/portal_conjoint.html'

    def dispatch(self, request, *args, **kwargs):
        if role_utilisateur(request.user) != 'CONJOINT' and not request.user.is_superuser:
            messages.error(request, 'Accès réservé aux conjoints enregistrés.')
            return redirect('dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        mariage = None
        if user.epoux_lie_id:
            mariage = Mariage.objects.filter(
                epoux=user.epoux_lie, statut='actif'
            ).select_related('epoux', 'epouse', 'dossier').first()
        elif user.epouse_lie_id:
            mariage = Mariage.objects.filter(
                epouse=user.epouse_lie, statut='actif'
            ).select_related('epoux', 'epouse', 'dossier').first()
        ctx['mariage'] = mariage
        return ctx


class PortalCitoyenView(LoginRequiredMixin, TemplateView):
    template_name = 'mariage/portail/portal_citoyen.html'

    def dispatch(self, request, *args, **kwargs):
        if role_utilisateur(request.user) != 'CITOYEN' and not request.user.is_superuser:
            messages.error(request, 'Accès réservé aux citoyens.')
            return redirect('dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        stats = stats_dashboard_general()
        ctx['total_mariages'] = stats.get('total_mariages', 0)
        ctx['mariages_actifs'] = stats.get('mariages_actifs', 0)
        ctx['total_divorces'] = stats.get('total_divorces', 0)
        ctx['total_dossiers'] = stats.get('total_dossiers', 0)
        ctx['chart_labels'] = stats.get('chart_labels', [])
        ctx['chart_data'] = stats.get('chart_data', [])
        profil = getattr(self.request.user, 'profil_citoyen', None)
        ctx['profil'] = profil
        return ctx


class ProfilCitoyenEditView(LoginRequiredMixin, View):
    template_name = 'mariage/portail/profil_citoyen_form.html'

    def dispatch(self, request, *args, **kwargs):
        if role_utilisateur(request.user) != 'CITOYEN' and not request.user.is_superuser:
            return redirect('dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        profil, _ = ProfilCitoyen.objects.get_or_create(
            utilisateur=request.user,
            defaults={'nom': request.user.last_name or request.user.username},
        )
        return render(request, self.template_name, {'profil': profil})

    def post(self, request):
        profil, _ = ProfilCitoyen.objects.get_or_create(
            utilisateur=request.user,
            defaults={'nom': request.POST.get('nom', '')},
        )
        for field in ('nom', 'post_nom', 'prenom', 'telephone', 'numero_piece',
                      'lieu_naissance', 'sexe', 'nationalite', 'profession'):
            setattr(profil, field, request.POST.get(field, getattr(profil, field, '')))
        dn = request.POST.get('date_naissance')
        if dn:
            profil.date_naissance = dn
        if request.FILES.get('photo'):
            profil.photo = request.FILES['photo']
        profil.save()
        messages.success(request, 'Profil civil enregistré. Il préremplira votre dossier le jour du mariage.')
        return redirect('portal_citoyen')


def _lieu_enregistrement_conjoint(conjoint, est_epoux, mariage_actif=None):
    """Commune / ville / province du dossier lié au mariage actif."""
    if mariage_actif and mariage_actif.dossier_id:
        dossier = mariage_actif.dossier
        if dossier.commune_enregistrement_id:
            c = dossier.commune_enregistrement
            return c.nom, c.ville.nom, c.ville.province.nom
    if est_epoux:
        dossier = (
            Dossier.objects.filter(epoux=conjoint)
            .select_related('commune_enregistrement__ville__province')
            .order_by('-date_creation')
            .first()
        )
    else:
        dossier = (
            Dossier.objects.filter(epouse=conjoint)
            .select_related('commune_enregistrement__ville__province')
            .order_by('-date_creation')
            .first()
        )
    if dossier and dossier.commune_enregistrement_id:
        c = dossier.commune_enregistrement
        return c.nom, c.ville.nom, c.ville.province.nom
    c = getattr(conjoint, 'commune_residence', None)
    if c:
        return c.nom, c.ville.nom, c.ville.province.nom
    return '—', '—', '—'


def _url_media_conjoint(conjoint, attr, request=None):
    from django.core.files.storage import default_storage

    img = getattr(conjoint, attr, None)
    if not img or not getattr(img, 'name', None) or not default_storage.exists(img.name):
        return ''
    url = img.url
    if request:
        url = request.build_absolute_uri(url)
    return url


def _url_photo_personne(conjoint, request=None):
    """Photo visage : champ photo, reconnaissance faciale, ou visage sur la carte."""
    url = _url_media_conjoint(conjoint, 'photo', request)
    if url:
        return url
    rf = getattr(conjoint, 'reconnaissance_faciale', None)
    if rf:
        img = getattr(rf, 'photo', None)
        if img and getattr(img, 'name', None):
            from django.core.files.storage import default_storage
            if default_storage.exists(img.name):
                u = img.url
                return request.build_absolute_uri(u) if request else u
    return _url_media_conjoint(conjoint, 'photo_carte', request)


def _serialiser_personne(conjoint, est_epoux, request=None, mariage_actif=None):
    post = getattr(conjoint, 'post_nom', '') or ''
    if mariage_actif is None:
        mariage_actif = _mariage_actif_pour_conjoint(conjoint, est_epoux)
    commune, ville, province = _lieu_enregistrement_conjoint(conjoint, est_epoux, mariage_actif)

    photo_carte_url = _url_media_conjoint(conjoint, 'photo_carte', request)
    photo_dediee = _url_media_conjoint(conjoint, 'photo', request)
    rf_url = ''
    rf = getattr(conjoint, 'reconnaissance_faciale', None)
    if rf and getattr(rf, 'photo', None):
        from django.core.files.storage import default_storage
        if rf.photo.name and default_storage.exists(rf.photo.name):
            rf_url = rf.photo.url
            if request:
                rf_url = request.build_absolute_uri(rf_url)
    if photo_dediee:
        photo_profil_url = photo_dediee
        photo_profil_depuis_carte = False
    elif rf_url:
        photo_profil_url = rf_url
        photo_profil_depuis_carte = False
    elif photo_carte_url:
        # Pas de photo dédiée : recadrer le visage depuis la carte (affichage gauche)
        photo_profil_url = photo_carte_url
        photo_profil_depuis_carte = True
    else:
        photo_profil_url = ''
        photo_profil_depuis_carte = False

    conjoint_lie = ''
    if mariage_actif:
        if est_epoux and mariage_actif.epouse_id:
            ep = mariage_actif.epouse
            conjoint_lie = f"{ep.nom} {ep.post_nom} {ep.prenom}".strip()
        elif not est_epoux and mariage_actif.epoux_id:
            ex = mariage_actif.epoux
            conjoint_lie = f"{ex.nom} {ex.post_nom} {ex.prenom}".strip()
    return {
        'id': conjoint.pk,
        'est_epoux': est_epoux,
        'nom': conjoint.nom,
        'postnom': post,
        'prenom': conjoint.prenom or '',
        'nom_complet': f"{conjoint.nom} {post} {conjoint.prenom or ''}".strip(),
        'numero_piece': conjoint.numero_piece or '',
        'numero_acte': mariage_actif.numero_acte if mariage_actif else '',
        'date_mariage': mariage_actif.date_mariage.isoformat() if mariage_actif and mariage_actif.date_mariage else '',
        'conjoint_lie': conjoint_lie,
        'commune_enregistrement': commune,
        'ville_enregistrement': ville,
        'province_enregistrement': province,
        'photo_url': photo_profil_url,
        'photo_profil_url': photo_profil_url,
        'photo_carte_url': photo_carte_url,
        'photo_profil_depuis_carte': photo_profil_depuis_carte,
        'mariage_actif': bool(mariage_actif),
    }


def _rechercher_par_permutations(role, texte, request):
    """Réessaie en permutant nom, postnom et prénom (2e passe de vérification)."""
    mots = [m for m in texte.split() if m.strip()]
    if len(mots) < 2:
        return []

    est_epoux = role == 'epoux'
    Model = Epoux if est_epoux else Epouse
    mariage_actif_q = Q(mariage__statut='actif') & ~Q(mariage__numero_acte='')
    combos = set()

    if len(mots) == 2:
        a, b = mots
        combos.update([
            (a, b, ''), (a, '', b), (b, a, ''), ('', a, b),
        ])
    else:
        reste = ' '.join(mots[3:]).strip()
        for trio in itertools.permutations(mots[:3]):
            prenom = trio[2]
            if reste:
                prenom = f"{prenom} {reste}".strip()
            combos.add((trio[0], trio[1], prenom))

    resultats = []
    vus = set()
    for nom, postnom, prenom in combos:
        qs = Model.objects.filter(mariage_actif_q).distinct()
        if nom:
            qs = qs.filter(nom__icontains=nom)
        if postnom:
            qs = qs.filter(post_nom__icontains=postnom)
        if prenom:
            qs = qs.filter(prenom__icontains=prenom)
        for obj in qs[:15]:
            if obj.pk in vus:
                continue
            mariage = _mariage_actif_pour_conjoint(obj, est_epoux)
            if mariage:
                vus.add(obj.pk)
                resultats.append(_serialiser_personne(obj, est_epoux, request, mariage))
    return resultats[:30]


class RecherchePersonnesNominativeAPIView(LoginRequiredMixin, View):
    """Recherche nominative : personnes sur un acte de mariage encore actif (non divorcé)."""

    def get(self, request):
        mot = request.GET.get('q', '').strip()
        role = request.GET.get('role', '').strip().lower()

        if role not in ('epoux', 'epouse'):
            return JsonResponse(
                {'success': False, 'errors': ['Paramètre role requis (epoux ou epouse).']},
                status=400,
            )
        if not mot:
            return JsonResponse({'success': True, 'resultats': [], 'count': 0})

        if request.GET.get('permute') == '1':
            resultats = _rechercher_par_permutations(role, mot, request)
            return JsonResponse({
                'success': True,
                'resultats': resultats,
                'count': len(resultats),
                'role': role,
                'filtre': 'mariage_actif',
                'permute': True,
            })

        filtre = (
            Q(nom__icontains=mot)
            | Q(post_nom__icontains=mot)
            | Q(prenom__icontains=mot)
        )
        mariage_actif_q = Q(mariage__statut='actif') & ~Q(mariage__numero_acte='')

        if role == 'epoux':
            qs = (
                Epoux.objects.filter(filtre, mariage_actif_q)
                .select_related('reconnaissance_faciale')
                .distinct()
                .order_by('nom', 'post_nom', 'prenom')[:30]
            )
            resultats = []
            for e in qs:
                mariage = _mariage_actif_pour_conjoint(e, True)
                if mariage:
                    resultats.append(_serialiser_personne(e, True, request, mariage))
        else:
            qs = (
                Epouse.objects.filter(filtre, mariage_actif_q)
                .select_related('reconnaissance_faciale')
                .distinct()
                .order_by('nom', 'post_nom', 'prenom')[:30]
            )
            resultats = []
            for e in qs:
                mariage = _mariage_actif_pour_conjoint(e, False)
                if mariage:
                    resultats.append(_serialiser_personne(e, False, request, mariage))

        return JsonResponse({
            'success': True,
            'resultats': resultats,
            'count': len(resultats),
            'role': role,
            'filtre': 'mariage_actif',
        })


class SessionCaptureMobileTunnelAPIView(LoginRequiredMixin, View):
    """Démarre ou interroge le tunnel Cloudflare pour la capture mobile."""

    def get(self, request):
        from .tunnel_manager import statut_tunnel
        data = statut_tunnel()
        if data.get('url'):
            data['local_url'] = f"{data['url']}/local/"
        return JsonResponse(data)

    def post(self, request):
        from .tunnel_manager import demarrer_tunnel
        return JsonResponse(demarrer_tunnel())


class SessionCaptureMobileCreateAPIView(LoginRequiredMixin, View):
    """Crée une session pour capture depuis téléphone."""

    def post(self, request):
        type_capture = request.POST.get('type_capture', 'photo')
        role_verif = request.POST.get('role', '')
        contexte = request.POST.get('contexte', 'dossier_verif')
        if type_capture not in ('photo', 'empreinte'):
            return JsonResponse({'success': False, 'errors': ['Type invalide.']}, status=400)

        token = secrets.token_urlsafe(32)
        session = SessionCaptureMobile.objects.create(
            token=token,
            agent=request.user,
            type_capture=type_capture,
            role_verif=role_verif,
            contexte=contexte,
            date_expiration=timezone.now() + timedelta(minutes=15),
        )
        enregistrer_session_locale(token)
        reseau = infos_reseau_capture(request)
        capture_url_direct = url_capture_directe(token, request)
        return JsonResponse({
            'success': True,
            'token': token,
            'capture_url': capture_url_direct,
            'capture_url_direct': capture_url_direct,
            'capture_url_short': reseau['capture_url_short'],
            'capture_url_lan': reseau['capture_url_lan'],
            'lan_ip': reseau['lan_ip'],
            'mode': reseau['mode'],
            'tunnel_actif': reseau['tunnel_actif'],
            'tunnel_hint': reseau['tunnel_hint'],
            'poll_url': reverse('mobile_capture_statut', kwargs={'token': token}),
            'expire_minutes': 15,
        })


class SessionCaptureMobileSanteView(View):
    """Test rapide : le téléphone atteint bien Django."""

    def get(self, request):
        return HttpResponse(
            'OK — serveur État civil joignable. Ouvrez /local/ ou le lien de capture.',
            content_type='text/plain; charset=utf-8',
        )


class SessionCaptureMobileLocalView(View):
    """Ouvre /local/ : dernière session de capture active (sans redirection)."""

    template_name = 'mariage/portail/mobile_capture.html'

    def get(self, request):
        token = resoudre_token_local()
        if not token:
            return render(
                request,
                'mariage/portail/mobile_capture_expire.html',
                {
                    'message': (
                        'Aucune session active. Sur le poste de saisie, cliquez '
                        '« Capturer depuis le téléphone », puis ouvrez le lien affiché.'
                    ),
                },
            )
        session = SessionCaptureMobile.objects.filter(token=token).first()
        if not session or session.date_expiration < timezone.now():
            return render(
                request,
                'mariage/portail/mobile_capture_expire.html',
                {
                    'message': 'Session expirée. Cliquez à nouveau « Capturer depuis le téléphone » au guichet.',
                },
            )
        return render(request, self.template_name, {'session': session})


@method_decorator(csrf_exempt, name='dispatch')
class SessionCaptureMobilePageView(View):
    """Page mobile minimaliste pour photo ou empreinte."""

    template_name = 'mariage/portail/mobile_capture.html'

    def get(self, request, token):
        session = get_object_or_404(SessionCaptureMobile, token=token)
        if session.date_expiration < timezone.now():
            return render(request, 'mariage/portail/mobile_capture_expire.html')
        return render(request, self.template_name, {'session': session})

    def post(self, request, token):
        session = get_object_or_404(SessionCaptureMobile, token=token)
        if session.date_expiration < timezone.now():
            return JsonResponse({'success': False, 'errors': ['Session expirée.']}, status=410)

        if request.FILES.get('fichier'):
            session.fichier = request.FILES['fichier']
        b64 = request.POST.get('image_base64', '')
        if b64:
            session.image_base64 = b64
        session.consomme = False
        session.save()
        return JsonResponse({'success': True, 'message': 'Capture reçue par le serveur.'})


class SessionCaptureMobileStatutAPIView(LoginRequiredMixin, View):
    """Polling depuis le poste de saisie."""

    def get(self, request, token):
        session = get_object_or_404(SessionCaptureMobile, token=token, agent=request.user)
        if session.date_expiration < timezone.now():
            return JsonResponse({'success': False, 'expired': True})

        if session.fichier or session.image_base64:
            data = {'success': True, 'ready': True, 'type_capture': session.type_capture}
            if session.image_base64:
                data['image_base64'] = session.image_base64
            if session.fichier:
                data['fichier_url'] = request.build_absolute_uri(session.fichier.url)
            session.consomme = True
            session.save(update_fields=['consomme'])
            return JsonResponse(data)

        return JsonResponse({'success': True, 'ready': False})


def profil_citoyen_pour_identite(nom, postnom, prenom, numero_piece=None):
    """Retrouve un profil citoyen pour préremplissage dossier."""
    qs = ProfilCitoyen.objects.all()
    if numero_piece:
        p = qs.filter(numero_piece=numero_piece).first()
        if p:
            return p
    if nom:
        qs = qs.filter(nom__iexact=nom.strip())
        if postnom:
            qs = qs.filter(post_nom__iexact=postnom.strip())
        if prenom:
            qs = qs.filter(prenom__iexact=prenom.strip())
        return qs.first()
    return None
