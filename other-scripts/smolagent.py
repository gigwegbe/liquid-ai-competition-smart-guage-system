from smolagents import TransformersModel
from smolagents import CodeAgent


model = TransformersModel(
    model_id="LiquidAI/LFM2-350M",
    max_new_tokens=4096,
    device_map="auto"
)

# Create an agent with no tools
agent = CodeAgent(tools=[], model=model)

# Run the agent with a task
result = agent.run("What is 3 + 2?")
print(result)