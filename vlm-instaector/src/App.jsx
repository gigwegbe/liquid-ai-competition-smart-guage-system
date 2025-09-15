import React, { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { Activity, Camera, Gauge, AlertCircle, CheckCircle, Clock, Settings, Power, AlertTriangle, Zap, MessageCircle, Bot, User, Send, X } from 'lucide-react';

const VLMGaugeInspector = () => {
  // Backend Configuration
  const BACKEND_URL = 'http://localhost:5001';
  const STREAM_ENDPOINT = `${BACKEND_URL}/stream`;
  const STATUS_ENDPOINT = `${BACKEND_URL}/status`;

  // LLM Inference Configuration
  const LLM_BASE_URL = 'http://localhost:5004';
  const LLM_INTERACT_ENDPOINT = `${LLM_BASE_URL}/interact`;

  const [connectionStatus, setConnectionStatus] = useState('connecting');
  const [currentImage, setCurrentImage] = useState(null);
  const [vlmResults, setVlmResults] = useState(null);
  const [chartData, setChartData] = useState([]);
  const [readingCount, setReadingCount] = useState(0);
  const [actuatorStatus, setActuatorStatus] = useState({});
  const [alerts, setAlerts] = useState([]);
  const [backendStatus, setBackendStatus] = useState(null);

  // LLM Interface states
  const [showLLMPanel, setShowLLMPanel] = useState(false);
  const [llmResponse, setLlmResponse] = useState('');
  const [isProcessingLLM, setIsProcessingLLM] = useState(false);
  const [sensorData, setSensorData] = useState(null);
  const [lastLLMAction, setLastLLMAction] = useState('');

  // Thresholds for different parameters (based on test_merged.py ranges)
  const thresholds = {
    rain_gauge: { min: 1.0, max: 10.0, critical_max: 15.0, unit: 'mm' },
    thermometer: { min: 15.0, max: 50.0, critical_max: 70.0, unit: '°C' },
    pressure_gauge: { min: 0.1, max: 1.0, critical_max: 1.5, unit: 'bar' }
  };

  // Actuator configurations
  const actuatorConfigs = {
    pressure_relief_valve: {
      name: 'Pressure Relief Valve',
      type: 'valve',
      controlled_parameter: 'pressure_gauge',
      icon: Settings
    },
    cooling_fan: {
      name: 'Cooling Fan',
      type: 'fan',
      controlled_parameter: 'thermometer',
      icon: Power
    },
    drainage_system: {
      name: 'Drainage Control',
      type: 'drain',
      controlled_parameter: 'rain_gauge',
      icon: Zap
    }
  };

  // LLM API call function
  const callLLMAPI = async (userInput) => {
    try {
      console.log('🤖 Calling LLM API with input:', userInput);
      setIsProcessingLLM(true);
      setLastLLMAction(userInput);

      const response = await fetch(LLM_INTERACT_ENDPOINT, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'ngrok-skip-browser-warning': 'true'
        },
        body: JSON.stringify({
          user_input: userInput
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      console.log('✅ LLM API response:', data);

      setLlmResponse(data.response || 'No response received');
      return data.response;

    } catch (error) {
      console.error('❌ LLM API call failed:', error);
      const errorMsg = `Error: ${error.message}`;
      setLlmResponse(errorMsg);
      return errorMsg;
    } finally {
      setIsProcessingLLM(false);
    }
  };

  // Specific action functions for the three main LLM capabilities
  const controlFan = async (state) => {
    const action = state === 'on' ? 'Turn the fan on' : 'Turn the fan off';
    return await callLLMAPI(action);
  };

  const controlDrain = async (state) => {
    const action = state === 'open' ? 'Open the drain' : 'Close the drain';
    return await callLLMAPI(action);
  };

  const getSensorData = async () => {
    return await callLLMAPI('Get the latest sensor data including temperature, pressure, and rain levels');
  };

  // Function to determine actuator response based on readings
  const calculateActuatorResponse = (gaugeResults) => {
    const responses = {};
    const newAlerts = [];

    Object.entries(gaugeResults).forEach(([param, value]) => {
      const threshold = thresholds[param];
      if (!threshold) return;

      // Find corresponding actuator
      const actuatorKey = Object.keys(actuatorConfigs).find(key =>
        actuatorConfigs[key].controlled_parameter === param
      );

      if (actuatorKey) {
        let status = 'normal';
        let action = 'maintain';
        let intensity = 0;
        let isOn = false;

        if (value >= threshold.critical_max) {
          status = 'critical';
          action = 'emergency_activate';
          intensity = 100;
          isOn = true;
          newAlerts.push({
            id: Date.now() + Math.random(),
            type: 'critical',
            message: `Critical ${param} level detected: ${value}`,
            parameter: param,
            timestamp: new Date().toLocaleTimeString()
          });
        } else if (value >= threshold.max) {
          status = 'warning';
          action = 'activate';
          intensity = Math.min(((value - threshold.max) / (threshold.critical_max - threshold.max)) * 80 + 20, 80);
          isOn = true;
          newAlerts.push({
            id: Date.now() + Math.random(),
            type: 'warning',
            message: `High ${param} detected: ${value}`,
            parameter: param,
            timestamp: new Date().toLocaleTimeString()
          });
        } else if (value <= threshold.min) {
          status = 'warning';
          action = 'reduce';
          intensity = Math.max(((threshold.min - value) / threshold.min) * 50, 10);
          isOn = true;
          newAlerts.push({
            id: Date.now() + Math.random(),
            type: 'warning',
            message: `Low ${param} detected: ${value}`,
            parameter: param,
            timestamp: new Date().toLocaleTimeString()
          });
        } else {
          status = 'normal';
          action = 'maintain';
          intensity = 0;
          isOn = false;
        }

        responses[actuatorKey] = {
          status,
          action,
          intensity,
          isOn,
          parameter: param,
          current_value: value,
          target_range: `${threshold.min}-${threshold.max}`,
          last_updated: new Date().toLocaleTimeString()
        };
      }
    });

    return { responses, alerts: newAlerts };
  };

  // Dummy data for demonstration
  const dummyImages = [
    'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48Y2lyY2xlIGN4PSIxMDAiIGN5PSIxMDAiIHI9IjgwIiBmaWxsPSIjZjVmNWY1IiBzdHJva2U9IiNjY2MiIHN0cm9rZS13aWR0aD0iMiIvPjx0ZXh0IHg9IjEwMCIgeT0iMTA1IiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBmb250LWZhbWlseT0iQXJpYWwiIGZvbnQtc2l6ZT0iMTQiIGZpbGw9IiM2NjYiPkdhdWdlIDE8L3RleHQ+PC9zdmc+',
    'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48Y2lyY2xlIGN4PSIxMDAiIGN5PSIxMDAiIHI9IjgwIiBmaWxsPSIjZjVmNWY1IiBzdHJva2U9IiNjY2MiIHN0cm9rZS13aWR0aD0iMiIvPjx0ZXh0IHg9IjEwMCIgeT0iMTA1IiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBmb250LWZhbWlseT0iQXJpYWwiIGZvbnQtc2l6ZT0iMTQiIGZpbGw9IiM2NjYiPkdhdWdlIDI8L3RleHQ+PC9zdmc+'
  ];

  // Check backend status
  const checkBackendStatus = async () => {
    try {
      console.log(`🔍 Checking backend status at: ${STATUS_ENDPOINT}`);
      const response = await fetch(STATUS_ENDPOINT, {
        method: 'GET',
        mode: 'cors',
        headers: {
          'ngrok-skip-browser-warning': 'true',
          'Accept': 'application/json',
          'Content-Type': 'application/json'
        }
      });

      console.log(`📡 Response status: ${response.status}`);
      console.log(`📡 Response headers:`, [...response.headers.entries()]);

      if (response.ok) {
        const status = await response.json();
        setBackendStatus(status);
        console.log('✅ Backend status:', status);
        return true;
      } else {
        const errorText = await response.text();
        console.error(`❌ Backend status check failed: ${response.status}`);
        console.error(`❌ Error response:`, errorText);
        setBackendStatus({ error: `HTTP ${response.status}: ${errorText}` });
        return false;
      }
    } catch (error) {
      console.error('❌ Backend status check error:', error);
      console.error('❌ Error details:', {
        name: error.name,
        message: error.message,
        stack: error.stack
      });
      setBackendStatus({ error: error.message });
      return false;
    }
  };

  // Connect to Flask backend stream using fetch (ngrok EventSource workaround)
  useEffect(() => {
    let abortController;
    let reconnectTimeout;
    let isConnected = false;

    const connectToStream = async () => {
      if (abortController) {
        console.log('🔄 Aborting existing stream connection');
        abortController.abort();
      }

      abortController = new AbortController();
      setConnectionStatus('connecting');
      console.log(`🔗 Attempting to connect to stream: ${STREAM_ENDPOINT}`);

      try {
        console.log('� Starting fetch-based EventSource streaming...');
        const response = await fetch(STREAM_ENDPOINT, {
          method: 'GET',
          headers: {
            'Accept': 'text/event-stream',
            'Cache-Control': 'no-cache',
            'ngrok-skip-browser-warning': 'true'
          },
          signal: abortController.signal
        });

        console.log('📡 Stream response status:', response.status);
        console.log('📡 Stream response headers:', [...response.headers.entries()]);

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('text/event-stream')) {
          throw new Error(`Invalid content-type: ${contentType}, expected text/event-stream`);
        }

        console.log('✅ Stream connection established!');
        setConnectionStatus('connected');
        isConnected = true;

        // Read the stream using ReadableStream
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        try {
          while (true) {
            const { done, value } = await reader.read();

            if (done) {
              console.log('� Stream ended');
              break;
            }

            // Decode the chunk and add to buffer
            buffer += decoder.decode(value, { stream: true });

            // Process complete messages
            const lines = buffer.split('\n\n');
            buffer = lines.pop() || ''; // Keep incomplete message in buffer

            for (const chunk of lines) {
              if (chunk.trim()) {
                try {
                  // Parse Server-Sent Event format
                  const eventLines = chunk.split('\n');
                  let eventData = '';

                  for (const line of eventLines) {
                    if (line.startsWith('data: ')) {
                      eventData += line.substring(6) + '\n';
                    }
                  }

                  if (eventData.trim()) {
                    console.log('📨 Received SSE message');
                    console.log('📨 Message preview:', eventData.substring(0, 100) + '...');

                    const data = JSON.parse(eventData.trim());

                    if (data.error) {
                      console.error('Server Error:', data.error);
                      continue;
                    }

                    if (data.image && data.vlm_analysis) {
                      const timestamp = new Date(data.timestamp * 1000).toLocaleTimeString();

                      // Set current image from Flask backend
                      setCurrentImage(`data:image/jpeg;base64,${data.image}`);

                      // Process VLM analysis results
                      if (data.vlm_analysis.success && data.vlm_analysis.gauge_readings) {
                        const gaugeReadings = data.vlm_analysis.gauge_readings;

                        const newVlmResults = {
                          timestamp: timestamp,
                          gauge_results: {
                            rain_gauge: gaugeReadings.rain_gauge,
                            thermometer: gaugeReadings.thermometer,
                            pressure_gauge: gaugeReadings.pressure_gauge
                          },
                          confidence: 0.85 + Math.random() * 0.1,
                          status: 'normal',
                          processing_time: data.vlm_analysis.processing_time || 0
                        };

                        // Calculate actuator responses
                        const { responses, alerts: newAlerts } = calculateActuatorResponse(newVlmResults.gauge_results);

                        // Update status based on alerts
                        if (newAlerts.some(alert => alert.type === 'critical')) {
                          newVlmResults.status = 'error';
                        } else if (newAlerts.length > 0) {
                          newVlmResults.status = 'warning';
                        }

                        setVlmResults(newVlmResults);
                        setActuatorStatus(responses);
                        setReadingCount(prev => prev + 1);

                        // Update alerts
                        if (newAlerts.length > 0) {
                          setAlerts(prev => [...newAlerts, ...prev].slice(0, 5));
                        }

                        // Update chart data
                        setChartData(prevData => {
                          const newDataPoint = {
                            time: timestamp,
                            rain_gauge: gaugeReadings.rain_gauge || 0,
                            thermometer: gaugeReadings.thermometer || 0,
                            pressure_gauge: gaugeReadings.pressure_gauge || 0
                          };

                          const updatedData = [...prevData, newDataPoint];
                          return updatedData.slice(-10);
                        });

                        console.log(`✅ Processed: ${data.filename} - VLM: ${JSON.stringify(gaugeReadings)} (${data.vlm_analysis.processing_time}s)`);
                      } else {
                        console.error('❌ VLM Analysis failed:', data.vlm_analysis.error);
                      }
                    }
                  }
                } catch (parseError) {
                  console.error('❌ Error parsing SSE message:', parseError);
                  console.error('❌ Raw chunk:', chunk);
                }
              }
            }
          }
        } catch (streamError) {
          if (!abortController.signal.aborted) {
            throw streamError;
          }
        } finally {
          reader.releaseLock();
        }

      } catch (error) {
        if (abortController.signal.aborted) {
          console.log('🔄 Stream connection aborted');
          return;
        }

        console.error('❌ Stream connection failed:', error);
        console.error('❌ Error details:', {
          name: error.name,
          message: error.message,
          cause: error.cause
        });

        setConnectionStatus('disconnected');
        isConnected = false;

        // Retry connection
        clearTimeout(reconnectTimeout);
        reconnectTimeout = setTimeout(() => {
          console.log('🔄 Attempting to reconnect...');
          connectToStream();
        }, 5000);
      }
    };

    connectToStream();

    return () => {
      if (abortController) {
        abortController.abort();
      }
      clearTimeout(reconnectTimeout);
      isConnected = false;
    };
  }, []);

  const getStatusColor = (status) => {
    switch (status) {
      case 'warning': return 'text-orange-500';
      case 'error': return 'text-red-500';
      default: return 'text-green-500';
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'warning': return <AlertCircle className="w-4 h-4" />;
      case 'error': return <AlertCircle className="w-4 h-4" />;
      default: return <CheckCircle className="w-4 h-4" />;
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 p-4">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-blue-100 rounded-lg">
                <Gauge className="w-6 h-6 text-blue-600" />
              </div>
              <div>
                <h1 className="text-2xl font-semibold text-gray-900">VLM Gauge Inspector</h1>
                <p className="text-gray-500">Real-time gauge monitoring and analysis</p>
                <p className="text-xs text-blue-600 font-mono">{BACKEND_URL}</p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              {/* LLM Control Panel Button */}
              <button
                onClick={() => setShowLLMPanel(true)}
                className="flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors"
              >
                <Bot className="w-4 h-4" />
                LLM Control
              </button>

              <div className={`flex items-center gap-2 px-3 py-1 rounded-full text-sm font-medium ${connectionStatus === 'connected' ? 'bg-green-100 text-green-800' :
                connectionStatus === 'connecting' ? 'bg-yellow-100 text-yellow-800' :
                  'bg-red-100 text-red-800'
                }`}>
                <div className={`w-2 h-2 rounded-full ${connectionStatus === 'connected' ? 'bg-green-500' :
                  connectionStatus === 'connecting' ? 'bg-yellow-500' :
                    'bg-red-500'
                  }`} />
                {connectionStatus === 'connected' ? 'Connected' :
                  connectionStatus === 'connecting' ? 'Connecting...' : 'Disconnected'}
              </div>

              {/* Backend Status Indicator */}
              {backendStatus && (
                <div className="text-xs text-gray-600">
                  {backendStatus.error ? (
                    <span className="text-red-600">Backend Error</span>
                  ) : (
                    <span className="text-green-600">
                      Backend OK ({backendStatus.total_images} images)
                    </span>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* LLM Control Panel Modal */}
        {showLLMPanel && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-lg shadow-2xl w-full max-w-4xl max-h-5/6 flex flex-col">
              <div className="flex items-center justify-between p-6 border-b">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-purple-100 rounded-lg">
                    <Bot className="w-5 h-5 text-purple-600" />
                  </div>
                  <div>
                    <h2 className="text-xl font-semibold text-gray-900">LLM System Control</h2>
                    <p className="text-gray-500">Control actuators and get sensor data using AI</p>
                    <p className="text-xs text-purple-600 font-mono">{LLM_BASE_URL}</p>
                  </div>
                </div>
                <button
                  onClick={() => setShowLLMPanel(false)}
                  className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
                >
                  <X className="w-5 h-5 text-gray-500" />
                </button>
              </div>

              {/* LLM Actions */}
              <div className="flex-1 overflow-y-auto p-6 space-y-6">
                {/* Action Buttons */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  {/* Fan Control */}
                  <div className="bg-blue-50 rounded-lg p-4 border border-blue-200">
                    <h3 className="text-lg font-semibold text-blue-800 mb-3 flex items-center gap-2">
                      <Power className="w-5 h-5" />
                      Fan Control
                    </h3>
                    <div className="space-y-2">
                      <button
                        onClick={() => controlFan('on')}
                        disabled={isProcessingLLM}
                        className="w-full px-4 py-2 bg-green-500 text-white rounded-lg hover:bg-green-600 disabled:opacity-50 transition-colors"
                      >
                        Turn Fan ON
                      </button>
                      <button
                        onClick={() => controlFan('off')}
                        disabled={isProcessingLLM}
                        className="w-full px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600 disabled:opacity-50 transition-colors"
                      >
                        Turn Fan OFF
                      </button>
                    </div>
                  </div>

                  {/* Drain Control */}
                  <div className="bg-teal-50 rounded-lg p-4 border border-teal-200">
                    <h3 className="text-lg font-semibold text-teal-800 mb-3 flex items-center gap-2">
                      <Zap className="w-5 h-5" />
                      Drain Control
                    </h3>
                    <div className="space-y-2">
                      <button
                        onClick={() => controlDrain('open')}
                        disabled={isProcessingLLM}
                        className="w-full px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50 transition-colors"
                      >
                        Open Drain
                      </button>
                      <button
                        onClick={() => controlDrain('closed')}
                        disabled={isProcessingLLM}
                        className="w-full px-4 py-2 bg-gray-500 text-white rounded-lg hover:bg-gray-600 disabled:opacity-50 transition-colors"
                      >
                        Close Drain
                      </button>
                    </div>
                  </div>

                  {/* Sensor Data */}
                  <div className="bg-green-50 rounded-lg p-4 border border-green-200">
                    <h3 className="text-lg font-semibold text-green-800 mb-3 flex items-center gap-2">
                      <Activity className="w-5 h-5" />
                      Sensor Data
                    </h3>
                    <button
                      onClick={getSensorData}
                      disabled={isProcessingLLM}
                      className="w-full px-4 py-2 bg-purple-500 text-white rounded-lg hover:bg-purple-600 disabled:opacity-50 transition-colors"
                    >
                      Get Latest Readings
                    </button>
                  </div>
                </div>

                {/* Status Display */}
                <div className="bg-gray-50 rounded-lg p-4">
                  <div className="flex items-center gap-2 mb-3">
                    <div className={`w-3 h-3 rounded-full ${isProcessingLLM ? 'bg-yellow-500 animate-pulse' : 'bg-gray-400'}`}></div>
                    <h3 className="text-lg font-semibold text-gray-800">
                      {isProcessingLLM ? 'Processing LLM Request...' : 'LLM Response'}
                    </h3>
                  </div>

                  {lastLLMAction && (
                    <div className="mb-3 text-sm text-gray-600">
                      <strong>Last Action:</strong> {lastLLMAction}
                    </div>
                  )}

                  <div className="bg-white rounded border p-4 min-h-32 max-h-60 overflow-y-auto">
                    {isProcessingLLM ? (
                      <div className="flex items-center gap-2">
                        <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                        <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                        <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                        <span className="text-gray-500 text-sm ml-2">Calling LLM API...</span>
                      </div>
                    ) : llmResponse ? (
                      <div className="whitespace-pre-wrap text-sm text-gray-800">
                        {llmResponse}
                      </div>
                    ) : (
                      <div className="text-gray-400 text-sm">
                        Click any action above to interact with the LLM system
                      </div>
                    )}
                  </div>
                </div>

                {/* Instructions */}
                <div className="bg-blue-50 rounded-lg p-4 border border-blue-200">
                  <h3 className="text-lg font-semibold text-blue-800 mb-2">How it works:</h3>
                  <ul className="text-sm text-blue-700 space-y-1">
                    <li>• <strong>Fan Control:</strong> Uses LLM to control cooling fan based on temperature readings</li>
                    <li>• <strong>Drain Control:</strong> Uses LLM to manage drainage system for rain water</li>
                    <li>• <strong>Sensor Data:</strong> Retrieves latest temperature, pressure, and rain data from database</li>
                    <li>• <strong>AI Processing:</strong> All actions are processed through the LLM inference API</li>
                  </ul>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Enhanced Layout for Better Space Utilization */}
        <div className="space-y-6">
          {/* Top Row - Large Current Image */}
          <div className="bg-white rounded-lg shadow-sm p-6">
            <div className="flex items-center gap-2 mb-6">
              <Camera className="w-6 h-6 text-gray-600" />
              <h2 className="text-xl font-medium text-gray-900">Current Gauge Image</h2>
            </div>

            <div className="w-full h-80 lg:h-96 bg-gray-100 rounded-lg flex items-center justify-center overflow-hidden">
              {currentImage ? (
                // <div className="relative w-full h-full overflow-hidden rounded-lg">
                <img
                  src={currentImage}
                  alt="Current gauge"
                  className="object-cover rounded-lg"
                  style={{
                    imageRendering: 'crisp-edges',
                    // width: '110%',
                    // height: '110%',
                    // top: '-8%',
                    // left: '-5%'
                  }}
                />
                // </div>
              ) : (
                <div className="text-gray-400 text-center">
                  <Camera className="w-16 h-16 mx-auto mb-4 opacity-50" />
                  <p className="text-lg">Waiting for gauge image...</p>
                  <p className="text-sm">Real-time stream from VLM processor</p>
                </div>
              )}
            </div>
          </div>

          {/* Middle Row - Gauge Values and Alerts */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Gauge Values - Larger */}
            <div className="lg:col-span-2 bg-white rounded-lg shadow-sm p-6">
              <div className="flex items-center gap-2 mb-6">
                <Gauge className="w-6 h-6 text-gray-600" />
                <h2 className="text-xl font-medium text-gray-900">VLM Gauge Readings</h2>
              </div>

              {vlmResults ? (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  {Object.entries(vlmResults.gauge_results).map(([key, value]) => {
                    const threshold = thresholds[key];
                    const isWarning = threshold && (value >= threshold.max || value <= threshold.min);
                    const isCritical = threshold && value >= threshold.critical_max;

                    const getDisplayLabel = (key) => {
                      switch (key) {
                        case 'rain_gauge': return 'Rain Gauge';
                        case 'thermometer': return 'Temperature';
                        case 'pressure_gauge': return 'Pressure';
                        default: return key.replace('_', ' ');
                      }
                    };

                    const displayValue = value !== null && value !== undefined ?
                      `${value} ${threshold?.unit || ''}` : 'Not detected';

                    return (
                      <div key={key} className={`p-4 rounded-lg border-2 ${isCritical ? 'border-red-300 bg-red-50' :
                        isWarning ? 'border-yellow-300 bg-yellow-50' :
                          'border-green-300 bg-green-50'
                        }`}>
                        <div className="text-center space-y-3">
                          <div className="flex items-center justify-center gap-2">
                            <span className="text-gray-600 font-medium text-lg">
                              {getDisplayLabel(key)}
                            </span>
                            {isCritical && <AlertCircle className="w-5 h-5 text-red-500" />}
                            {isWarning && !isCritical && <AlertTriangle className="w-5 h-5 text-yellow-500" />}
                          </div>

                          <div className={`text-3xl font-bold ${value === null || value === undefined ? 'text-gray-400' :
                            isCritical ? 'text-red-600' :
                              isWarning ? 'text-yellow-600' : 'text-green-600'
                            }`}>
                            {displayValue}
                          </div>

                          {value !== null && value !== undefined && threshold && (
                            <>
                              <div className="w-full bg-gray-200 rounded-full h-3">
                                <div
                                  className={`h-3 rounded-full transition-all duration-300 ${isCritical ? 'bg-red-500' :
                                    isWarning ? 'bg-yellow-500' : 'bg-green-500'
                                    }`}
                                  style={{ width: `${Math.min((value / threshold.critical_max) * 100, 100)}%` }}
                                />
                              </div>

                              <div className="text-xs text-gray-500 space-y-1">
                                <div>Normal: {threshold.min}-{threshold.max} {threshold.unit}</div>
                                <div>Critical: {'>'}{threshold.critical_max} {threshold.unit}</div>
                              </div>

                              {(isWarning || isCritical) && (
                                <div className={`text-xs font-medium px-2 py-1 rounded-full ${isCritical ? 'bg-red-100 text-red-800' : 'bg-yellow-100 text-yellow-800'
                                  }`}>
                                  {isCritical ? '🚨 CRITICAL' : '⚠️ ANOMALY'}
                                </div>
                              )}
                            </>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="flex items-center justify-center h-48 text-gray-400">
                  <div className="text-center">
                    <Clock className="w-16 h-16 mx-auto mb-4 opacity-50" />
                    <p className="text-lg">Waiting for VLM analysis...</p>
                  </div>
                </div>
              )}
            </div>

            {/* Alerts - Compact */}
            <div className="bg-white rounded-lg shadow-sm p-6">
              <div className="flex items-center gap-2 mb-4">
                <AlertTriangle className="w-5 h-5 text-gray-600" />
                <h2 className="text-lg font-medium text-gray-900">System Alerts</h2>
              </div>

              <div className="space-y-3 max-h-80 overflow-y-auto">
                {alerts.length > 0 ? (
                  alerts.map((alert) => (
                    <div key={alert.id} className={`p-3 rounded-lg border-l-4 ${alert.type === 'critical' ? 'bg-red-50 border-red-500' : 'bg-yellow-50 border-yellow-500'
                      }`}>
                      <div className="flex items-start gap-2">
                        <AlertCircle className={`w-4 h-4 mt-0.5 ${alert.type === 'critical' ? 'text-red-500' : 'text-yellow-500'
                          }`} />
                        <div className="flex-1">
                          <p className={`text-sm font-medium ${alert.type === 'critical' ? 'text-red-800' : 'text-yellow-800'
                            }`}>
                            {alert.message}
                          </p>
                          <p className="text-xs text-gray-500 mt-1">{alert.timestamp}</p>
                        </div>
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="text-center text-gray-400 py-8">
                    <AlertTriangle className="w-8 h-8 mx-auto mb-2 opacity-50" />
                    <p>No active alerts</p>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Actuator Controls - Horizontal Layout */}
          <div className="bg-white rounded-lg shadow-sm p-6">
            <div className="flex items-center gap-2 mb-6">
              <Settings className="w-6 h-6 text-gray-600" />
              <h2 className="text-xl font-medium text-gray-900">Actuator Control System</h2>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {Object.entries(actuatorConfigs).map(([actuatorKey, config]) => {
                const status = actuatorStatus[actuatorKey];
                const IconComponent = config.icon;

                return (
                  <div key={actuatorKey} className={`p-6 rounded-lg border-2 transition-all ${status?.status === 'critical' ? 'border-red-300 bg-red-50' :
                    status?.status === 'warning' ? 'border-yellow-300 bg-yellow-50' :
                      status?.status === 'normal' ? 'border-green-300 bg-green-50' :
                        'border-gray-300 bg-gray-50'
                    }`}>
                    <div className="text-center space-y-4">
                      <div className={`p-4 rounded-full mx-auto w-16 h-16 flex items-center justify-center ${status?.status === 'critical' ? 'bg-red-200 text-red-700' :
                        status?.status === 'warning' ? 'bg-yellow-200 text-yellow-700' :
                          status?.status === 'normal' ? 'bg-green-200 text-green-700' :
                            'bg-gray-200 text-gray-700'
                        }`}>
                        <IconComponent className="w-8 h-8" />
                      </div>

                      <div>
                        <h3 className="font-semibold text-lg text-gray-900">{config.name}</h3>
                        <p className="text-sm text-gray-500 capitalize">{config.type}</p>
                      </div>

                      <div className={`px-4 py-2 rounded-full text-sm font-medium ${status?.isOn ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                        }`}>
                        {status?.isOn ? 'ACTIVE' : 'STANDBY'}
                      </div>

                      {status && (
                        <div className="space-y-2 text-sm">
                          <div className="flex justify-between">
                            <span className="text-gray-600">Current:</span>
                            <span className="font-medium">{status.current_value}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-gray-600">Target:</span>
                            <span className="font-medium">{status.target_range}</span>
                          </div>
                          <div className="text-xs text-gray-500">
                            Updated: {status.last_updated}
                          </div>

                          {/* Enhanced Status Indicator */}
                          <div className="flex items-center justify-center pt-2">
                            <div className={`w-16 h-8 rounded-full transition-all duration-300 relative ${status.isOn ? 'bg-green-500 shadow-lg' : 'bg-gray-300'
                              } ${status.isOn && status.status === 'critical' ? 'animate-pulse' : ''}`}>
                              <div className={`w-6 h-6 rounded-full bg-white shadow-md transition-all duration-300 absolute top-1 ${status.isOn ? 'left-9' : 'left-1'
                                }`} />
                            </div>
                            {status.isOn && (
                              <div className="ml-3 flex items-center">
                                <div className={`w-3 h-3 rounded-full ${status.status === 'critical' ? 'bg-red-500 animate-pulse' : 'bg-green-500'
                                  }`} />
                              </div>
                            )}
                          </div>
                        </div>
                      )}

                      {!status && (
                        <div className="text-gray-400 py-4">
                          <p className="text-sm">Waiting for data...</p>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Bottom Row - Enhanced Chart and Statistics */}
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
            {/* Real-time Trends - Expanded */}
            <div className="lg:col-span-3 bg-white rounded-lg shadow-sm p-6">
              <div className="flex items-center gap-2 mb-6">
                <Activity className="w-6 h-6 text-gray-600" />
                <h2 className="text-xl font-medium text-gray-900">Real-time Performance Trends</h2>
              </div>

              <div className="h-96">
                {chartData.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                      <XAxis
                        dataKey="time"
                        tick={{ fontSize: 11 }}
                        angle={-45}
                        textAnchor="end"
                        height={60}
                      />
                      <YAxis tick={{ fontSize: 11 }} />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: 'white',
                          border: '1px solid #e5e7eb',
                          borderRadius: '8px',
                          boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)'
                        }}
                      />
                      <Legend />
                      <Line
                        type="monotone"
                        dataKey="pressure_gauge"
                        stroke="#3b82f6"
                        strokeWidth={3}
                        dot={{ fill: '#3b82f6', strokeWidth: 2, r: 4 }}
                        name="Pressure (bar)"
                      />
                      <Line
                        type="monotone"
                        dataKey="thermometer"
                        stroke="#ef4444"
                        strokeWidth={3}
                        dot={{ fill: '#ef4444', strokeWidth: 2, r: 4 }}
                        name="Temperature (°C)"
                      />
                      <Line
                        type="monotone"
                        dataKey="rain_gauge"
                        stroke="#10b981"
                        strokeWidth={3}
                        dot={{ fill: '#10b981', strokeWidth: 2, r: 4 }}
                        name="Rain Gauge (mm)"
                      />
                    </LineChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="flex items-center justify-center h-full text-gray-400">
                    <div className="text-center">
                      <Activity className="w-16 h-16 mx-auto mb-4 opacity-50" />
                      <p className="text-lg">Collecting trend data...</p>
                      <p className="text-sm">Real-time data visualization will appear here</p>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Statistics - Compact */}
            <div className="bg-white rounded-lg shadow-sm p-6">
              <div className="flex items-center gap-2 mb-4">
                <Activity className="w-5 h-5 text-gray-600" />
                <h2 className="text-lg font-medium text-gray-900">System Stats</h2>
              </div>

              <div className="space-y-4">
                <div className="text-center">
                  <div className="text-2xl font-bold text-gray-900">{readingCount}</div>
                  <div className="text-sm text-gray-600">Total Readings</div>
                </div>
                <div className="text-center">
                  <div className={`text-2xl font-bold ${alerts.length > 0 ? 'text-red-600' : 'text-green-600'}`}>
                    {alerts.length}
                  </div>
                  <div className="text-sm text-gray-600">Active Alerts</div>
                </div>
                {vlmResults && (
                  <>
                    <div className="text-center">
                      <div className="text-2xl font-bold text-blue-600">
                        {(vlmResults.confidence * 100).toFixed(1)}%
                      </div>
                      <div className="text-sm text-gray-600">AI Confidence</div>
                    </div>
                    <div className="text-center">
                      <div className={`flex items-center justify-center gap-2 ${getStatusColor(vlmResults.status)}`}>
                        {getStatusIcon(vlmResults.status)}
                        <span className="font-semibold capitalize">{vlmResults.status}</span>
                      </div>
                      <div className="text-sm text-gray-600">System Status</div>
                    </div>
                    <div className="text-center border-t pt-3">
                      <div className="text-sm font-medium text-gray-900">{vlmResults.timestamp}</div>
                      <div className="text-xs text-gray-600">Last Update</div>
                      {vlmResults.processing_time && (
                        <div className="text-xs text-gray-500 mt-1">
                          VLM: {vlmResults.processing_time}s
                        </div>
                      )}
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default VLMGaugeInspector;