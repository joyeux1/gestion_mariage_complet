// static/mariage/js/divorce_list.js

let mariageDivorceSelectionne = null;
let divorceFacialStream = null;
let divorceFacialCameraActive = false;

function getContainer() {
    return document.getElementById('divorce-app-container');
}

function getCsrfToken() {
    return getContainer()?.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
}

function showDivorceView(viewId) {
    ['view-list-divorces', 'view-recherche-divorce', 'view-ceremonie-divorce'].forEach(function (id) {
        const el = document.getElementById(id);
        if (el) el.classList.toggle('d-none', id !== viewId);
    });
}

function ouvrirRechercheDivorce() {
    mariageDivorceSelectionne = null;
    window._divorceMariageIdentifie = null;
    showDivorceView('view-recherche-divorce');
}

function revenirListeDivorce() {
    mariageDivorceSelectionne = null;
    arreterWebcamDivorce();
    showDivorceView('view-list-divorces');
}

function retourRechercheDivorce() {
    showDivorceView('view-recherche-divorce');
}

function showDivorceAlert(message, type) {
    const zone = document.getElementById('divorce-alert-zone');
    if (!zone) return;
    zone.innerHTML = `<div class="alert alert-${type} alert-dismissible fade show">${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button></div>`;
}

function afficherResultatsMariages(mariages) {
    const block = document.getElementById('divorce-resultats-mariages');
    const tbody = document.getElementById('divorce-table-mariages');
    if (!block || !tbody) return;

    if (!mariages.length) {
        block.classList.add('d-none');
        tbody.innerHTML = '';
        return;
    }

    tbody.innerHTML = mariages.map(function (m, index) {
        const lieu = m.lieu ? `Commune de ${m.lieu.commune} (${m.lieu.ville})` : (m.lieu_mariage || '—');
        const badge = m.correspondance
            ? `<br><span class="badge bg-info text-dark mt-1">${m.correspondance.role_label} — ${m.correspondance.confiance} %</span>`
            : '';
        return `<tr>
            <td class="fw-bold text-primary">${m.numero_acte}</td>
            <td>${m.epoux.nom_complet}${m.correspondance && m.correspondance.role === 'epoux' ? badge : ''}</td>
            <td>${m.epouse.nom_complet}${m.correspondance && m.correspondance.role === 'epouse' ? badge : ''}</td>
            <td class="small">${lieu}</td>
            <td class="text-center">
                <button type="button" class="btn btn-sm btn-danger btn-select-mariage-divorce" data-index="${index}">
                    Procéder au divorce
                </button>
            </td>
        </tr>`;
    }).join('');

    window._divorceMariagesResultats = mariages;
    block.classList.remove('d-none');

    tbody.querySelectorAll('.btn-select-mariage-divorce').forEach(function (btn) {
        btn.addEventListener('click', function () {
            const idx = parseInt(btn.dataset.index, 10);
            if (window._divorceMariagesResultats && window._divorceMariagesResultats[idx]) {
                selectionnerMariageDivorce(window._divorceMariagesResultats[idx]);
            }
        });
    });
}

function selectionnerMariageDivorce(mariage) {
    mariageDivorceSelectionne = mariage;
    document.getElementById('ceremonie-numero-acte').textContent = mariage.numero_acte;
    document.getElementById('ceremonie-mariage-id').value = mariage.id;
    document.getElementById('ceremonie-numero-divorce').placeholder =
        `DIV-${new Date().getFullYear()}-${String(mariage.id).padStart(4, '0')}`;

    const embedUrl = mariage.acte_url ? mariage.acte_url.replace(/\/acte\/?$/, '/acte/embed/') : '';
    const iframe = document.getElementById('ceremonie-acte-iframe');
    const lien = document.getElementById('ceremonie-acte-lien');
    if (iframe) iframe.src = embedUrl || mariage.acte_url || '';
    if (lien) lien.href = mariage.acte_url || '#';

    document.getElementById('ceremonie-identites').innerHTML = `
        <p class="mb-1"><strong>Époux :</strong> ${mariage.epoux.nom_complet}</p>
        <p class="mb-1"><strong>Épouse :</strong> ${mariage.epouse.nom_complet}</p>
        <p class="mb-0 text-muted">Mariage célébré le ${mariage.date_mariage || '—'} — ${mariage.lieu_mariage || ''}</p>`;

    const dateInput = document.querySelector('#form-enregistrer-divorce [name=date_divorce]');
    if (dateInput && !dateInput.value) {
        dateInput.value = new Date().toISOString().split('T')[0];
    }

    showDivorceView('view-ceremonie-divorce');
}

function rechercherDivorceNominatif() {
    const container = getContainer();
    const nom = document.getElementById('divorce-nom')?.value || '';
    const postnom = document.getElementById('divorce-postnom')?.value || '';
    const prenom = document.getElementById('divorce-prenom')?.value || '';
    const url = container?.dataset.rechercheNomUrl;

    if (!nom && !postnom && !prenom) {
        showDivorceAlert('Saisissez au moins un critère de recherche.', 'warning');
        return;
    }

    const params = new URLSearchParams({ nom, postnom, prenom });
    fetch(`${url}?${params}`, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
        .then((r) => r.json())
        .then((data) => {
            if (!data.success) {
                showDivorceAlert(Object.values(data.errors || {}).flat().join(' '), 'danger');
                return;
            }
            if (data.message) showDivorceAlert(data.message, data.mariages.length ? 'success' : 'info');
            else showDivorceAlert(`${data.mariages.length} mariage(s) actif(s) trouvé(s).`, 'success');
            afficherResultatsMariages(data.mariages);
        })
        .catch(() => showDivorceAlert('Erreur de connexion au serveur.', 'danger'));
}

function rechercherDivorceEmpreinte() {
    const container = getContainer();
    const url = container?.dataset.rechercheEmpreinteUrl;
    const epoux = document.getElementById('divorce-empreinte-epoux');
    const epouse = document.getElementById('divorce-empreinte-epouse');

    if (!epoux?.files?.length && !epouse?.files?.length) {
        showDivorceAlert('Chargez au moins une empreinte (époux ou épouse).', 'warning');
        return;
    }

    const fd = new FormData();
    fd.append('csrfmiddlewaretoken', getCsrfToken());
    if (epoux?.files?.length) fd.append('scan_empreinte_epoux', epoux.files[0]);
    if (epouse?.files?.length) fd.append('scan_empreinte_epouse', epouse.files[0]);

    fetch(url, {
        method: 'POST',
        body: fd,
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
    })
        .then((r) => r.json())
        .then((data) => {
            if (!data.success) {
                showDivorceAlert(Object.values(data.errors || {}).flat().join(' '), 'danger');
                return;
            }
            if (data.message) showDivorceAlert(data.message, data.mariages.length ? 'success' : 'info');
            else showDivorceAlert(`${data.mariages.length} mariage(s) identifié(s).`, 'success');
            afficherResultatsMariages(data.mariages);
        })
        .catch(() => showDivorceAlert('Erreur de connexion au serveur.', 'danger'));
}

function arreterWebcamDivorce() {
    if (divorceFacialStream) {
        divorceFacialStream.getTracks().forEach(function (t) { t.stop(); });
        divorceFacialStream = null;
    }
    divorceFacialCameraActive = false;
    const video = document.getElementById('divorce-facial-webcam');
    if (video) video.srcObject = null;
}

async function demarrerWebcamDivorce() {
    const video = document.getElementById('divorce-facial-webcam');
    if (!video || !navigator.mediaDevices) {
        showDivorceAlert('Webcam non disponible.', 'danger');
        return;
    }
    try {
        arreterWebcamDivorce();
        divorceFacialStream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } },
            audio: false,
        });
        video.srcObject = divorceFacialStream;
        await video.play();
        divorceFacialCameraActive = true;
    } catch (e) {
        showDivorceAlert('Accès caméra refusé : ' + e.message, 'danger');
    }
}

function capturerPhotoDivorce() {
    const video = document.getElementById('divorce-facial-webcam');
    const canvas = document.getElementById('divorce-facial-canvas');
    const hidden = document.getElementById('divorce-facial-base64');
    const searchBtn = document.getElementById('divorce-facial-search-btn');

    if (!video || !canvas || !hidden || !video.videoWidth) {
        showDivorceAlert('Webcam non prête.', 'warning');
        return;
    }
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext('2d').drawImage(video, 0, 0);
    hidden.value = canvas.toDataURL('image/jpeg');
    arreterWebcamDivorce();
    if (searchBtn) searchBtn.disabled = false;
    showDivorceAlert('Photo capturée. Lancez la recherche faciale.', 'success');
}

function rechercherDivorceFacial() {
    const container = getContainer();
    const url = container?.dataset.rechercheFacialeUrl;
    const b64 = document.getElementById('divorce-facial-base64')?.value;

    if (!b64) {
        showDivorceAlert('Capturez d\'abord une photo.', 'warning');
        return;
    }

    const fd = new FormData();
    fd.append('csrfmiddlewaretoken', getCsrfToken());
    fd.append('image_base64', b64);

    fetch(url, { method: 'POST', body: fd, headers: { 'X-Requested-With': 'XMLHttpRequest' } })
        .then((r) => r.json())
        .then((data) => {
            if (!data.success) {
                showDivorceAlert(Object.values(data.errors || {}).flat().join(' '), 'danger');
                return;
            }
            if (data.message) showDivorceAlert(data.message, data.mariages.length ? 'success' : 'info');
            afficherResultatsMariages(data.mariages);
        })
        .catch(() => showDivorceAlert('Erreur de connexion au serveur.', 'danger'));
}

document.getElementById('divorce-facial-camera-btn')?.addEventListener('click', function () {
    if (!divorceFacialCameraActive) demarrerWebcamDivorce();
    else capturerPhotoDivorce();
});

document.getElementById('divorce-facial-search-btn')?.addEventListener('click', rechercherDivorceFacial);

document.getElementById('form-enregistrer-divorce')?.addEventListener('submit', function (e) {
    e.preventDefault();
    const container = getContainer();
    const url = container?.dataset.enregistrerUrl;
    const btn = document.getElementById('btn-enregistrer-divorce');
    const fd = new FormData(this);
    fd.append('csrfmiddlewaretoken', getCsrfToken());

    if (!confirm('Confirmez-vous l\'enregistrement de l\'acte de divorce et l\'annulation du mariage ?')) {
        return;
    }

    btn.disabled = true;
    fetch(url, { method: 'POST', body: fd, headers: { 'X-Requested-With': 'XMLHttpRequest' } })
        .then((r) => r.json())
        .then((data) => {
            if (!data.success) {
                btn.disabled = false;
                showDivorceAlert(Object.values(data.errors || {}).flat().join(' '), 'danger');
                return;
            }
            showToast(data.message, 'success');
            if (data.redirect_url) {
                setTimeout(function () { window.location.href = data.redirect_url; }, 1200);
            } else {
                window.location.reload();
            }
        })
        .catch(function () {
            btn.disabled = false;
            showDivorceAlert('Erreur lors de l\'enregistrement.', 'danger');
        });
});

window.onDivorceVerifComplete = function () {
    const mariage = window._divorceMariageIdentifie;
    if (mariage) {
        selectionnerMariageDivorce(mariage);
    } else {
        showDivorceAlert('Mariage identifié mais données incomplètes — recommencez la vérification.', 'warning');
    }
};

window.ouvrirRechercheDivorce = ouvrirRechercheDivorce;
window.revenirListeDivorce = revenirListeDivorce;
window.retourRechercheDivorce = retourRechercheDivorce;
window.rechercherDivorceNominatif = rechercherDivorceNominatif;
window.rechercherDivorceEmpreinte = rechercherDivorceEmpreinte;
