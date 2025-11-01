import sys
import os
import json
import uuid
import datetime
import tkinter as tk
from tkinter import filedialog
import html
import subprocess
import platform

from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QPushButton,
    QTextEdit,
    QLabel,
    QMessageBox,
    QStackedWidget,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QMenu,
    QStyledItemDelegate
)
from PyQt6.QtCore import Qt, QSize, QPropertyAnimation, QEasingCurve, QThread, pyqtSignal, QTimer, QPoint, QRect
from PyQt6.QtGui import QCursor, QPainter, QPen, QColor
from llama_cpp import Llama


CHAT_DIR = "chats"
SYSTEM_PROMPT = "You are a friendly, conversational AI. Keep responses casual and engaging."


def load_stylesheet(qss_file):
    with open(qss_file, "r") as file:
        return file.read()


class ChatManager:
    def __init__(self, chat_dir=CHAT_DIR):
        self.chat_dir = chat_dir
        os.makedirs(self.chat_dir, exist_ok=True)

    def _chat_path(self, chat_id: str) -> str:
        return os.path.join(self.chat_dir, f"{chat_id}.json")

    def list_chats(self):
        chats = []
        for fname in os.listdir(self.chat_dir):
            if not fname.endswith(".json"):
                continue
            fpath = os.path.join(self.chat_dir, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                chats.append(data)
            except Exception:
                continue
        chats.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return chats

    def create_new_chat(self, save: bool = False):
        chat_id = str(uuid.uuid4())
        data = {
            "id": chat_id,
            "title": "New chat",
            "created_at": datetime.datetime.utcnow().isoformat(),
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT}
            ]
        }
        if save:
            self.save_chat(data)
        return data

    def save_chat(self, chat_data: dict):
        chat_id = chat_data["id"]
        with open(self._chat_path(chat_id), "w", encoding="utf-8") as f:
            json.dump(chat_data, f, ensure_ascii=False, indent=2)

    def load_chat(self, chat_id: str):
        with open(self._chat_path(chat_id), "r", encoding="utf-8") as f:
            return json.load(f)
    
    def delete_chat(self, chat_id: str):
        """Delete a chat file"""
        try:
            os.remove(self._chat_path(chat_id))
            return True
        except Exception as e:
            print(f"Error deleting chat: {e}")
            return False
    
    def open_chat_location(self, chat_id: str):
        """Open file explorer to the chat's directory"""
        file_path = self._chat_path(chat_id)
        folder_path = os.path.dirname(os.path.abspath(file_path))
        
        try:
            system = platform.system()
            if system == "Windows":
                subprocess.run(["explorer", "/select,", os.path.abspath(file_path)])
            elif system == "Darwin":  # macOS
                subprocess.run(["open", "-R", file_path])
            else:  # Linux
                subprocess.run(["xdg-open", folder_path])
        except Exception as e:
            print(f"Error opening file location: {e}")


# Custom delegate to draw three dots on hover
class ChatItemDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.hovered_index = None
        self.dots_rect = QRect()
    
    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        
        # Draw three dots if this item is hovered
        if self.hovered_index == index:
            # Position dots on the right side
            dots_x = option.rect.right() - 30
            dots_y = option.rect.center().y()
            
            # Store rect for click detection
            self.dots_rect = QRect(dots_x - 5, option.rect.top(), 30, option.rect.height())
            
            painter.save()
            painter.setPen(QPen(QColor(180, 180, 180), 2))
            
            # Draw three dots
            for i in range(3):
                y_offset = (i - 1) * 6
                painter.drawEllipse(dots_x, dots_y + y_offset - 2, 4, 4)
            
            painter.restore()


# Custom list widget with hover detection
class ChatListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.parent_gui = None
        
        # Set custom delegate
        self.delegate = ChatItemDelegate(self)
        self.setItemDelegate(self.delegate)
        
    def mouseMoveEvent(self, event):
        item = self.itemAt(event.pos())
        index = self.indexAt(event.pos())
        
        # Update hovered index in delegate
        if item:
            self.delegate.hovered_index = index
            # Change cursor to pointer when over dots area
            if self.is_over_dots(event.pos(), index):
                self.setCursor(Qt.CursorShape.PointingHandCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)
        else:
            self.delegate.hovered_index = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
        
        self.viewport().update()
        super().mouseMoveEvent(event)
    
    def leaveEvent(self, event):
        self.delegate.hovered_index = None
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.viewport().update()
        super().leaveEvent(event)
    
    def is_over_dots(self, pos, index):
        """Check if mouse is over the three dots area (with expanded clickable area)"""
        rect = self.visualRect(index)
        # Expanded clickable area: 50px wide instead of 30px
        dots_x = rect.right() - 50
        dots_rect = QRect(dots_x, rect.top(), 50, rect.height())
        return dots_rect.contains(pos)
    
    def mousePressEvent(self, event):
        item = self.itemAt(event.pos())
        index = self.indexAt(event.pos())
        
        if item and self.is_over_dots(event.pos(), index):
            # Clicked on dots - show menu
            if self.parent_gui:
                self.parent_gui.show_chat_options(item, event.globalPosition().toPoint())
            event.accept()
        else:
            # Normal click - select item
            super().mousePressEvent(event)


class AIWorkerThread(QThread):
    """Background thread for AI model inference"""
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    
    def __init__(self, model, messages):
        super().__init__()
        self.model = model
        self.messages = messages
    
    def run(self):
        try:
            output = self.model.create_chat_completion(
                self.messages,
                max_tokens=200
            )
            response = output["choices"][0]["message"]["content"].strip()
            self.finished.emit(response)
        except Exception as e:
            self.error.emit(str(e))


class GPUSelectionScreen(QWidget):
    def __init__(self, switch_to_chat):
        super().__init__()
        self.switch_to_chat = switch_to_chat

        self.setWindowTitle("Select Processing Mode")
        self.setGeometry(200, 200, 800, 600)

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


class ChatInputBox(QTextEdit):
    """Custom QTextEdit that sends on Enter, newlines on Shift+Enter."""
    def __init__(self, parent=None):
        super().__init__(parent)

    def _find_sender(self):
        w = self.parent()
        while w is not None and not hasattr(w, "send_message"):
            w = w.parent()
        return w

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() == Qt.KeyboardModifier.ShiftModifier:
                super().keyPressEvent(event)
            else:
                sender = self._find_sender()
                if sender is not None:
                    sender.send_message()
                else:
                    super().keyPressEvent(event)
        else:
            super().keyPressEvent(event)


class AIChatGUI(QWidget):
    def __init__(self, use_gpu):
        super().__init__()
        self.USE_GPU = use_gpu

        self.setWindowTitle("Local AI Chat")
        self.setGeometry(200, 200, 1000, 650)

        self.chat_manager = ChatManager()
        self.current_chat = None
        
        self.worker_thread = None
        self.is_generating = False
        
        self.typing_timer = QTimer()
        self.typing_timer.timeout.connect(self.update_typing_indicator)
        self.typing_dots = 0

        self.splitter = QSplitter(Qt.Orientation.Horizontal, self)

        # ===== SIDEBAR =====
        self.sidebar_widget = QWidget()
        sidebar_layout = QVBoxLayout()
        self.sidebar_widget.setLayout(sidebar_layout)

        self.sidebar_label = QLabel("Chats")
        self.sidebar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sidebar_layout.addWidget(self.sidebar_label)

        # Use custom list widget
        self.chat_list = ChatListWidget()
        self.chat_list.parent_gui = self
        self.chat_list.itemClicked.connect(self.on_chat_selected)
        self.chat_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.chat_list.setTextElideMode(Qt.TextElideMode.ElideRight)

        self.chat_list.setStyleSheet("""
            QListWidget::item {
                padding: 8px;
                border-radius: 4px;
            }
            QListWidget::item:hover {
                background-color: rgba(255, 255, 255, 0.1);
            }
            QListWidget::item:selected {
                background-color: #2a5adf;
                color: white;
            }
            QListWidget::item:selected:!active {
                background-color: #2a5adf;
                color: white;
            }
        """)
        sidebar_layout.addWidget(self.chat_list)

        self.new_chat_btn = QPushButton("➕ New chat")
        self.new_chat_btn.clicked.connect(self.create_new_chat)
        sidebar_layout.addWidget(self.new_chat_btn)

        self.splitter.addWidget(self.sidebar_widget)

        # ===== MAIN AREA =====
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        main_widget.setLayout(main_layout)

        top_bar = QHBoxLayout()
        self.toggle_sidebar_btn = QPushButton("☰")
        self.toggle_sidebar_btn.setFixedWidth(40)
        self.toggle_sidebar_btn.clicked.connect(self.toggle_sidebar)
        top_bar.addWidget(self.toggle_sidebar_btn)

        self.model_label = QLabel("No model selected.", self)
        self.model_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top_bar.addWidget(self.model_label, stretch=1)

        self.select_model_button = QPushButton("Select Model File", self)
        self.select_model_button.clicked.connect(self.select_model_file)
        top_bar.addWidget(self.select_model_button)

        main_layout.addLayout(top_bar)

        self.chat_display = QTextEdit(self)
        self.chat_display.setReadOnly(True)
        main_layout.addWidget(self.chat_display)

        self.user_input = ChatInputBox(self)
        self.user_input.setPlaceholderText("Type your message.")
        self.user_input.setFixedHeight(100)
        main_layout.addWidget(self.user_input)

        self.send_button = QPushButton("Send", self)
        self.send_button.clicked.connect(self.send_message)
        main_layout.addWidget(self.send_button)

        self.splitter.addWidget(main_widget)
        self.splitter.setSizes([220, 780])

        root_layout = QHBoxLayout()
        root_layout.addWidget(self.splitter)
        self.setLayout(root_layout)

        self.MODEL_PATH = None
        self.model = None

        self.sidebar_expanded = True
        self.sidebar_width_expanded = 220
        self.sidebar_width_collapsed = 0
        self.sidebar_widget.setMaximumWidth(self.sidebar_width_expanded)

        self.refresh_chat_list()

    def show_chat_options(self, item: QListWidgetItem, global_pos: QPoint):
        """Show options menu for a chat item"""
        try:
            chat_id = item.data(Qt.ItemDataRole.UserRole)
            
            menu = QMenu(self)

            # File location option
            file_location_action = menu.addAction("📁 File Location")
            file_location_action.triggered.connect(lambda: self.chat_manager.open_chat_location(chat_id))
            
            # Delete option
            delete_action = menu.addAction("🗑️ Delete Chat")
            delete_action.triggered.connect(lambda: self.delete_chat_confirm(chat_id))
            
            
            
            # Custom styling for menu
            menu.setStyleSheet("""
                QMenu {
                    background-color: #2a2a2a;
                    border: 1px solid #444;
                    padding: 5px;
                }
                QMenu::item {
                    padding: 8px 25px;
                    background-color: transparent;
                }
                QMenu::item:selected {
                    background-color: rgba(255, 255, 255, 0.1);
                }
            """)
            
            menu.exec(global_pos)
        except Exception as e:
            print(f"Error showing menu: {e}")
    
    def delete_chat_confirm(self, chat_id: str):
        """Show confirmation dialog before deleting chat"""
        try:
            reply = QMessageBox.question(
                self,
                "Delete Chat",
                "Are you sure you want to delete this chat? This action cannot be undone.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                success = self.chat_manager.delete_chat(chat_id)
                
                if success:
                    if self.current_chat and self.current_chat["id"] == chat_id:
                        self.current_chat = None
                        self.chat_display.clear()
                    
                    self.refresh_chat_list()
                    QMessageBox.information(self, "Success", "Chat deleted successfully.")
                else:
                    QMessageBox.critical(self, "Error", "Failed to delete chat.")
        except Exception as e:
            print(f"Error in delete confirmation: {e}")
            QMessageBox.critical(self, "Error", f"An error occurred: {e}")

    def show_typing_indicator(self):
        """Display animated typing indicator"""
        self.typing_dots = 0
        self.typing_indicator_visible = True
        
        cursor = self.chat_display.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.chat_display.setTextCursor(cursor)
        
        typing_html = self.format_message("assistant", "...", None)
        self.chat_display.append(typing_html)
        self.chat_display.append("")
        
        self.typing_timer.start(400)
    
    def update_typing_indicator(self):
        """Animate the typing dots"""
        if not self.typing_indicator_visible:
            return
            
        self.typing_dots = (self.typing_dots % 3) + 1
        dots = "." * self.typing_dots
        
        full_text = self.chat_display.toPlainText()
        lines = full_text.split('\n')
        
        for i in range(len(lines) - 1, -1, -1):
            line = lines[i].strip()
            if line in [".", "..", "..."]:
                lines[i] = dots
                break
        
        scrollbar = self.chat_display.verticalScrollBar()
        at_bottom = scrollbar.value() >= scrollbar.maximum() - 10
        
        self.chat_display.clear()
        if self.current_chat:
            messages = self.current_chat.get("messages", [])
            for msg in messages:
                role = msg.get("role", "")
                content = msg.get("content", "")
                created_at = msg.get("created_at")
                html_block = self.format_message(role, content, created_at)
                self.chat_display.append(html_block)
        
        typing_html = self.format_message("assistant", dots, None)
        self.chat_display.append(typing_html)
        
        if at_bottom:
            scrollbar.setValue(scrollbar.maximum())
    
    def remove_typing_indicator(self):
        """Remove typing indicator from display"""
        self.typing_timer.stop()
        self.typing_indicator_visible = False
        
        self.chat_display.clear()
        if self.current_chat:
            messages = self.current_chat.get("messages", [])
            for msg in messages:
                role = msg.get("role", "")
                content = msg.get("content", "")
                created_at = msg.get("created_at")
                html_block = self.format_message(role, content, created_at)
                self.chat_display.append(html_block)

    def format_message(self, role: str, content: str, created_at: str | None = None) -> str:
        safe_content = html.escape(content).replace("\n", "<br>")
        ts = None
        if created_at:
            try:
                dt = datetime.datetime.fromisoformat(created_at.replace("Z", ""))
                ts = dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                ts = created_at

        meta_html = ""
        if ts:
            meta_html = f'<div style="font-size:0.5px; color:#202d4f; margin-bottom:0.5px;">{ts} — {role.capitalize()}</div>'

        if role == "user":
            return f"""
            <div style="margin:6px 0;">
                {meta_html}
                <div style="
                    background: rgba(42, 90, 223, 0.25);
                    color:white;
                    padding:7px 10px;
                    border-radius:8px;
                    display:inline-block;
                    max-width:95%;
                    ">
                    <b style="color:#dbe6ff;">You</b><br>{safe_content}
                </div>
            </div>
            """
        elif role == "assistant":
            return f"""
            <div style="margin:6px 0;">
                {meta_html}
                <div style="
                    background: rgba(255, 255, 255, 0.04);
                    color:#eee;
                    padding:7px 10px;
                    border-radius:8px;
                    display:inline-block;
                    max-width:95%;
                    ">
                    <b style="color:#7fb3ff;">AI</b><br>{safe_content}
                </div>
            </div>
            """
        elif role == "separator":
            return "<div style='margin:4px 0;'></div>"
        else:
            return f"""
            <div style="margin:6px 0;">
                <div style="color:#aaa; font-style:italic; font-size:11px;">
                    [system] {safe_content}
                </div>
            </div>
            """

    def toggle_sidebar(self):
        was_expanded = self.sidebar_expanded
        target_expanded = not was_expanded

        if was_expanded:
            start_w = self.sidebar_widget.width()
            end_w = self.sidebar_width_collapsed
        else:
            start_w = self.sidebar_widget.width()
            end_w = self.sidebar_width_expanded

        anim = QPropertyAnimation(self.sidebar_widget, b"maximumWidth")
        anim.setDuration(180)
        anim.setStartValue(start_w)
        anim.setEndValue(end_w)
        anim.setEasingCurve(QEasingCurve.Type.InOutQuad)

        def on_finished():
            if target_expanded:
                self.splitter.setSizes([
                    self.sidebar_width_expanded,
                    self.width() - self.sidebar_width_expanded
                ])
            else:
                self.splitter.setSizes([0, self.width()])
            self.sidebar_expanded = target_expanded

        anim.finished.connect(on_finished)

        self._sidebar_anim = anim
        anim.start()

    def refresh_chat_list(self):
        self.chat_list.clear()
        chats = self.chat_manager.list_chats()
        for chat in chats:
            item = QListWidgetItem(chat.get("title", "Untitled chat"))
            item.setData(Qt.ItemDataRole.UserRole, chat["id"])
            item.setSizeHint(QSize(200, 40))
            self.chat_list.addItem(item)

        if self.current_chat:
            for i in range(self.chat_list.count()):
                item = self.chat_list.item(i)
                if item.data(Qt.ItemDataRole.UserRole) == self.current_chat["id"]:
                    self.chat_list.setCurrentItem(item)
                    break

    def create_new_chat(self):
        chat = self.chat_manager.create_new_chat(save=False)
        self.current_chat = chat
        self.load_chat_into_ui(chat)

    def on_chat_selected(self, item: QListWidgetItem):
        if self.is_generating:
            QMessageBox.warning(self, "Please Wait", "Please wait for the current response to finish.")
            return
            
        chat_id = item.data(Qt.ItemDataRole.UserRole)
        try:
            chat = self.chat_manager.load_chat(chat_id)
            self.current_chat = chat
            self.load_chat_into_ui(chat)
            self.chat_list.setCurrentItem(item)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not load chat:\n{e}")

    def load_chat_into_ui(self, chat_data: dict):
        self.chat_display.clear()
        messages = chat_data.get("messages", [])
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            created_at = msg.get("created_at")
            html_block = self.format_message(role, content, created_at)
            self.chat_display.append(html_block)
        self.chat_display.append("")

    def update_chat_title_from_first_message(self):
        if not self.current_chat:
            return
        msgs = self.current_chat.get("messages", [])
        for m in msgs:
            if m["role"] == "user":
                title = m["content"].strip()
                if len(title) > 40:
                    title = title[:40] + "."
                self.current_chat["title"] = title if title else "New chat"
                self.chat_manager.save_chat(self.current_chat)
                self.refresh_chat_list()
                break

    def select_model_file(self):
        root = tk.Tk()
        root.withdraw()
        file_path = filedialog.askopenfilename(
            title="Select a GGUF Model",
            filetypes=[("GGUF files", "*.gguf")]
        )

        if file_path:
            self.MODEL_PATH = file_path
            self.model_label.setText(f"Model: {os.path.basename(file_path)}")
            self.load_model()

    def load_model(self):
        try:
            if self.MODEL_PATH is None:
                QMessageBox.warning(self, "Warning", "Please select a model file first!")
                return

            n_gpu_layers = -1 if self.USE_GPU else 0
            n_batch = 2048 if self.USE_GPU else 512

            self.model = Llama(
                self.MODEL_PATH,
                n_ctx=8192,
                chat_format="chatml",
                n_gpu_layers=n_gpu_layers,
                n_batch=n_batch,
                f16_kv=True
            )
            loaded_html = self.format_message(
                "assistant",
                "Model Loaded! Ready to chat. 🔥",
                datetime.datetime.utcnow().isoformat()
            )
            self.chat_display.append(loaded_html)
            self.chat_display.append("")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load model:\n{e}")

    def on_ai_response_finished(self, response: str):
        """Called when AI generation completes successfully"""
        self.is_generating = False
        self.remove_typing_indicator()
        
        ai_now = datetime.datetime.utcnow().isoformat()
        ai_html = self.format_message("assistant", response, ai_now)
        self.chat_display.append(ai_html)
        self.chat_display.append("")

        self.current_chat["messages"].append(
            {"role": "assistant", "content": response, "created_at": ai_now}
        )
        self.current_chat["messages"].append(
            {"role": "separator", "content": ""}
        )

        self.chat_manager.save_chat(self.current_chat)
        
        self.send_button.setEnabled(True)
        self.send_button.setText("Send")
    
    def on_ai_response_error(self, error_msg: str):
        """Called when AI generation fails"""
        self.is_generating = False
        self.remove_typing_indicator()
        
        QMessageBox.critical(self, "Error", f"Error generating response:\n{error_msg}")
        
        self.send_button.setEnabled(True)
        self.send_button.setText("Send")

    def send_message(self):
        if not self.model:
            QMessageBox.warning(self, "Warning", "No model loaded! Please select a model first.")
            return
        
        if self.is_generating:
            QMessageBox.warning(self, "Please Wait", "Please wait for the current response to finish.")
            return

        if not self.current_chat:
            self.current_chat = self.chat_manager.create_new_chat(save=False)

        user_text = self.user_input.toPlainText().strip()
        if not user_text:
            return

        self.user_input.clear()

        now_iso = datetime.datetime.utcnow().isoformat()
        user_html = self.format_message("user", user_text, now_iso)
        self.chat_display.append(user_html)

        user_msg = {"role": "user", "content": user_text, "created_at": now_iso}
        self.current_chat["messages"].append(user_msg)

        self.update_chat_title_from_first_message()
        self.chat_manager.save_chat(self.current_chat)
        self.refresh_chat_list()

        self.chat_display.append("")
        
        self.show_typing_indicator()
        
        self.send_button.setEnabled(False)
        self.send_button.setText("Generating...")
        self.is_generating = True

        self.worker_thread = AIWorkerThread(self.model, self.current_chat["messages"])
        self.worker_thread.finished.connect(self.on_ai_response_finished)
        self.worker_thread.error.connect(self.on_ai_response_error)
        self.worker_thread.start()


class MainApp(QStackedWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Chat Application")
        self.setGeometry(200, 200, 1000, 650)

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
    if os.path.exists("dark_theme.qss"):
        app.setStyleSheet(load_stylesheet("dark_theme.qss"))
    window = MainApp()
    window.show()
    sys.exit(app.exec())