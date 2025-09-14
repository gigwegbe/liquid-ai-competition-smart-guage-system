from flask import Flask, Response, render_template_string
from flask_cors import CORS
import os
import time
import base64
import json
import threading
import random
import json 




app = Flask(__name__)
CORS(app)

IMAGE_FOLDER = '/Users/george/Downloads/merged_gauges_csv'
STREAM_INTERVAL = 10

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
    try:
        with open(image_path, 'rb') as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            return encoded_string
    except Exception as e:
        print(f"Error encoding image {image_path}: {e}")
        return None

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
                data = {
                    'image': encoded_image,
                    'filename': current_image,
                    'index': image_index + 1,
                    'total': len(image_files),
                    'timestamp': time.time()
                }
                
                yield f"data: {json.dumps(data)}\n\n"
                
                print(f"Sent image: {current_image} ({image_index + 1}/{len(image_files)})")
            else:
                error_data = {
                    'error': f'Could not load image: {current_image}',
                    'timestamp': time.time()
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
    image_files = get_image_files()
    return {
        'status': 'running',
        'image_folder': IMAGE_FOLDER,
        'stream_interval': STREAM_INTERVAL,
        'total_images': len(image_files),
        'image_files': image_files[:10]
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
                        
                        console.log(`Received image: ${data.filename}`);
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
    print(f"Starting Flask Image Streaming Server...")
    print(f"Image folder: {IMAGE_FOLDER}")
    print(f"Stream interval: {STREAM_INTERVAL} seconds")
    
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
    
    app.run(debug=True, host='0.0.0.0', port=5001)
