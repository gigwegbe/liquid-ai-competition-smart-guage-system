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
    
# ========================
# 3️⃣ Main processing function
# ========================
def process_llm_response(user_input):
    # Construct the prompt with tool definitions
    system_message = """List of tools: <|tool_list_start|>[{"name": "control_fan", "description": "Controls the state of the fan. Use this to turn the fan on or off.", "parameters": {"type": "object", "properties": {"state": {"type": "string", "enum": ["on", "off"], "description": "The desired state of the fan ('on' or 'off')."}}, "required": ["state"]}}]<|tool_list_end|>
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
        max_new_tokens=512, # Adjust as needed
        do_sample=True,
        temperature=0.3,
        min_p=0.15,
        repetition_penalty=1.05,
    )

    decoded_output = tokenizer.decode(output[0], skip_special_tokens=False)

    # Parse the output for tool calls
    tool_call_match = re.search(r"<\|tool_call_start\|>\[(.*?)\]<\|tool_call_end\|>", decoded_output)

    if tool_call_match:
        tool_call_str = tool_call_match.group(1)
        try:
            # Very basic parsing, a proper JSON parser would be better for complex tools
            # This assumes a simple function call format like: function_name(arg1="value1", arg2="value2")
            func_name_match = re.match(r"(\w+)\((.*)\)", tool_call_str)
            if func_name_match:
                func_name = func_name_match.group(1)
                args_str = func_name_match.group(2)
                args = {}
                # Parse arguments (simple key-value pairs)
                for arg_pair in args_str.split(','):
                    if '=' in arg_pair:
                        key, value = arg_pair.split('=', 1)
                        args[key.strip()] = value.strip().strip('"\'') # Remove quotes

                if func_name == "control_fan":
                    tool_response = control_fan(**args)
                    # Now, you'd typically send this tool_response back to the LLM
                    # to get a final answer. For simplicity, we'll just return it.
                    return f"<|tool_response_start|>{tool_response}<|tool_response_end|>"
            else:
                return "Error: Could not parse tool call arguments."
        except Exception as e:
            return f"Error executing tool call: {e}"
    else:
        # If no tool call, return the decoded assistant response
        # You might need to clean up the decoded_output further
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