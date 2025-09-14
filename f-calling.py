# Install required packages first if not installed
# pip install torch transformers

from transformers import AutoModelForCausalLM, AutoTokenizer
import torch
import json

# Device setup (CPU/GPU/MPS)
device = torch.device("cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu")

# Load LiquidAI LFM2-350M model and tokenizer
model_name = "LiquidAI/LFM2-350M"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(model_name).to(device)

# --------------------------
# Smart Farm Functions
# --------------------------
def turn_on_water_pump(duration_minutes: int = None):
    """Turns on the water pump for a specified duration or until manually stopped."""
    if duration_minutes:
        # In a real system, this would schedule the pump to turn off after 'duration_minutes'
        return {"status": f"Water pump turned ON for {duration_minutes} minutes."}
    else:
        # In a real system, this would turn the pump on indefinitely until a stop command
        return {"status": "Water pump turned ON. It will run until manually stopped."}

def turn_off_water_pump():
    """Turns off the water pump."""
    # In a real system, this would immediately stop the pump
    return {"status": "Water pump turned OFF."}

def check_soil_moisture(location: str):
    """Checks the soil moisture level at a specific location."""
    # This is a placeholder. In a real system, it would read from sensors.
    # For demonstration, we'll return a canned response.
    mock_moisture = {"field_a": 45, "greenhouse_1": 60, "orchard": 30}
    moisture_level = mock_moisture.get(location, 50) # Default to 50 if location not found
    return {"status": f"Soil moisture at {location} is {moisture_level}%."}

def set_irrigation_schedule(location: str, start_time: str, duration_minutes: int):
    """Sets an automated irrigation schedule for a specific location."""
    # In a real system, this would configure a scheduling service.
    return {"status": f"Irrigation scheduled for {location} at {start_time} for {duration_minutes} minutes."}

# Map function names to actual implementations
TOOLS = {
    "turn_on_water_pump": turn_on_water_pump,
    "turn_off_water_pump": turn_off_water_pump,
    "check_soil_moisture": check_soil_moisture,
    "set_irrigation_schedule": set_irrigation_schedule
}

# --------------------------
# Define tools JSON for LFM2
# --------------------------
tools_json = [
    {
        "name": "turn_on_water_pump",
        "description": "Turn on the farm's water pump. Can be for a specific duration or until manually stopped.",
        "parameters": {
            "type": "object",
            "properties": {
                "duration_minutes": {
                    "type": "integer",
                    "description": "Optional: Duration in minutes for which the pump should run. If not specified, it runs until manually stopped."
                }
            },
            "required": [] # Duration is optional
        }
    },
    {
        "name": "turn_off_water_pump",
        "description": "Turn off the farm's water pump.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "check_soil_moisture",
        "description": "Check the current soil moisture level at a specific farm location.",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "The specific location in the farm (e.g., 'field_a', 'greenhouse_1', 'orchard')"}
            },
            "required": ["location"]
        }
    },
    {
        "name": "set_irrigation_schedule",
        "description": "Set up an automated irrigation schedule for a specific farm location.",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "The location to schedule irrigation for (e.g., 'field_a', 'greenhouse_1')"},
                "start_time": {"type": "string", "description": "The desired start time for the irrigation (e.g., '06:00', '18:30')"},
                "duration_minutes": {"type": "integer", "description": "The duration of the irrigation in minutes."}
            },
            "required": ["location", "start_time", "duration_minutes"]
        }
    }
]

# --------------------------
# Smart Farm Assistant Loop
# --------------------------
def run_smart_farm():
    print("Welcome to Smart Farm Assistant! Type 'exit' to quit.\n")
    while True:
        user_input = input("User: ")
        if user_input.lower() == "exit":
            break

        # Construct prompt for LFM2 with tool definitions
        prompt = (
            "<|startoftext|><|im_start|>system\n"
            "You are a smart farm assistant. You can control the water pump, check soil moisture, and set irrigation schedules. "
            f"List of available tools: <|tool_list_start|>{json.dumps(tools_json)}<|tool_list_end|><|im_end|>\n"
            f"<|im_start|>user\n{user_input}<|im_end|>\n<|im_start|>assistant\n"
        )

        inputs = tokenizer(prompt, return_tensors="pt").to(device)
        # Using a slightly more controlled generation for function calls
        outputs = model.generate(
            **inputs,
            max_new_tokens=200,
            pad_token_id=tokenizer.eos_token_id, # Ensure padding token is set
            eos_token_id=tokenizer.encode("<|tool_call_end|>")[0] # Set EOS token to the end of tool call marker
        )
        decoded = tokenizer.decode(outputs[0], skip_special_tokens=False) # Keep special tokens for parsing

        # Extract function call if present
        tool_call_marker_start = "<|tool_call_start|>"
        tool_call_marker_end = "<|tool_call_end|>"

        if tool_call_marker_start in decoded:
            try:
                start = decoded.index(tool_call_marker_start) + len(tool_call_marker_start)
                end = decoded.index(tool_call_marker_end)
                func_call_str = decoded[start:end].strip()

                # The model might output the tool call within a JSON-like structure or directly.
                # We need to parse it robustly.
                # Example raw output from model: "tool_code: {\"name\": \"turn_on_water_pump\", \"arguments\": \"{\\\"duration_minutes\\\": 30}\"}"

                # A more robust parsing might involve looking for JSON within the string,
                # but for simplicity, we'll assume a direct function call format if not JSON.

                # Attempt to parse as JSON first, as it's more structured
                try:
                    import json
                    call_data = json.loads(func_call_str)
                    func_name = call_data["name"]
                    args_dict = json.loads(call_data["arguments"]) # Arguments are often a JSON string within JSON
                except (json.JSONDecodeError, KeyError):
                    # Fallback to parsing function name and arguments if not JSON
                    # Example: turn_on_water_pump(duration_minutes=30)
                    if "(" in func_call_str and ")" in func_call_str:
                        func_name = func_call_str.split("(", 1)[0]
                        args_raw = func_call_str.split("(", 1)[1].rstrip(")")
                        args_dict = {}
                        if args_raw.strip():
                            for pair in args_raw.split(","):
                                if "=" in pair:
                                    k, v = pair.split("=", 1)
                                    k = k.strip()
                                    v = v.strip().strip('"') # Remove quotes
                                    # Attempt to convert numbers if possible
                                    try:
                                        args_dict[k] = int(v)
                                    except ValueError:
                                        try:
                                            args_dict[k] = float(v)
                                        except ValueError:
                                            args_dict[k] = v
                                else:
                                    print(f"[Warning] Skipping malformed argument pair: {pair}")
                    else:
                        raise ValueError("Could not parse function call string.")


                print(f"\n[Function call generated by LFM2]: {func_name}({', '.join(f'{k}={v!r}' for k, v in args_dict.items())})\n")

                # Execute function
                if func_name in TOOLS:
                    result = TOOLS[func_name](**args_dict)
                    print(f"[Smart Farm System Response]: {result['status']}\n")
                else:
                    print(f"[Error]: Unknown function '{func_name}'.\n")

            except Exception as e:
                print(f"[Error executing function]: {e}\n")
                import traceback
                traceback.print_exc() # For detailed debugging
        else:
            # If no tool call, just print the assistant's response
            # We need to clean up the output from the model, removing system prompts and user inputs.
            # This is a simplified cleanup. A more robust solution would parse the turn-based conversation.
            assistant_response = decoded.split("<|im_start|>assistant")[1].split("<|im_end|>")[0].strip()
            print(f"[Assistant]: {assistant_response}\n")

if __name__ == "__main__":
    run_smart_farm()