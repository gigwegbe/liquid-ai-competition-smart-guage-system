# Liquid AI Competition Smart Guage System 

Demo: [Video 1](?) [Video 2](?)

### Using With Vision Capabilities to Inspector Guages
![Guage Inspector](./assets/asset-full.png)

### Using Tool Calling to get sensor reading from database 
![Guage Inspector](./assets/asset-sensor-reading.png)

### Using Tool Calling to control actuator (fan)
![Guage Inspector](./assets/asset-fan.png)
## How to run the Application

### Backend

- Create a virtualenv or conda env 

```
conda create --name vlmenv python=3.10
```
- Activate environment
```
conda activate vlmenv
```

- Install the dependencies
```
pip install  -r requirements.txt
```

- Start the Guage Inspector VLM
```
python3 app-vlm-inference.py
```

- Start the Guage Inspector LLM (In another terminal with the same environment)
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

open the app and refresh the page: 
```
http://localhost:5173/
```

## TODO 
- update video 
- install on jetson (check the vlm_processor_jetson)
- Add dataset samples