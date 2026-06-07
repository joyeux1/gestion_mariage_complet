// static/mariage/js/dossier_verification.js

(function () {
    const container = document.getElementById('dossier-verif-container');
    if (!container) return;

    const verifUrl = container.dataset.verifUrl;
    const etatEl = document.getElementById('dossier-verif-etat');
    let etat = etatEl ? JSON.parse(etatEl.textContent) : {};

    const streams = { epoux: null, epouse: null };
    const webcamReady = { epoux: false, epouse: false };

    function getCsrfToken() {
        return container.querySelector('[name=csrfmiddlewaretoken]')?.value
            || document.querySelector('[name=csrfmiddlewaretoken]')?.value
            || '';
    }

    function showAlert(message, type) {
        const zone = document.getElementById('verif-alert-zone');
        if (!zone) return;
        zone.innerHTML = `<div class="alert alert-${type} alert-dismissible fade show" role="alert">
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>`;
    }

    function setWebcamStatus(role, text) {
        const el = document.getElementById(`dossier-webcam-status-${role}`);
        if (el) el.textContent = text;
    }

    function afficherCorrespondanceBloquee(match, message) {
        const zone = document.getElementById('verif-match-zone');
        if (!zone || !match) return;

        const confiance = match.confiance_facial
            ? `<span class="badge bg-info text-dark ms-2">Confiance faciale ${match.confiance_facial} %</span>`
            : '';

        const photoProfil = match.photo_profil
            ? `<div class="col-md-3 text-center">
                <p class="small fw-bold text-muted mb-2">Photo identifiée</p>
                <img src="${match.photo_profil}" alt="Photo de la personne"
                     class="rounded-circle border border-3 border-danger shadow"
                     width="120" height="120" style="object-fit:cover;">
               </div>`
            : '';

        const photoCarte = match.photo_carte
            ? `<div class="col-md-3 text-center">
                <p class="small fw-bold text-muted mb-2">Carte d'électeur</p>
                <img src="${match.photo_carte}" alt="Carte d'électeur"
                     class="img-fluid rounded border shadow-sm" style="max-height:220px;object-fit:contain;">
               </div>`
            : '';

        const acteBlock = match.mariage_actif && (match.acte_pdf_url || match.acte_url)
            ? `<div class="col-md-6">
                <p class="small fw-bold text-muted mb-2">Acte de mariage N° ${match.numero_acte || '—'}</p>
                ${match.acte_pdf_url
                    ? `<iframe src="${match.acte_pdf_url}" class="w-100 rounded border" style="height:280px;" title="Acte de mariage"></iframe>
                       <a href="${match.acte_pdf_url}" target="_blank" class="btn btn-sm btn-outline-danger mt-2">
                           <i class="bi bi-file-earmark-pdf me-1"></i> Ouvrir l'acte en plein écran
                       </a>`
                    : `<a href="${match.acte_url}" class="btn btn-danger" target="_blank"><i class="bi bi-file-earmark-text me-1"></i> Voir l'acte de mariage</a>`}
               </div>`
            : '';

        const docsRow = (photoProfil || photoCarte || acteBlock)
            ? `<div class="row g-3 align-items-start mt-2">${photoProfil}${photoCarte}${acteBlock}</div>`
            : '';

        zone.innerHTML = `
            <div class="card border-danger shadow-sm">
                <div class="card-header bg-danger text-white fw-bold">
                    <i class="bi bi-exclamation-octagon me-2"></i>
                    Mariage actif détecté — ${match.nom_complet}${confiance}
                </div>
                <div class="card-body">
                    <div class="alert alert-danger mb-3 py-2 small mb-0">
                        <i class="bi bi-heartbreak me-1"></i> ${message}
                    </div>
                    ${docsRow}
                    ${match.numero_acte ? `<p class="small text-muted mb-0 mt-3"><i class="bi bi-info-circle me-1"></i> Procédez au divorce avant toute nouvelle demande de mariage.</p>` : ''}
                </div>
            </div>`;
        zone.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    function effacerCorrespondanceBloquee() {
        const zone = document.getElementById('verif-match-zone');
        if (zone) zone.innerHTML = '';
    }

    function updateProgressBadge() {
        const badge = document.getElementById('verif-progress-badge');
        if (!badge) return;
        if (etat.epoux_ok && etat.epouse_ok) {
            badge.textContent = 'Validé — chargement du formulaire…';
            badge.className = 'badge bg-success';
        } else if (etat.epoux_ok) {
            badge.textContent = 'Étape 2/2 — Future épouse';
            badge.className = 'badge bg-warning text-dark';
        } else {
            badge.textContent = 'Étape 1/2 — Futur époux';
            badge.className = 'badge bg-warning text-dark';
        }
    }

    function setEpouseEnabled(enabled) {
        const selectors = [
            '#verif-empreinte-epouse-card',
            '#verif-nom-epouse-card',
            '#verif-face-epouse-card',
        ];
        selectors.forEach(function (sel) {
            const card = document.querySelector(sel);
            if (!card) return;
            card.classList.toggle('opacity-50', !enabled);
            card.querySelectorAll('input, button').forEach(function (el) {
                if (el.classList.contains('btn-verif-conjoint') && el.dataset.role === 'epouse') {
                    el.disabled = !enabled;
                } else if (el.id && el.id.includes('epouse')) {
                    el.disabled = !enabled;
                }
            });
        });
        if (enabled) {
            setWebcamStatus('epouse', 'Webcam ou import photo disponible.');
        }
    }

    function markRoleOk(role) {
        document.querySelectorAll(`.btn-verif-conjoint[data-role="${role}"]`).forEach(function (btn) {
            const card = btn.closest('.card');
            if (card) {
                card.classList.add('border-success');
                const ok = card.querySelector('.verif-ok-badge');
                if (ok) ok.classList.remove('d-none');
            }
            btn.disabled = true;
        });
    }

    function applyEtatUI(reloadOnComplete) {
        updateProgressBadge();
        if (etat.epoux_ok) {
            markRoleOk('epoux');
            setEpouseEnabled(true);
        } else {
            setEpouseEnabled(false);
        }
        if (etat.epouse_ok) {
            markRoleOk('epouse');
        }
        if (reloadOnComplete && etat.epoux_ok && etat.epouse_ok) {
            setTimeout(function () {
                window.location.reload();
            }, 800);
        }
    }

    function waitForVideoReady(video, timeoutMs) {
        return new Promise(function (resolve) {
            if (video.videoWidth > 0 && video.videoHeight > 0) {
                resolve(true);
                return;
            }
            const timer = setTimeout(function () { resolve(false); }, timeoutMs || 8000);
            video.addEventListener('loadeddata', function onReady() {
                video.removeEventListener('loadeddata', onReady);
                clearTimeout(timer);
                resolve(video.videoWidth > 0);
            });
        });
    }

    async function startWebcam(role) {
        const video = document.getElementById(`dossier-webcam-${role}`);
        const captureBtn = document.getElementById(`dossier-capture-${role}-btn`);
        if (!video || streams[role]) return;

        setWebcamStatus(role, 'Activation de la webcam…');
        try {
            streams[role] = await navigator.mediaDevices.getUserMedia({
                video: {
                    facingMode: 'user',
                    width: { ideal: 640, min: 320 },
                    height: { ideal: 480, min: 240 },
                },
                audio: false,
            });
            video.srcObject = streams[role];
            video.muted = true;
            video.style.transform = 'scaleX(-1)';
            await video.play();

            const ready = await waitForVideoReady(video, 10000);
            webcamReady[role] = ready;
            if (ready) {
                setWebcamStatus(role, 'Webcam active — capturez ou cliquez directement « Vérifier ».');
                if (captureBtn) captureBtn.disabled = false;
            } else {
                setWebcamStatus(role, 'Webcam lente : importez une photo ou réessayez.');
            }
        } catch (e) {
            webcamReady[role] = false;
            setWebcamStatus(role, 'Webcam indisponible — utilisez « Importer une photo » ci-dessous.');
            showAlert('Webcam indisponible : ' + e.message + ' Vous pouvez importer une photo.', 'warning');
        }
    }

    function stopWebcam(role) {
        if (streams[role]) {
            streams[role].getTracks().forEach(function (t) { t.stop(); });
            streams[role] = null;
        }
        webcamReady[role] = false;
    }

    function isCanvasValid(canvas) {
        const w = canvas.width;
        const h = canvas.height;
        if (!w || !h) return false;
        const ctx = canvas.getContext('2d');
        const sample = ctx.getImageData(0, 0, Math.min(w, 80), Math.min(h, 80)).data;
        let sum = 0;
        for (let i = 0; i < sample.length; i += 4) {
            sum += sample[i] + sample[i + 1] + sample[i + 2];
        }
        const avg = sum / (sample.length / 4) / 3;
        return avg > 20;
    }

    function showPreview(role, dataUrl) {
        const video = document.getElementById(`dossier-webcam-${role}`);
        if (!video) return;
        const container = video.parentElement;
        if (!container) return;
        let preview = container.querySelector('.capture-preview');
        if (!preview) {
            preview = document.createElement('img');
            preview.className = 'capture-preview w-100 h-100 position-absolute top-0 start-0';
            preview.style.objectFit = 'cover';
            preview.alt = 'Photo capturée';
            container.appendChild(preview);
        }
        preview.src = dataUrl;
        preview.classList.remove('d-none');
        video.classList.add('d-none');
    }

    function captureFace(role, silent) {
        const video = document.getElementById(`dossier-webcam-${role}`);
        const canvas = document.getElementById(`dossier-canvas-${role}`);
        const hidden = document.getElementById(`dossier-base64-${role}`);
        if (!video || !canvas || !hidden) {
            if (!silent) showAlert('Webcam non configurée.', 'warning');
            return false;
        }
        if (!video.videoWidth || !video.videoHeight) {
            if (!silent) showAlert('Webcam non prête. Attendez l\'affichage de la vidéo.', 'warning');
            return false;
        }

        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        const ctx = canvas.getContext('2d');
        ctx.translate(canvas.width, 0);
        ctx.scale(-1, 1);
        ctx.drawImage(video, 0, 0);
        ctx.setTransform(1, 0, 0, 1, 0, 0);

        if (!isCanvasValid(canvas)) {
            if (!silent) {
                showAlert(
                    'Image noire ou trop sombre. Autorisez la caméra, attendez de voir votre visage, puis réessayez.',
                    'warning'
                );
            }
            return false;
        }

        const dataUrl = canvas.toDataURL('image/jpeg', 0.95);
        hidden.value = dataUrl;
        hidden.dataset.captured = '1';
        showPreview(role, dataUrl);
        setWebcamStatus(role, 'Photo capturée — cliquez « Vérifier ».');
        if (!silent) {
            showAlert(`Photo du ${role === 'epoux' ? 'futur époux' : 'future épouse'} capturée.`, 'success');
        }
        return true;
    }

    function loadPhotoFromFile(role, file) {
        return new Promise(function (resolve, reject) {
            if (!file || !file.type.startsWith('image/')) {
                reject(new Error('Sélectionnez une image (JPG, PNG…).'));
                return;
            }
            const reader = new FileReader();
            reader.onload = function () {
                const hidden = document.getElementById(`dossier-base64-${role}`);
                if (!hidden) {
                    reject(new Error('Champ photo introuvable.'));
                    return;
                }
                hidden.value = reader.result;
                hidden.dataset.captured = '1';
                showPreview(role, reader.result);
                setWebcamStatus(role, 'Photo importée — cliquez « Vérifier ».');
                showAlert('Photo importée avec succès.', 'success');
                resolve(true);
            };
            reader.onerror = function () { reject(new Error('Lecture du fichier impossible.')); };
            reader.readAsDataURL(file);
        });
    }

    function buildFormData(type, role) {
        const fd = new FormData();
        fd.append('type_verif', type);
        fd.append('role', role);
        fd.append('csrfmiddlewaretoken', getCsrfToken());

        if (type === 'empreinte') {
            const input = document.getElementById(`empreinte-${role}-file`);
            if (!input?.files?.length) {
                throw new Error('Sélectionnez un fichier d\'empreinte.');
            }
            fd.append('scan_empreinte', input.files[0]);
        } else if (type === 'nominative') {
            const nom = document.getElementById(`nom-${role}`)?.value?.trim();
            if (!nom) throw new Error('Le nom est obligatoire.');
            fd.append('nom', nom);
            fd.append('postnom', document.getElementById(`postnom-${role}`)?.value || '');
            fd.append('prenom', document.getElementById(`prenom-${role}`)?.value || '');
        } else {
            const hidden = document.getElementById(`dossier-base64-${role}`);
            const b64 = hidden?.value;
            if (!b64 || hidden?.dataset.captured !== '1') {
                throw new Error('Capturez une photo, importez une image, ou laissez la webcam active puis cliquez « Vérifier ».');
            }
            fd.append('image_base64', b64);
        }
        return fd;
    }

    async function verifierConjoint(type, role) {
        if (type === 'faciale') {
            if (streams[role]) {
                const ok = captureFace(role, true);
                if (!ok) {
                    showAlert(
                        'Impossible de capturer depuis la webcam. Importez une photo ou attendez que la vidéo s\'affiche.',
                        'warning'
                    );
                    return;
                }
            }
        }

        let fd;
        try {
            fd = buildFormData(type, role);
        } catch (e) {
            showAlert(e.message, 'warning');
            return;
        }

        const buttons = document.querySelectorAll('.btn-verif-conjoint');
        buttons.forEach(function (b) { b.disabled = true; });

        try {
            const response = await fetch(verifUrl, {
                method: 'POST',
                body: fd,
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
            });

            let data;
            try {
                data = await response.json();
            } catch (parseErr) {
                throw new Error(response.ok ? 'Réponse serveur invalide.' : `Erreur serveur (${response.status}).`);
            }

            if (data.bloque) {
                showAlert(data.message, 'danger');
                afficherCorrespondanceBloquee(data.match, data.message);
                document.querySelectorAll('.btn-verif-conjoint').forEach(function (b) {
                    b.disabled = b.dataset.role !== role;
                });
                return;
            }

            effacerCorrespondanceBloquee();

            if (!data.success) {
                const msg = data.errors
                    ? Object.values(data.errors).flat().join(' ')
                    : 'Erreur de vérification.';
                showAlert(msg, 'danger');
                document.querySelectorAll('.btn-verif-conjoint').forEach(function (b) {
                    b.disabled = b.dataset.role !== role;
                });
                if (type === 'faciale') {
                    const hidden = document.getElementById(`dossier-base64-${role}`);
                    if (hidden) hidden.dataset.captured = '';
                }
                return;
            }

            etat = data.etat;
            showAlert(data.message, 'success');
            markRoleOk(role);
            stopWebcam(role);
            if (role === 'epoux') {
                setEpouseEnabled(true);
                updateProgressBadge();
                const facialPane = document.getElementById('verif-faciale');
                if (facialPane && facialPane.classList.contains('show')) {
                    startWebcam('epouse');
                }
            }
            if (data.complete) {
                etat = data.etat;
                applyEtatUI(true);
            } else {
                buttons.forEach(function (b) {
                    if (b.dataset.role === 'epouse' && etat.epoux_ok) {
                        b.disabled = false;
                    }
                });
            }
        } catch (e) {
            showAlert(e.message || 'Erreur de connexion au serveur.', 'danger');
            buttons.forEach(function (b) { b.disabled = false; });
        }
    }

    document.querySelectorAll('.btn-verif-conjoint').forEach(function (btn) {
        btn.addEventListener('click', function () {
            verifierConjoint(btn.dataset.type, btn.dataset.role);
        });
    });

    document.getElementById('dossier-capture-epoux-btn')?.addEventListener('click', function () {
        captureFace('epoux', false);
    });
    document.getElementById('dossier-capture-epouse-btn')?.addEventListener('click', function () {
        captureFace('epouse', false);
    });

    document.getElementById('dossier-file-epoux')?.addEventListener('change', function (e) {
        if (e.target.files?.[0]) {
            loadPhotoFromFile('epoux', e.target.files[0]).catch(function (err) {
                showAlert(err.message, 'warning');
            });
        }
    });
    document.getElementById('dossier-file-epouse')?.addEventListener('change', function (e) {
        if (e.target.files?.[0]) {
            loadPhotoFromFile('epouse', e.target.files[0]).catch(function (err) {
                showAlert(err.message, 'warning');
            });
        }
    });

    document.querySelectorAll('#dossierVerifTabs button[data-bs-toggle="pill"]').forEach(function (tab) {
        tab.addEventListener('shown.bs.tab', function (e) {
            if (e.target.getAttribute('data-bs-target') === '#verif-faciale') {
                if (!etat.epoux_ok) startWebcam('epoux');
                else if (etat.epoux_ok && !etat.epouse_ok) startWebcam('epouse');
            } else {
                stopWebcam('epoux');
                stopWebcam('epouse');
            }
        });
    });

    if (document.getElementById('verif-faciale')?.classList.contains('show')) {
        if (!etat.epoux_ok) startWebcam('epoux');
    }

    applyEtatUI(false);
})();
