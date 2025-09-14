from llama_cpp import Llama

# Load the model (must be in GGUF format)
llm = Llama(
    model_path="./models/LFM2-350M-Q5_K_M.gguf",  # Path to your quantized model
    n_ctx=2048,
    n_threads=8,
    n_gpu_layers=0,  # -1 if you compiled with GPU, 0 = CPU only
)

# Prompt
prompt = "What is C. elegans?"

# Generate text
output = llm(
    prompt=prompt,
    max_tokens=512,
    temperature=0.3,
    repeat_penalty=1.05,
    top_p=0.85,   # maps roughly to min_p=0.15 in HF
)

print(output["choices"][0]["text"])
