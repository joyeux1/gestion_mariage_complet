(function () {
    'use strict';

    const form = document.getElementById('form-filtre-dossiers');
    const tbody = document.getElementById('dossier-list-tbody');
    if (!form || !tbody) return;

    const searchUrl = form.dataset.searchUrl;
    const nomInput = form.querySelector('[name="nom"]');
    const numeroInput = form.querySelector('[name="numero"]');
    const sousTitre = document.getElementById('dossier-list-sous-titre');
    const indicateur = document.getElementById('dossier-list-loading');

    let timer = null;
    let requeteEnCours = null;

    function collectParams() {
        const params = new URLSearchParams();
        form.querySelectorAll('input, select').forEach(function (el) {
            if (!el.name) return;
            const val = (el.value || '').trim();
            if (val) params.set(el.name, val);
        });
        return params;
    }

    function majUrl(params) {
        const qs = params.toString();
        const url = window.location.pathname + (qs ? '?' + qs : '');
        history.replaceState(null, '', url);
    }

    function initPhotoThumbs() {
        const modalEl = document.getElementById('modalPhotoConjoint');
        if (!modalEl) return;

        const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
        const imgEl = document.getElementById('modalPhotoConjointImg');
        const titleEl = document.getElementById('modalPhotoConjointLabel');

        function ouvrirPhoto(thumb) {
            const url = thumb.dataset.photoUrl;
            const label = thumb.dataset.photoLabel || 'Photo du conjoint';
            if (!url) return;
            imgEl.src = url;
            imgEl.alt = label;
            titleEl.textContent = label;
            modal.show();
        }

        tbody.querySelectorAll('.photo-conjoint-thumb').forEach(function (thumb) {
            thumb.addEventListener('click', function () { ouvrirPhoto(thumb); });
            thumb.addEventListener('keydown', function (e) {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    ouvrirPhoto(thumb);
                }
            });
        });
    }

    function setChargement(actif) {
        if (!indicateur) return;
        indicateur.classList.toggle('d-none', !actif);
    }

    function lancerRecherche() {
        if (!searchUrl) return;

        const params = collectParams();
        majUrl(params);

        if (requeteEnCours) requeteEnCours.abort();
        const controller = new AbortController();
        requeteEnCours = controller;

        setChargement(true);

        fetch(searchUrl + '?' + params.toString(), {
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            credentials: 'same-origin',
            signal: controller.signal,
        })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (!data.success) return;
                tbody.innerHTML = data.html;
                if (sousTitre && data.sous_titre) {
                    sousTitre.textContent = data.sous_titre;
                }
                initPhotoThumbs();
            })
            .catch(function (err) {
                if (err.name !== 'AbortError') console.error(err);
            })
            .finally(function () {
                if (requeteEnCours === controller) {
                    requeteEnCours = null;
                    setChargement(false);
                }
            });
    }

    function onSaisieProgressive() {
        clearTimeout(timer);
        timer = setTimeout(lancerRecherche, 280);
    }

    [nomInput, numeroInput].forEach(function (input) {
        if (input) input.addEventListener('input', onSaisieProgressive);
    });

    form.addEventListener('submit', function (e) {
        e.preventDefault();
        clearTimeout(timer);
        lancerRecherche();
    });

    initPhotoThumbs();
})();
