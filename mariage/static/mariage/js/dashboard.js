// static/mariage/js/dashboard.js

const DASHBOARD_REFRESH_MS = 45000;

function createLineChart(canvasId, labels, data, label) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || typeof Chart === 'undefined') return null;

    return new Chart(canvas.getContext('2d'), {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: label,
                data: data,
                borderColor: '#0d6efd',
                backgroundColor: 'rgba(13, 110, 253, 0.1)',
                fill: true,
                tension: 0.35,
                borderWidth: 2,
                pointBackgroundColor: '#0d6efd',
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                y: { beginAtZero: true, grid: { borderDash: [2, 2] } },
                x: { grid: { display: false } },
            },
        },
    });
}

function initDashboardMain(initial) {
    const container = document.getElementById('dashboard-main');
    if (!container) return;

    let chart = createLineChart(
        'mariageChart',
        initial.labels,
        initial.data,
        'Mariages par mois'
    );

    function updateVariation(pct, dir) {
        const el = document.getElementById('kpi-variation-mariages');
        if (!el) return;
        const icon = dir === 'up' ? '<i class="bi bi-arrow-up"></i>' : dir === 'down' ? '<i class="bi bi-arrow-down"></i>' : '';
        el.className = dir === 'down' ? 'text-danger' : dir === 'up' ? 'text-success' : 'text-muted';
        el.innerHTML = `${icon} ${pct}% ce mois`;
    }

    function updateActivites(items) {
        const list = document.getElementById('dash-activites-list');
        if (!list) return;
        if (!items.length) {
            list.innerHTML = '<div class="list-group-item border-0 px-4 py-4 text-muted text-center small">Aucune activité récente.</div>';
            return;
        }
        list.innerHTML = items.map(function (act) {
            return `<div class="list-group-item border-0 px-4 py-3">
                <div class="d-flex justify-content-between align-items-start">
                    <span class="fw-bold small">${act.titre}</span>
                    <span class="text-muted x-small">${act.date_label}</span>
                </div>
                <p class="text-muted mb-1 small">${act.detail}</p>
                <span class="badge ${act.badge_class}">${act.badge_label}</span>
            </div>`;
        }).join('');
    }

    function applyStats(data) {
        document.getElementById('kpi-total-mariages').textContent = data.total_mariages;
        document.getElementById('kpi-dossiers-cours').textContent = data.dossiers_en_cours;
        document.getElementById('kpi-total-epoux').textContent = data.total_epoux;
        document.getElementById('kpi-taux-succes').textContent = data.taux_succes;
        document.getElementById('kpi-dossiers-valides').textContent = data.dossiers_valides;
        document.getElementById('kpi-total-dossiers').textContent = data.total_dossiers;
        document.getElementById('kpi-mariages-actifs').textContent = data.mariages_actifs;
        document.getElementById('kpi-total-divorces').textContent = data.total_divorces;
        if (data.now_label) document.getElementById('dash-date-label').textContent = data.now_label;
        if (data.perimetre_label) {
            const perimetreEl = document.getElementById('dash-perimetre-label');
            if (perimetreEl) {
                perimetreEl.innerHTML = '<i class="bi bi-geo-alt me-1"></i> Périmètre : <strong>'
                    + data.perimetre_label + '</strong>';
            }
        }
        updateVariation(data.variation_mariages_pct, data.variation_mariages_dir);
        updateActivites(data.activites_recentes || []);

        if (chart) {
            chart.data.labels = data.chart_labels;
            chart.data.datasets[0].data = data.chart_data;
            chart.update();
        }
    }

    function refresh() {
        const url = container.dataset.statsUrl;
        if (!url) return;
        fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.success) applyStats(data);
            })
            .catch(function () { /* silencieux */ });
    }

    setInterval(refresh, DASHBOARD_REFRESH_MS);
    document.addEventListener('visibilitychange', function () {
        if (!document.hidden) refresh();
    });
}

function initDashboardBourgmestre(initial) {
    const container = document.getElementById('dashboard-bourgmestre');
    if (!container) return;

    const graph = initial.graph || [];
    let chart = createLineChart(
        'recettesChart',
        graph.map(function (e) { return e.date; }),
        graph.map(function (e) { return e.total; }),
        'Recettes journalières ($)'
    );

    const modalEl = document.getElementById('modalMouvementsCaisse');
    let modalInstance = null;

    function getCommuneQuery() {
        const communeId = container.dataset.communeId;
        return communeId ? '?commune=' + encodeURIComponent(communeId) : '';
    }

    function formatMontant(val) {
        if (val === null || val === undefined) return '—';
        return Number(val).toFixed(2) + ' $';
    }

    function afficherMouvements(data) {
        const tbody = document.getElementById('bm-mouvements-body');
        const footer = document.getElementById('bm-solde-footer');
        if (!tbody) return;

        const mouvements = data.mouvements || [];
        if (!mouvements.length) {
            tbody.innerHTML = '<tr><td colspan="8" class="text-center text-muted py-4">Aucun mouvement enregistré.</td></tr>';
        } else {
            tbody.innerHTML = mouvements.map(function (m) {
                const rowClass = m.type_mouvement === 'sortie' ? 'table-danger' : '';
                const montantVerse = m.type_mouvement === 'sortie'
                    ? '− ' + formatMontant(m.montant_mouvement)
                    : formatMontant(m.montant_verse);
                return '<tr class="' + rowClass + '">'
                    + '<td class="text-nowrap">' + m.date_paiement + '</td>'
                    + '<td>' + m.motif + '</td>'
                    + '<td class="text-end">' + formatMontant(m.montant_du) + '</td>'
                    + '<td class="text-end fw-semibold">' + montantVerse + '</td>'
                    + '<td class="text-end">' + formatMontant(m.montant_restant) + '</td>'
                    + '<td>' + (m.epoux || '—') + '</td>'
                    + '<td>' + (m.epouse || '—') + '</td>'
                    + '<td class="small">' + (m.numero_dossier || '—') + '</td>'
                    + '</tr>';
            }).join('');
        }

        if (footer && data.solde_total !== undefined) {
            footer.textContent = Number(data.solde_total).toFixed(2) + ' $';
        }
        if (data.solde_total !== undefined) {
            document.getElementById('bm-solde').textContent = Number(data.solde_total).toFixed(2);
        }
    }

    function chargerMouvements() {
        const url = container.dataset.mouvementsUrl;
        if (!url) return Promise.resolve();

        const loading = document.getElementById('bm-mouvements-loading');
        const erreur = document.getElementById('bm-mouvements-erreur');
        if (loading) loading.classList.remove('d-none');
        if (erreur) erreur.classList.add('d-none');

        return fetch(url + getCommuneQuery(), { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (loading) loading.classList.add('d-none');
                if (data.success) {
                    afficherMouvements(data);
                } else if (erreur) {
                    erreur.textContent = (data.errors || ['Erreur de chargement.']).join(' ');
                    erreur.classList.remove('d-none');
                }
            })
            .catch(function () {
                if (loading) loading.classList.add('d-none');
                if (erreur) {
                    erreur.textContent = 'Impossible de charger les mouvements.';
                    erreur.classList.remove('d-none');
                }
            });
    }

    function ouvrirModalMouvements() {
        if (!modalEl || typeof bootstrap === 'undefined') return;
        if (!modalInstance) modalInstance = new bootstrap.Modal(modalEl);
        modalInstance.show();
        chargerMouvements();
    }

    document.getElementById('bm-card-recettes')?.addEventListener('click', ouvrirModalMouvements);

    const formSortie = document.getElementById('bm-form-sortie');
    if (formSortie) {
        formSortie.addEventListener('submit', function (e) {
            e.preventDefault();
            const sortieUrl = container.dataset.sortieUrl;
            const msgEl = document.getElementById('bm-sortie-message');
            if (!sortieUrl) return;

            const fd = new FormData(formSortie);
            const communeId = container.dataset.communeId;
            if (communeId) fd.append('commune', communeId);

            fetch(sortieUrl, {
                method: 'POST',
                body: fd,
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
            })
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    if (data.success) {
                        afficherMouvements(data);
                        formSortie.reset();
                        if (msgEl) {
                            msgEl.className = 'small text-success';
                            msgEl.textContent = data.message;
                        }
                    } else if (msgEl) {
                        msgEl.className = 'small text-danger';
                        msgEl.textContent = (data.errors || ['Erreur.']).join(' ');
                    }
                })
                .catch(function () {
                    if (msgEl) {
                        msgEl.className = 'small text-danger';
                        msgEl.textContent = 'Erreur réseau.';
                    }
                });
        });
    }

    function applyStats(data) {
        document.getElementById('bm-solde').textContent = data.solde.toFixed(2);
        document.getElementById('bm-nb-dossiers').textContent = data.nb_dossiers;
        document.getElementById('bm-nb-mariages').textContent = data.nb_mariages_commune;
        document.getElementById('bm-nb-divorces').textContent = data.nb_divorces_commune;
        document.getElementById('bm-recettes-semaine').textContent = data.recettes_semaine.toFixed(2);
        if (data.commune_nom) document.getElementById('bm-commune-nom').textContent = data.commune_nom;
        if (data.derniere_mise_a_jour) document.getElementById('bm-derniere-maj').textContent = data.derniere_mise_a_jour;
        const footer = document.getElementById('bm-solde-footer');
        if (footer) footer.textContent = data.solde.toFixed(2) + ' $';

        if (chart && data.stats_graph) {
            chart.data.labels = data.stats_graph.map(function (e) { return e.date; });
            chart.data.datasets[0].data = data.stats_graph.map(function (e) { return e.total; });
            chart.update();
        }
    }

    function refresh() {
        const url = container.dataset.statsUrl;
        if (!url) return;
        fetch(url + getCommuneQuery(), { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.success) applyStats(data);
            })
            .catch(function () { /* silencieux */ });
    }

    setInterval(refresh, DASHBOARD_REFRESH_MS);
    document.addEventListener('visibilitychange', function () {
        if (!document.hidden) refresh();
    });
}

window.initDashboardMain = initDashboardMain;
window.initDashboardBourgmestre = initDashboardBourgmestre;
