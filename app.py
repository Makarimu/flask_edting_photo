from flask import Flask, render_template, request, jsonify
import cv2
import numpy as np
import os
from werkzeug.utils import secure_filename
from datetime import datetime
import base64

app = Flask(__name__)

# Konfigurasi
UPLOAD_FOLDER = 'static/uploads'
PROCESSED_FOLDER = 'static/processed'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PROCESSED_FOLDER'] = PROCESSED_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ==================== FITUR PENGOLAHAN CITRA ====================

def apply_grayscale(img):
    """Konversi ke Grayscale"""
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

def apply_brightness_contrast(img, brightness=0, contrast=0):
    """Operasi Pixel: Brightness & Contrast"""
    alpha = 1.0 + (contrast / 100.0)
    beta = brightness
    return cv2.convertScaleAbs(img, alpha=alpha, beta=beta)

def apply_histogram_equalization(img):
    """Histogram Equalization"""
    if len(img.shape) == 2:  # Grayscale
        return cv2.equalizeHist(img)
    else:  # Color
        ycrcb = cv2.cvtColor(img, cv2.COLOR_BGR2YCrCb)
        ycrcb[:, :, 0] = cv2.equalizeHist(ycrcb[:, :, 0])
        return cv2.cvtColor(ycrcb, cv2.COLOR_YCrCb2BGR)

def apply_median_filter(img, kernel_size=3):
    """Filter Median untuk noise reduction"""
    return cv2.medianBlur(img, kernel_size)

def apply_gaussian_blur(img, kernel_size=5):
    """Filter Gaussian Blur"""
    return cv2.GaussianBlur(img, (kernel_size, kernel_size), 0)

def apply_sharpening(img):
    """Konvolusi: Sharpening"""
    kernel = np.array([[-1, -1, -1],
                       [-1,  9, -1],
                       [-1, -1, -1]])
    return cv2.filter2D(img, -1, kernel)

def apply_edge_detection(img, method='canny'):
    """Segmentasi: Deteksi Tepi"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
    if method == 'canny':
        return cv2.Canny(gray, 100, 200)
    elif method == 'sobel':
        sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        return cv2.addWeighted(cv2.convertScaleAbs(sobelx), 0.5, 
                               cv2.convertScaleAbs(sobely), 0.5, 0)
    return gray

def apply_morphology(img, operation='dilate'):
    """Morfologi Citra"""
    kernel = np.ones((3,3), np.uint8)
    if operation == 'dilate':
        return cv2.dilate(img, kernel, iterations=1)
    elif operation == 'erode':
        return cv2.erode(img, kernel, iterations=1)
    elif operation == 'opening':
        return cv2.morphologyEx(img, cv2.MORPH_OPEN, kernel)
    elif operation == 'closing':
        return cv2.morphologyEx(img, cv2.MORPH_CLOSE, kernel)
    return img

def apply_threshold(img, value=127):
    """Jenis Citra: Biner Thresholding"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
    _, binary = cv2.threshold(gray, value, 255, cv2.THRESH_BINARY)
    return binary

# ==================== API ROUTES ====================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/process', methods=['POST'])
def process_image_api():
    """API untuk proses gambar real-time"""
    try:
        data = request.json
        image_data = data.get('image')
        features = data.get('features', {})
        
        # Debugging: Lihat fitur apa yang diterima (bisa dihapus nanti)
        print("Features received:", features)

        # Decode base64 image
        if ',' in image_data:
            header, encoded = image_data.split(',', 1)
            img_bytes = base64.b64decode(encoded)
        else:
            img_bytes = base64.b64decode(image_data)
            
        img_array = np.frombuffer(img_bytes, dtype=np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        
        if img is None:
            return jsonify({'error': 'Failed to decode image'}), 400
        
        # Mulai dengan copy gambar asli
        result = img.copy()
        
        # --- TERAPKAN FITUR ---
        
        # 1. Grayscale
        if features.get('grayscale'):
            result = cv2.cvtColor(result, cv2.COLOR_BGR2GRAY)
            result = cv2.cvtColor(result, cv2.COLOR_GRAY2BGR) # Kembali ke BGR agar konsisten
            
        # 2. Brightness & Contrast
        # Cek apakah ada nilai brightness/contrast (bisa 0)
        if 'brightness' in features or 'contrast' in features:
            brightness = features.get('brightness', 0)
            contrast = features.get('contrast', 0)
            # Rumus OpenCV: new_img = alpha * old_img + beta
            alpha = 1.0 + (contrast / 100.0)
            beta = brightness
            result = cv2.convertScaleAbs(result, alpha=alpha, beta=beta)
            
        # 3. Histogram Equalization
        if features.get('histogram'):
            # Jika grayscale (1 channel)
            if len(result.shape) == 2:
                result = cv2.equalizeHist(result)
                result = cv2.cvtColor(result, cv2.COLOR_GRAY2BGR)
            else:
                # Jika color (3 channel), equalize di channel Y (YCrCb)
                ycrcb = cv2.cvtColor(result, cv2.COLOR_BGR2YCrCb)
                ycrcb[:, :, 0] = cv2.equalizeHist(ycrcb[:, :, 0])
                result = cv2.cvtColor(ycrcb, cv2.COLOR_YCrCb2BGR)

        # 4. Median Filter
        if features.get('median_filter'):
            result = cv2.medianBlur(result, 5) # Kernel 5x5 lebih terlihat efeknya
            
        # 5. Gaussian Blur
        if features.get('gaussian_blur'):
            result = cv2.GaussianBlur(result, (15, 15), 0) # Kernel besar agar blur terlihat
            
        # 6. Sharpening
        if features.get('sharpening'):
            kernel = np.array([[-1, -1, -1],
                               [-1,  9, -1],
                               [-1, -1, -1]])
            result = cv2.filter2D(result, -1, kernel)
            
        # 7. Edge Detection (PERBAIKAN NAMA: edge_canny)
        if features.get('edge_canny'):
            gray = cv2.cvtColor(result, cv2.COLOR_BGR2GRAY) if len(result.shape) == 3 else result
            edges = cv2.Canny(gray, 50, 150)
            result = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR) # Agar bisa ditampilkan
            
        # 8. Morphology (Opsional, jika ada di fitur)
        if features.get('morphology'):
            kernel = np.ones((5,5), np.uint8)
            result = cv2.dilate(result, kernel, iterations=2)

        # Encode hasil ke base64
        _, buffer = cv2.imencode('.jpg', result)
        result_base64 = base64.b64encode(buffer).decode('utf-8')
        
        return jsonify({
            'success': True,
            'result': f'data:image/jpeg;base64,{result_base64}'
        })
        
    except Exception as e:
        print("Error:", str(e))
        return jsonify({'error': str(e)}), 500

@app.route('/api/pipeline', methods=['POST'])
def pipeline_full():
    """Pipeline lengkap untuk video demo"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_name = f"{timestamp}_{filename}"
            upload_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
            file.save(upload_path)
            
            # Read image
            img = cv2.imread(upload_path)
            steps = []
            
            # Step 1: Grayscale + Scaling
            h, w = img.shape[:2]
            new_w, new_h = 500, int(h * (500 / w))
            img = cv2.resize(img, (new_w, new_h))
            img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            step1_path = os.path.join(app.config['PROCESSED_FOLDER'], f'{timestamp}_1_gray.jpg')
            cv2.imwrite(step1_path, img_gray)
            steps.append(('1. Grayscale + Scaling', step1_path))
            
            # Step 2: Brightness & Contrast
            img_bc = cv2.convertScaleAbs(img_gray, alpha=1.2, beta=30)
            step2_path = os.path.join(app.config['PROCESSED_FOLDER'], f'{timestamp}_2_bc.jpg')
            cv2.imwrite(step2_path, img_bc)
            steps.append(('2. Brightness & Contrast', step2_path))
            
            # Step 3: Histogram Equalization
            img_hist = cv2.equalizeHist(img_bc)
            step3_path = os.path.join(app.config['PROCESSED_FOLDER'], f'{timestamp}_3_hist.jpg')
            cv2.imwrite(step3_path, img_hist)
            steps.append(('3. Histogram Equalization', step3_path))
            
            # Step 4: Median Filter
            img_median = cv2.medianBlur(img_hist, 3)
            step4_path = os.path.join(app.config['PROCESSED_FOLDER'], f'{timestamp}_4_median.jpg')
            cv2.imwrite(step4_path, img_median)
            steps.append(('4. Median Filter', step4_path))
            
            # Step 5: Sharpening
            kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
            img_sharp = cv2.filter2D(img_median, -1, kernel)
            step5_path = os.path.join(app.config['PROCESSED_FOLDER'], f'{timestamp}_5_sharp.jpg')
            cv2.imwrite(step5_path, img_sharp)
            steps.append(('5. Sharpening', step5_path))
            
            # Step 6: Morphology
            _, binary = cv2.threshold(img_sharp, 127, 255, cv2.THRESH_BINARY)
            kernel_morph = np.ones((3,3), np.uint8)
            img_morph = cv2.dilate(binary, kernel_morph, iterations=1)
            step6_path = os.path.join(app.config['PROCESSED_FOLDER'], f'{timestamp}_6_morph.jpg')
            cv2.imwrite(step6_path, img_morph)
            steps.append(('6. Morphology (Dilasi)', step6_path))
            
            # Step 7: Edge Detection
            edges = cv2.Canny(img_morph, 100, 200)
            edges_color = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
            final_path = os.path.join(app.config['PROCESSED_FOLDER'], f'{timestamp}_final.jpg')
            cv2.imwrite(final_path, edges_color)
            steps.append(('7. Canny Edge Detection', final_path))
            
            return jsonify({
                'success': True,
                'original': upload_path,
                'steps': steps,
                'final': final_path
            })
        
        return jsonify({'error': 'Invalid file type'}), 400
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)