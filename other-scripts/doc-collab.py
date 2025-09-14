import outlines
from transformers import AutoModelForCausalLM, AutoTokenizer
from outlines.types import CFG

MODEL_NAME = "LiquidAI/LFM2-350M"
model = outlines.from_transformers(
    AutoModelForCausalLM.from_pretrained(MODEL_NAME, device_map="auto"),
    AutoTokenizer.from_pretrained(MODEL_NAME),
)
  
# Example grammar for “save_note(str)”
note_grammar = """
?start: "save_note(" UNESCAPED_STRING ")"
%import common.UNESCAPED_STRING
"""

PROMPT = "Create a reminder for me to look into other movies by this person."

result = model(
    PROMPT,
    CFG(note_grammar),
    max_new_tokens=64,
)

print("Result sequence:", result.sequence)
# The result.sequence should include the tool_call tokens and valid arguments via the grammar.
