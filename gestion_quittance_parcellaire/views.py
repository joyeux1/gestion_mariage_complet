from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.shortcuts import redirect
from django.views.generic import ListView

from mariage.role_permissions import role_utilisateur, url_accueil_utilisateur
from mariage.roles import ROLES_AUTORITE

from .models import QuittanceParcellaire
from .permissions import filtrer_quittances_par_acces, libelle_perimetre_quittances


class QuittanceSecurityMixin(LoginRequiredMixin):
    """Accès réservé aux autorités (nationales et provinciales)."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if request.user.is_superuser:
            return super().dispatch(request, *args, **kwargs)
        role = role_utilisateur(request.user)
        if role not in ROLES_AUTORITE:
            messages.error(
                request,
                'Accès réservé aux autorités (Gouverneur, Ministres, Présidence…).',
            )
            return redirect(url_accueil_utilisateur(request.user))
        return super().dispatch(request, *args, **kwargs)


class QuittanceListView(QuittanceSecurityMixin, ListView):
    model = QuittanceParcellaire
    template_name = 'gestion_quittance_parcellaire/quittance_list.html'
    context_object_name = 'quittances'
    paginate_by = 25

    def get_queryset(self):
        return filtrer_quittances_par_acces(self.request.user)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['perimetre_label'] = libelle_perimetre_quittances(self.request.user)
        return ctx
