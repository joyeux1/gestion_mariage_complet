// static/mariage/js/dossier_verification.js

(function () {
    const container = document.getElementById('workflow-verif-container')
        || document.getElementById('dossier-verif-container');
    if (!container) return;

    const mode = container.dataset.mode || 'dossier';
    const isDossierMode = mode === 'dossier';
    const isDivorceMode = mode === 'divorce';
    const isMariageMode = mode === 'mariage';
    const isFindMode = isDivorceMode || isMariageMode;

    const verifUrl = container.dataset.verifUrl;
    const rechercheUrl = container.dataset.rechercheUrl
        || container.getAttribute('data-recherche-url')
        || '';
    const captureCreateUrl = container.dataset.captureCreateUrl;
    const tunnelApiUrl = container.dataset.tunnelUrl;
    const reinitUrl = container.dataset.reinitUrl || '';
    const etatEl = document.getElementById('dossier-verif-etat');
    let etat = {};
    if (etatEl && etatEl.textContent) {
        try {
            etat = JSON.parse(etatEl.textContent);
        } catch (parseEtatErr) {
            etat = {};
        }
    }

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
        const nominativePane = document.getElementById('verif-nominative');
        if (
            isMariageMode
            && document.getElementById('recherche-dossier-mariage')
            && nominativePane
            && nominativePane.classList.contains('show')
        ) {
            badge.textContent = 'Recherche nominative — votre commune';
            badge.className = 'badge bg-success';
            return;
        }
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
                } else if (el.classList.contains('btn-mobile-capture') && el.dataset.role === 'epouse') {
                    el.disabled = !enabled;
                } else if (el.id && el.id.includes('epouse')) {
                    el.disabled = !enabled;
                }
            });
        });
        if (enabled) {
            setWebcamStatus('epouse', 'Webcam ou import photo disponible.');
            ['mobile-qr-empreinte-epouse', 'mobile-qr-photo-epouse'].forEach(function (id) {
                const qr = document.getElementById(id);
                if (qr) qr.classList.remove('opacity-50');
            });
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

    function finaliserChampEpouxValide() {
        const epouxInput = document.getElementById('recherche-epoux');
        if (epouxInput) {
            epouxInput.readOnly = true;
            epouxInput.classList.add('bg-light');
        }
        const epouxLabel = document.getElementById('selection-epoux-label');
        if (epouxLabel) {
            epouxLabel.textContent = 'Époux validé ✓ — le système passe à la future épouse.';
            epouxLabel.classList.remove('text-danger');
            epouxLabel.classList.add('text-success');
        }
        masquerPropositionsNom('epoux');
    }

    function activerEtapeEpouse(autoFocus) {
        setEpouseEnabled(true);
        updateProgressBadge();
        finaliserChampEpouxValide();
        const epouseCard = document.getElementById('verif-nom-epouse-card');
        if (epouseCard) {
            epouseCard.classList.remove('opacity-50');
            if (autoFocus !== false) {
                epouseCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            }
        }
        const epouseInput = document.getElementById('recherche-epouse');
        if (epouseInput && autoFocus !== false) {
            setTimeout(function () { epouseInput.focus(); }, 350);
        }
        const epouseLabel = document.getElementById('selection-epouse-label');
        if (epouseLabel) {
            epouseLabel.textContent = 'Étape 2/2 : saisissez le nom complet de la future épouse.';
            epouseLabel.classList.remove('text-danger');
        }
    }

    function applyEtatUI(reloadOnComplete) {
        updateProgressBadge();
        if (etat.epoux_ok) {
            markRoleOk('epoux');
            setEpouseEnabled(true);
            finaliserChampEpouxValide();
        } else {
            setEpouseEnabled(false);
            const epouxInput = document.getElementById('recherche-epoux');
            if (epouxInput) {
                epouxInput.readOnly = false;
                epouxInput.classList.remove('bg-light');
            }
        }
        if (etat.epouse_ok) {
            markRoleOk('epouse');
            const epouseInput = document.getElementById('recherche-epouse');
            if (epouseInput) {
                epouseInput.readOnly = true;
                epouseInput.classList.add('bg-light');
            }
            masquerPropositionsNom('epouse');
        }
        if (reloadOnComplete && etat.epoux_ok && etat.epouse_ok) {
            if (isDossierMode) {
                setTimeout(function () {
                    window.location.href = window.location.pathname + '?verif_ok=1';
                }, 1200);
            } else if (isDivorceMode && typeof window.onDivorceVerifComplete === 'function') {
                setTimeout(function () { window.onDivorceVerifComplete(etat); }, 800);
            } else if (isMariageMode && typeof window.onMariageVerifComplete === 'function') {
                setTimeout(function () { window.onMariageVerifComplete(etat); }, 800);
            }
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
            const personneId = document.getElementById(`selection-${role}-id`)?.value;
            const mot = document.getElementById(`recherche-${role}`)?.value?.trim();
            if (personneId) {
                fd.append('personne_id', personneId);
                fd.append('est_epoux', document.getElementById(`selection-${role}-est-epoux`)?.value || '0');
                fd.append('est_profil_citoyen', '0');
            } else if (mot) {
                const parts = parseNomComplet(mot);
                fd.append('nom', parts.nom);
                fd.append('postnom', parts.postnom);
                fd.append('prenom', parts.prenom);
            } else {
                throw new Error('Saisissez le nom complet ou sélectionnez une personne dans la liste.');
            }
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
        if (role === 'epouse' && !etat.epoux_ok) {
            showAlert(
                'Étape 1/2 : validez d\'abord le futur époux avant de vérifier la future épouse.',
                'warning'
            );
            return;
        }

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

            if (data.echec && isFindMode) {
                showAlert(data.message, 'danger');
                if (data.match) {
                    afficherCorrespondanceBloquee(data.match, data.message);
                }
                document.querySelectorAll('.btn-verif-conjoint').forEach(function (b) {
                    if (role === 'epoux') {
                        b.disabled = b.dataset.role !== 'epoux';
                    } else if (etat.epoux_ok) {
                        b.disabled = b.dataset.role === 'epoux';
                    } else {
                        b.disabled = b.dataset.role !== role;
                    }
                });
                return;
            }

            if (data.bloque) {
                showAlert(data.message, 'danger');
                afficherCorrespondanceBloquee(data.match, data.message);
                reinitialiserSelectionNom(role);
                const labelEl = document.getElementById(`selection-${role}-label`);
                if (labelEl) {
                    labelEl.textContent = '⛔ Mariage actif — cette personne ne peut pas se remarier. Corrigez le nom ou procédez au divorce.';
                    labelEl.classList.remove('text-success', 'fw-semibold');
                    labelEl.classList.add('text-danger');
                }
                document.querySelectorAll(`#resultats-${role} .btn-select-personne`).forEach(function (b) {
                    b.classList.remove('active');
                });
                document.querySelectorAll('.btn-verif-conjoint').forEach(function (b) {
                    if (role === 'epoux') {
                        b.disabled = b.dataset.role !== 'epoux';
                    } else if (etat.epoux_ok) {
                        b.disabled = b.dataset.role === 'epoux';
                    } else {
                        b.disabled = b.dataset.role !== role;
                    }
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
            if (isDivorceMode && data.mariage) {
                window._divorceMariageIdentifie = data.mariage;
            }
            if (isMariageMode && data.dossier) {
                window._mariageDossierIdentifie = data.dossier;
            }
            showAlert(data.message, 'success');
            markRoleOk(role);
            stopWebcam(role);
            if (role === 'epoux') {
                activerEtapeEpouse();
                const facialPane = document.getElementById('verif-faciale');
                if (facialPane && facialPane.classList.contains('show')) {
                    startWebcam('epouse');
                }
            }
            if (data.complete) {
                etat = data.etat;
                const completeMsg = isDossierMode
                    ? 'Vérification terminée : époux et épouse sans mariage actif. Ouverture du formulaire d\'enregistrement…'
                    : (isDivorceMode
                        ? 'Couple identifié — ouverture de la cérémonie de divorce…'
                        : 'Dossier identifié — ouverture du formulaire d\'acte…');
                showAlert(completeMsg, 'success');
                updateProgressBadge();
                applyEtatUI(true);
            } else if (role === 'epoux' && etat.epoux_ok && !etat.epouse_ok) {
                activerEtapeEpouse();
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

    // --- Recherche nominative automatique (sans boutons Vérifier) ---
    const rechercheTimers = {};
    const absenceTimers = {};
    const rechercheSeq = { epoux: 0, epouse: 0 };
    const derniersResultats = { epoux: [], epouse: [] };
    const nomAutoState = {
        epoux: { motValide: '', enCours: false },
        epouse: { motValide: '', enCours: false },
    };

    function parseNomComplet(texte) {
        const mots = (texte || '').trim().split(/\s+/).filter(Boolean);
        return {
            nom: mots[0] || '',
            postnom: mots[1] || '',
            prenom: mots.slice(2).join(' ') || '',
        };
    }

    function roleEstValide(role) {
        return role === 'epoux' ? etat.epoux_ok : etat.epouse_ok;
    }

    function peutRechercherNom(role) {
        const input = document.getElementById(`recherche-${role}`);
        if (!input || input.disabled) return false;
        if (role === 'epouse' && !etat.epoux_ok) return false;
        return !roleEstValide(role);
    }

    function urlsPhotosProposition(r) {
        const carteUrl = r.photo_carte_url || '';
        let profilUrl = r.photo_profil_url || r.photo_url || '';
        let depuisCarte = !!r.photo_profil_depuis_carte;
        if (!profilUrl && carteUrl) {
            profilUrl = carteUrl;
            depuisCarte = true;
        } else if (profilUrl && carteUrl && profilUrl === carteUrl) {
            depuisCarte = true;
        }
        return { profilUrl, carteUrl, depuisCarte };
    }

    function htmlPhotoProfilProposition(profilUrl, labelNom, depuisCarte) {
        if (!profilUrl) {
            return `<div class="rounded-circle bg-secondary bg-opacity-25 flex-shrink-0 d-flex align-items-center justify-content-center text-muted border"
                       style="width:58px;height:58px;" title="Photo absente"><i class="bi bi-person fs-5"></i></div>`;
        }
        const style = depuisCarte
            ? 'width:58px;height:58px;object-fit:cover;object-position:center 12%;cursor:pointer;'
            : 'width:58px;height:58px;object-fit:cover;cursor:pointer;';
        return `<img src="${profilUrl}" alt="Photo de profil" title="Photo de profil — cliquer pour agrandir"
                   class="rounded-circle border border-2 border-primary btn-photo-nom-verif flex-shrink-0 verif-nom-photo-profil"
                   style="${style}" loading="lazy"
                   data-photo-url="${profilUrl}"
                   data-photo-label="Photo de profil — ${labelNom}">`;
    }

    function htmlPhotoCarteProposition(carteUrl, labelNom) {
        if (!carteUrl) {
            return `<div class="rounded border bg-secondary bg-opacity-25 flex-shrink-0 d-flex align-items-center justify-content-center text-muted"
                       style="width:72px;height:58px;" title="Carte absente"><i class="bi bi-credit-card-2-front"></i></div>`;
        }
        return `<img src="${carteUrl}" alt="Carte d'électeur" title="Carte d'électeur — cliquer pour agrandir"
                   class="rounded border border-2 border-secondary btn-photo-nom-verif flex-shrink-0 verif-nom-photo-carte"
                   style="width:72px;height:58px;object-fit:contain;cursor:pointer;background:#fff;"
                   loading="lazy"
                   data-photo-url="${carteUrl}"
                   data-photo-label="Carte d'électeur — ${labelNom}">`;
    }

    const modalPhotoEl = document.getElementById('modalPhotoNomVerif');
    const modalPhotoImg = document.getElementById('modalPhotoNomVerifImg');
    const modalPhotoTitle = document.getElementById('modalPhotoNomVerifLabel');
    let modalPhotoInstance = null;

    function getModalPhoto() {
        if (!modalPhotoEl || typeof bootstrap === 'undefined') return null;
        if (!modalPhotoInstance) {
            modalPhotoInstance = new bootstrap.Modal(modalPhotoEl);
        }
        return modalPhotoInstance;
    }

    function ouvrirPhotoNom(url, label) {
        const modalPhoto = getModalPhoto();
        if (!modalPhoto || !url || !modalPhotoImg) return;
        modalPhotoImg.src = url;
        modalPhotoImg.alt = label || 'Photo';
        if (modalPhotoTitle) modalPhotoTitle.textContent = label || 'Photo';
        modalPhoto.show();
    }

    if (modalPhotoEl) {
        modalPhotoEl.addEventListener('hidden.bs.modal', function () {
            if (modalPhotoImg) modalPhotoImg.removeAttribute('src');
        });
    }

    function reinitialiserSelectionNom(role) {
        const idEl = document.getElementById(`selection-${role}-id`);
        if (idEl) idEl.value = '';
        const labelEl = document.getElementById(`selection-${role}-label`);
        if (labelEl) {
            labelEl.classList.remove('text-success', 'fw-semibold');
        }
    }

    function fetchRechercheNominative(role, mot, permute) {
        let url = `${rechercheUrl}?q=${encodeURIComponent(mot)}&role=${encodeURIComponent(role)}`;
        if (permute) url += '&permute=1';
        return fetch(url, {
            credentials: 'same-origin',
            headers: { 'X-Requested-With': 'XMLHttpRequest', Accept: 'application/json' },
        }).then(function (r) {
            if (!r.ok) {
                throw new Error(`Recherche impossible (${r.status}).`);
            }
            return r.json();
        });
    }

    function afficherErreurRecherche(role, message) {
        const listEl = document.getElementById(`resultats-${role}`);
        if (!listEl) return;
        listEl.classList.remove('d-none');
        listEl.innerHTML = `<div class="list-group-item text-danger py-2"><i class="bi bi-exclamation-triangle me-1"></i> ${message}</div>`;
    }

    function afficherChargementRecherche(role) {
        const listEl = document.getElementById(`resultats-${role}`);
        if (!listEl) return;
        listEl.classList.remove('d-none');
        listEl.innerHTML = '<div class="list-group-item text-muted py-2"><i class="bi bi-search me-1"></i> Recherche en cours…</div>';
    }

    function masquerPropositionsNom(role) {
        const listEl = document.getElementById(`resultats-${role}`);
        if (!listEl) return;
        listEl.innerHTML = '';
        listEl.classList.add('d-none');
    }

    function afficherPanneauPropositions(role) {
        const listEl = document.getElementById(`resultats-${role}`);
        if (listEl) listEl.classList.remove('d-none');
    }

    function nomCompletSuffisant(mot) {
        return mot.split(/\s+/).filter(Boolean).length >= 3;
    }

    async function validerAutomatiquementSiLibre(role, mot) {
        if (!isDossierMode) return;
        if (!peutRechercherNom(role) || !mot || !nomCompletSuffisant(mot)) return;
        if (roleEstValide(role)) return;
        if (nomAutoState[role].enCours) return;
        if (nomAutoState[role].motValide === mot) {
            if (role === 'epoux' && etat.epoux_ok && !etat.epouse_ok) {
                activerEtapeEpouse();
            }
            return;
        }
        if (derniersResultats[role].length > 0) return;
        if (document.getElementById(`selection-${role}-id`)?.value) return;

        nomAutoState[role].enCours = true;
        afficherLibreDeSeMarier(role);

        const labelEl = document.getElementById(`selection-${role}-label`);
        if (labelEl) {
            labelEl.textContent = 'Contrôle des permutations nom / postnom / prénom…';
        }

        try {
            const dataPerm = await fetchRechercheNominative(role, mot, true);
            if (dataPerm.success && dataPerm.resultats && dataPerm.resultats.length > 0) {
                afficherResultatsNominatifs(role, dataPerm.resultats);
                if (labelEl) {
                    labelEl.textContent = '⛔ Mariage actif détecté après permutation — dossier refusé.';
                    labelEl.classList.add('text-danger');
                    labelEl.classList.remove('text-success');
                }
                return;
            }

            if (labelEl) {
                labelEl.textContent = messagePeutSeMarier(role) + ' Validation…';
            }

            await verifierConjoint('nominative', role);

            if (roleEstValide(role)) {
                nomAutoState[role].motValide = mot;
            }

            if (role === 'epoux' && etat.epoux_ok && !etat.epouse_ok) {
                activerEtapeEpouse();
            }
        } catch (err) {
            if (labelEl) {
                labelEl.textContent = 'Erreur lors de la vérification automatique.';
            }
            showAlert(err.message || 'Erreur de vérification automatique.', 'danger');
        } finally {
            nomAutoState[role].enCours = false;
        }
    }

    function messagePeutSeMarier(role) {
        if (role === 'epouse') {
            return 'Ce nom n\'existe pas sur un acte de mariage actif — elle peut se marier.';
        }
        return 'Ce nom n\'existe pas sur un acte de mariage actif — il peut se marier.';
    }

    function afficherLibreDeSeMarier(role) {
        const listEl = document.getElementById(`resultats-${role}`);
        const labelEl = document.getElementById(`selection-${role}-label`);
        if (listEl) {
            afficherPanneauPropositions(role);
            listEl.innerHTML = `<div class="list-group-item text-success py-2 border-success border-start border-3">
                <i class="bi bi-check-circle-fill me-1"></i> ${messagePeutSeMarier(role)}
            </div>`;
        }
        if (labelEl) {
            labelEl.textContent = 'Vérification automatique en cours…';
            labelEl.classList.remove('text-danger');
            labelEl.classList.add('text-success');
        }
    }

    function planifierValidationAutomatique(role, mot) {
        clearTimeout(absenceTimers[role]);
        absenceTimers[role] = setTimeout(function () {
            validerAutomatiquementSiLibre(role, mot);
        }, 400);
    }

    function afficherResultatsNominatifs(role, resultats) {
        const listEl = document.getElementById(`resultats-${role}`);
        const labelEl = document.getElementById(`selection-${role}-label`);
        if (!listEl) return;

        derniersResultats[role] = resultats || [];
        reinitialiserSelectionNom(role);

        if (!resultats.length) {
            const mot = document.getElementById(`recherche-${role}`)?.value?.trim() || '';
            if (!mot) {
                masquerPropositionsNom(role);
            } else if (nomCompletSuffisant(mot) && isDossierMode) {
                afficherLibreDeSeMarier(role);
                planifierValidationAutomatique(role, mot);
            } else if (nomCompletSuffisant(mot) && isFindMode) {
                afficherPanneauPropositions(role);
                listEl.innerHTML = `<div class="list-group-item text-warning py-2 border-warning border-start border-3">
                    <i class="bi bi-info-circle me-1"></i> Aucun résultat — sélectionnez une proposition ou utilisez empreinte / reconnaissance faciale.</div>`;
                if (labelEl) {
                    labelEl.textContent = 'Aucune correspondance dans la liste. Essayez un autre mode de vérification.';
                    labelEl.classList.add('text-warning');
                }
            } else {
                afficherPanneauPropositions(role);
                listEl.innerHTML = '<div class="list-group-item text-muted py-2"><i class="bi bi-pencil me-1"></i> Complétez le nom complet (Nom Postnom Prénom)…</div>';
                if (labelEl) {
                    labelEl.textContent = 'Saisie en cours — saisissez Nom, Postnom et Prénom.';
                    labelEl.classList.remove('text-success', 'text-danger');
                }
            }
            return;
        }

        clearTimeout(absenceTimers[role]);
        afficherPanneauPropositions(role);

        if (labelEl) {
            if (isDossierMode) {
                labelEl.textContent = '⛔ Mariage(s) actif(s) détecté(s) — ces personnes ne peuvent pas se remarier. '
                    + 'Cliquez pour confirmer le blocage, ou saisissez un autre nom si ce n\'est pas la bonne personne.';
                labelEl.classList.remove('text-success', 'fw-semibold');
                labelEl.classList.add('text-danger');
            } else if (isDivorceMode) {
                labelEl.textContent = 'Mariage(s) actif(s) trouvé(s) — cliquez pour identifier l\'acte à dissoudre.';
                labelEl.classList.remove('text-success');
                labelEl.classList.add('text-primary', 'fw-semibold');
            } else {
                labelEl.textContent = 'Dossier(s) non validé(s) trouvé(s) — cliquez pour sélectionner.';
                labelEl.classList.remove('text-danger');
                labelEl.classList.add('text-success', 'fw-semibold');
            }
        }

        listEl.innerHTML = resultats.map(function (r) {
            const labelNom = `${r.nom} ${r.postnom} ${r.prenom}`.trim();
            const photos = urlsPhotosProposition(r);
            const photoProfilHtml = htmlPhotoProfilProposition(photos.profilUrl, labelNom, photos.depuisCarte);
            const photoCarteHtml = htmlPhotoCarteProposition(photos.carteUrl, labelNom);

            const borderClass = isMariageMode ? 'border-success' : (isDivorceMode ? 'border-primary' : 'border-danger');
            const acteLine = r.numero_acte
                ? `<div class="${isMariageMode ? 'text-success' : 'text-danger'} fw-semibold" style="font-size:0.72rem;"><i class="bi bi-file-earmark-text me-1"></i>Acte N° ${r.numero_acte}${r.conjoint_lie ? ' — Union avec ' + r.conjoint_lie : ''}</div>`
                : '';
            const dossierLine = r.numero_dossier
                ? `<div class="text-success fw-semibold" style="font-size:0.72rem;"><i class="bi bi-folder2-open me-1"></i>Dossier N° ${r.numero_dossier}${r.conjoint_lie ? ' — avec ' + r.conjoint_lie : ''} (${r.dossier_statut || ''})</div>`
                : '';
            const refLine = acteLine || dossierLine;
            const dataLabel = r.numero_dossier
                ? `${r.nom_complet} (dossier ${r.numero_dossier})`
                : `${r.nom_complet} (acte ${r.numero_acte || ''})`;

            return `<button type="button" class="list-group-item list-group-item-action py-2 px-2 btn-select-personne text-start border-0 verif-nom-proposition-item"
                data-role="${role}" data-id="${r.id}" data-est-epoux="${r.est_epoux ? '1' : '0'}"
                data-profil="0" data-label="${dataLabel}">
                <div class="d-flex gap-2 align-items-start border rounded p-2 bg-white ${borderClass} border-start border-3 shadow-sm">
                    <div class="flex-shrink-0 text-center" style="width:58px;">
                        ${photoProfilHtml}
                        <div class="text-muted mt-1" style="font-size:0.58rem;line-height:1;">Profil</div>
                    </div>
                    <div class="flex-grow-1 min-w-0">
                        <div class="fw-semibold text-truncate">${r.nom} <span class="text-muted fw-normal">${r.postnom}</span> ${r.prenom}</div>
                        ${refLine}
                        <div class="text-muted" style="font-size:0.72rem;line-height:1.35;">
                            <i class="bi bi-geo-alt me-1"></i>
                            Commune : <strong>${r.commune_enregistrement}</strong> —
                            Ville : <strong>${r.ville_enregistrement}</strong> —
                            Province : <strong>${r.province_enregistrement}</strong>
                        </div>
                        ${r.numero_piece ? `<div class="text-muted" style="font-size:0.72rem;">Pièce : ${r.numero_piece}</div>` : ''}
                    </div>
                    <div class="flex-shrink-0 text-center" style="width:72px;">
                        ${photoCarteHtml}
                        <div class="text-muted mt-1" style="font-size:0.58rem;line-height:1;">Carte</div>
                    </div>
                </div>
            </button>`;
        }).join('');
    }

    function lancerRechercheNominative(role, mot) {
        const listEl = document.getElementById(`resultats-${role}`);
        if (!rechercheUrl) {
            afficherErreurRecherche(role, 'URL de recherche non configurée.');
            return;
        }
        if (!peutRechercherNom(role)) return;

        if (!mot) {
            masquerPropositionsNom(role);
            derniersResultats[role] = [];
            reinitialiserSelectionNom(role);
            nomAutoState[role].motValide = '';
            clearTimeout(absenceTimers[role]);
            return;
        }

        const seq = ++rechercheSeq[role];
        afficherChargementRecherche(role);

        fetchRechercheNominative(role, mot, false)
            .then(function (data) {
                if (seq !== rechercheSeq[role]) return;
                if (data.success) {
                    afficherResultatsNominatifs(role, data.resultats || []);
                } else {
                    const msg = data.errors
                        ? Object.values(data.errors).flat().join(' ')
                        : 'Recherche nominative indisponible.';
                    afficherErreurRecherche(role, msg);
                }
            })
            .catch(function (err) {
                if (seq !== rechercheSeq[role]) return;
                afficherErreurRecherche(role, err.message || 'Erreur de connexion lors de la recherche.');
            });
    }

    function initialiserRechercheNominativeMariage() {
        const input = document.getElementById('recherche-dossier-mariage');
        const listEl = document.getElementById('resultats-dossiers-mariage');
        const labelEl = document.getElementById('recherche-dossier-mariage-label');
        if (!input || !listEl) return;

        let seq = 0;
        let timer = null;
        let derniersDossiers = [];

        function photoMini(personne) {
            const src = personne?.photo_url || personne?.photo_carte || personne?.photo;
            if (!src) {
                return '<div class="rounded-circle bg-secondary bg-opacity-25 flex-shrink-0" style="width:38px;height:38px;"></div>';
            }
            return `<img src="${src}" alt="" class="rounded-circle border flex-shrink-0" width="38" height="38" style="object-fit:cover;">`;
        }

        function afficherDossiers(dossiers) {
            derniersDossiers = dossiers || [];
            if (!derniersDossiers.length) {
                listEl.classList.remove('d-none');
                listEl.innerHTML = '<div class="list-group-item text-muted py-2"><i class="bi bi-inbox me-1"></i> Aucun dossier non validé ne correspond.</div>';
                return;
            }
            listEl.classList.remove('d-none');
            listEl.innerHTML = derniersDossiers.map(function (d) {
                return `<button type="button" class="list-group-item list-group-item-action py-2 px-2 btn-select-dossier-mariage text-start border-0"
                    data-dossier-id="${d.id}">
                    <div class="border rounded p-2 bg-white border-success border-start border-3 shadow-sm">
                        <div class="fw-bold text-success mb-2"><i class="bi bi-folder2-open me-1"></i>Dossier N° ${d.numero_dossier}
                            <span class="badge bg-light text-dark ms-1">${d.statut_label}</span></div>
                        <div class="d-flex flex-wrap gap-2 align-items-center small mb-1">
                            ${photoMini(d.epoux)}
                            <span><span class="badge bg-light text-primary">M.</span> ${d.epoux.nom_complet}</span>
                            ${photoMini(d.epouse)}
                            <span><span class="badge bg-light text-danger">Mme</span> ${d.epouse.nom_complet}</span>
                        </div>
                        <div class="text-muted" style="font-size:0.72rem;"><i class="bi bi-geo-alt me-1"></i>${d.lieu.commune}, ${d.lieu.ville}</div>
                    </div>
                </button>`;
            }).join('');

            listEl.querySelectorAll('.btn-select-dossier-mariage').forEach(function (btn) {
                btn.addEventListener('click', function () {
                    const id = parseInt(btn.dataset.dossierId, 10);
                    const dossier = derniersDossiers.find(function (x) { return x.id === id; });
                    if (!dossier) return;
                    window._mariageDossierIdentifie = dossier;
                    if (labelEl) {
                        labelEl.textContent = `Dossier N° ${dossier.numero_dossier} sélectionné — ouverture du formulaire…`;
                        labelEl.classList.add('text-success');
                    }
                    showAlert(`Dossier N° ${dossier.numero_dossier} identifié.`, 'success');
                    if (typeof window.onMariageVerifComplete === 'function') {
                        setTimeout(function () { window.onMariageVerifComplete(); }, 500);
                    }
                });
            });
        }

        function lancerRecherche(mot) {
            if (!rechercheUrl) return;
            if (mot.length < 2) {
                listEl.innerHTML = '';
                listEl.classList.add('d-none');
                if (labelEl) {
                    labelEl.textContent = 'Saisissez au moins 2 caractères (nom, postnom ou prénom de l\'époux ou de l\'épouse).';
                    labelEl.classList.remove('text-success');
                }
                return;
            }
            const currentSeq = ++seq;
            listEl.classList.remove('d-none');
            listEl.innerHTML = '<div class="list-group-item text-muted py-2"><i class="bi bi-search me-1"></i> Recherche en cours…</div>';
            if (labelEl) {
                labelEl.textContent = 'Interrogation des dossiers non validés de votre commune…';
            }

            fetch(`${rechercheUrl}?q=${encodeURIComponent(mot)}`, {
                credentials: 'same-origin',
                headers: { 'X-Requested-With': 'XMLHttpRequest', Accept: 'application/json' },
            })
                .then(function (r) {
                    if (!r.ok) throw new Error('Recherche impossible.');
                    return r.json();
                })
                .then(function (data) {
                    if (currentSeq !== seq) return;
                    if (data.success) {
                        afficherDossiers(data.dossiers || []);
                        if (labelEl && !(data.dossiers || []).length) {
                            labelEl.textContent = 'Aucun dossier non validé de votre commune pour ce mot-clé.';
                            labelEl.classList.remove('text-success');
                        }
                    }
                })
                .catch(function (err) {
                    if (currentSeq !== seq) return;
                    listEl.innerHTML = `<div class="list-group-item text-danger py-2">${err.message || 'Erreur de connexion.'}</div>`;
                });
        }

        input.addEventListener('input', function () {
            clearTimeout(timer);
            timer = setTimeout(function () {
                lancerRecherche(input.value.trim());
            }, 150);
        });
        input.addEventListener('focus', function () {
            const mot = input.value.trim();
            if (mot.length >= 2) lancerRecherche(mot);
        });
    }

    function initialiserRechercheNominative() {
        ['epoux', 'epouse'].forEach(function (role) {
            const input = document.getElementById(`recherche-${role}`);
            if (!input) return;

            function declencherRecherche() {
                if (!peutRechercherNom(role)) return;
                const selId = document.getElementById(`selection-${role}-id`);
                if (selId) selId.value = '';
                nomAutoState[role].motValide = '';
                clearTimeout(absenceTimers[role]);
                clearTimeout(rechercheTimers[role]);
                rechercheTimers[role] = setTimeout(function () {
                    lancerRechercheNominative(role, input.value.trim());
                }, 150);
            }

            input.addEventListener('input', declencherRecherche);
            input.addEventListener('focus', function () {
                const mot = input.value.trim();
                if (mot && peutRechercherNom(role)) {
                    lancerRechercheNominative(role, mot);
                }
            });

            if (input.value.trim() && peutRechercherNom(role)) {
                lancerRechercheNominative(role, input.value.trim());
            }
        });
    }

    document.addEventListener('click', function (e) {
        const photoBtn = e.target.closest('.btn-photo-nom-verif');
        if (photoBtn) {
            e.preventDefault();
            e.stopPropagation();
            ouvrirPhotoNom(photoBtn.dataset.photoUrl, photoBtn.dataset.photoLabel);
            return;
        }

        const btn = e.target.closest('.btn-select-personne');
        if (!btn) return;
        const role = btn.dataset.role;
        document.getElementById(`selection-${role}-id`).value = btn.dataset.id;
        document.getElementById(`selection-${role}-est-epoux`).value = btn.dataset.estEpoux;
        document.getElementById(`selection-${role}-profil`).value = '0';
        const labelEl = document.getElementById(`selection-${role}-label`);
        if (labelEl) {
            labelEl.textContent = 'Sélectionné : ' + btn.dataset.label + ' — vérification…';
            labelEl.classList.add('text-success', 'fw-semibold');
        }
        document.querySelectorAll(`#resultats-${role} .btn-select-personne`).forEach(function (b) {
            b.classList.toggle('active', b === btn);
        });
        verifierConjoint('nominative', role);
    });

    // --- Capture mobile (téléphone sur réseau local / internet) ---
    const pollIntervals = {};

    function urlQrCode(targetUrl, size) {
        return 'https://api.qrserver.com/v1/create-qr-code/?size=' + size + 'x' + size
            + '&data=' + encodeURIComponent(targetUrl);
    }

    function suffixQrType(typeCapture) {
        return typeCapture === 'photo' ? 'photo' : 'empreinte';
    }

    function afficherQrDansCarre(role, targetUrl, typeCapture) {
        const suffix = suffixQrType(typeCapture || 'empreinte');
        const box = document.getElementById('mobile-qr-' + suffix + '-' + role);
        if (!box || !targetUrl) return;
        box.classList.remove('opacity-50');
        box.innerHTML = '<a href="' + targetUrl + '" target="_blank" rel="noopener" title="' + targetUrl + '">'
            + '<img src="' + urlQrCode(targetUrl, 110) + '" alt="QR code capture" width="110" height="110" class="rounded">'
            + '</a>';
    }

    function afficherQrLocalPourTous(urlLocal, typesCapture) {
        const types = typesCapture || ['empreinte', 'photo'];
        types.forEach(function (type) {
            ['epoux', 'epouse'].forEach(function (role) {
                afficherQrDansCarre(role, urlLocal, type);
            });
        });
    }

    function banniereTunnelPourType(typeCapture) {
        return typeCapture === 'photo'
            ? document.getElementById('tunnel-faciale-status')
            : document.getElementById('tunnel-empreinte-status');
    }

    function typesCaptureActifs() {
        const faciale = document.getElementById('verif-faciale');
        if (faciale && faciale.classList.contains('show') && faciale.classList.contains('active')) {
            return ['photo'];
        }
        return ['empreinte'];
    }

    async function appliquerPhotoMobileRecue(role, statut, statusEl) {
        const hidden = document.getElementById('dossier-base64-' + role);
        if (!hidden) return false;

        if (statut.image_base64) {
            hidden.value = statut.image_base64;
            hidden.dataset.captured = '1';
            showPreview(role, statut.image_base64);
        } else if (statut.fichier_url) {
            const fileUrl = statut.fichier_url.startsWith('http')
                ? statut.fichier_url
                : (window.location.origin + statut.fichier_url);
            const fileResp = await fetch(fileUrl);
            const blob = await fileResp.blob();
            const dataUrl = await new Promise(function (resolve, reject) {
                const reader = new FileReader();
                reader.onload = function () { resolve(reader.result); };
                reader.onerror = reject;
                reader.readAsDataURL(blob);
            });
            hidden.value = dataUrl;
            hidden.dataset.captured = '1';
            showPreview(role, dataUrl);
        } else {
            return false;
        }

        stopWebcam(role);
        setWebcamStatus(role, 'Photo reçue depuis le téléphone — vérification en cours…');
        if (statusEl) {
            statusEl.innerHTML = '<span class="text-success fw-semibold">Photo reçue — vérification en cours…</span>';
        }
        showAlert('Photo reçue depuis le téléphone. Lancement de la vérification faciale…', 'success');
        await verifierConjoint('faciale', role);
        return true;
    }

    async function demarrerCaptureMobile(typeCapture, role) {
        if (!captureCreateUrl) {
            showAlert('Capture mobile non configurée.', 'warning');
            return;
        }
        if (tunnelApiUrl) {
            await demarrerTunnelAutomatique(typeCapture === 'photo' ? 'photo' : 'empreinte');
        }
        const statusEl = document.getElementById(`mobile-status-${typeCapture}-${role}`)
            || document.getElementById(`mobile-status-empreinte-${role}`);
        if (statusEl) statusEl.textContent = 'Création de la session…';

        const fd = new FormData();
        fd.append('type_capture', typeCapture === 'photo' ? 'photo' : 'empreinte');
        fd.append('role', role);
        fd.append('csrfmiddlewaretoken', getCsrfToken());

        try {
            const resp = await fetch(captureCreateUrl, {
                method: 'POST',
                body: fd,
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
            });
            const data = await resp.json();
            if (!data.success) throw new Error('Impossible de créer la session mobile.');

            const pollUrl = data.poll_url.startsWith('http') ? data.poll_url : (window.location.origin + data.poll_url);
            const captureUrlDirect = data.capture_url_direct || data.capture_url || data.capture_url_short;
            const captureUrlShort = data.capture_url_short || captureUrlDirect;
            const modeTunnel = data.mode === 'tunnel' || data.tunnel_actif;
            const phoneUrl = modeTunnel ? captureUrlDirect : captureUrlShort;

            afficherQrDansCarre(role, phoneUrl, typeCapture);

            if (statusEl) {
                statusEl.innerHTML =
                    (modeTunnel
                        ? '<span class="badge bg-success mb-1">Mode Internet (tunnel)</span> '
                        : '<span class="badge bg-secondary mb-1">Mode Wi‑Fi local</span> ') +
                    '<span class="d-block small text-muted">Scannez le QR ou ouvrez :</span>' +
                    `<a href="${phoneUrl}" target="_blank" rel="noopener" class="small fw-semibold text-break">${phoneUrl}</a>` +
                    '<span class="d-block small text-muted mt-1">En attente de la capture…</span>';
            }
            if (modeTunnel) {
                showAlert(
                    'Scannez le QR code ou ouvrez sur le téléphone : <strong>' + phoneUrl + '</strong>',
                    'success'
                );
            } else {
                showAlert(
                    'Scannez le QR code ou ouvrez : <strong>' + phoneUrl + '</strong>',
                    'warning'
                );
            }

            if (pollIntervals[role + typeCapture]) {
                clearInterval(pollIntervals[role + typeCapture]);
            }
            pollIntervals[role + typeCapture] = setInterval(async function () {
                try {
                    const st = await fetch(pollUrl, { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
                    const statut = await st.json();
                    if (statut.expired) {
                        clearInterval(pollIntervals[role + typeCapture]);
                        if (statusEl) statusEl.textContent = 'Session expirée.';
                        return;
                    }
                    if (statut.ready) {
                        clearInterval(pollIntervals[role + typeCapture]);
                        if (typeCapture === 'photo') {
                            await appliquerPhotoMobileRecue(role, statut, statusEl);
                        } else if (statut.fichier_url || statut.image_base64) {
                            let file;
                            if (statut.fichier_url) {
                                const fileUrl = statut.fichier_url.startsWith('http')
                                    ? statut.fichier_url
                                    : (window.location.origin + statut.fichier_url);
                                const fileResp = await fetch(fileUrl);
                                const blob = await fileResp.blob();
                                file = new File([blob], 'empreinte_mobile.jpg', { type: blob.type || 'image/jpeg' });
                            } else {
                                const resp = await fetch(statut.image_base64);
                                const blob = await resp.blob();
                                file = new File([blob], 'empreinte_mobile.jpg', { type: 'image/jpeg' });
                            }
                            const input = document.getElementById(`empreinte-${role}-file`);
                            if (input) {
                                const dt = new DataTransfer();
                                dt.items.add(file);
                                input.files = dt.files;
                            }
                            if (statusEl) {
                                statusEl.innerHTML = '<span class="text-success fw-semibold">Empreinte reçue — vérification en cours…</span>';
                            }
                            showAlert('Empreinte reçue depuis le téléphone. Lancement de la vérification anti-polygamie…', 'success');
                            if (typeCapture === 'empreinte') {
                                await verifierConjoint('empreinte', role);
                            }
                        }
                    }
                } catch (pollErr) {
                    /* ignore transient poll errors */
                }
            }, 1500);
        } catch (err) {
            if (statusEl) statusEl.textContent = '';
            showAlert(err.message || 'Erreur capture mobile.', 'danger');
        }
    }

    document.querySelectorAll('.btn-mobile-capture').forEach(function (btn) {
        btn.addEventListener('click', function () {
            demarrerCaptureMobile(btn.dataset.typeCapture, btn.dataset.role);
        });
    });

    // --- Tunnel Cloudflare : démarrage auto à l'ouverture de l'onglet Empreintes ---
    let tunnelAutoEnCours = false;

    function afficherBandeauTunnel(bannerEl, html, type) {
        if (!bannerEl) return;
        bannerEl.classList.remove('d-none', 'alert-info', 'alert-success', 'alert-warning', 'alert-danger');
        bannerEl.classList.add('alert-' + (type || 'info'));
        bannerEl.innerHTML = html;
    }

    function htmlTunnelPret(url) {
        const base = url.replace(/\/$/, '');
        const local = base + '/local/';
        return (
            '<strong><i class="bi bi-wifi me-1"></i> Tunnel Internet prêt</strong> — ' +
            'Le téléphone peut ouvrir : ' +
            '<a href="' + local + '" target="_blank" rel="noopener" class="alert-link fw-bold">' +
            local + '</a> (ou scannez le QR après « Capturer / Photo depuis le téléphone »).'
        );
    }

    async function demarrerTunnelAutomatique(typeCapturePrefere) {
        if (!tunnelApiUrl || tunnelAutoEnCours) return;
        const typesQr = typeCapturePrefere ? [typeCapturePrefere] : typesCaptureActifs();
        const bannerEl = typeCapturePrefere
            ? banniereTunnelPourType(typeCapturePrefere)
            : (banniereTunnelPourType(typesQr[0]) || document.getElementById('tunnel-empreinte-status'));
        tunnelAutoEnCours = true;
        afficherBandeauTunnel(
            bannerEl,
            '<span class="spinner-border spinner-border-sm me-1" role="status"></span> ' +
            'Démarrage automatique du tunnel pour le téléphone…',
            'info'
        );
        try {
            const statut = await fetch(tunnelApiUrl, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
            }).then(function (r) { return r.json(); });

            if (statut.ok && statut.url) {
                afficherBandeauTunnel(bannerEl, htmlTunnelPret(statut.url), 'success');
                afficherQrLocalPourTous(
                    statut.local_url || (statut.url.replace(/\/$/, '') + '/local/'),
                    typesQr
                );
                return;
            }

            const resp = await fetch(tunnelApiUrl, {
                method: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': getCsrfToken(),
                },
            });
            const data = await resp.json();
            if (data.ok && data.url) {
                afficherBandeauTunnel(bannerEl, htmlTunnelPret(data.url), 'success');
                afficherQrLocalPourTous(
                    data.local_url || (data.url.replace(/\/$/, '') + '/local/'),
                    typesQr
                );
            } else {
                afficherBandeauTunnel(
                    bannerEl,
                    'Tunnel indisponible : ' + (data.error || 'vérifiez que cloudflared est installé.'),
                    'warning'
                );
            }
        } catch (err) {
            afficherBandeauTunnel(bannerEl, 'Impossible de contacter le serveur pour le tunnel.', 'warning');
        } finally {
            tunnelAutoEnCours = false;
        }
    }

    document.querySelectorAll('[data-bs-target="#verif-empreinte"]').forEach(function (btn) {
        btn.addEventListener('shown.bs.tab', function () {
            demarrerTunnelAutomatique('empreinte');
        });
    });

    document.querySelectorAll('[data-bs-target="#verif-faciale"]').forEach(function (btn) {
        btn.addEventListener('shown.bs.tab', function () {
            stopWebcam('epoux');
            stopWebcam('epouse');
            if (!etat.epoux_ok) startWebcam('epoux');
            else if (etat.epoux_ok && !etat.epouse_ok) startWebcam('epouse');
            demarrerTunnelAutomatique('photo');
        });
    });

    const empreintePane = document.getElementById('verif-empreinte');
    if (empreintePane && empreintePane.classList.contains('show') && empreintePane.classList.contains('active')) {
        demarrerTunnelAutomatique('empreinte');
    }

    const facialePaneInit = document.getElementById('verif-faciale');
    if (facialePaneInit && facialePaneInit.classList.contains('show') && facialePaneInit.classList.contains('active')) {
        demarrerTunnelAutomatique('photo');
    }

    document.querySelector('.btn-reinit-workflow-verif')?.addEventListener('click', async function () {
        if (reinitUrl) {
            try {
                await fetch(reinitUrl, {
                    method: 'POST',
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRFToken': getCsrfToken(),
                    },
                });
            } catch (reinitErr) { /* ignore */ }
        }
        etat = { epoux_ok: false, epouse_ok: false };
        effacerCorrespondanceBloquee();
        const zone = document.getElementById('verif-alert-zone');
        if (zone) zone.innerHTML = '';
        ['epoux', 'epouse'].forEach(function (role) {
            stopWebcam(role);
            masquerPropositionsNom(role);
            const input = document.getElementById(`recherche-${role}`);
            if (input) {
                input.value = '';
                input.readOnly = false;
                input.disabled = role === 'epouse';
                input.classList.remove('bg-light');
            }
        });
        setEpouseEnabled(false);
        document.querySelectorAll('.verif-ok-badge').forEach(function (b) { b.classList.add('d-none'); });
        document.querySelectorAll('.btn-verif-conjoint').forEach(function (b) {
            b.disabled = b.dataset.role === 'epouse';
        });
        updateProgressBadge();
        if (isFindMode) {
            window.location.reload();
        }
    });

    document.querySelectorAll('[data-bs-target="#verif-nominative"]').forEach(function (btn) {
        btn.addEventListener('shown.bs.tab', function () {
            updateProgressBadge();
        });
    });

    applyEtatUI(false);
    if (isMariageMode && document.getElementById('recherche-dossier-mariage')) {
        initialiserRechercheNominativeMariage();
    } else {
        initialiserRechercheNominative();
    }
})();
