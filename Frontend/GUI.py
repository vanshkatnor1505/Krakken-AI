import os
import sys
import atexit
import threading
import traceback

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTextEdit, QStackedWidget, QPushButton,
    QVBoxLayout, QWidget, QLabel, QHBoxLayout, QLineEdit, QFrame,
    QSizePolicy
)
from PyQt5.QtGui import QIcon, QMovie, QColor, QTextCharFormat, QFont, QPixmap, QTextBlockFormat
from PyQt5.QtCore import Qt, QSize, QTimer, pyqtSignal, QThread

# Setup backend import paths
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
backend_dir = os.path.join(parent_dir, "Backend")
sys.path.extend([backend_dir, parent_dir])

# Import backend modules with fallback dummies
try:
    from Backend.Automation import FirstLayerDMM, handle_action, TextToSpeech, SpeechToTextSystem
except ImportError:
    print("Backend.Automation import failed; loading dummy implementations.")

    def FirstLayerDMM(*args): return ["general Hello! I'm your AI assistant."]
    def handle_action(*args): return "Automation system ready"
    def TextToSpeech(*args):
        if not app_shutting_down:
            print(f"TTS: {args[0] if args else 'No text'}")
    class SpeechToTextSystem:
        def __init__(self): pass
        def capture_speech(self): return "Speech system not available"
        def cleanup(self): pass

# Global shutdown flag
app_shutting_down = False

# Load Assistant name from .env
from dotenv import dotenv_values
env_vars = dotenv_values(os.path.join(parent_dir, ".env"))
AssistantName = env_vars.get("AssistantName", "Assistant")

# Directories for assets and temp data
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GraphicsDirPath = os.path.join(BASE_DIR, "Graphics")
TempDirPath = os.path.join(BASE_DIR, "Files")
os.makedirs(GraphicsDirPath, exist_ok=True)
os.makedirs(TempDirPath, exist_ok=True)

# Ensure essential files exist
for fname in ("Responses.data", "Status.data", "Mic.data", "ChatLog.json"):
    fpath = os.path.join(TempDirPath, fname)
    if not os.path.exists(fpath):
        with open(fpath, "w", encoding="utf-8") as f:
            f.write("[]" if fname == "ChatLog.json" else "")

# Utility path helpers
def GraphicsDirectoryPath(filename): return os.path.join(GraphicsDirPath, filename)
def TempDirectoryPath(filename): return os.path.join(TempDirPath, filename)

# Safe TTS invoker to prevent crashes during shutdown
def safe_text_to_speech(text):
    if app_shutting_down:
        return
    try:
        TextToSpeech(text)
    except RuntimeError as e:
        if "cannot schedule new futures after interpreter shutdown" in str(e):
            print("TTS skipped: Application is shutting down")
        else:
            print(f"TTS error: {e}")
    except Exception as e:
        if not app_shutting_down:
            print(f"TTS error: {e}")

# Worker threads
class AutomationWorker(QThread):
    response_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()

    def __init__(self, command_text):
        super().__init__()
        self.command_text = command_text

    def run(self):
        if app_shutting_down:
            return
        try:
            decisions = FirstLayerDMM(self.command_text)
            responses = []
            for act in decisions:
                if app_shutting_down:
                    return
                res = handle_action(act, self.command_text)
                if res == "EXIT":
                    self.response_signal.emit("EXIT")
                    break
                if res:
                    responses.append(res)
            self.response_signal.emit("\n".join(responses) if responses else "Command executed successfully.")
        except Exception as e:
            if not app_shutting_down:
                self.error_signal.emit(f"Automation error: {str(e)}\n{traceback.format_exc()}")
        finally:
            self.finished_signal.emit()

class SpeechRecognitionWorker(QThread):
    speech_detected = pyqtSignal(str)
    status_update = pyqtSignal(str)
    error_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.speech_system = None
        self._is_running = True
        self._stop_requested = False

    def init_speech_system(self):
        try:
            self.speech_system = SpeechToTextSystem()
            return True
        except Exception as e:
            self.error_signal.emit(f"Speech system initialization failed: {e}")
            return False

    def run(self):
        if not self.init_speech_system():
            return
        while self._is_running and not self._stop_requested and not app_shutting_down:
            try:
                self.status_update.emit("Listening...")
                user_input = self.speech_system.capture_speech()
                if user_input and not (self._stop_requested or app_shutting_down):
                    self.speech_detected.emit(user_input)
                    self.status_update.emit("Speech detected")
                elif not (self._stop_requested or app_shutting_down):
                    self.status_update.emit("No speech detected")
            except Exception as e:
                if self._is_running and not app_shutting_down:
                    self.error_signal.emit(f"Speech recognition error: {e}")
                break

    def stop(self):
        self._stop_requested = True
        self._is_running = False
        if self.speech_system:
            try:
                self.speech_system.cleanup()
            except Exception:
                pass

    def __del__(self):
        self.stop()
        self.wait(1000)

# Chat UI section
class ChatSection(QWidget):
    def __init__(self):
        super().__init__()
        self.speech_worker = None
        self.automation_workers = []
        self.tts_in_progress = False  # Flag to prevent looping TTS calls
        self._setup_ui()
        self._setup_timers()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 30, 20, 40)
        layout.setSpacing(15)

        # Chat display - black theme
        self.chat_text_edit = QTextEdit(readOnly=True)
        self.chat_text_edit.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.chat_text_edit.setFrameShape(QFrame.StyledPanel)
        self.chat_text_edit.setFrameShadow(QFrame.Raised)
        layout.addWidget(self.chat_text_edit)

        self.setStyleSheet("""
            background-color: #000000;
            color: #EEEEEE;
        """)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        fmt = QTextCharFormat()
        fmt.setForeground(QColor("#1EA5CE"))  # Aqua accent color
        self.chat_text_edit.setCurrentCharFormat(fmt)

        font = QFont("Segoe UI", 14)
        self.chat_text_edit.setFont(font)

        # Input layout
        input_layout = QHBoxLayout()
        input_layout.setSpacing(15)

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Type your command here...")
        self.input_field.setStyleSheet("""
            QLineEdit {
                background-color: #000000;
                border: 2px solid #1EA5CE;
                border-radius: 12px;
                padding: 12px 16px;
                color: #EEEEEE;
                font-size: 16px;
                selection-background-color: #1EA5CE;
            }
            QLineEdit:focus {
                border-color: #4DD0E1;
                background-color: #111111;
            }
        """)
        self.input_field.returnPressed.connect(self.handle_send)
        input_layout.addWidget(self.input_field)

        self.send_button = QPushButton("Send")
        self.send_button.setStyleSheet("""
            QPushButton {
                background-color: #1EA5CE;
                color: white;
                font-weight: bold;
                border-radius: 12px;
                padding: 12px 24px;
                font-size: 16px;
                min-width: 90px;
            }
            QPushButton:hover {
                background-color: #14ACC9;
            }
            QPushButton:pressed {
                background-color: #0E7C94;
            }
            QPushButton:disabled {
                background-color: #555555;
                color: #AAAAAA;
            }
        """)
        self.send_button.setCursor(Qt.PointingHandCursor)
        self.send_button.clicked.connect(self.handle_send)
        input_layout.addWidget(self.send_button)

        self.mic_button = QPushButton()
        self.mic_button.setIcon(QIcon(GraphicsDirectoryPath("mic_off.png")))
        self.mic_button.setFixedSize(48, 48)
        self.mic_button.setStyleSheet("""
            QPushButton {
                background-color: #000000;
                border-radius: 24px;
                padding: 8px;
            }
            QPushButton:hover {
                background-color: #222222;
            }
            QPushButton:pressed {
                background-color: #333333;
            }
        """)
        self.mic_button.setCursor(Qt.PointingHandCursor)
        self.mic_button.clicked.connect(self.toggle_voice_input)
        input_layout.addWidget(self.mic_button)

        layout.addLayout(input_layout)

        # Jarvis GIF
        self.gif_label = QLabel()
        movie = QMovie(GraphicsDirectoryPath("Jarvis.gif"))
        size = 300
        movie.setScaledSize(QSize(size, size))
        self.gif_label.setFixedSize(size, size)
        self.gif_label.setAlignment(Qt.AlignRight | Qt.AlignBottom)
        self.gif_label.setMovie(movie)
        movie.start()
        layout.addWidget(self.gif_label)

        # Status label
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("""
            color: #1EA5CE;
            font-size: 18px;
            font-weight: 600;
            margin-right: 195px;
            margin-top: -30px;
        """)
        self.status_label.setAlignment(Qt.AlignRight)
        layout.addWidget(self.status_label)

    def _setup_timers(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.loadMessages)
        self.timer.timeout.connect(self.update_status_from_file)
        self.timer.start(200)

    def toggle_voice_input(self):
        if app_shutting_down:
            return
        if self.speech_worker and self.speech_worker.isRunning():
            self.stop_voice_input()
        else:
            self.start_voice_input()

    def start_voice_input(self):
        if app_shutting_down or (self.speech_worker and self.speech_worker.isRunning()):
            return
        self.speech_worker = SpeechRecognitionWorker()
        self.speech_worker.speech_detected.connect(self.handle_voice_command)
        self.speech_worker.status_update.connect(self.update_status)
        self.speech_worker.error_signal.connect(self.handle_speech_error)
        self.speech_worker.finished.connect(self.on_speech_worker_finished)
        self.speech_worker.start()
        self.mic_button.setIcon(QIcon(GraphicsDirectoryPath("mic_on.png")))
        self.update_status("Voice recognition started...")

    def stop_voice_input(self):
        if self.speech_worker:
            self.speech_worker.stop()
        self.mic_button.setIcon(QIcon(GraphicsDirectoryPath("mic_off.png")))
        self.update_status("Voice recognition stopped")

    def on_speech_worker_finished(self):
        self.mic_button.setIcon(QIcon(GraphicsDirectoryPath("mic_off.png")))
        self.update_status("Voice recognition stopped")

    def handle_voice_command(self, command_text):
        if app_shutting_down:
            return
        self.addMessage(f"You (Voice): {command_text}", color='cyan')
        self.execute_command(command_text)

    def handle_speech_error(self, error_msg):
        if not app_shutting_down:
            self.update_status(f"Speech error: {error_msg}")
            self.stop_voice_input()

    def update_status(self, status):
        if not app_shutting_down:
            self.status_label.setText(status)

    def handle_send(self):
        if app_shutting_down:
            return
        user_input = self.input_field.text().strip()
        if not user_input:
            return
        self.input_field.clear()
        self.addMessage(f"You: {user_input}", color='cyan')
        self.execute_command(user_input)

    def execute_command(self, command_text):
        if app_shutting_down:
            return
        worker = AutomationWorker(command_text)
        worker.response_signal.connect(self.handle_automation_response)
        worker.error_signal.connect(self.handle_automation_error)
        worker.finished_signal.connect(lambda: self.on_automation_worker_finished(worker))
        self.automation_workers.append(worker)
        worker.start()
        self.update_status("Processing command...")

    def handle_automation_response(self, response):
        print(f"[DEBUG] Response received in GUI: {response!r}")
        if app_shutting_down or self.tts_in_progress:
            return
        if response == "EXIT":
            QTimer.singleShot(100, self.initiate_shutdown)
            return

        self.tts_in_progress = True

        def tts_done():
            self.tts_in_progress = False
            print("[DEBUG] TTS playback finished")

        try:
            threading.Thread(target=lambda: TextToSpeech(response, on_complete=tts_done), daemon=True).start()
        except Exception as e:
            print(f"TTS thread error: {e}")

        self.addMessage(f"JARVIS: {response}", color='white')
        self.update_status("Ready")

    def initiate_shutdown(self):
        global app_shutting_down
        app_shutting_down = True
        self.stop_voice_input()
        for worker in self.automation_workers:
            if worker.isRunning():
                worker.quit()
                worker.wait(500)
        QApplication.quit()

    def handle_automation_error(self, error_msg):
        if not app_shutting_down:
            self.addMessage(f"JARVIS: Error - {error_msg}", color='red')
            self.update_status("Error occurred")

    def on_automation_worker_finished(self, worker):
        if worker in self.automation_workers:
            self.automation_workers.remove(worker)

    def loadMessages(self):
        if app_shutting_down:
            return
        try:
            with open(TempDirectoryPath("Responses.data"), "r", encoding="utf-8") as file:
                messages = file.read()
                if messages and messages.strip() not in self.chat_text_edit.toPlainText():
                    self.addMessage(messages, color='white')
        except Exception:
            pass

    def update_status_from_file(self):
        if app_shutting_down:
            return
        try:
            with open(TempDirectoryPath("Status.data"), "r", encoding="utf-8") as file:
                status = file.read()
                if status and not (self.speech_worker and self.speech_worker.isRunning()):
                    self.status_label.setText(status)
        except Exception:
            if not (self.speech_worker and self.speech_worker.isRunning()):
                self.status_label.setText("Ready")

    def addMessage(self, message, color):
        cursor = self.chat_text_edit.textCursor()
        fmt = QTextCharFormat()
        block_fmt = QTextBlockFormat()
        block_fmt.setTopMargin(10)
        block_fmt.setLeftMargin(10)
        fmt.setForeground(QColor(color))
        cursor.setCharFormat(fmt)
        cursor.setBlockFormat(block_fmt)
        cursor.insertText(message + "\n")
        self.chat_text_edit.setTextCursor(cursor)
        self.chat_text_edit.ensureCursorVisible()

    def closeEvent(self, event):
        global app_shutting_down
        app_shutting_down = True
        if self.speech_worker:
            self.speech_worker.stop()
            self.speech_worker.wait(1000)
        for worker in self.automation_workers:
            if worker.isRunning():
                worker.quit()
                worker.wait(500)
        super().closeEvent(event)

# Initial screen with GIF + mic icon
class InitialScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        screen = QApplication.primaryScreen()
        size = screen.size()
        screen_width, screen_height = size.width(), size.height()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 150)
        layout.setSpacing(20)

        gif_label = QLabel()
        movie = QMovie(GraphicsDirectoryPath("Jarvis.gif"))
        size = min(screen_width, screen_height) * 2 // 3
        movie.setScaledSize(QSize(size, size))
        gif_label.setFixedSize(size, size)
        gif_label.setAlignment(Qt.AlignCenter)
        gif_label.setMovie(movie)
        movie.start()

        self.icon_label = QLabel()
        self.icon_label.setPixmap(QPixmap(GraphicsDirectoryPath("mic_off.png")).scaled(80, 80))
        self.icon_label.setFixedSize(150, 150)
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.mousePressEvent = self.toggle_icon

        self.label = QLabel("Click mic to start voice recognition")
        self.label.setStyleSheet("""
            color: #1EA5CE;
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 0;
        """)

        layout.addWidget(gif_label, alignment=Qt.AlignCenter)
        layout.addWidget(self.label, alignment=Qt.AlignCenter)
        layout.addWidget(self.icon_label, alignment=Qt.AlignCenter)

        self.setFixedHeight(screen_height)
        self.setFixedWidth(screen_width)
        self.setStyleSheet("background-color: #000000;")

        self.toggled = False
        self.speech_worker = None

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_status_from_file)
        self.timer.start(200)

    def toggle_icon(self, event=None):
        if app_shutting_down:
            return
        if not self.toggled:
            self.start_voice_input()
        else:
            self.stop_voice_input()

    def start_voice_input(self):
        if app_shutting_down or (self.speech_worker and self.speech_worker.isRunning()):
            return
        self.speech_worker = SpeechRecognitionWorker()
        self.speech_worker.speech_detected.connect(self.handle_voice_command)
        self.speech_worker.status_update.connect(self.update_status)
        self.speech_worker.error_signal.connect(self.handle_speech_error)
        self.speech_worker.finished.connect(self.on_speech_worker_finished)
        self.speech_worker.start()
        self.icon_label.setPixmap(QPixmap(GraphicsDirectoryPath("mic_on.png")).scaled(80, 80))
        self.toggled = True
        print("[MicButtonInitialized] Starting speech recognition...")

    def stop_voice_input(self):
        if self.speech_worker:
            self.speech_worker.stop()
        self.toggled = False
        self.label.setText("Click mic to start voice recognition")
        self.icon_label.setPixmap(QPixmap(GraphicsDirectoryPath("mic_off.png")).scaled(80, 80))
        print("[MicButtonClosed] Stopping speech recognition...")

    def on_speech_worker_finished(self):
        self.icon_label.setPixmap(QPixmap(GraphicsDirectoryPath("mic_off.png")).scaled(80, 80))
        self.toggled = False
        self.label.setText("Click mic to start voice recognition")

    def handle_voice_command(self, command_text):
        if app_shutting_down:
            return
        mw = self.get_main_window()
        if mw:
            mw.centralWidget().setCurrentIndex(1)
            chat_section = mw.centralWidget().widget(1).findChild(ChatSection)
            if chat_section:
                chat_section.handle_voice_command(command_text)

    def handle_speech_error(self, error_msg):
        if not app_shutting_down:
            self.label.setText(f"Speech error: {error_msg}")
            self.stop_voice_input()

    def update_status(self, status):
        if not app_shutting_down:
            self.label.setText(status)

    def update_status_from_file(self):
        if app_shutting_down:
            return
        try:
            with open(TempDirectoryPath("Status.data"), "r", encoding="utf-8") as file:
                status = file.read()
                if status and not self.toggled:
                    self.label.setText(status)
        except Exception:
            if not self.toggled:
                self.label.setText("Click mic to start voice recognition")

    def get_main_window(self):
        parent = self.parent()
        while parent and not isinstance(parent, QMainWindow):
            parent = parent.parent()
        return parent

    def closeEvent(self, event):
        global app_shutting_down
        app_shutting_down = True
        if self.speech_worker:
            self.speech_worker.stop()
            self.speech_worker.wait(1000)
        super().closeEvent(event)

# Message screen wrapping ChatSection
class MessageScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.last_response = None
        self.tts_in_progress = False
        screen = QApplication.primaryScreen()
        size = screen.size()
        screen_width, screen_height = size.width(), size.height()

        layout = QVBoxLayout(self)
        self.chat_section = ChatSection()
        layout.addWidget(self.chat_section)
        self.setFixedHeight(screen_height)
        self.setFixedWidth(screen_width)
        self.setStyleSheet("background-color: #000000;")

    
    def handle_automation_response(self, response):
        if response == self.last_response:
            print("[DEBUG] Duplicate response ignored to prevent replay")
            return
        self.last_response = response
        if app_shutting_down or self.tts_in_progress:
            return
        if response == "EXIT":
            QTimer.singleShot(100, self.initiate_shutdown)
            return

        self.tts_in_progress = True

        def tts_done():
            self.tts_in_progress = False
            print("[DEBUG] TTS playback finished")

        try:
            threading.Thread(target=lambda: TextToSpeech(response, on_complete=tts_done), daemon=True).start()
        except Exception as e:
            print(f"TTS thread error: {e}")

        self.addMessage(f"JARVIS: {response}", color='white')
        self.update_status("Ready")    

# Custom top bar with navigation and window controls
class CustomTopBar(QWidget):
    def __init__(self, parent, stacked_widget):
        super().__init__(parent)
        self.stacked_widget = stacked_widget
        self._setup_ui()

    def _setup_ui(self):
        self.setFixedHeight(50)
        layout = QHBoxLayout(self)
        layout.setAlignment(Qt.AlignRight)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 5, 10, 5)

        button_style = """
            QPushButton {
                background-color: #000000;
                border: none;
                color: white;
                font-weight: 600;
                font-size: 14px;
                padding: 10px 15px;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #222222;
            }
            QPushButton:pressed {
                background-color: #333333;
            }
        """

        # home and chat buttons with icons and texts
        home_button = QPushButton(" Home")
        home_button.setIcon(QIcon(GraphicsDirectoryPath("Home.png")))
        home_button.setStyleSheet(button_style)
        home_button.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(0))

        chat_button = QPushButton(" Chat")
        chat_button.setIcon(QIcon(GraphicsDirectoryPath("chat.png")))
        chat_button.setStyleSheet(button_style)
        chat_button.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(1))

        def window_button(icon_path, hover_bg="#222222", pressed_bg="#333333"):
            btn = QPushButton()
            btn.setIcon(QIcon(GraphicsDirectoryPath(icon_path)))
            btn.setFixedSize(36, 36)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #000000;
                    border-radius: 18px;
                }}
                QPushButton:hover {{
                    background-color: {hover_bg};
                }}
                QPushButton:pressed {{
                    background-color: {pressed_bg};
                }}
            """)
            btn.setCursor(Qt.PointingHandCursor)
            return btn

        minimize_button = window_button("minimize2.png")
        minimize_button.clicked.connect(self.minimizeWindow)

        self.maximize_button = window_button("miximize.png")
        self.maximize_button.clicked.connect(self.maximizeWindow)

        close_button = window_button("cross.png", hover_bg="#C42B1C", pressed_bg="#8B0000")
        close_button.clicked.connect(self.closeWindow)

        title_label = QLabel(f"{AssistantName.capitalize()} AI   ")
        title_label.setStyleSheet("color: #1EA5CE; font-size: 16px; font-weight: bold;")

        layout.addWidget(title_label)
        layout.addStretch(1)
        layout.addWidget(home_button)
        layout.addWidget(chat_button)
        layout.addStretch(1)
        layout.addWidget(minimize_button)
        layout.addWidget(self.maximize_button)
        layout.addWidget(close_button)
        self.setLayout(layout)

    def minimizeWindow(self):
        self.parent().showMinimized()

    def maximizeWindow(self):
        if self.parent().isMaximized():
            self.parent().showNormal()
            self.maximize_button.setIcon(QIcon(GraphicsDirectoryPath("miximize.png")))
        else:
            self.parent().showMaximized()
            self.maximize_button.setIcon(QIcon(GraphicsDirectoryPath("minimize.png")))

    def closeWindow(self):
        global app_shutting_down
        app_shutting_down = True
        self.parent().close()

# Main application window
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint)
        self._setup_ui()

    def _setup_ui(self):
        screen = QApplication.primaryScreen()
        size = screen.size()
        sw, sh = size.width(), size.height()

        stacked_widget = QStackedWidget(self)
        stacked_widget.addWidget(InitialScreen())
        stacked_widget.addWidget(MessageScreen())

        self.setCentralWidget(stacked_widget)
        self.setGeometry(0, 0, sw, sh)

        top_bar = CustomTopBar(self, stacked_widget)
        self.setMenuWidget(top_bar)
        self.setStyleSheet("background-color: #000000;")

    def closeEvent(self, event):
        global app_shutting_down
        app_shutting_down = True
        for i in range(self.centralWidget().count()):
            widget = self.centralWidget().widget(i)
            if hasattr(widget, "closeEvent"):
                widget.closeEvent(event)
        super().closeEvent(event)

# Application shutdown cleanup
def cleanup_on_shutdown():
    global app_shutting_down
    app_shutting_down = True
    print("Application shutdown cleanup completed")

atexit.register(cleanup_on_shutdown)

# App entry point
def GraphicalUserInterface():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    try:
        sys.exit(app.exec_())
    except SystemExit:
        global app_shutting_down
        app_shutting_down = True
        print("Application exited cleanly")

if __name__ == "__main__":
    GraphicalUserInterface()
