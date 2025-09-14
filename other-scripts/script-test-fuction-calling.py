# # from transformers import AutoTokenizer
# # tok = AutoTokenizer.from_pretrained("LiquidAI/LFM2-350M")
# # print(tok.__class__)
# # print(tok.decoder)  # or tok._tokenizer.decoder or tok.backend_tokenizer


# # import outlines
# # from transformers import AutoModelForCausalLM, AutoTokenizer
# # from outlines.types import CFG

# # MODEL_NAME = "LiquidAI/LFM2-350M"
# # model = outlines.from_transformers(
# #     AutoModelForCausalLM.from_pretrained(MODEL_NAME, device_map="auto"),
# #     AutoTokenizer.from_pretrained(MODEL_NAME)
# # )

# # GRAMMAR = '''
# # ?start: command
# # ?command: set_mode "(" mode ")"
# # mode: "night_mode" | "day_mode" | "cinema_mode"
# # '''

# # PROMPT = "It's movie time! Set the projector to what mode?"

# # result = model(
# #     PROMPT,
# #     CFG(GRAMMAR),
# #     max_new_tokens=64
# # )

# # print(result)







# # import outlines
# # from transformers import AutoModelForCausalLM, AutoTokenizer
# # from outlines.types import CFG
# # import llguidance

# # MODEL_NAME = "LiquidAI/LFM2-350M"

# # # Load tokenizer and model
# # tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
# # model_hf = AutoModelForCausalLM.from_pretrained(MODEL_NAME, device_map="auto")

# # # Define a custom byte_decoder
# # # Depending on your tokenizer's internal ByteLevel decoder settings, you may need to replicate or wrap them.
# # # Here’s a sketch:

# # class CustomByteDecoder:
# #     def __init__(self, tokenizer):
# #         self.tokenizer = tokenizer
    
# #     def decode(self, token_ids, skip_special_tokens=True):
# #         # Use the tokenizer's decode; adapt if you need to remove prefix spaces or regex features
# #         return self.tokenizer.decode(token_ids, skip_special_tokens=skip_special_tokens)

# #     def __call__(self, token_ids, **kwargs):
# #         return self.decode(token_ids, **kwargs)

# # # Attach the custom byte decoder to the tokenizer in a way llguidance.hf.from_tokenizer can pick up
# # # This part depends on the API of llguidance.hf

# # # For example, create a wrapper or monkey‐patch
# # tokenizer._byte_decoder = CustomByteDecoder(tokenizer)  # or another attribute that llguidance expects

# # # Then call from_tokenizer with this
# # llg_tokenizer = llguidance.hf.from_tokenizer(
# #     tokenizer,
# #     byte_decoder=getattr(tokenizer, "_byte_decoder", None)
# # )

# # # Now wrap with outlines
# # model = outlines.from_transformers(model_hf, tokenizer)

# # GRAMMAR = r'''
# # ?start: command
# # ?command: "set_mode(" mode ")"
# # mode: "night_mode" | "day_mode" | "cinema_mode"
# # '''

# # PROMPT = "It's movie time! Set the projector to what mode?"

# # # Use CFG
# # result = model(
# #     PROMPT,
# #     CFG(GRAMMAR),
# #     max_new_tokens=64
# # )

# # print(result)








# import outlines
# from transformers import AutoModelForCausalLM, AutoTokenizer
# from outlines.types import CFG

# # --- Load the model and tokenizer ---
# MODEL_NAME = "LiquidAI/LFM2-350M"
# model = outlines.from_transformers(
#     AutoModelForCausalLM.from_pretrained(MODEL_NAME, device_map="auto"),
#     AutoTokenizer.from_pretrained(MODEL_NAME)
# )

# # --- Define the grammar for the function call ---
# GRAMMAR = '''
# ?start: command
# ?command: set_mode "(" mode ")"
# mode: "night_mode" | "day_mode" | "cinema_mode"
# '''

# # --- Define the prompt ---
# PROMPT = "It's movie time! Set the projector to "

# # --- Generate the response with the grammar constraint ---
# # Fix: The CFG object must be passed as a keyword argument (cfg=...).
# result = model(
#     PROMPT,
#     cfg=CFG(GRAMMAR),
#     max_new_tokens=64
# )

# # --- Print the result ---
# print(result)



# import outlines
# from transformers import AutoModelForCausalLM, AutoTokenizer
# from outlines.types import CFG

# MODEL_NAME = "LiquidAI/LFM2-350M"

# # Load model & tokenizer
# model = outlines.from_transformers(
#     AutoModelForCausalLM.from_pretrained(MODEL_NAME, device_map="auto"),
#     AutoTokenizer.from_pretrained(MODEL_NAME)
# )

# # Define the grammar
# GRAMMAR = '''
# ?start: command
# ?command: set_mode "(" mode ")"
# mode: "night_mode" | "day_mode" | "cinema_mode"
# '''

# PROMPT = "It's movie time! Set the projector to "

# # ✅ Call the outlines model with CFG
# result = model(PROMPT, cfg=CFG(GRAMMAR), max_new_tokens=64)

# print(result)


import outlines
from transformers import AutoModelForCausalLM, AutoTokenizer
from outlines.types import CFG

MODEL_NAME = "LiquidAI/LFM2-350M"

# ✅ Wrap the HF model in outlines
hf_model = AutoModelForCausalLM.from_pretrained(MODEL_NAME, device_map="auto")
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = outlines.from_transformers(hf_model, tokenizer)  # <-- MUST wrap here

# Define CFG grammar
GRAMMAR = '''
?start: command
?command: set_mode "(" mode ")"
mode: "night_mode" | "day_mode" | "cinema_mode"
'''

PROMPT = "It's movie time! Set the projector to "

# ✅ Use outlines wrapper with CFG
result = model(PROMPT, cfg=CFG(GRAMMAR), max_new_tokens=64)
print(result)
