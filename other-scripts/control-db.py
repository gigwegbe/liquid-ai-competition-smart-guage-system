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
# 2️⃣ Function definitions for tools
# ========================
def get_sensor_data():
    """
    Fetches the latest sensor data from the SQLite database.
    Returns:
        str: A JSON string containing the latest temperature, pressure and rain.
    """
    db_path = "sensors-json.db"
    try:
        conn = sqlite3.connect(db_path)
        # Select the latest temperature, pressure and rain  from the sensor_data table
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
    # Construct the prompt with the new tool definition
    system_message = """List of tools: <|tool_list_start|>[{"name": "get_sensor_data", "description": "Retrieves the most recent temperature and humidity data from the sensors database. Use this tool when asked about the current sensor readings or environmental conditions.", "parameters": {"type": "object", "properties": {}}}]<|tool_list_end|>
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
            # The tool call is expected to be a simple function name with no arguments
            if tool_call_str.startswith("get_sensor_data"):
                tool_response = get_sensor_data()
                # Now, we send this tool_response back to the LLM to get a final answer.
                # This is the "tool-use" pattern. For this simple example, we'll just return it.
                return f"<|tool_response_start|>{tool_response}<|tool_response_end|>"
            else:
                return "Error: Unsupported tool call."
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
# 4️⃣ Dynamic User Input and Execution
# ========================
if __name__ == "__main__":
    while True:
        user_request = input("Enter your request (type 'exit' to quit): ")
        if user_request.lower() == 'exit':
            break
        
        response = process_llm_response(user_request)
        print(f"\nUser: {user_request}\nAssistant: {response}\n")