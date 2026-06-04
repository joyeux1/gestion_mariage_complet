// static/mariage/js/dossier_verification.js

(function () {
    const container = document.getElementById('dossier-verif-container');
    if (!container) return;

    const verifUrl = container.dataset.verifUrl;
    const etatEl = document.getElementById('dossier-verif-etat');
    let etat = etatEl ? JSON.parse(etatEl.textContent) : {};

    const streams = { epoux: null, epouse: null };

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

    function afficherCorrespondanceBloquee(match, message) {
        const zone = document.getElementById('verif-match-zone');
        if (!zone || !match) return;

        const confiance = match.confiance_facial
            ? `<span class="badge bg-info text-dark ms-2">Confiance faciale ${match.confiance_facial} %</span>`
            : '';

        zone.innerHTML = `
            <div class="card border-danger shadow-sm">
                <div class="card-header bg-danger text-white fw-bold">
                    <i class="bi bi-exclamation-octagon me-2"></i>
                    Correspondance trouvée dans le système — ${match.nom_complet}${confiance}
                </div>
                <div class="card-body">
                    <p class="text-danger fw-semibold mb-0">${message}</p>
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

    async function startWebcam(role) {
        const video = document.getElementById(`dossier-webcam-${role}`);
        if (!video || streams[role]) return;
        try {
            streams[role] = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } },
                audio: false,
            });
            video.srcObject = streams[role];
            await video.play();
        } catch (e) {
            showAlert('Webcam indisponible : ' + e.message, 'danger');
        }
    }

    function stopWebcam(role) {
        if (streams[role]) {
            streams[role].getTracks().forEach(function (t) { t.stop(); });
            streams[role] = null;
        }
    }

    function captureFace(role) {
        const video = document.getElementById(`dossier-webcam-${role}`);
        const canvas = document.getElementById(`dossier-canvas-${role}`);
        const hidden = document.getElementById(`dossier-base64-${role}`);
        if (!video || !canvas || !hidden || !video.videoWidth) {
            showAlert('Webcam non prête. Patientez un instant.', 'warning');
            return;
        }
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        canvas.getContext('2d').drawImage(video, 0, 0);
        hidden.value = canvas.toDataURL('image/jpeg');
        stopWebcam(role);
        showAlert(`Photo du ${role === 'epoux' ? 'futur époux' : 'future épouse'} capturée.`, 'success');
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
            const b64 = document.getElementById(`dossier-base64-${role}`)?.value;
            if (!b64) throw new Error('Capturez d\'abord la photo du visage.');
            fd.append('image_base64', b64);
        }
        return fd;
    }

    async function verifierConjoint(type, role) {
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
                buttons.forEach(function (b) { b.disabled = false; });
                return;
            }

            effacerCorrespondanceBloquee();

            if (!data.success) {
                const msg = data.errors
                    ? Object.values(data.errors).flat().join(' ')
                    : 'Erreur de vérification.';
                showAlert(msg, 'danger');
                buttons.forEach(function (b) { b.disabled = false; });
                return;
            }

            etat = data.etat;
            showAlert(data.message, 'success');
            markRoleOk(role);
            if (role === 'epoux') {
                setEpouseEnabled(true);
                updateProgressBadge();
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
        captureFace('epoux');
    });
    document.getElementById('dossier-capture-epouse-btn')?.addEventListener('click', function () {
        captureFace('epouse');
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

    applyEtatUI(false);
})();
