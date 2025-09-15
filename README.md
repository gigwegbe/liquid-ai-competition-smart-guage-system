# Liquid AI Competition Smart Guage System 

Demo: [Video 1](?) [Video 2](?)

### Using Text Capabilities Only With Ollama
![Guage Inspector](./assets/asset-full.png)

### Using Tool Calling to get sensor reading from database 
![Guage Inspector](./assets/asset-sensor-reading.png)

### Using Tool Calling to control actuator (fan)
![Guage Inspector](./assets/asset-fan.png)
## How to run the Application

### Backend

```
    pip install requirements.txt
```

- Start the Guage Inspector VLM
```
python3 app-vlm-inference.py
```

- Start the Guage Inspector LLM
```
python3 app-llm-inference.py
```

### Frontend 
```
cd vlm-instaector 
```

```
npm install 
```

```
npm run dev 
```