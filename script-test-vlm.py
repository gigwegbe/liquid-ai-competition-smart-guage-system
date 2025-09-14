from transformers import AutoProcessor, AutoModelForImageTextToText, AutoModelForCausalLM, AutoTokenizer
from transformers.image_utils import load_image
from PIL import Image
import torch

# device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")

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
image_path = "data/dg.png"
image = Image.open(image_path)
if image.mode != "RGB":
    image = image.convert("RGB")



# Load model and processor
model_id_llm = "LiquidAI/LFM2-350M"
model_llm = AutoModelForCausalLM.from_pretrained(
    model_id_llm,
    device_map="auto",
    torch_dtype="bfloat16",
    trust_remote_code=True
)
tokenizer = AutoTokenizer.from_pretrained(model_id_llm)

conversation = [
    {
        "role": "user",
        "content": [
            {"type": "image", "image": image},
            {
                "type": "text",
                "text": """You are an expert gauge inspector. Carefully analyze the image of the gauge and do the following:
1. Identify the type of gauge (e.g., thermometer, pressure gauge, etc.).
2. Provide the current meter reading shown by the needle.
3. State the unit of measurement.
4. Present the final reading clearly in the format: "<value> <unit>".
Only provide the direct reading, no extra explanation."""
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