import json
import time
import requests
import sseclient
import torch
import sqlite3
import pandas as pd 
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

# =======



# ========================
# 4️⃣ Continuous Database Monitoring
# ========================
def monitor_sensors_db(db_path="sensors-json.db", interval_seconds=10):
    """
    Monitors sensor data from a SQLite database at regular intervals.
    """
    while True: # Loop to keep the monitoring running
        try:
            print(f"[INFO] Fetching latest sensor data from {db_path}...")
            
            # --- Database Access ---
            conn = sqlite3.connect(db_path)
            # Fetch the latest entry (assuming 'timestamp' column exists and is ordered)
            # You might need to adjust the query based on your table structure
            query = "SELECT * FROM sensor_data ORDER BY timestamp DESC LIMIT 1"
            df = pd.read_sql_query(query, conn)
            conn.close()
            
            if df.empty:
                print("[WARNING] No data found in the database.")
                time.sleep(interval_seconds)
                continue
            
            # Get the latest reading from the DataFrame
            latest_reading = df.iloc[0].to_dict()
            # --- End Database Access ---
            
            # Format data for LLM prompt - adjust keys as needed based on your DB schema
            # Assuming your DB columns are 'temperature', 'pressure', 'rainfall_height'
            gauge_readings = {
                'temperature': latest_reading.get('temperature'),
                'pressure': latest_reading.get('pressure'),
                'rainfall_height': latest_reading.get('rain')
            }
            
            # Remove None values if sensors are not reporting
            gauge_readings = {k: v for k, v in gauge_readings.items() if v is not None}

            if not gauge_readings:
                print("[WARNING] No valid sensor readings found in the latest DB entry.")
                time.sleep(interval_seconds)
                continue
            
            prompt = f"""You are an AI assistant monitoring environmental sensors.
                Your task is to analyze the following readings and trigger actions based on predefined thresholds.
                Respond ONLY in JSON format, listing the tool calls to be executed.

                Thresholds:
                - Rainfall height > 20mm: turn_on_drain
                - Pressure > 1 bar: open_pressure_valve
                - Temperature > 50 C: start_cooling_system

                Current readings:
                Temperature: {gauge_readings.get('temperature', 'N/A')} C
                Pressure: {gauge_readings.get('pressure', 'N/A')} bar
                Rainfall Height: {gauge_readings.get('rainfall_height', 'N/A')} mm

                Available tools:
                - turn_on_drain(): No arguments needed.
                - open_pressure_valve(): No arguments needed.
                - start_cooling_system(): No arguments needed. **DO NOT pass any arguments to start_cooling_system.**

                Your JSON output should be a list of objects, where each object has a "tool" key specifying the action.
                Example: [{{"tool": "turn_on_drain"}}, {{"tool": "open_pressure_valve"}}]

                If no actions are needed, output an empty JSON list [].

                JSON Output:
                """



#             # Build prompt for LLM (same as before)
#             prompt = f"""You are an AI assistant monitoring environmental sensors.
# Your task is to analyze the following readings and trigger actions based on predefined thresholds.
# Respond ONLY in JSON format, listing the tool calls to be executed.

# Thresholds:
# - Rainfall height > 10mm: turn_on_drain
# - Pressure > 1 bar: open_pressure_valve
# - Temperature > 50 C: start_cooling_system

# Current readings:
# Temperature: {gauge_readings.get('temperature', 'N/A')} C
# Pressure: {gauge_readings.get('pressure', 'N/A')} bar
# Rainfall Height: {gauge_readings.get('rainfall_height', 'N/A')} mm

# Your JSON output should be a list of objects, where each object has a "tool" key specifying the action and an optional "args" key for parameters.
# Example: [{{"tool": "turn_on_drain"}}, {{"tool": "start_cooling_system", "args": {{"level": "high"}}}}]

# If no actions are needed, output an empty JSON list [].

# JSON Output:
# """
            # print(f"[DEBUG] Prompt sent to LLM:\n{prompt}") # Uncomment for debugging
            
            output = query_model(prompt)
            # print(f"[DEBUG] Raw LLM output:\n{output}") # Uncomment for debugging
            
            parsed_calls = parse_tool_calls(output)
            execute_calls(parsed_calls)

            print(f"[INFO] Processed readings from DB: {gauge_readings}")

        except sqlite3.Error as e:
            print(f"[ERROR] Database error: {e}. Retrying in {interval_seconds} seconds...")
        except Exception as e:
            print(f"[ERROR] An unexpected error occurred during DB monitoring: {e}. Retrying in {interval_seconds} seconds...")
        
        time.sleep(interval_seconds) # Wait before the next check

# Example of how to run the monitoring
if __name__ == "__main__":
    # Call the database monitoring function
    monitor_sensors_db(db_path="sensors-json.db", interval_seconds=10) # Adjust db_path and interval as needed