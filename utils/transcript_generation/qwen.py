import time
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
import os

# Constants
MODEL_NAME = "Qwen/Qwen2.5-1.5B-Instruct"

def load_model_and_tokenizer(model_name: str):
    """Load the language model and tokenizer."""
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype="auto",
        device_map="auto"
    )
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    return model, tokenizer

def prepare_prompt(ocr_text: str) -> str:
    """Create a formatted question prompt for entity extraction."""
    return f"""
    Extract the following details from the given text and present them in a table format with two columns: one for 'Entity Name' and the other for 'Value'. The required details are:
    - Bank Guarantee Number
    - Issuance Date
    - Bid Document Number
    - Name of Bidder
    - Address of Registered Office of Bidder
    - Alternate Office Address of Bidder
    - Name of Package
    - Amount of Bid Security in Rupees (in Words)
    - Amount of Bid Security/Guaranteed Amount in Rupees (in Figures)
    - Validity Start Date
    - Validity End Date/Expiry Date
    - Valid for (Number of Days)
    - Name of Bank
    - Address of Issuing Branch
    - Address of Registered Head Office

    Text:

    {ocr_text}
    """

def ask_question(model, tokenizer, prompt: str) -> str:
    """Ask a question and get a response from the model as a single string."""
    # Prepare the messages
    messages = [
        {"role": "system", "content": "You are Qwen, created by Alibaba Cloud. You are a helpful assistant."},
        {"role": "user", "content": prompt}
    ]

    # Create input text from messages and tokenize
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    model_inputs = tokenizer([text], return_tensors="pt").to(model.device)

    # Generate response
    generated_ids = model.generate(
        **model_inputs,
        max_new_tokens=1024,
        return_dict_in_generate=True,
        output_scores=True
    )

    # Decode and return the generated text after input length
    input_length = model_inputs.input_ids[0].size(0)
    generated_text = tokenizer.decode(generated_ids.sequences[0][input_length:], skip_special_tokens=True)
    
    return generated_text

def save_to_file(text: str, file_path: str):
    """Save text to a file."""
    with open(file_path, 'w') as file:
        file.write(text)

def display_neatly(text: str):
    """Display text values neatly line by line."""
    values = text.strip().splitlines()
    print("Extracted Values:")
    print("-" * 50)
    for i, value in enumerate(values, start=1):
        print(f"{i}. {value}")
    print("-" * 50)

def getMetadata(id, OCR_TEXT_FILE, OUTPUT_FOLDER):
    """Main function to load OCR text, prepare the prompt, get the response, and save/display results."""
    # Load model and tokenizer
    model, tokenizer = load_model_and_tokenizer(MODEL_NAME)

    # Load OCR text and clean up
    with open(OCR_TEXT_FILE, 'r') as file:
        ocr_text = file.read().replace('\n', ' ').strip()

    # Prepare the question prompt
    question_prompt = prepare_prompt(ocr_text)

    # Get model response
    response_text = ask_question(model, tokenizer, question_prompt)

    # Save the extracted values to a file
    save_to_file(response_text, os.path.join(OUTPUT_FOLDER, f'metadata_{id}.txt'))

    # Display the extracted values neatly
    display_neatly(response_text)
