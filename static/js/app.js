let videoStream = null;
let currentImage = null;
let processedImageBase64 = null;

// Debug helper
const debug = {
    log: (msg, data) => console.log(`[DEBUG] ${msg}`, data),
    error: (msg, err) => console.error(`[ERROR] ${msg}`, err)
};

// Initialize Camera
async function initCamera() {
    try {
        if (videoStream) {
            videoStream.getTracks().forEach(track => track.stop());
        }
        
        debug.log('Requesting camera access...');
        
        videoStream = await navigator.mediaDevices.getUserMedia({
            video: { 
                width: { ideal: 1280 },
                height: { ideal: 720 }
            },
            audio: false
        });
        
        const videoElement = document.getElementById('videoElement');
        videoElement.srcObject = videoStream;
        
        await new Promise((resolve) => {
            videoElement.onloadedmetadata = () => {
                videoElement.play();
                debug.log('✅ Camera initialized successfully', {
                    width: videoElement.videoWidth,
                    height: videoElement.videoHeight
                });
                resolve();
            };
        });
        
    } catch (err) {
        debug.error('Camera error:', err);
        
        if (err.name === 'NotAllowedError') {
            alert('❌ Akses kamera ditolak.');
        } else if (err.name === 'NotFoundError') {
            alert('❌ Kamera tidak ditemukan.');
        } else {
            alert('❌ Gagal mengakses kamera: ' + err.message);
        }
        
        switchSource('upload');
    }
}

function switchSource(source) {
    event.target.classList.add('active');
    document.querySelectorAll('.source-btn').forEach(btn => {
        if (btn !== event.target) btn.classList.remove('active');
    });
    
    if (source === 'camera') {
        document.getElementById('cameraContainer').classList.add('show');
        document.getElementById('uploadContainer').style.display = 'none';
        initCamera();
    } else {
        document.getElementById('cameraContainer').classList.remove('show');
        document.getElementById('uploadContainer').style.display = 'block';
        if (videoStream) {
            videoStream.getTracks().forEach(track => track.stop());
        }
    }
}

function captureImage() {
    const video = document.getElementById('videoElement');
    
    if (video.readyState !== video.HAVE_ENOUGH_DATA) {
        alert('⚠️ Kamera belum siap.');
        return;
    }
    
    const canvas = document.getElementById('canvas');
    const context = canvas.getContext('2d');
    
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    
    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    
    currentImage = canvas.toDataURL('image/jpeg', 0.9);
    
    debug.log('📸 Image captured');
    
    displayImage(currentImage);
    
    // Auto process jika ada fitur yang dipilih
    const checkedFeatures = document.querySelectorAll('.feature-item input[type="checkbox"]:checked');
    if (checkedFeatures.length > 0) {
        setTimeout(() => processImage(), 100);
    }
}

function handleFileUpload(event) {
    const file = event.target.files[0];
    
    if (!file) return;
    
    if (!file.type.startsWith('image/')) {
        alert('⚠️ Silakan pilih file gambar (JPG, PNG, JPEG)');
        return;
    }
    
    if (file.size > 10 * 1024 * 1024) {
        alert('⚠️ Ukuran file terlalu besar. Maksimal 10MB.');
        return;
    }
    
    const reader = new FileReader();
    
    reader.onload = function(e) {
        currentImage = e.target.result;
        debug.log('✅ Image loaded');
        
        displayImage(currentImage);
        
        // Auto process jika ada fitur yang dipilih
        const checkedFeatures = document.querySelectorAll('.feature-item input[type="checkbox"]:checked');
        if (checkedFeatures.length > 0) {
            setTimeout(() => processImage(), 100);
        }
    };
    
    reader.onerror = function(err) {
        debug.error('❌ File read error:', err);
        alert('⚠️ Gagal membaca file.');
    };
    
    reader.readAsDataURL(file);
}

// Display single image (hasil processing)
function displayImage(src) {
    const display = document.getElementById('imageDisplay');
    const resultImg = document.getElementById('resultImage');
    
    resultImg.src = src;
    display.classList.add('show');
    
    debug.log('🖼️ Image displayed');
}

// Feature Toggle - AUTO PROCESS
function toggleFeature(element) {
    const checkbox = element.querySelector('input[type="checkbox"]');
    checkbox.checked = !checkbox.checked;
    element.classList.toggle('active', checkbox.checked);
    
    if (checkbox.checked) {
        document.getElementById('slidersContainer').classList.add('show');
    }
    
    // Auto process image
    if (currentImage) {
        processImage();
    }
}

// Update Slider Value - AUTO PROCESS dengan debounce
function updateSliderValue(type, value) {
    document.getElementById(`${type}Value`).textContent = value;
    
    if (currentImage) {
        clearTimeout(window.sliderTimeout);
        window.sliderTimeout = setTimeout(() => {
            processImage();
        }, 300);
    }
}

// Process Image - AUTO
async function processImage() {
    if (!currentImage) {
        return;
    }
    
    const features = {};
    document.querySelectorAll('.feature-item input[type="checkbox"]:checked').forEach(cb => {
        features[cb.value] = true;
    });
    
    const brightness = parseInt(document.getElementById('brightnessSlider').value);
    const contrast = parseInt(document.getElementById('contrastSlider').value);
    if (brightness !== 0 || contrast !== 0) {
        features.brightness = brightness;
        features.contrast = contrast;
    }
    
    if (Object.keys(features).length === 0) {
        displayImage(currentImage);
        return;
    }
    
    const imageDisplay = document.getElementById('imageDisplay');
    imageDisplay.style.opacity = '0.6';
    
    debug.log('🚀 Processing image with features:', features);
    
    try {
        const response = await fetch('/api/process', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                image: currentImage,
                features: features
            })
        });
        
        const data = await response.json();
        if (data.success) {
            processedImageBase64 = data.result;
            debug.log('✅ Image processed successfully');
            displayImage(data.result);
        } else {
            debug.error('❌ Server error:', data.error);
        }
    } catch (error) {
        debug.error('❌ Processing error:', error);
    } finally {
        imageDisplay.style.opacity = '1';
    }
}

// Reset Image
function resetImage() {
    document.querySelectorAll('.feature-item').forEach(item => {
        item.classList.remove('active');
        item.querySelector('input[type="checkbox"]').checked = false;
    });
    
    document.getElementById('brightnessSlider').value = 0;
    document.getElementById('contrastSlider').value = 0;
    document.getElementById('brightnessValue').textContent = '0';
    document.getElementById('contrastValue').textContent = '0';
    document.getElementById('slidersContainer').classList.remove('show');
    
    if (currentImage) {
        displayImage(currentImage);
        processedImageBase64 = null;
    }
    
    debug.log('🔄 Image reset');
}

// Download Result
function downloadResult() {
    if (!processedImageBase64) {
        alert('⚠️ Proses gambar terlebih dahulu!');
        return;
    }
    
    const link = document.createElement('a');
    link.download = 'processed_image_' + Date.now() + '.jpg';
    link.href = processedImageBase64;
    link.click();
    
    debug.log('💾 Image downloaded');
}

// Initialize on load
window.addEventListener('load', () => {
    debug.log('🌐 Application loaded');
    initCamera();
});