// static/mariage/js/form_handler.js

async function handleAjaxForm(formId, submitBtnId) {
    const form = document.getElementById(formId);
    const btn = document.getElementById(submitBtnId);
    
    if (!form) return;

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        // Reset visual errors
        form.querySelectorAll('.is-invalid').forEach(el => el.classList.remove('is-invalid'));
        btn.disabled = true;

        const formData = new FormData(form);
        
        try {
            const response = await fetch(window.location.href, {
                method: 'POST',
                body: formData,
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            });

            const data = await response.json();

            if (data.success) {
                showToast(data.message, 'success');
                if (data.redirect_url) {
                    setTimeout(() => window.location.href = data.redirect_url, 1500);
                }
            } else {
                btn.disabled = false;
                // Field-specific validation
                for (const [field, errors] of Object.entries(data.errors)) {
                    const input = form.querySelector(`[name="${field}"]`);
                    if (input) {
                        input.classList.add('is-invalid');
                        // On suppose qu'un div .invalid-feedback existe après l'input
                        const feedback = input.nextElementSibling;
                        if (feedback && feedback.classList.contains('invalid-feedback')) {
                            feedback.innerText = errors[0];
                        }
                    }
                }
                showToast("Veuillez corriger les erreurs.", "danger");
            }
        } catch (error) {
            btn.disabled = false;
            showToast("Erreur de connexion au serveur.", "danger");
        }
    });
}

function showToast(message, type) {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `alert alert-${type} alert-dismissible fade show shadow`;
    toast.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 5000);
}