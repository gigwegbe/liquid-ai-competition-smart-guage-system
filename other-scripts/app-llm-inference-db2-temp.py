import json
import time
import torch
import sqlite3
import pandas as pd
from transformers import AutoTokenizer, AutoModelForCausalLM
import re

# ========================
# 1️⃣ Load the LLM and its specific tool-use template
# ========================
MODEL_NAME = "LiquidAI/LFM2-350M"
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, trust_remote_code=True)
model = AutoModelForCausalLM.from_pretrained(MODEL_NAME, trust_remote_code=True)
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = model.to(device)

print(f"[INFO] LLM loaded successfully on {device}.")

# ========================
# 2️⃣ Define tools/actions
# ========================
def start_cooling_system():
    """Starts the cooling system."""
    print("[ACTION] Cooling system is now ON")

TOOLS = {
    "start_cooling_system": start_cooling_system,
}

# Define the function for the LLM in the required JSON format
TOOL_DEFINITIONS = [
    {
        "name": "start_cooling_system",
        "description": "Starts the cooling system to lower the temperature.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
]

# ========================
# 3️⃣ Query LLM with the correct template
# ========================
def query_model(prompt, max_tokens=150):
    """Queries the LLM with a given prompt and returns the decoded response."""
    # The prompt is now a list of messages using the ChatML-like template
    messages = [
        {"role": "system", "content": f"List of tools: <|tool_list_start|>{json.dumps(TOOL_DEFINITIONS)}<|tool_list_end|> You are a helpful assistant that monitors temperature. If the temperature is over 50 C, use the available tool to start the cooling system. Do not take any action if the temperature is below 50 C."},
        {"role": "user", "content": prompt}
    ]

    # Apply the tokenizer's chat template
    tokenized_prompt = tokenizer.apply_chat_template(messages, add_generation_prompt=True, return_tensors="pt")
    inputs = tokenized_prompt.to(device)

    # Generate the response
    outputs = model.generate(
        inputs,
        max_new_tokens=max_tokens,
        temperature=0.1,  
        do_sample=True,
        pad_token_id=tokenizer.eos_token_id
    )
    # Decode only the newly generated part to avoid re-parsing the whole prompt
    response = tokenizer.decode(outputs[0][len(inputs[0]):], skip_special_tokens=True)
    return response

def parse_tool_calls(output_text):
    """
    Parses the LLM output to extract tool calls from the specific <|tool_call_start|> block.
    """
    tool_calls = []
    # Use regex to find the content between the tool call special tokens
    match = re.search(r"<\|tool_call_start\|>(.*?)<\|tool_call_end\|>", output_text, re.DOTALL)
    if match:
        # The content should be a valid JSON list of Pythonic function calls
        # We need to transform the Pythonic syntax to a JSON-parsable list
        call_str = match.group(1).strip()
        
        # A simple hack to convert Python-like calls into a parsable format
        # This is a key step to handle the specific model output format
        call_str = call_str.replace("(", '({"args": ').replace(")", "})").replace("=", '": "')
        call_str = call_str.replace("[", "").replace("]", "").replace(", ", "}, {")
        call_str = f'[{call_str}]'

        try:
            parsed_calls = json.loads(call_str)
            # The format is [{"args": {"candidate_id": "12345"}}] which can be simplified
            for call in parsed_calls:
                # The 'tool' key is the function name, not explicitly returned by the model
                # The model's output `[get_candidate_status...]` requires us to extract it
                func_name = re.search(r'(\w+)\(', match.group(1))
                if func_name:
                    tool_calls.append({"tool": func_name.group(1), "args": call.get("args", {})})
        except json.JSONDecodeError:
            print(f"[ERROR] Could not parse tool call JSON: {call_str}")
    return tool_calls


def execute_calls(calls):
    """Executes a list of tool calls by looking them up in the TOOLS dictionary."""
    if not calls:
        print("[INFO] No tool calls to execute.")
        return
        
    print(f"[INFO] Executing calls: {calls}")
    
    for call in calls:
        tool_name = call.get("tool") or call.get("action")
        args = call.get("args", {})
        tool_fn = TOOLS.get(tool_name)
        
        if tool_fn:
            try:
                tool_fn(**args) if args else tool_fn()
            except Exception as e:
                print(f"[ERROR] Failed to execute tool '{tool_name}' with args {args}: {e}")
        else:
            print(f"[WARNING] Tool '{tool_name}' not found in TOOLS dictionary.")

# ========================
# 4️⃣ Continuous Database Monitoring
# ========================
def monitor_sensors_db(db_path="sensors-json.db", interval_seconds=10):
    while True:
        try:
            print(f"[INFO] Fetching latest sensor data from {db_path}...")
            
            conn = sqlite3.connect(db_path)
            query = "SELECT temperature FROM sensor_data ORDER BY timestamp DESC LIMIT 1"
            df = pd.read_sql_query(query, conn)
            conn.close()
            
            if df.empty:
                print("[WARNING] No data found in the database.")
                time.sleep(interval_seconds)
                continue
            
            latest_temperature = df.iloc[0].get('temperature')
            
            if latest_temperature is None:
                print("[WARNING] No valid temperature reading found.")
                time.sleep(interval_seconds)
                continue
            
            # The prompt now reflects the real user query with the sensor data
            prompt = f"The current temperature is {latest_temperature} C."
            
            output = query_model(prompt)
            parsed_calls = parse_tool_calls(output)
            execute_calls(parsed_calls)

            print(f"[INFO] Processed reading from DB: {{'temperature': {latest_temperature}}}")

        except sqlite3.Error as e:
            print(f"[ERROR] Database error: {e}. Retrying in {interval_seconds} seconds...")
        except Exception as e:
            print(f"[ERROR] An unexpected error occurred during DB monitoring: {e}. Retrying in {interval_seconds} seconds...")
        
        time.sleep(interval_seconds)

if __name__ == "__main__":
    monitor_sensors_db(db_path="sensors-json.db", interval_seconds=10)