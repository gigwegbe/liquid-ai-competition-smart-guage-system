import json
import time
import torch
import sqlite3
import pandas as pd
from transformers import AutoTokenizer, AutoModelForCausalLM
import re
from flask import Flask, request, jsonify
from flask_cors import CORS

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

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
# 2️⃣ Function definitions for tools
# ========================
def control_fan(state: str):
    """
    Controls the state of the fan.
    Args:
        state (str): The desired state of the fan, either "on" or "off".
    Returns:
        str: A confirmation message indicating the fan's new state.
    """
    if state.lower() == "on":
        print("Turning fan ON...")
        # Add your actual fan ON logic here
        return "The fan has been turned on."
    elif state.lower() == "off":
        print("Turning fan OFF...")
        # Add your actual fan OFF logic here
        return "The fan has been turned off."
    else:
        return "Invalid state. Please specify 'on' or 'off'."

def control_drain(state: str):
    """
    Controls the state of the drain.
    Args:
        state (str): The desired state of the drain, either "open" or "closed".
    Returns:
        str: A confirmation message indicating the drain's new state.
    """
    if state.lower() == "open":
        print("Opening drain...")
        # Add your actual drain OPEN logic here
        return "The drain has been opened."
    elif state.lower() == "closed":
        print("Closing drain...")
        # Add your actual drain CLOSE logic here
        return "The drain has been closed."
    else:
        return "Invalid state. Please specify 'open' or 'closed'."

def get_sensor_data():
    """
    Fetches the latest sensor data from the SQLite database.
    Returns:
        str: A JSON string containing the latest temperature, pressure, and rain.
    """
    db_path = "sensors-json.db"
    try:
        conn = sqlite3.connect(db_path)
        # Select the latest temperature, pressure, and rain from the sensor_data table
        # Note: The error "no such column: humidity" suggests your database might not have a 'humidity' column.
        # I've adjusted the query to only include columns that are present in your original code (temperature, pressure, rain).
        query = "SELECT temperature, pressure, rain FROM sensor_data ORDER BY timestamp DESC LIMIT 1"
        df = pd.read_sql_query(query, conn)
        conn.close()

        if df.empty:
            return json.dumps({"status": "error", "message": "No data found in the database."})

        latest_data = df.iloc[0].to_dict()
        return json.dumps({"status": "success", "data": latest_data})

    except sqlite3.Error as e:
        return json.dumps({"status": "error", "message": f"Database error: {e}"})
    except Exception as e:
        return json.dumps({"status": "error", "message": f"An unexpected error occurred: {e}"})

# ========================
# 3️⃣ Main processing function
# ========================
def process_llm_response(user_input):
    # Construct the prompt with all tool definitions
    system_message = """List of tools: <|tool_list_start|>[
        {"name": "control_fan", "description": "Controls the state of the fan. Use this to turn the fan on or off.", "parameters": {"type": "object", "properties": {"state": {"type": "string", "enum": ["on", "off"], "description": "The desired state of the fan ('on' or 'off')."}}, "required": ["state"]}},
        {"name": "control_drain", "description": "Controls the state of the drain. Use this to open or close the drain.", "parameters": {"type": "object", "properties": {"state": {"type": "string", "enum": ["open", "closed"], "description": "The desired state of the drain ('open' or 'closed')."}}, "required": ["state"]}},
        {"name": "get_sensor_data", "description": "Retrieves the most recent temperature, pressure, and rain data from the sensors database. Use this tool when asked about current sensor readings or environmental conditions.", "parameters": {"type": "object", "properties": {}}}
    ]<|tool_list_end|>
    You are a helpful assistant.
    """
    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": user_input}
    ]

    input_ids = tokenizer.apply_chat_template(
        messages,
        add_generation_prompt=True,
        return_tensors="pt",
        tokenize=True,
    ).to(device)

    # Generate the model's response
    output = model.generate(
        input_ids,
        max_new_tokens=512,  # Adjust as needed
        do_sample=True,
        temperature=0.3,
        min_p=0.15,
        repetition_penalty=1.05,
    )

    decoded_output = tokenizer.decode(output[0], skip_special_tokens=False)

    # Parse the output for tool calls
    tool_call_match = re.search(r"<\|tool_call_start\|>\[(.*?)\]<\|tool_call_end\|>", decoded_output, re.DOTALL)

    if tool_call_match:
        tool_call_str = tool_call_match.group(1).strip()
        try:
            # Basic parsing for function calls
            func_name_match = re.match(r"(\w+)\((.*)\)", tool_call_str)
            if func_name_match:
                func_name = func_name_match.group(1)
                args_str = func_name_match.group(2)
                args = {}
                # Parse arguments (simple key-value pairs)
                for arg_pair in args_str.split(','):
                    if '=' in arg_pair:
                        key, value = arg_pair.split('=', 1)
                        # Clean up potential quotes around values
                        args[key.strip()] = value.strip().strip('"\'')

                if func_name == "control_fan":
                    tool_response = control_fan(**args)
                elif func_name == "control_drain":
                    tool_response = control_drain(**args)
                elif func_name == "get_sensor_data":
                    tool_response = get_sensor_data()
                else:
                    return "Error: Unsupported tool call."
                
                # Format the tool response to send back to the LLM
                return f"<|tool_response_start|>{tool_response}<|tool_response_end|>"
            else:
                return "Error: Could not parse tool call arguments."
        except Exception as e:
            return f"Error executing tool call: {e}"
    else:
        # If no tool call, return the decoded assistant response
        assistant_response_match = re.search(r"<\|im_start\|>assistant(.*?)<\|im_end\|>", decoded_output, re.DOTALL)
        if assistant_response_match:
            return assistant_response_match.group(1).strip()
        else:
            return "Could not understand the request or generate a response."

# ========================
# 4️⃣ Flask API Endpoint
# ========================
@app.route('/interact', methods=['POST', 'OPTIONS'])
def interact_with_llm():
    """
    API endpoint to interact with the LLM.
    Expects a JSON payload with a 'user_input' key.
    """
    # Handle CORS preflight request
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'OK'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,ngrok-skip-browser-warning')
        response.headers.add('Access-Control-Allow-Methods', 'POST,OPTIONS')
        return response
    
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 415

    data = request.get_json()
    user_input = data.get('user_input')

    if not user_input:
        return jsonify({"error": "Missing 'user_input' in request payload"}), 400

    # Process the user input with the LLM
    response = process_llm_response(user_input)

    # The response might be a tool call response or a direct assistant response
    # For simplicity, we'll just return the processed response as JSON
    # In a more complex app, you might want to handle tool call chaining differently
    result = jsonify({"response": response})
    result.headers.add('Access-Control-Allow-Origin', '*')
    return result

# ========================
# 5️⃣ Run the Flask App
# ========================
if __name__ == '__main__':
    # You can run this script directly: python your_script_name.py
    # Then access the API at http://127.0.0.1:5000/interact
    # Example POST request using curl:
    # curl -X POST -H "Content-Type: application/json" -d '{"user_input": "Turn the fan on"}' http://127.0.0.1:5004/interact
    app.run(debug=True, port=5004)
