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

    function applyStats(data) {
        document.getElementById('bm-solde').textContent = data.solde.toFixed(2);
        document.getElementById('bm-nb-dossiers').textContent = data.nb_dossiers;
        document.getElementById('bm-nb-mariages').textContent = data.nb_mariages_commune;
        document.getElementById('bm-nb-divorces').textContent = data.nb_divorces_commune;
        document.getElementById('bm-recettes-semaine').textContent = data.recettes_semaine.toFixed(2);
        if (data.commune_nom) document.getElementById('bm-commune-nom').textContent = data.commune_nom;
        if (data.derniere_mise_a_jour) document.getElementById('bm-derniere-maj').textContent = data.derniere_mise_a_jour;

        if (chart && data.stats_graph) {
            chart.data.labels = data.stats_graph.map(function (e) { return e.date; });
            chart.data.datasets[0].data = data.stats_graph.map(function (e) { return e.total; });
            chart.update();
        }
    }

    function refresh() {
        const url = container.dataset.statsUrl;
        if (!url) return;
        const communeId = container.dataset.communeId;
        const fullUrl = communeId ? url + '?commune=' + encodeURIComponent(communeId) : url;
        fetch(fullUrl, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
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
