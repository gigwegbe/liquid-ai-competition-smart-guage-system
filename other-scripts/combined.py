from transformers import AutoProcessor, AutoModelForImageTextToText, AutoModelForCausalLM, AutoTokenizer
from transformers.image_utils import load_image
from PIL import Image
import torch
import re

# Load models and processor
model_id_vlm = "google/gemma-2b"
model_id_llm = "google/gemma-2b-it"

processor = AutoProcessor.from_pretrained(model_id_vlm)
model_vlm = AutoModelForImageTextToText.from_pretrained(model_id_vlm, device_map={}, torch_dtype=torch.float32)

tokenizer_llm = AutoTokenizer.from_pretrained(model_id_llm)
model_llm = AutoModelForCausalLM.from_pretrained(model_id_llm, device_map="cpu", torch_dtype=torch.float32)

# Load image
image = load_image("gauge.jpg")

# Process image and generate prompt
prompt = "What is the reading on the gauge?"
inputs = processor(text=prompt, images=image, return_tensors="pt")
vlm_outputs = model_vlm.generate(**inputs, max_new_tokens=256)
vlm_text = processor.decode(vlm_outputs[0], skip_special_tokens=True).strip()

# Check gauge reading and turn off light
gauge_value_str = re.search(r'\d+', vlm_text)
if gauge_value_str:
    gauge_value = int(gauge_value_str.group())
    print(f"Gauge reading: {gauge_value}mm")
    if gauge_value > 80:
        print("Gauge reading exceeds 80mm. Turning off the light.")
        # Add your code here to turn off the light, e.g., using an API call or GPIO pin control.
    else:
        print("Gauge reading is within the safe limit.")
else:
    print("Could not find a gauge reading in the VLM output.")

# Generate LLM output based on VLM reading
prompt = "What is the reading? " + vlm_text
input_ids = tokenizer_llm.apply_chat_template(
    [{"role": "user", "content": prompt}],
    add_generation_prompt=True,
    return_tensors="pt",
    tokenize=True,
).to(model_llm.device)

output = model_llm.generate(
    input_ids,
    do_sample=True,
    temperature=0.3,
    min_p=0.15,
    repetition_penalty=1.05,
    max_new_tokens=512,
)

print(tokenizer_llm.decode(output[0], skip_special_tokens=False))