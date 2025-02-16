import sys
import os
import tkinter as tk
from tkinter import filedialog
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QTextEdit, QLabel, QMessageBox, QStackedWidget, QHBoxLayout
from PyQt6.QtCore import Qt
from llama_cpp import Llama

# Function to load the QSS file
def load_stylesheet(qss_file):
    with open(qss_file, "r") as file:
        return file.read()

class GPUSelectionScreen(QWidget):
    def __init__(self, switch_to_chat):
        super().__init__()
        self.switch_to_chat = switch_to_chat
        
        self.setWindowTitle("Select Processing Mode")
        self.setGeometry(200, 200, 800, 600)  # Adjusted window size
        
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.label = QLabel("Use GPU acceleration?", self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label)
        
        button_layout = QHBoxLayout()
        
        self.gpu_button_yes = QPushButton("Yes (GPU)", self)
        self.gpu_button_yes.clicked.connect(lambda: self.select_mode(True))
        button_layout.addWidget(self.gpu_button_yes)
        
        self.gpu_button_no = QPushButton("No (CPU)", self)
        self.gpu_button_no.clicked.connect(lambda: self.select_mode(False))
        button_layout.addWidget(self.gpu_button_no)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def select_mode(self, use_gpu):
        self.switch_to_chat(use_gpu)

class AIChatGUI(QWidget):
    def __init__(self, use_gpu):
        super().__init__()
        self.USE_GPU = use_gpu
        
        self.setWindowTitle("Local AI Chat")
        self.setGeometry(200, 200, 800, 600)  # Adjusted window size

        # Layout
        layout = QVBoxLayout()

        # Model Selection
        self.model_label = QLabel("No model selected.", self)
        self.model_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.model_label)

        self.select_model_button = QPushButton("Select Model File", self)
        self.select_model_button.clicked.connect(self.select_model_file)
        layout.addWidget(self.select_model_button)

        # Chat Display
        self.chat_display = QTextEdit(self)
        self.chat_display.setReadOnly(True)
        layout.addWidget(self.chat_display)

        # User Input
        self.user_input = QTextEdit(self)
        self.user_input.setPlaceholderText("Type your message...")
        layout.addWidget(self.user_input)

        # Send Button
        self.send_button = QPushButton("Send", self)
        self.send_button.clicked.connect(self.send_message)
        layout.addWidget(self.send_button)

        self.setLayout(layout)
        
        # Internal Variables
        self.MODEL_PATH = None
        self.model = None
        self.conversation_history = [
            {"role": "system", "content": "You are a friendly, conversational AI. Keep responses casual and engaging."}
        ]

    def select_model_file(self):
        """Opens a file dialog for model selection."""
        root = tk.Tk()
        root.withdraw()
        file_path = filedialog.askopenfilename(title="Select a GGUF Model", filetypes=[("GGUF files", "*.gguf")])
        
        if file_path:
            if self.model:
                # Ask user if they want to keep chat history
                reply = QMessageBox.question(
                    self, "Model Change", "Do you want to continue the current chat with the new model?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                
                if reply == QMessageBox.StandardButton.No:
                    self.conversation_history = [
                        {"role": "system", "content": "You are a friendly, conversational AI. Keep responses casual and engaging."}
                    ]
                    self.chat_display.clear()

            self.MODEL_PATH = file_path
            self.model_label.setText(f"Model: {os.path.basename(file_path)}")
            self.load_model()

    def load_model(self):
        """Loads the selected model with GPU or CPU settings."""
        try:
            if self.MODEL_PATH is None:
                QMessageBox.warning(self, "Warning", "Please select a model file first!")
                return
            
            n_gpu_layers = -1 if self.USE_GPU else 0  # Maximum GPU offload if available
            n_batch = 2048 if self.USE_GPU else 512  # Adjust batch size for performance
            
            self.model = Llama(self.MODEL_PATH, n_ctx=8192, chat_format="chatml", n_gpu_layers=n_gpu_layers, n_batch=n_batch, f16_kv=True)
            self.chat_display.append("Model Loaded! Ready to chat. 🔥\n")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load model:\n{e}")

    def send_message(self):
        """Handles user input and gets a response from the model."""
        if not self.model:
            QMessageBox.warning(self, "Warning", "No model loaded! Please select a model first.")
            return
        
        user_text = self.user_input.toPlainText().strip()
        if not user_text:
            return
        
        self.chat_display.append(f"You: {user_text}")
        self.conversation_history.append({"role": "user", "content": user_text})
        
        # Generate response
        try:
            output = self.model.create_chat_completion(self.conversation_history, max_tokens=200)
            response = output["choices"][0]["message"]["content"].strip()
            self.conversation_history.append({"role": "assistant", "content": response})
            self.chat_display.append(f"AI: {response}\n")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error generating response:\n{e}")

        self.user_input.clear()

class MainApp(QStackedWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Chat Application")
        self.setGeometry(200, 200, 800, 600)  # Adjusted window size
        
        self.gpu_screen = GPUSelectionScreen(self.switch_to_chat)
        self.chat_screen = None
        
        self.addWidget(self.gpu_screen)
        self.setCurrentWidget(self.gpu_screen)
    
    def switch_to_chat(self, use_gpu):
        self.chat_screen = AIChatGUI(use_gpu)
        self.addWidget(self.chat_screen)
        self.setCurrentWidget(self.chat_screen)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(load_stylesheet("dark_theme.qss"))  # Load theme after app is created
    window = MainApp()
    window.show()
    sys.exit(app.exec())
