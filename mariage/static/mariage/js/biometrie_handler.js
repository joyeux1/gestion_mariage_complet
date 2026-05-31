// static/mariage/js/biometrie_handler.js

const BIOMETRIE_FORM_ID = 'biometrieForm';
const BASE64_FIELD_NAME = 'image_base64';

let webcamStream = null;
let cameraActive = false;

function getBiometrieForm() {
    return document.getElementById(BIOMETRIE_FORM_ID);
}

function getOrCreateBase64Input() {
    const form = getBiometrieForm();
    if (!form) {
        return null;
    }

    let input = form.querySelector(`input[name="${BASE64_FIELD_NAME}"]`);
    if (!input) {
        input = document.createElement('input');
        input.type = 'hidden';
        input.name = BASE64_FIELD_NAME;
        input.id = BASE64_FIELD_NAME;
        form.appendChild(input);
    }

    return input;
}

async function startWebcam() {
    const video = document.getElementById('webcam');
    const cameraBtn = document.getElementById('cameraBtn');

    if (!video || !cameraBtn) {
        return;
    }

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        showToast('Votre navigateur ne prend pas en charge l\'accès à la webcam.', 'danger');
        return;
    }

    try {
        webcamStream = await navigator.mediaDevices.getUserMedia({
            video: {
                facingMode: 'user',
                width: { ideal: 640 },
                height: { ideal: 480 },
            },
            audio: false,
        });

        video.srcObject = webcamStream;
        await video.play();

        cameraActive = true;
        cameraBtn.innerHTML = '<i class="bi bi-camera me-2"></i> Capturer la Photo';
        showToast('Caméra activée. Positionnez-vous face à l\'objectif.', 'info');
    } catch (error) {
        stopWebcam();
        showToast('Impossible d\'accéder à la webcam : ' + error.message, 'danger');
    }
}

function stopWebcam() {
    if (webcamStream) {
        webcamStream.getTracks().forEach(function (track) {
            track.stop();
        });
        webcamStream = null;
    }
    cameraActive = false;
}

function captureWebcamPhoto() {
    const video = document.getElementById('webcam');
    const canvas = document.getElementById('canvas');
    const icon = document.getElementById('fingerprint-icon');
    const cameraBtn = document.getElementById('cameraBtn');
    const saveBtn = document.getElementById('saveBiometrieBtn');

    if (!video || !canvas || !cameraBtn || !saveBtn) {
        return;
    }

    if (!cameraActive || !video.srcObject) {
        showToast('Démarrez d\'abord la caméra avant de capturer.', 'warning');
        return;
    }

    if (!video.videoWidth || !video.videoHeight) {
        showToast('La webcam n\'est pas prête. Réessayez dans un instant.', 'warning');
        return;
    }

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    const context = canvas.getContext('2d');
    context.drawImage(video, 0, 0, canvas.width, canvas.height);

    const imageBase64 = canvas.toDataURL('image/jpeg');

    const base64Input = getOrCreateBase64Input();
    if (!base64Input) {
        showToast('Formulaire biométrique introuvable.', 'danger');
        return;
    }
    base64Input.value = imageBase64;

    stopWebcam();
    video.srcObject = null;
    video.poster = imageBase64;

    if (icon) {
        icon.style.opacity = '1';
        icon.classList.replace('text-primary', 'text-success');
    }

    cameraBtn.innerHTML = '<i class="bi bi-check-lg me-2"></i> Photo capturée';
    cameraBtn.className = 'btn btn-success';
    cameraBtn.disabled = true;

    saveBtn.disabled = false;
    showToast('Photo capturée avec succès. Vous pouvez enregistrer.', 'success');
}

function toggleWebcamCapture() {
    if (!cameraActive) {
        startWebcam();
    } else {
        captureWebcamPhoto();
    }
}

(function initBiometrieHandler() {
    getOrCreateBase64Input();
})();
