from transformers import AutoModelForCausalLM
from qwen_vl_utils import process_vision_info

print("started...")
# default: Load the model on the available device(s)
model = AutoModelForCausalLM.from_pretrained(
        "microsoft/Phi-3.5-mini-instruct",
        torch_dtype="auto",
        device_map="auto"
    )

print("Model added")