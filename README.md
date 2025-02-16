# Local AI Chat

AIText-Model Interface is a lightweight, offline AI chat application that allows users to run GGUF-based LLaMA models locally. It supports **GPU acceleration** for improved performance and provides a modern, dark-themed user interface. Users can **switch models dynamically while retaining chat history**.

---

## Features
- **Run GGUF-based AI models locally** (no internet required)
- **Choose between CPU or GPU acceleration**
- **Dynamically switch models** without losing chat history
- **Modern dark-themed interface**
- **Simple setup with automated installation**

---

## Installation and Setup

### 1. **Automatic Installation**
The easiest way to install and run the application is through the provided batch script:

1. Download the repository and extract the files.
2. Run **`start_chat.bat`** (it will automatically install dependencies and launch the application).
3. Follow the on-screen instructions to select CPU/GPU and load a model.

### 2. **Manual Installation**
If you prefer to install manually, follow these steps:

1. Ensure you have **Python 3.12 or higher** installed.
2. Open a terminal in the project directory.
3. Create and activate a virtual environment:
   ```sh
   python -m venv venv
   venv\Scripts\activate   # Windows
   source venv/bin/activate  # Linux/Mac
4. Install dependencies:
	pip install -r requirements.txt

5. Run the application:
	python ai_chat_ui.py


Usage Instructions:

Choose Processing Mode
        On launch, select whether to use CPU or GPU acceleration.
        If using a GPU, ensure you have CUDA installed.

 Load an AI Model
        Select a GGUF model file when prompted.
        You can obtain GGUF models from sources like TheBloke's Hugging Face page.

 Chat with AI
        Enter your message in the chat box.
        Click Send to receive a response.
        To switch models, click Select Model File (you can keep or reset chat history).


Troubleshooting
Application Fails to Launch

 Ensure Python 3.12+ is installed.
    Run:

	pip install -r requirements.txt

If using a virtual environment, activate it first:

    venv\Scripts\activate   # Windows
    source venv/bin/activate  # Linux/Mac

Model Fails to Load:

-Make sure the selected model is a valid GGUF file.
-Adjust n_ctx and n_batch values in ai_chat_ui.py if memory issues occur:

	n_ctx = 4096  # Increase or decrease based on available RAM
	n_batch = 2048  # Reduce if using CPU to avoid memory overload

For GPU users, set:

	n_gpu_layers = -1  # Enables full GPU offload

For CPU users, try reducing:

    n_batch = 512  # Lower batch size for better stability

Contributing

This project is open-source, and contributions are welcome! Feel free to submit issues, pull requests, or suggestions to improve the application.
License

This project is released under the MIT License. You are free to use, modify, and distribute it with attribution.
Credits

Developed by Henrique with a focus on local AI model execution and an intuitive user experience.

