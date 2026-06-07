// static/mariage/js/dossier_prefill.js
// Préremplit le formulaire d'ouverture après vérification anti-polygamie réussie.

(function () {
    const etatEl = document.getElementById('dossier-verif-etat');
    if (!etatEl) return;

    let etat;
    try {
        etat = JSON.parse(etatEl.textContent);
    } catch (e) {
        return;
    }
    if (!etat.epoux_ok || !etat.epouse_ok) return;

    function base64ToFile(dataUrl, filename) {
        let payload = dataUrl;
        let mime = 'image/jpeg';
        if (dataUrl.indexOf(';base64,') !== -1) {
            const parts = dataUrl.split(';base64,');
            mime = parts[0].replace('data:', '') || mime;
            payload = parts[1];
        } else if (dataUrl.indexOf(',') !== -1 && dataUrl.indexOf('data:') === 0) {
            payload = dataUrl.split(',')[1];
        }
        const binary = atob(payload);
        const bytes = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i++) {
            bytes[i] = binary.charCodeAt(i);
        }
        return new File([bytes], filename, { type: mime });
    }

    function assignFileToInput(inputId, dataUrl, filename, previewId) {
        const input = document.getElementById(inputId);
        if (!input || !dataUrl) return;
        const file = base64ToFile(dataUrl, filename);
        const dt = new DataTransfer();
        dt.items.add(file);
        input.files = dt.files;
        input.removeAttribute('required');

        const preview = previewId ? document.getElementById(previewId) : null;
        if (preview) {
            preview.src = dataUrl.indexOf('data:') === 0 ? dataUrl : 'data:image/jpeg;base64,' + dataUrl;
            preview.classList.remove('d-none');
        }
    }

    if (etat.type === 'faciale') {
        assignFileToInput('e_photo_input', etat.photo_b64_epoux, 'photo_epoux.jpg', 'e_photo_preview');
        assignFileToInput('f_photo_input', etat.photo_b64_epouse, 'photo_epouse.jpg', 'f_photo_preview');
    }

    if (etat.type === 'empreinte') {
        assignFileToInput('e_scan_empreinte', etat.empreinte_b64_epoux, etat.empreinte_nom_epoux || 'empreinte_epoux.png');
        assignFileToInput('f_scan_empreinte', etat.empreinte_b64_epouse, etat.empreinte_nom_epouse || 'empreinte_epouse.png');
    }
})();
