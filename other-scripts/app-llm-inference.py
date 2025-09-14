import json
import time
import requests
import sseclient
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
import re # Import regex for more advanced parsing


# ========================
# 1️⃣ Load the LLM
# ========================
MODEL_NAME = "LiquidAI/LFM2-350M"
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForCausalLM.from_pretrained(MODEL_NAME)
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = model.to(device)

print(f"[INFO] LLM loaded successfully on {device}.")

# ========================
# 2️⃣ Define tools/actions
# ========================
def turn_on_drain():
    print("[ACTION] Drain is now ON")

def open_pressure_valve():
    print("[ACTION] Pressure valve is now OPEN")

def start_cooling_system():
    print("[ACTION] Cooling system is now ON")

TOOLS = {
    "turn_on_drain": turn_on_drain,
    "open_pressure_valve": open_pressure_valve,
    "start_cooling_system": start_cooling_system,
}


# ========================
# 3️⃣ Query LLM
# ========================
def query_model(prompt, max_tokens=150):
    """Queries the LLM with a given prompt and returns the decoded response."""
    inputs = tokenizer(prompt, return_tensors="pt").to(device)
    
    # Adjust generation parameters for more structured output
    # Lower temperature makes output more deterministic, crucial for JSON generation.
    # do_sample=True is still needed to enable sampling even with low temperature.
    outputs = model.generate(
        **inputs,
        max_new_tokens=max_tokens,
        temperature=0.1,  
        do_sample=True,
        pad_token_id=tokenizer.eos_token_id # Set pad_token_id to prevent warnings
    )
    response = tokenizer.decode(outputs[0], skip_special_tokens=True)
    return response

def parse_tool_calls(output_text):
    """
    Parses the LLM output to extract tool calls.
    Handles cases where tool calls are embedded within other text or are not valid JSON.
    Returns a list of tool call dictionaries.
    """
    tool_calls = []
    
    # Regular expression to find potential JSON structures (lists or single objects)
    # that might represent tool calls. This is more robust than simple string finding.
    json_pattern = re.compile(r'(\[.*?\]|\{.*?\})', re.DOTALL)
    potential_jsons = json_pattern.findall(output_text)

    for json_str in potential_jsons:
        try:
            # Try parsing as a list of calls first
            calls_list = json.loads(json_str)
            if isinstance(calls_list, list):
                for call in calls_list:
                    # Ensure it's a dictionary and has a tool/action key
                    if isinstance(call, dict) and ("tool" in call or "action" in call):
                        tool_calls.append(call)
            # If not a list, try parsing as a single call dictionary
            elif isinstance(calls_list, dict) and ("tool" in calls_list or "action" in calls_list):
                tool_calls.append(calls_list)
        except json.JSONDecodeError:
            # If parsing fails, it's not valid JSON.
            # We could add more complex logic here to search for specific LLM tokens 
            # if the model used custom delimiters for tool calls, but for now, 
            # we rely on it outputting valid JSON as instructed.
            # print(f"[DEBUG] Skipping non-JSON string: {json_str}") # Uncomment for debugging
            pass
    
    # If no JSON was found but the model output might have indicated a tool call
    # this section could be expanded. For now, we assume the model adheres to JSON output.
    # Example: if output_text contains "<|tool_call_start|>" etc.

    return tool_calls

def execute_calls(calls):
    """Executes a list of tool calls by looking them up in the TOOLS dictionary."""
    if not calls:
        print("[INFO] No tool calls to execute.")
        return
        
    print(f"[INFO] Executing calls: {calls}")
    
    for call in calls:
        # Determine the tool name, prioritizing 'tool' key, then 'action'
        tool_name = call.get("tool") or call.get("action")
        args = call.get("args", {})
        
        tool_fn = TOOLS.get(tool_name) # Look up the function in our TOOLS dictionary
        
        if tool_fn:
            try:
                # Call the function, passing arguments if they exist
                if args:
                    tool_fn(**args)
                else:
                    tool_fn()
            except Exception as e:
                # Catch and report errors during function execution (e.g., wrong arguments)
                print(f"[ERROR] Failed to execute tool '{tool_name}' with args {args}: {e}")
        else:
            # Warn if the identified tool name is not in our defined TOOLS
            print(f"[WARNING] Tool '{tool_name}' not found in TOOLS dictionary.")

# ========================
# 4️⃣ Continuous SSE monitoring
# ========================
def monitor_sensors_sse(stream_url="http://localhost:5001/stream"):
    """Connects to an SSE stream, processes sensor readings, and triggers LLM actions."""
    while True: # Loop indefinitely to maintain connection and retries
        try:
            print(f"[INFO] Connecting to SSE stream at {stream_url}...")
            # Establish connection with a timeout to avoid hanging
            response = requests.get(stream_url, stream=True, timeout=10) 
            response.raise_for_status() # Raise an exception for bad HTTP status codes (e.g., 404, 500)
            
            client = sseclient.SSEClient(response)
            print("[INFO] Connected to SSE stream successfully.")

            for event in client.events():
                try:
                    data = json.loads(event.data)
                except json.JSONDecodeError:
                    print(f"[WARNING] Could not decode JSON from SSE event: {event.data}")
                    continue # Skip this event if data is not valid JSON

                # Safely extract gauge readings
                gauge_readings = data.get("vlm_analysis", {}).get("gauge_readings", {})
                if not gauge_readings:
                    # print("[DEBUG] No gauge readings in event data.") # Uncomment for debugging
                    continue # Skip if no gauge readings are present in this event

                # Build a structured prompt for the LLM
                # Explicitly instruct the model to ONLY output JSON for tool calls.
                # Provide clear thresholds and current sensor values.
                prompt = f"""You are an AI assistant monitoring environmental sensors.
Your task is to analyze the following readings and trigger actions based on predefined thresholds.
Respond ONLY in JSON format, listing the tool calls to be executed.

**Thresholds:**
- Rainfall height > 10mm: trigger `turn_on_drain`
- Pressure > 1 bar: trigger `open_pressure_valve`
- Temperature > 50 C: trigger `start_cooling_system`

**Current readings:**
Temperature: {gauge_readings.get('temperature', 'N/A')} C
Pressure: {gauge_readings.get('pressure', 'N/A')} bar
Rainfall Height: {gauge_readings.get('rainfall_height', 'N/A')} mm

Your JSON output should be a list of objects, where each object has a "tool" key specifying the action and an optional "args" key for parameters.
Example: `[{{"tool": "turn_on_drain"}}, {{"tool": "start_cooling_system", "args": {{"level": "high"}}}}]`

If no actions are needed based on the thresholds, output an empty JSON list `[]`.

**JSON Output:**
"""
                # print(f"[DEBUG] Prompt sent to LLM:\n{prompt}") # Uncomment for debugging
                
                output = query_model(prompt)
                # print(f"[DEBUG] Raw LLM output:\n{output}") # Uncomment for debugging
                
                parsed_calls = parse_tool_calls(output)
                execute_calls(parsed_calls)

                print(f"[INFO] Processed readings: {gauge_readings}")

        except requests.exceptions.RequestException as e:
            # Handle network-related errors and retry
            print(f"[ERROR] SSE connection error: {e}. Retrying in 5 seconds...")
            time.sleep(5)
        except Exception as e:
            # Catch any other unexpected errors and retry
            print(f"[ERROR] An unexpected error occurred during SSE monitoring: {e}. Retrying in 5 seconds...")
            time.sleep(5)

# ========================
# 5️⃣ Main Execution Block
# ========================
if __name__ == "__main__":
    # This assumes your SSE server is running on http://localhost:5001/stream
    # If your server uses a different URL, update the stream_url accordingly.
    # Example: monitor_sensors_sse(stream_url="http://192.168.1.100:8080/events")
    monitor_sensors_sse()