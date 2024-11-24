from transformers import AutoModelForCausalLM
from qwen_vl_utils import process_vision_info

print("started...")
# default: Load the model on the available device(s)
model = AutoModelForCausalLM.from_pretrained(
        "Qwen/Qwen2.5-1.5B-Instruct",
        torch_dtype="auto",
        device_map="auto"
    )

print("Model added")