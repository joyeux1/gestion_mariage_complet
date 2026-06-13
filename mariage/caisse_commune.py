"""Mouvements et solde de la caisse communale."""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db.models import Case, F, Sum, When
from django.db.models.functions import TruncDate

from .models import CaisseCommune, MouvementCaisse

MOTIF_ENTREE_MARIAGE = 'Enregistrement nouveau mariage'
MOTIF_SORTIE_BOURGMESTRE = 'Sortie caisse par le bourgmestre'


def enregistrer_mouvement_entree(caisse, dossier, montant, agent, paiement=None):
    """Crédite la caisse et enregistre une entrée liée à un dossier."""
    montant = Decimal(str(montant))
    if montant == 0:
        return None

    if paiement is None and dossier:
        paiement = dossier.paiements.order_by('-date_paiement').first()

    montant_total_du = paiement.montant_total_du if paiement else None
    montant_paye = paiement.montant_paye if paiement else None

    caisse.solde_actuel += montant
    caisse.save(update_fields=['solde_actuel', 'derniere_mise_a_jour'])

    return MouvementCaisse.objects.create(
        caisse=caisse,
        type_mouvement='entree',
        motif=MOTIF_ENTREE_MARIAGE,
        dossier=dossier,
        paiement=paiement,
        montant=montant,
        montant_total_du=montant_total_du,
        montant_paye=montant_paye,
        agent=agent,
    )


def enregistrer_sortie_caisse(caisse, montant, agent, motif=None):
    """Débite la caisse (réservé au bourgmestre)."""
    montant = Decimal(str(montant))
    if montant <= 0:
        raise ValidationError('Le montant de sortie doit être positif.')
    if caisse.solde_actuel < montant:
        raise ValidationError('Solde insuffisant dans la caisse communale.')

    caisse.solde_actuel -= montant
    caisse.save(update_fields=['solde_actuel', 'derniere_mise_a_jour'])

    return MouvementCaisse.objects.create(
        caisse=caisse,
        type_mouvement='sortie',
        motif=motif or MOTIF_SORTIE_BOURGMESTRE,
        montant=montant,
        agent=agent,
    )


def _nom_complet_conjoint(conjoint):
    if not conjoint:
        return '—'
    return ' '.join(
        filter(None, [conjoint.nom, conjoint.post_nom, conjoint.prenom])
    ).strip() or '—'


def _ligne_mouvement(mouvement):
    dossier = mouvement.dossier
    paiement = mouvement.paiement
    if not paiement and dossier:
        paiement = dossier.paiements.order_by('-date_paiement').first()

    montant_du = mouvement.montant_total_du
    montant_verse = mouvement.montant_paye
    if montant_du is None and paiement:
        montant_du = paiement.montant_total_du
    if montant_verse is None and paiement:
        montant_verse = paiement.montant_paye

    restant = None
    if montant_du is not None and montant_verse is not None:
        restant = montant_du - montant_verse

    motif = mouvement.motif
    if not motif:
        motif = (
            MOTIF_SORTIE_BOURGMESTRE
            if mouvement.type_mouvement == 'sortie'
            else MOTIF_ENTREE_MARIAGE
        )

    epoux = dossier.epoux if dossier else None
    epouse = dossier.epouse if dossier else None

    return {
        'id': mouvement.pk,
        'date_paiement': mouvement.date_mouvement.strftime('%d/%m/%Y %H:%M'),
        'motif': motif,
        'type_mouvement': mouvement.type_mouvement,
        'montant_du': float(montant_du) if montant_du is not None else None,
        'montant_verse': float(montant_verse) if montant_verse is not None else None,
        'montant_mouvement': float(mouvement.montant),
        'montant_net': float(mouvement.montant_net),
        'montant_restant': float(restant) if restant is not None else None,
        'epoux': _nom_complet_conjoint(epoux),
        'epouse': _nom_complet_conjoint(epouse),
        'numero_dossier': dossier.numero_dossier if dossier else '',
        'agent': mouvement.agent.get_full_name() or mouvement.agent.username,
    }


def mouvements_caisse_commune(commune):
    """Liste des mouvements pour affichage tableau de bord."""
    if not commune:
        return [], Decimal('0.00')

    caisse, _ = CaisseCommune.objects.get_or_create(commune=commune)
    qs = (
        MouvementCaisse.objects.filter(caisse=caisse)
        .select_related('dossier__epoux', 'dossier__epouse', 'paiement', 'agent')
        .order_by('-date_mouvement')
    )
    lignes = [_ligne_mouvement(m) for m in qs]
    return lignes, caisse.solde_actuel


def somme_nette_mouvements(queryset):
    """Somme entrées − sorties."""
    return queryset.aggregate(
        total=Sum(
            Case(
                When(type_mouvement='sortie', then=-F('montant')),
                default=F('montant'),
            )
        )
    )['total'] or Decimal('0.00')
