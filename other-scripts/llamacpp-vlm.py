from PIL import Image
from llama_cpp import Llama
import tempfile
import os

# Path to your vision-enabled GGUF model (LLaVA/LFM2-VL style converted to .gguf)
MODEL_PATH = "./models/lfm2-vl-450m.gguf"

# Load model (CPU-only here; set n_gpu_layers=-1 if you compiled with CUDA and want GPU)
llm = Llama(
    model_path=MODEL_PATH,
    n_ctx=2048,
    n_threads=8,
    n_gpu_layers=0,   # 0 => CPU-only. Use -1 to enable GPU layers if compiled with CUDA.
)

# Image path
image_path = "data/dg.png"

# Ensure we pass an RGB file (llama-cpp expects image files on disk)
tmp_path = image_path
img = Image.open(image_path)
if img.mode != "RGB":
    tmpf = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    img.convert("RGB").save(tmpf.name)
    tmp_path = tmpf.name

# Instruction (same as your original)
prompt_text = (
    "You are an expert gauge inspector. Carefully analyze the image of the gauge and do the following:\n"
    "1. Identify the type of gauge (e.g., thermometer, pressure gauge, etc.).\n"
    "2. Provide the current meter reading shown by the needle.\n"
    "3. State the unit of measurement.\n"
    '4. Present the final reading clearly in the format: "<value> <unit>".\n'
    "Only provide the direct reading, no extra explanation."
)

# Make a chat-style request including the image
resp = llm.create_chat_completion(
    messages=[
        {
            "role": "user",
            "content": prompt_text,
            "images": [tmp_path],  # pass path(s) to image files
        }
    ],
    temperature=0.0,     # deterministic for exact readings; change if you want more creativity
    max_tokens=512,
    top_p=0.85,          # maps loosely to HF's min_p=0.15
    repeat_penalty=1.05,
)

# Print assistant reply
print(resp["choices"][0]["message"]["content"].strip())

# cleanup temp file if created
if tmp_path != image_path:
    os.remove(tmp_path)
