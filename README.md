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
Install Node.js and npm
Make sure you have Node.js (which includes npm) installed on your machine.

- Navigate to the project directory: 
```
cd vlm-instaector 
```

- Install the dependencies: 
```
npm install 
```

- Run the development server: 
```
npm run dev 
```

- Open the app in your browser. The terminal will show a local URL. By default, it’s usually:
```
http://localhost:5173/
```

- Refresh if needed: If the app doesn’t load immediately, try refreshing the page in your browser.


## TODO 
- update video 
- install on jetson (check the vlm_processor_jetson)
- Add dataset samples