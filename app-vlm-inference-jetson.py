from flask import Flask, Response, render_template_string
from flask_cors import CORS
import os
import time
import base64
import json
import threading
import random
from PIL import Image
import io
import sqlite3
from datetime import datetime


# Import VLM processor
try:
    from vlm_processor_jetson import initialize_vlm, process_image_for_gauges
    VLM_AVAILABLE = True
    print("VLM processor imported successfully!")
except ImportError as e:
    print(f"Warning: VLM processor not available: {e}")
    VLM_AVAILABLE = False

app = Flask(__name__)
CORS(app)

# Configuration
# IMAGE_FOLDER = 'merged_gauges_csv'
IMAGE_FOLDER = 'merged_gauges_csv'
STREAM_INTERVAL = 10  # seconds
ENABLE_VLM = VLM_AVAILABLE  # Only enable if VLM is available

# Global VLM processor
vlm_processor = None

def get_image_files():
    if not os.path.exists(IMAGE_FOLDER):
        return []
    
    image_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.bmp')
    image_files = []
    
    for filename in os.listdir(IMAGE_FOLDER):
        if filename.lower().endswith(image_extensions):
            image_files.append(filename)
    
    return sorted(image_files)

def encode_image_to_base64(image_path):
    """Convert image to base64 string"""
    try:
        with open(image_path, 'rb') as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            return encoded_string
    except Exception as e:
        print(f"Error encoding image {image_path}: {e}")
        return None

def process_image_with_vlm(image_path):
    """Process image with VLM and return gauge readings"""
    global vlm_processor
    
    if not ENABLE_VLM or not VLM_AVAILABLE:
        return {
            'success': False,
            'error': 'VLM processing disabled or not available',
            'gauge_readings': None,
            'processing_time': 0
        }
    
    try:
        start_time = time.time()
        
        # Initialize VLM if not already done
        if vlm_processor is None:
            print("Initializing VLM processor...")
            vlm_processor = initialize_vlm()
            print("VLM processor initialized successfully!")
        
        # Process image
        result = process_image_for_gauges(image_path=image_path)
        processing_time = time.time() - start_time
        
        result['processing_time'] = round(processing_time, 2)
        return result
        
    except Exception as e:
        error_msg = f"VLM processing error: {str(e)}"
        print(error_msg)
        return {
            'success': False,
            'error': error_msg,
            'gauge_readings': None,
            'processing_time': 0
        }

def save_vlm_readings_to_db(vlm_result):
    """Save VLM gauge readings to SQLite database."""
    if not vlm_result.get('success'):
        return
    
    readings = vlm_result.get('gauge_readings', {})
    temperature = float(readings.get("thermometer", 0))
    pressure = float(readings.get("pressure_gauge", 0))
    rain = float(readings.get("rain_gauge", 0))
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    conn = sqlite3.connect("sensors-json.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sensor_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            temperature REAL,
            pressure REAL,
            rain REAL
        )
    """)
    cursor.execute("""
        INSERT INTO sensor_data (timestamp, temperature, pressure, rain)
        VALUES (?, ?, ?, ?)
    """, (timestamp, temperature, pressure, rain))
    conn.commit()
    conn.close()


def generate_image_stream():
    image_files = get_image_files()
    
    if not image_files:
        yield f"data: {json.dumps({'error': 'No images found in folder'})}\n\n"
        return
    
    image_index = 0
    
    while True:
        try:
            current_image = image_files[image_index]
            image_path = os.path.join(IMAGE_FOLDER, current_image)
            
            encoded_image = encode_image_to_base64(image_path)
            
            if encoded_image:
                # Process image with VLM
                vlm_result = process_image_with_vlm(image_path)
                
                # Save readings to DB
                save_vlm_readings_to_db(vlm_result)

                data = {
                    'image': encoded_image,
                    'filename': current_image,
                    'index': image_index + 1,
                    'total': len(image_files),
                    'timestamp': time.time(),
                    'vlm_analysis': vlm_result
                }
                
                yield f"data: {json.dumps(data)}\n\n"
                
                # Enhanced logging
                if vlm_result['success']:
                    gauge_readings = vlm_result.get('gauge_readings', {})
                    print(f"Sent image: {current_image} ({image_index + 1}/{len(image_files)}) - "
                          f"VLM: {gauge_readings} (processed in {vlm_result.get('processing_time', 0)}s)")
                else:
                    print(f"Sent image: {current_image} ({image_index + 1}/{len(image_files)}) - "
                          f"VLM failed: {vlm_result.get('error', 'Unknown error')}")
            else:
                error_data = {
                    'error': f'Could not load image: {current_image}',
                    'timestamp': time.time(),
                    'vlm_analysis': {
                        'success': False,
                        'error': 'Image loading failed',
                        'gauge_readings': None,
                        'processing_time': 0
                    }
                }
                yield f"data: {json.dumps(error_data)}\n\n"
            
            image_index = (image_index + 1) % len(image_files)
            
            time.sleep(STREAM_INTERVAL)
            
        except Exception as e:
            error_data = {
                'error': f'Stream error: {str(e)}',
                'timestamp': time.time()
            }
            yield f"data: {json.dumps(error_data)}\n\n"
            time.sleep(STREAM_INTERVAL)

@app.route('/')
def index():
    return render_template_string(CLIENT_HTML)

@app.route('/stream')
def stream():
    return Response(
        generate_image_stream(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Cache-Control'
        }
    )

@app.route('/status')
def status():
    """Get server status including VLM information"""
    image_files = get_image_files()
    return {
        'status': 'running',
        'image_folder': IMAGE_FOLDER,
        'stream_interval': STREAM_INTERVAL,
        'total_images': len(image_files),
        'image_files': image_files[:10],
        'vlm_config': {
            'available': VLM_AVAILABLE,
            'enabled': ENABLE_VLM,
            'initialized': vlm_processor is not None
        }
    }

CLIENT_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Image Stream Client</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f0f0f0;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .status {
            background-color: #e8f5e8;
            padding: 10px;
            border-radius: 5px;
            margin-bottom: 20px;
            border-left: 4px solid #4CAF50;
        }
        .error {
            background-color: #ffe8e8;
            padding: 10px;
            border-radius: 5px;
            margin-bottom: 20px;
            border-left: 4px solid #f44336;
        }
        .image-container {
            text-align: center;
            margin: 20px 0;
        }
        .image-container img {
            max-width: 100%;
            max-height: 600px;
            border: 2px solid #ddd;
            border-radius: 5px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        .image-info {
            margin-top: 10px;
            font-size: 14px;
            color: #666;
        }
        .vlm-analysis {
            background-color: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 5px;
            padding: 15px;
            margin-top: 20px;
        }
        .gauge-readings {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 10px;
            margin-top: 10px;
        }
        .gauge-item {
            background-color: white;
            padding: 10px;
            border-radius: 3px;
            border-left: 4px solid #007bff;
        }
        .gauge-label {
            font-weight: bold;
            color: #495057;
        }
        .gauge-value {
            font-size: 18px;
            color: #007bff;
            margin-top: 5px;
        }
        .vlm-error {
            color: #dc3545;
            font-style: italic;
        }
        .processing-time {
            font-size: 12px;
            color: #6c757d;
            margin-top: 5px;
        }
        .loading {
            text-align: center;
            padding: 50px;
            font-size: 18px;
            color: #666;
        }
        .connection-status {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            margin-right: 5px;
        }
        .connected { background-color: #4CAF50; }
        .disconnected { background-color: #f44336; }
        .connecting { background-color: #ff9800; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Image Stream Client</h1>
        
        <div class="status">
            <span class="connection-status" id="connectionStatus"></span>
            <span id="statusText">Connecting to stream...</span>
        </div>
        
        <div id="errorContainer"></div>
        
        <div class="loading" id="loadingMessage">
            Waiting for images from server...
        </div>
        
        <div class="image-container" id="imageContainer" style="display: none;">
            <img id="streamedImage" src="" alt="Streamed Image">
            <div class="image-info" id="imageInfo"></div>
            
            <!-- VLM Analysis Section -->
            <div class="vlm-analysis" id="vlmAnalysis">
                <h3>🔍 Gauge Analysis</h3>
                <div id="vlmContent">
                    <p>Processing image with VLM...</p>
                </div>
            </div>
        </div>
    </div>

    <script>
        const statusElement = document.getElementById('statusText');
        const connectionStatus = document.getElementById('connectionStatus');
        const errorContainer = document.getElementById('errorContainer');
        const loadingMessage = document.getElementById('loadingMessage');
        const imageContainer = document.getElementById('imageContainer');
        const streamedImage = document.getElementById('streamedImage');
        const imageInfo = document.getElementById('imageInfo');
        const vlmContent = document.getElementById('vlmContent');

        let eventSource;
        let reconnectTimeout;

        function updateConnectionStatus(status, message) {
            statusElement.textContent = message;
            connectionStatus.className = 'connection-status ' + status;
        }

        function showError(message) {
            errorContainer.innerHTML = `<div class="error">${message}</div>`;
        }

        function clearError() {
            errorContainer.innerHTML = '';
        }

        function displayVLMAnalysis(vlmData) {
            if (!vlmData) {
                vlmContent.innerHTML = '<p class="vlm-error">No VLM analysis data available</p>';
                return;
            }

            if (!vlmData.success) {
                vlmContent.innerHTML = `<p class="vlm-error">VLM Error: ${vlmData.error || 'Unknown error'}</p>`;
                return;
            }

            const gaugeReadings = vlmData.gauge_readings;
            const processingTime = vlmData.processing_time || 0;

            if (!gaugeReadings) {
                vlmContent.innerHTML = '<p class="vlm-error">No gauge readings extracted</p>';
                return;
            }

            // Create gauge readings display
            let html = '<div class="gauge-readings">';
            
            const gaugeConfig = [
                { key: 'rain_gauge', label: 'Rain Gauge', unit: 'mm', color: '#28a745' },
                { key: 'thermometer', label: 'Temperature', unit: '°C', color: '#dc3545' },
                { key: 'pressure_gauge', label: 'Pressure', unit: 'bar', color: '#007bff' }
            ];

            gaugeConfig.forEach(gauge => {
                const value = gaugeReadings[gauge.key];
                const displayValue = value !== null && value !== undefined ? 
                    `${value} ${gauge.unit}` : 'Not detected';
                
                html += `
                    <div class="gauge-item" style="border-left-color: ${gauge.color}">
                        <div class="gauge-label">${gauge.label}</div>
                        <div class="gauge-value" style="color: ${gauge.color}">${displayValue}</div>
                    </div>
                `;
            });

            html += '</div>';
            html += `<div class="processing-time">Processed in ${processingTime}s</div>`;

            vlmContent.innerHTML = html;
        }

        function connectToStream() {
            if (eventSource) {
                eventSource.close();
            }

            updateConnectionStatus('connecting', 'Connecting to stream...');
            
            eventSource = new EventSource('/stream');

            eventSource.onopen = function(event) {
                updateConnectionStatus('connected', 'Connected - Streaming images every 10 seconds');
                clearError();
                console.log('Connection opened');
            };

            eventSource.onmessage = function(event) {
                try {
                    const data = JSON.parse(event.data);
                    
                    if (data.error) {
                        showError(`Server Error: ${data.error}`);
                        return;
                    }

                    if (data.image) {
                        loadingMessage.style.display = 'none';
                        imageContainer.style.display = 'block';
                        
                        streamedImage.src = `data:image/jpeg;base64,${data.image}`;
                        
                        const timestamp = new Date(data.timestamp * 1000).toLocaleTimeString();
                        imageInfo.innerHTML = `
                            <strong>File:</strong> ${data.filename}<br>
                            <strong>Image:</strong> ${data.index} of ${data.total}<br>
                            <strong>Time:</strong> ${timestamp}
                        `;
                        
                        // Display VLM analysis results
                        displayVLMAnalysis(data.vlm_analysis);
                        
                        console.log(`Received image: ${data.filename}`, data.vlm_analysis);
                    }
                } catch (error) {
                    showError(`Error parsing data: ${error.message}`);
                    console.error('Error parsing server data:', error);
                }
            };

            eventSource.onerror = function(event) {
                updateConnectionStatus('disconnected', 'Connection lost - Reconnecting...');
                console.error('EventSource error:', event);
                
                clearTimeout(reconnectTimeout);
                reconnectTimeout = setTimeout(() => {
                    connectToStream();
                }, 5000);
            };
        }

        window.addEventListener('load', () => {
            connectToStream();
        });

        window.addEventListener('beforeunload', () => {
            if (eventSource) {
                eventSource.close();
            }
            clearTimeout(reconnectTimeout);
        });
    </script>
</body>
</html>
'''

if __name__ == '__main__':
    print(f"Starting Flask Image Streaming Server with VLM Integration...")
    print(f"Image folder: {IMAGE_FOLDER}")
    print(f"Stream interval: {STREAM_INTERVAL} seconds")
    
    # VLM Status
    print(f"VLM Available: {VLM_AVAILABLE}")
    print(f"VLM Enabled: {ENABLE_VLM}")
    
    image_files = get_image_files()
    print(f"Found {len(image_files)} images to stream")
    
    if image_files:
        print("Sample images:", image_files[:5])
    else:
        print("Warning: No images found in the specified folder!")
    
    print("\nServer will be available at:")
    print("- Client page: http://localhost:5001/")
    print("- Stream endpoint: http://localhost:5001/stream")
    print("- Status endpoint: http://localhost:5001/status")
    
    if VLM_AVAILABLE and ENABLE_VLM:
        print("\n⚡ VLM Integration Active - Images will be analyzed for gauge readings!")
    else:
        print("\n⚠️  VLM Integration Disabled - Only image streaming will be available")
    
    app.run(debug=True, host='0.0.0.0', port=5001)
