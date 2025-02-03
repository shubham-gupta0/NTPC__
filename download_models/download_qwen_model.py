from transformers import AutoModelForCausalLM
from qwen_vl_utils import process_vision_info

print("started...")
# default: Load the model on the available device(s)
model = AutoModelForCausalLM.from_pretrained(
        "distributed/optimized-gpt2-2b",
        torch_dtype="auto",
        device_map="auto",
        trust_remote_code=True
    )

print("Model added")