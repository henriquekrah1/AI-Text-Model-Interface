import os
import tkinter as tk
from tkinter import filedialog
from llama_cpp import Llama  # Use CUDA-accelerated llama-cpp-python for GGUF models

# Ask User About GPU Usage
def ask_gpu_usage():
    """Prompts the user to choose between CPU-only or GPU acceleration."""
    while True:
        choice = input("Do you have a GPU and want to use it? (Y/N): ").strip().lower()
        if choice in ["y", "n"]:
            return choice == "y"
        print("Invalid input. Please enter 'Y' or 'N'.")

USE_GPU = ask_gpu_usage()

# Prompt User to Select Model File
def select_model_file():
    """Opens a file dialog for the user to select a .gguf model file."""
    root = tk.Tk()
    root.withdraw()  # Hide the main window
    file_path = filedialog.askopenfilename(title="Select a GGUF Model", filetypes=[("GGUF files", "*.gguf")])
    return file_path

MODEL_PATH = select_model_file()
if not MODEL_PATH:
    print("No model selected. Exiting.")
    exit()

# Load the GGUF Model
def load_model(model_path, use_gpu):
    """Loads a GGUF model using CUDA-accelerated llama-cpp-python with GPU optimization."""
    try:
        n_gpu_layers = -1 if use_gpu else 0  # Enable full GPU acceleration
        n_batch = 4096 if use_gpu else 256  # Batch size for performance tuning

        model = Llama(
            model_path,
            n_ctx=8192,  # Increase context size
            chat_format="chatml",
            n_gpu_layers=n_gpu_layers,
            n_batch=n_batch,
            f16_kv=True  # Use FP16 for better VRAM efficiency
        )
        return model
    except Exception as e:
        print(f"Error loading model: {e}")
        return None

# Initialize Model
model = load_model(MODEL_PATH, USE_GPU)

if model is None:
    print("Failed to load model. Exiting.")
    exit()

# System Prompt to Guide the Model
system_prompt = "You are a friendly, conversational AI. Keep responses casual and engaging."

# Chat Loop
def chat():
    """Runs the text-based chat interface."""
    print("\nLocal AI Chat is Ready! Type 'exit' to quit.\n")
    conversation_history = [
        {"role": "system", "content": system_prompt}  # Provide system context
    ]
    
    while True:
        user_input = input("You: ")
        if user_input.lower() == "exit":
            print("Exiting chat. Goodbye!")
            break
        
        conversation_history.append({"role": "user", "content": user_input})
        
        # Generate response
        output = model.create_chat_completion(conversation_history, max_tokens=200)
        response = output["choices"][0]["message"]["content"].strip()
        
        conversation_history.append({"role": "assistant", "content": response})
        print(f"AI: {response}\n")

# Start Chat
if __name__ == "__main__":
    chat()
