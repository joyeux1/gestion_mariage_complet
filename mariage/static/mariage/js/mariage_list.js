// static/mariage/js/mariage_list.js

let dossierSelectionne = null;
let mariageFacialStream = null;
let mariageFacialCameraActive = false;

function getCsrfToken() {
    const input = document.querySelector('[name=csrfmiddlewaretoken]');
    return input ? input.value : '';
}

function showView(viewId) {
    const showList = viewId === 'view-list-mariages';
    ['view-list-mariages', 'view-recherche-dossier', 'view-formulaire-generation'].forEach(function (id) {
        const el = document.getElementById(id);
        if (el) {
            el.classList.toggle('d-none', id !== viewId);
        }
    });
    const btnWrap = document.getElementById('mariage-btn-nouveau-wrap');
    if (btnWrap) {
        btnWrap.classList.toggle('d-none', !showList);
    }
}

function openNouveauMariageWorkflow() {
    dossierSelectionne = null;
    document.getElementById('resultats-dossiers-container')?.classList.add('d-none');
    document.getElementById('table-resultat-dossiers').innerHTML = '';
    arreterWebcamFacialeMariage();
    showView('view-recherche-dossier');
}

function resetToListView() {
    dossierSelectionne = null;
    arreterWebcamFacialeMariage();
    showView('view-list-mariages');
}

function simulerScanBiometriqueMariage() {
    executerRechercheDossier();
    showToast('Recherche biométrique simulée : affichage des dossiers éligibles.', 'info');
}

function executerRechercheDossier() {
    const nom = document.getElementById('s_nom')?.value || '';
    const postnom = document.getElementById('s_postnom')?.value || '';
    const prenom = document.getElementById('s_prenom')?.value || '';

    const params = new URLSearchParams({ nom, postnom, prenom });
    const url = document.getElementById('mariage-app-container')?.dataset.rechercheUrl;

    if (!url) {
        showToast('Configuration de recherche manquante.', 'danger');
        return;
    }

    fetch(`${url}?${params}`, {
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
    })
        .then((response) => response.json())
        .then((data) => {
            if (!data.success) {
                showToast('Erreur lors de la recherche.', 'danger');
                return;
            }
            if (data.message) {
                showToast(data.message, data.dossiers.length ? 'success' : 'info');
            }
            afficherResultatsDossiers(data.dossiers);
        })
        .catch(() => showToast('Erreur de connexion au serveur.', 'danger'));
}

function arreterWebcamFacialeMariage() {
    if (mariageFacialStream) {
        mariageFacialStream.getTracks().forEach(function (track) {
            track.stop();
        });
        mariageFacialStream = null;
    }
    mariageFacialCameraActive = false;
    const video = document.getElementById('mariage-facial-webcam');
    if (video) {
        video.srcObject = null;
    }
}

async function demarrerWebcamFacialeMariage() {
    const video = document.getElementById('mariage-facial-webcam');
    const cameraBtn = document.getElementById('mariage-facial-camera-btn');

    if (!video || !cameraBtn) {
        return;
    }

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        showToast('Webcam non disponible sur ce navigateur.', 'danger');
        return;
    }

    try {
        arreterWebcamFacialeMariage();
        mariageFacialStream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } },
            audio: false,
        });
        video.srcObject = mariageFacialStream;
        await video.play();
        mariageFacialCameraActive = true;
        cameraBtn.innerHTML = '<i class="bi bi-camera me-2"></i>Capturer la photo';
        cameraBtn.className = 'btn btn-outline-success';
        showToast('Caméra activée. Capturez le visage à rechercher.', 'info');
    } catch (error) {
        showToast('Accès caméra refusé : ' + error.message, 'danger');
    }
}

function capturerPhotoFacialeMariage() {
    const video = document.getElementById('mariage-facial-webcam');
    const canvas = document.getElementById('mariage-facial-canvas');
    const base64Input = document.getElementById('mariage-facial-base64');
    const apercu = document.getElementById('mariage-facial-apercu');
    const apercuImg = document.getElementById('mariage-facial-apercu-img');
    const cameraBtn = document.getElementById('mariage-facial-camera-btn');
    const searchBtn = document.getElementById('mariage-facial-search-btn');

    if (!video || !canvas || !base64Input || !mariageFacialCameraActive) {
        showToast('Démarrez la caméra avant de capturer.', 'warning');
        return;
    }

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);

    const imageBase64 = canvas.toDataURL('image/jpeg');
    base64Input.value = imageBase64;

    if (apercu && apercuImg) {
        apercuImg.src = imageBase64;
        apercu.classList.remove('d-none');
    }

    arreterWebcamFacialeMariage();
    if (cameraBtn) {
        cameraBtn.innerHTML = '<i class="bi bi-check-lg me-2"></i>Photo capturée';
        cameraBtn.className = 'btn btn-success';
        cameraBtn.disabled = true;
    }
    if (searchBtn) {
        searchBtn.disabled = false;
    }
    showToast('Photo capturée. Lancez la recherche faciale.', 'success');
}

function toggleWebcamFacialeMariage() {
    if (!mariageFacialCameraActive) {
        demarrerWebcamFacialeMariage();
    } else {
        capturerPhotoFacialeMariage();
    }
}

function executerRechercheFaciale() {
    const base64Input = document.getElementById('mariage-facial-base64');
    const url = document.getElementById('mariage-app-container')?.dataset.rechercheFacialeUrl;
    const searchBtn = document.getElementById('mariage-facial-search-btn');

    if (!base64Input?.value) {
        showToast('Capturez d\'abord une photo du visage.', 'warning');
        return;
    }
    if (!url) {
        showToast('URL de recherche faciale manquante.', 'danger');
        return;
    }

    const formData = new FormData();
    formData.append('image_base64', base64Input.value);
    formData.append('csrfmiddlewaretoken', getCsrfToken());

    if (searchBtn) {
        searchBtn.disabled = true;
    }

    fetch(url, {
        method: 'POST',
        body: formData,
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
    })
        .then((response) => response.json())
        .then((data) => {
            if (searchBtn) {
                searchBtn.disabled = false;
            }
            if (!data.success) {
                const msg = data.errors
                    ? Object.values(data.errors).flat().join(' ')
                    : 'Erreur lors de la reconnaissance faciale.';
                showToast(msg, 'danger');
                return;
            }
            if (data.message) {
                showToast(data.message, data.dossiers.length ? 'success' : 'warning');
            }
            afficherResultatsDossiers(data.dossiers);
        })
        .catch(() => {
            if (searchBtn) {
                searchBtn.disabled = false;
            }
            showToast('Erreur de connexion au serveur.', 'danger');
        });
}

function afficherResultatsDossiers(dossiers) {
    const container = document.getElementById('resultats-dossiers-container');
    const tbody = document.getElementById('table-resultat-dossiers');

    if (!container || !tbody) {
        return;
    }

    container.classList.remove('d-none');
    tbody.innerHTML = '';

    if (!dossiers.length) {
        tbody.innerHTML = `
            <tr>
                <td colspan="5" class="text-center py-4 text-muted">
                    Aucun dossier validé trouvé. Créez d'abord un dossier (menu Dossiers).
                </td>
            </tr>`;
        return;
    }

    dossiers.forEach(function (d) {
        const matchBadge = d.correspondance
            ? `<div class="mt-1"><span class="badge bg-success-subtle text-success border border-success-subtle">
                <i class="bi bi-person-bounding-box me-1"></i>${d.correspondance.role_label} — ${d.correspondance.nom_complet}
                (${d.correspondance.confiance} %)</span></div>`
            : '';
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td class="fw-bold">#${d.numero_dossier}</td>
            <td class="text-center">${photoCell(d.epoux, 'Époux — ' + d.epoux.nom_complet)}</td>
            <td class="text-center">${photoCell(d.epouse, 'Épouse — ' + d.epouse.nom_complet)}</td>
            <td>
                <div><span class="badge bg-light text-dark">M.</span> ${d.epoux.nom_complet}</div>
                <div><span class="badge bg-light text-danger">Mme</span> ${d.epouse.nom_complet}</div>
                <small class="text-muted">${d.lieu.commune}, ${d.lieu.ville}</small>
                ${matchBadge}
            </td>
            <td class="text-center">
                <button type="button" class="btn btn-sm btn-primary" data-dossier-id="${d.id}">
                    <i class="bi bi-check-circle me-1"></i> Sélectionner
                </button>
            </td>`;
        tr.querySelector('button').addEventListener('click', function () {
            selectionnerDossier(d);
        });
        tbody.appendChild(tr);
    });

    if (typeof window.lierPhotosConjoints === 'function') {
        window.lierPhotosConjoints(tbody);
    }
}

function photoCell(personne, label) {
    const src = personne.photo_url || personne.photo_carte || personne.photo;
    if (src) {
        const safeLabel = (label || 'Photo').replace(/"/g, '&quot;');
        return `<img src="${src}" alt="${safeLabel}"
            class="rounded-circle border photo-conjoint-thumb" width="45" height="45"
            style="object-fit:cover;cursor:pointer"
            role="button" tabindex="0"
            data-photo-url="${src}"
            data-photo-label="${safeLabel}"
            title="Cliquer pour agrandir">`;
    }
    return '<span class="text-muted small">—</span>';
}

function selectionnerDossier(dossier) {
    dossierSelectionne = dossier;
    document.getElementById('form-epoux-nom').value = dossier.epoux.nom_complet;
    document.getElementById('form-epouse-nom').value = dossier.epouse.nom_complet;
    document.getElementById('form-commune').value = dossier.lieu.commune;
    document.getElementById('form-ville').value = dossier.lieu.ville;
    document.getElementById('form-province').value = dossier.lieu.province;
    document.getElementById('form-numero-acte').value = `ACTE-${dossier.numero_dossier}`;
    document.getElementById('form-dossier-id').value = dossier.id;
    document.getElementById('form-lieu-mariage').value = `Commune de ${dossier.lieu.commune}`;
    showView('view-formulaire-generation');
    showToast(`Dossier n°${dossier.numero_dossier} sélectionné.`, 'success');
}

function genererApercuAvantImpression(event) {
    event.preventDefault();

    if (!dossierSelectionne) {
        showToast('Sélectionnez d\'abord un dossier.', 'warning');
        return;
    }

    const url = document.getElementById('mariage-app-container')?.dataset.enregistrerUrl;
    const btn = document.getElementById('btn-generer-acte');
    if (!url) {
        return;
    }

    const formData = new FormData();
    formData.append('dossier_id', document.getElementById('form-dossier-id').value);
    formData.append('numero_acte', document.getElementById('form-numero-acte').value);
    formData.append('date_mariage', document.getElementById('form-date-mariage').value);
    formData.append('lieu_mariage', document.getElementById('form-lieu-mariage').value);
    formData.append('regime_matrimonial', document.getElementById('form-regime').value);
    formData.append('remarque', document.getElementById('form-remarque').value);
    formData.append('csrfmiddlewaretoken', getCsrfToken());

    btn.disabled = true;

    fetch(url, {
        method: 'POST',
        body: formData,
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
    })
        .then((response) => response.json())
        .then((data) => {
            if (data.success) {
                showToast(data.message, 'success');
                if (data.redirect_url) {
                    setTimeout(() => {
                        window.location.href = data.redirect_url;
                    }, 1200);
                }
            } else {
                btn.disabled = false;
                const msg = data.errors
                    ? Object.values(data.errors).flat().join(' ')
                    : 'Erreur lors de l\'enregistrement.';
                showToast(msg, 'danger');
            }
        })
        .catch(() => {
            btn.disabled = false;
            showToast('Erreur de connexion au serveur.', 'danger');
        });
}

document.addEventListener('DOMContentLoaded', function () {
    document.getElementById('mariage-facial-camera-btn')?.addEventListener('click', toggleWebcamFacialeMariage);
    document.getElementById('mariage-facial-search-btn')?.addEventListener('click', executerRechercheFaciale);
});
