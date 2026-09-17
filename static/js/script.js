// ==============================================================================
// StuHub – Client-side Interactive Script (Vanilla JavaScript)
// ==============================================================================

document.addEventListener('DOMContentLoaded', () => {
  // 1. Sidebar Drawer Toggle (Three-Line Menu ☰)
  const menuToggleBtn = document.getElementById('menuToggleBtn');
  const sidebarDrawer = document.getElementById('sidebarDrawer');
  const sidebarOverlay = document.getElementById('sidebarOverlay');
  const sidebarCloseBtn = document.getElementById('sidebarCloseBtn');

  function openSidebar() {
    if (sidebarDrawer && sidebarOverlay) {
      sidebarDrawer.classList.add('open');
      sidebarOverlay.classList.add('active');
      document.body.style.overflow = 'hidden'; // Prevent page scroll behind drawer
    }
  }

  function closeSidebar() {
    if (sidebarDrawer && sidebarOverlay) {
      sidebarDrawer.classList.remove('open');
      sidebarOverlay.classList.remove('active');
      document.body.style.overflow = '';
    }
  }

  if (menuToggleBtn) {
    menuToggleBtn.addEventListener('click', openSidebar);
  }

  if (sidebarCloseBtn) {
    sidebarCloseBtn.addEventListener('click', closeSidebar);
  }

  if (sidebarOverlay) {
    sidebarOverlay.addEventListener('click', closeSidebar);
  }

  // Close sidebar on ESC key press
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      closeSidebar();
      closeModal();
    }
  });

  // 2. Auto-dismiss Flash Alerts after 5 seconds
  const alerts = document.querySelectorAll('.alert');
  alerts.forEach((alert) => {
    // Add close button handler
    const closeBtn = alert.querySelector('.alert-close-btn');
    if (closeBtn) {
      closeBtn.addEventListener('click', () => {
        alert.style.transition = 'opacity 0.3s, transform 0.3s';
        alert.style.opacity = '0';
        alert.style.transform = 'translateY(-10px)';
        setTimeout(() => alert.remove(), 300);
      });
    }

    // Auto fade after 5s
    setTimeout(() => {
      if (alert.parentElement) {
        alert.style.transition = 'opacity 0.3s, transform 0.3s';
        alert.style.opacity = '0';
        alert.style.transform = 'translateY(-10px)';
        setTimeout(() => alert.remove(), 300);
      }
    }, 5000);
  });

  // 3. Image File Upload Preview
  const imageInputs = document.querySelectorAll('input[type="file"][accept*="image"]');
  imageInputs.forEach((input) => {
    input.addEventListener('change', function () {
      const previewId = this.dataset.previewId || 'imagePreview';
      const previewEl = document.getElementById(previewId);

      if (previewEl && this.files && this.files[0]) {
        const reader = new FileReader();
        reader.onload = function (e) {
          previewEl.src = e.target.result;
          previewEl.style.display = 'block';
        };
        reader.readAsDataURL(this.files[0]);
      }
    });
  });

  // 4. Edit Profile Modal
  const editProfileBtn = document.getElementById('openEditProfileBtn');
  const editProfileModal = document.getElementById('editProfileModal');
  const closeProfileModalBtn = document.getElementById('closeProfileModalBtn');
  const cancelProfileModalBtn = document.getElementById('cancelProfileModalBtn');

  function openModal() {
    if (editProfileModal) {
      editProfileModal.classList.add('active');
      document.body.style.overflow = 'hidden';
    }
  }

  function closeModal() {
    if (editProfileModal) {
      editProfileModal.classList.remove('active');
      document.body.style.overflow = '';
    }
  }

  if (editProfileBtn) editProfileBtn.addEventListener('click', openModal);
  if (closeProfileModalBtn) closeProfileModalBtn.addEventListener('click', closeModal);
  if (cancelProfileModalBtn) cancelProfileModalBtn.addEventListener('click', closeModal);

  if (editProfileModal) {
    editProfileModal.addEventListener('click', (e) => {
      if (e.target === editProfileModal) closeModal();
    });
  }
});

// Quick fill helper for demo login screen
function fillDemoCredentials(identifier, password) {
  const idInput = document.getElementById('identifier');
  const passInput = document.getElementById('password');
  if (idInput && passInput) {
    idInput.value = identifier;
    passInput.value = password;
    idInput.focus();
  }
}

// Dynamic Campus Events Sub-Category Updater (Technical & Non-Technical)
const campusEventCategories = {
  'Technical': [
    'Hackathons', 'Coding Competitions', 'Technical Quiz',
    'Workshops', 'Project Expo', 'Paper Presentation',
    'Tech Fest', 'Seminars'
  ],
  'Non-Technical': [
    'Dancing', 'Singing', 'Debate', 'Photography',
    'Drawing & Painting', 'Cultural Events', 'Sports',
    'College Fest', 'Quiz', 'Student Activities'
  ]
};

function updateEventSubCategories(mainSelectId, subSelectId, defaultText) {
  const mainEl = document.getElementById(mainSelectId);
  const subEl = document.getElementById(subSelectId);
  if (!mainEl || !subEl) return;

  const selected = mainEl.value;
  subEl.innerHTML = `<option value="">${defaultText || 'Select Category'}</option>`;

  let list = [];
  if (selected && campusEventCategories[selected]) {
    list = campusEventCategories[selected];
  } else {
    Object.values(campusEventCategories).forEach(arr => list.push(...arr));
  }

  list.forEach(sub => {
    const opt = document.createElement('option');
    opt.value = sub;
    opt.textContent = sub;
    subEl.appendChild(opt);
  });
}

// ==============================================================================
// 5. Dual Photo Input (Camera Capture & File Upload)
// ==============================================================================
let cameraStream = null;

function setPhotoMode(mode) {
  const uploadSection = document.getElementById('uploadPhotoSection');
  const cameraSection = document.getElementById('cameraPhotoSection');
  const btnUpload = document.getElementById('btnModeUpload');
  const btnCamera = document.getElementById('btnModeCamera');

  if (mode === 'camera') {
    if (uploadSection) uploadSection.style.display = 'none';
    if (cameraSection) cameraSection.style.display = 'block';
    if (btnCamera) { btnCamera.classList.add('active', 'btn-primary'); btnCamera.classList.remove('btn-secondary'); }
    if (btnUpload) { btnUpload.classList.remove('active', 'btn-primary'); btnUpload.classList.add('btn-secondary'); }
  } else {
    if (uploadSection) uploadSection.style.display = 'block';
    if (cameraSection) cameraSection.style.display = 'none';
    if (btnUpload) { btnUpload.classList.add('active', 'btn-primary'); btnUpload.classList.remove('btn-secondary'); }
    if (btnCamera) { btnCamera.classList.remove('active', 'btn-primary'); btnCamera.classList.add('btn-secondary'); }
    stopDeviceCamera();
  }
}

function previewUploadedFile(input) {
  const previewWrapper = document.getElementById('uploadPreviewWrapper');
  const previewImg = document.getElementById('uploadImgPreview');
  if (input.files && input.files[0]) {
    const reader = new FileReader();
    reader.onload = function (e) {
      if (previewImg) previewImg.src = e.target.result;
      if (previewWrapper) previewWrapper.style.display = 'block';
    };
    reader.readAsDataURL(input.files[0]);
  }
}

function clearUploadPreview() {
  const fileInput = document.getElementById('filePhotoInput');
  const previewWrapper = document.getElementById('uploadPreviewWrapper');
  const previewImg = document.getElementById('uploadImgPreview');
  if (fileInput) fileInput.value = '';
  if (previewImg) previewImg.src = '';
  if (previewWrapper) previewWrapper.style.display = 'none';
}

async function startDeviceCamera() {
  const video = document.getElementById('cameraVideo');
  const preview = document.getElementById('cameraSnapshotPreview');
  const idleMsg = document.getElementById('cameraIdleMessage');
  const btnStart = document.getElementById('btnStartCamera');
  const btnCapture = document.getElementById('btnCapturePhoto');
  const btnRetake = document.getElementById('btnRetakePhoto');
  const btnUse = document.getElementById('btnUsePhoto');
  const btnStop = document.getElementById('btnStopCamera');
  const statusText = document.getElementById('cameraStatusText');

  if (preview) preview.style.display = 'none';
  if (statusText) statusText.style.display = 'none';

  try {
    if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
      cameraStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' }, audio: false });
      if (video) {
        video.srcObject = cameraStream;
        video.style.display = 'block';
        video.play();
      }
      if (idleMsg) idleMsg.style.display = 'none';
      if (btnStart) btnStart.style.display = 'none';
      if (btnCapture) btnCapture.style.display = 'inline-block';
      if (btnStop) btnStop.style.display = 'inline-block';
      if (btnRetake) btnRetake.style.display = 'none';
      if (btnUse) btnUse.style.display = 'none';
    } else {
      alert('Camera access is not supported by your browser or requires HTTPS.');
    }
  } catch (err) {
    console.error('Camera error:', err);
    alert('Unable to access camera: ' + (err.message || 'Permission denied'));
  }
}

function captureCameraSnapshot() {
  const video = document.getElementById('cameraVideo');
  const canvas = document.getElementById('cameraCanvas');
  const preview = document.getElementById('cameraSnapshotPreview');
  const btnCapture = document.getElementById('btnCapturePhoto');
  const btnRetake = document.getElementById('btnRetakePhoto');
  const btnUse = document.getElementById('btnUsePhoto');

  if (!video || !canvas) return;

  canvas.width = video.videoWidth || 640;
  canvas.height = video.videoHeight || 480;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

  const dataUrl = canvas.toDataURL('image/jpeg', 0.85);
  if (preview) {
    preview.src = dataUrl;
    preview.style.display = 'block';
  }
  video.style.display = 'none';

  if (btnCapture) btnCapture.style.display = 'none';
  if (btnRetake) btnRetake.style.display = 'inline-block';
  if (btnUse) btnUse.style.display = 'inline-block';
}

function retakeCameraSnapshot() {
  const video = document.getElementById('cameraVideo');
  const preview = document.getElementById('cameraSnapshotPreview');
  const btnCapture = document.getElementById('btnCapturePhoto');
  const btnRetake = document.getElementById('btnRetakePhoto');
  const btnUse = document.getElementById('btnUsePhoto');
  const hiddenData = document.getElementById('cameraPhotoData');
  const statusText = document.getElementById('cameraStatusText');

  if (hiddenData) hiddenData.value = '';
  if (preview) preview.style.display = 'none';
  if (video) video.style.display = 'block';
  if (statusText) statusText.style.display = 'none';

  if (btnCapture) btnCapture.style.display = 'inline-block';
  if (btnRetake) btnRetake.style.display = 'none';
  if (btnUse) btnUse.style.display = 'none';
}

function confirmCameraSnapshot() {
  const preview = document.getElementById('cameraSnapshotPreview');
  const hiddenData = document.getElementById('cameraPhotoData');
  const statusText = document.getElementById('cameraStatusText');
  const btnUse = document.getElementById('btnUsePhoto');

  if (preview && preview.src && hiddenData) {
    hiddenData.value = preview.src;
    stopDeviceCamera();
    if (statusText) {
      statusText.textContent = '✓ Camera Photo Selected & Ready for Submission!';
      statusText.style.display = 'block';
    }
    if (btnUse) btnUse.style.display = 'none';
  }
}

function stopDeviceCamera() {
  if (cameraStream) {
    cameraStream.getTracks().forEach(track => track.stop());
    cameraStream = null;
  }
  const video = document.getElementById('cameraVideo');
  const btnStart = document.getElementById('btnStartCamera');
  const btnCapture = document.getElementById('btnCapturePhoto');
  const btnStop = document.getElementById('btnStopCamera');
  const idleMsg = document.getElementById('cameraIdleMessage');

  if (video) video.style.display = 'none';
  if (btnStart) btnStart.style.display = 'inline-block';
  if (btnCapture) btnCapture.style.display = 'none';
  if (btnStop) btnStop.style.display = 'none';
  if (idleMsg) idleMsg.style.display = 'block';
}


