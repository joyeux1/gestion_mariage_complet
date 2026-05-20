// static/mariage/js/biometrie_handler.js

function startFingerprintScan() {
    const icon = document.getElementById('fingerprint-icon');
    const scanBtn = document.getElementById('scanBtn');
    const saveBtn = document.getElementById('saveBiometrieBtn');

    // Animation de scan
    icon.style.opacity = "1";
    icon.classList.add('animate-pulse'); // Ajoute une classe de clignotement si définie en CSS
    scanBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span> Scan en cours...';
    scanBtn.disabled = true;

    // Simulation d'une capture (3 secondes)
    setTimeout(() => {
        icon.classList.remove('animate-pulse');
        icon.classList.replace('text-primary', 'text-success');
        
        scanBtn.innerHTML = '<i class="bi bi-check-lg me-2"></i> Capture terminée';
        scanBtn.className = "btn btn-success w-100";
        
        // On déverrouille le bouton de sauvegarde
        saveBtn.disabled = false;
        
        showToast("Données biométriques capturées avec succès.", "success");
    }, 3000);
}