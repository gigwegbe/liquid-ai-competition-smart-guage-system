import sqlite3
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch
import json
from datetime import datetime, timedelta
import time, threading

# ========================
# 1️⃣ Load the LLM
# ========================
MODEL_NAME = "LiquidAI/LFM2-350M"
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForCausalLM.from_pretrained(MODEL_NAME)
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = model.to(device)


# ========================
# 2️⃣ Sensor DB Tools
# ========================
def get_last_n_readings(sensor: str, n: int = 3):
    conn = sqlite3.connect("sensors-json.db")
    cursor = conn.cursor()
    query = f"""
    SELECT {sensor} 
    FROM sensor_data 
    ORDER BY id DESC 
    LIMIT {n}
    """
    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()
    return [r[0] for r in rows]


def get_latest_row():
    conn = sqlite3.connect("sensors-json.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, timestamp, temperature, pressure, rain FROM sensor_data ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    return row  # (id, timestamp, temp, pressure, rain)


def compute_average(sensor: str, n: int = 10):
    readings = get_last_n_readings(sensor, n)
    if not readings:
        return None
    return sum(readings) / len(readings)


# ========================
# 3️⃣ Maintenance Scheduling Tool
# ========================
MAINTENANCE_SCHEDULE = []

def schedule_maintenance(equipment: str, days_from_now: int):
    date = datetime.now() + timedelta(days=days_from_now)
    MAINTENANCE_SCHEDULE.append({
        "equipment": equipment,
        "date": date.strftime("%Y-%m-%d %H:%M:%S")
    })
    return f"Scheduled maintenance for {equipment} on {date}"


# ========================
# 4️⃣ Threshold Actions
# ========================
def control_drain():
    return "✅ Drain turned ON (rainfall too high)."

def control_pressure_valve():
    return "✅ Pressure valve opened (pressure too high)."

def control_cooling_system():
    return "✅ Cooling system activated (temperature too high)."


# ========================
# 5️⃣ Tool Registry
# ========================
TOOLS = {
    "get_last_readings": get_last_n_readings,
    "compute_average": compute_average,
    "schedule_maintenance": schedule_maintenance,
    "control_drain": control_drain,
    "control_pressure_valve": control_pressure_valve,
    "control_cooling_system": control_cooling_system,
}


# ========================
# 6️⃣ Query LLM
# ========================
def query_model(prompt, max_tokens=150):
    inputs = tokenizer(prompt, return_tensors="pt").to(device)
    outputs = model.generate(**inputs, max_new_tokens=max_tokens)
    response = tokenizer.decode(outputs[0], skip_special_tokens=True)
    return response


# ========================
# 7️⃣ JSON Parser
# ========================
def parse_json_output(output_text):
    try:
        start_idx = output_text.find("{")
        if start_idx == -1:
            start_idx = output_text.find("[")
        if start_idx == -1:
            return None
        return json.loads(output_text[start_idx:])
    except json.JSONDecodeError:
        return None


# ========================
# 8️⃣ Execute tool calls
# ========================
def execute_calls(calls):
    if not calls:
        return
    if isinstance(calls, dict):
        tool_fn = TOOLS.get(calls.get("tool"))
        args = calls.get("args", {})
        if tool_fn:
            result = tool_fn(**args)
            print(f"[TOOL RESULT] {result}")
    elif isinstance(calls, list):
        for call in calls:
            execute_calls(call)


# ========================
# 9️⃣ Monitoring Loop
# ========================
def monitor_loop(interval=5):
    print("📡 Starting continuous monitoring...")
    last_id = None

    while True:
        row = get_latest_row()
        if row and (last_id is None or row[0] > last_id):
            last_id = row[0]
            _, timestamp, temp, pressure, rain = row
            print(f"\n📥 New reading @ {timestamp}: Temp={temp}°C, Pressure={pressure} bar, Rain={rain} mm")

            prompt = f"""
You are a smart IoT assistant. Based on rules, trigger actions when thresholds are crossed.

Threshold rules:
- If rainfall > 10mm → control_drain
- If pressure > 1 bar → control_pressure_valve
- If temperature > 50°C → control_cooling_system

Current reading:
Temperature={temp}, Pressure={pressure}, Rainfall={rain}

Output JSON only.
"""
            output = query_model(prompt)
            parsed_calls = parse_json_output(output)
            execute_calls(parsed_calls)

        time.sleep(interval)


# ========================
# 🔟 Interactive Query Loop
# ========================
def user_loop():
    print("💬 You can now ask me things like:")
    print("- What are the last 3 temperature readings?")
    print("- What is the average temperature over the last 10 readings?")
    print("- Schedule pump maintenance in 5 days")
    print("Type 'exit' to quit.\n")

    while True:
        user_input = input("User: ")
        if user_input.lower() in ["exit", "quit"]:
            break

        # Wrap user input into a prompt
        prompt = f"""
You are a smart assistant. You can call tools to answer the user.

Available tools:
- get_last_readings(sensor: str, n: int)
- compute_average(sensor: str, n: int)
- schedule_maintenance(equipment: str, days_from_now: int)

User: {user_input}

Output JSON only.
"""
        output = query_model(prompt)
        parsed_calls = parse_json_output(output)
        execute_calls(parsed_calls)

        if MAINTENANCE_SCHEDULE:
            print("\n[MAINTENANCE SCHEDULE]")
            for item in MAINTENANCE_SCHEDULE:
                print(item)


# ========================
# 1️⃣1️⃣ Run Both Loops
# ========================
if __name__ == "__main__":
    # Run monitoring in background thread
    monitor_thread = threading.Thread(target=monitor_loop, args=(10,), daemon=True)
    monitor_thread.start()

    # Handle interactive queries in main thread
    user_loop()
