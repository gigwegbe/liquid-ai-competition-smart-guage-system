from transformers import AutoProcessor, AutoModelForImageTextToText,AutoModelForCausalLM,AutoTokenizer
from transformers.image_utils import load_image
from transformers import AutoTokenizer
from PIL import Image
import torch
import json




# Load model and processor
model_id_vlm = "LiquidAI/LFM2-VL-450M"
model_vlm = AutoModelForImageTextToText.from_pretrained(
    model_id_vlm,
    device_map={"": "cpu"},  # force CPU
    torch_dtype="float32",   # safer on CPU
    trust_remote_code=True
)
processor_vlm = AutoProcessor.from_pretrained(model_id_vlm, trust_remote_code=True)

# ===== LOAD TEST IMAGE =====
# image_path = "./detected/003843_detections.jpg"
image_path = "/Users/george/Downloads/merged_gauges_csv/merged_0175_caliper_5.93mm_temperature_15.0C_pressure_0.36bar.jpg"
image = Image.open(image_path)
if image.mode != "RGB":
    image = image.convert("RGB")

# image = image.resize((256, 256), Image.LANCZOS)
# image = image.resize((512, 512), Image.LANCZOS)
# image = image.resize((384, 680), Image.LANCZOS)
# image = image.resize((1000, 3000), Image.LANCZOS)


# Load model and processor
model_id_llm = "LiquidAI/LFM2-350M"
model_llm = AutoModelForCausalLM.from_pretrained(
    model_id_llm,
    device_map="auto",
    torch_dtype="bfloat16",
    trust_remote_code=True
)
tokenizer_vlm = AutoTokenizer.from_pretrained(model_id_llm)

conversation = [
    {
        "role": "user",
        "content": [
            {"type": "image", "image": image},
            {
                "type": "text",
                "text": """TASK: Extract numeric readings from three digital gauges in this image.

GAUGE IDENTIFICATION (left to right):
- LEFT gauge (black/dark): rain_gauge (units: mm)
- MIDDLE gauge (white with blue header): thermometer (units: °C) 
- RIGHT gauge (white/red circular): pressure_gauge (units: bar)

READING INSTRUCTIONS:
1. Focus ONLY on the main numeric display on each gauge's LCD/LED screen
2. Read the complete number including decimal points if present
3. Ignore any secondary displays, unit labels, or interface elements
4. If a gauge shows multiple numbers, use the largest/primary display

OUTPUT FORMAT:
- Return ONLY valid JSON with no additional text, markdown, or formatting
- Use null for unreadable or missing gauges
- Round to maximum 2 decimal places
- Use integers when the value is a whole number

REQUIRED JSON STRUCTURE:
{
  "rain_gauge": <number|null>,
  "thermometer": <number|null>, 
  "pressure_gauge": <number|null>
}

Analyze the image now and return the JSON response."""
            },
        ],
    },
]



# Generate Answer
inputs = processor_vlm.apply_chat_template(
    conversation,
    add_generation_prompt=True,
    return_tensors="pt",
    return_dict=True,
    tokenize=True,
).to(model_vlm.device)


outputs = model_vlm.generate(**inputs, max_new_tokens=512)
decoded = processor_vlm.batch_decode(outputs, skip_special_tokens=True)[0]

# Extract only the assistant's reply
if "assistant" in decoded:
    response = decoded.split("assistant", 1)[1].strip()
else:
    response = decoded.strip()

print("\n--- Model Response ---")
print(response)