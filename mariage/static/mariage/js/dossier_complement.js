// static/mariage/js/dossier_complement.js
// Validation temporaire du complément de profil (époux / épouse) avant enregistrement du dossier.

(function () {
    const form = document.getElementById('form-dossier-edit');
    if (!form) return;

    const configs = {
        epoux: {
            modalId: 'modalEpoux',
            btnId: 'btn-valider-complement-epoux',
            badgeId: 'badge-complement-epoux',
            msgId: 'modal-epoux-validation-msg',
            photoModalId: 'e_photo_modal',
            photoMainId: 'e_photo_input',
            photoPreviewId: 'e_photo_preview',
            triggerId: 'btn-open-modal-epoux',
            required: [
                { name: 'e_piece_identite', label: 'Type de pièce' },
                { name: 'e_profession', label: 'Profession' },
                { name: 'e_commune_residence', label: 'Commune de résidence' },
            ],
        },
        epouse: {
            modalId: 'modalEpouse',
            btnId: 'btn-valider-complement-epouse',
            badgeId: 'badge-complement-epouse',
            msgId: 'modal-epouse-validation-msg',
            photoModalId: 'f_photo_modal',
            photoMainId: 'f_photo_input',
            photoPreviewId: 'f_photo_preview',
            triggerId: 'btn-open-modal-epouse',
            required: [
                { name: 'f_piece_identite', label: 'Type de pièce' },
                { name: 'f_profession', label: 'Profession' },
                { name: 'f_commune_residence', label: 'Commune de résidence' },
            ],
        },
    };

    function getModalField(name) {
        return form.querySelector('[name="' + name + '"]');
    }

    function syncPhotoFromModal(cfg) {
        const modalInput = document.getElementById(cfg.photoModalId);
        const mainInput = document.getElementById(cfg.photoMainId);
        if (!modalInput?.files?.length || !mainInput) return;

        const dt = new DataTransfer();
        dt.items.add(modalInput.files[0]);
        mainInput.files = dt.files;
        mainInput.removeAttribute('required');

        const preview = document.getElementById(cfg.photoPreviewId);
        if (preview) {
            preview.src = URL.createObjectURL(modalInput.files[0]);
            preview.classList.remove('d-none');
        }
    }

    function validerComplement(role) {
        const cfg = configs[role];
        if (!cfg) return;

        const errors = [];
        cfg.required.forEach(function (field) {
            const el = getModalField(field.name);
            const val = el ? (el.value || '').trim() : '';
            if (!val) {
                errors.push(field.label);
                if (el) el.classList.add('is-invalid');
            } else if (el) {
                el.classList.remove('is-invalid');
            }
        });

        if (errors.length) {
            alert('Veuillez compléter : ' + errors.join(', ') + '.');
            return;
        }

        syncPhotoFromModal(cfg);

        const badge = document.getElementById(cfg.badgeId);
        if (badge) badge.classList.remove('d-none');

        const trigger = document.getElementById(cfg.triggerId);
        if (trigger) {
            trigger.classList.remove('text-primary', 'text-danger');
            trigger.classList.add('text-success');
            trigger.innerHTML = '<i class="bi bi-check-circle-fill me-1"></i> Complément validé'
                + ' <span class="badge bg-success ms-1">Enregistré pour le dossier</span>';
        }

        const msg = document.getElementById(cfg.msgId);
        if (msg) {
            msg.classList.remove('d-none');
            msg.innerHTML = '<i class="bi bi-check-circle-fill me-1"></i> Complément enregistré — '
                + 'sera sauvegardé avec le dossier.';
        }

        const modalEl = document.getElementById(cfg.modalId);
        if (modalEl && typeof bootstrap !== 'undefined') {
            const instance = bootstrap.Modal.getInstance(modalEl)
                || new bootstrap.Modal(modalEl);
            instance.hide();
        }
    }

    Object.keys(configs).forEach(function (role) {
        const cfg = configs[role];
        const btn = document.getElementById(cfg.btnId);
        if (btn) {
            btn.addEventListener('click', function () {
                validerComplement(role);
            });
        }
    });
})();
