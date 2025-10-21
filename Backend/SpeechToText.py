from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from dotenv import dotenv_values
import os
import time
import mtranslate as mt
import atexit

class SpeechToTextSystem:
    def __init__(self):
        self.load_env_config()
        self.setup_folders()
        self.create_html_interface()
        self.setup_browser()
        atexit.register(self.cleanup)

    def load_env_config(self):
        env_vars = dotenv_values(os.path.join(os.path.dirname(__file__), ".env"))
        self.InputLanguage = env_vars.get("InputLanguage", "en-US")

    def setup_folders(self):
        self.current_dir = os.getcwd()
        self.temp_dir_path = os.path.join(self.current_dir, "Frontend", "Files")
        os.makedirs(os.path.join(self.current_dir, "Data"), exist_ok=True)
        os.makedirs(self.temp_dir_path, exist_ok=True)

    def create_html_interface(self):
        html = '''<!DOCTYPE html>
<html lang="en">
<head>
<title>Speech to Text Recognition</title>
<style>
body { font-family: Arial; margin: 40px; }
button { padding: 10px 20px; margin: 5px; cursor: pointer; }
#output { margin-top: 20px; padding: 15px; border: 1px solid #ccc; min-height: 50px; background: #f9f9f9; }
.listening { background: #e8f5e8; }
.status { color: #666; font-style: italic; }
</style>
</head>
<body>
<h2>Speech to Text System</h2>
<button id="start" onclick="startRecognition()">🎤 Start Listening</button>
<button id="end" onclick="stopRecognition()" disabled>⏹️ Stop Listening</button>
<div id="output"><div class="status">Click 'Start Listening' to begin speech recognition...</div></div>
<script>
const output = document.getElementById('output');
const startBtn = document.getElementById('start');
const endBtn = document.getElementById('end');
let recognition, isListening = false;
function startRecognition() {
    if (isListening) return;
    recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
    recognition.lang = 'LANGUAGE_PLACEHOLDER';
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.onstart = function() {
        isListening = true;
        startBtn.disabled = true;
        endBtn.disabled = false;
        output.innerHTML = "<div class='status'>🎤 Listening... Speak now!</div>";
        document.body.classList.add('listening');
    };
    recognition.onresult = function(e) {
        let txt = '';
        for (let i=e.resultIndex; i < e.results.length; i++) {
            if (e.results[i].isFinal) {
                txt += e.results[i][0].transcript;
            }
        }
        if (txt) output.innerHTML = txt;
    };
    recognition.onerror = function(e) {
        if (e.error === 'not-allowed')
            output.innerHTML = "<div class='status'>❌ Microphone access denied.</div>";
    };
    recognition.onend = function() {
        isListening = false;
        startBtn.disabled = false;
        endBtn.disabled = true;
        document.body.classList.remove('listening');
        if (output.textContent.includes('Listening'))
            output.innerHTML = "<div class='status'>Ready to listen. Click 'Start Listening' again.</div>";
    };
    recognition.start();
}
function stopRecognition() {
    if (recognition && isListening) recognition.stop();
    startBtn.disabled = false;
    endBtn.disabled = true;
    document.body.classList.remove('listening');
}
</script>
</body>
</html>'''
        html = html.replace('LANGUAGE_PLACEHOLDER', self.InputLanguage)
        html_path = os.path.join(self.current_dir, "Data", "Voice.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)
        self.html_file_url = f"file:///{html_path.replace(os.sep, '/')}"

    def setup_browser(self):
        options = Options()
        options.add_argument("user-agent=Mozilla/5.0")
        options.add_argument("--use-fake-ui-for-media-stream")
        options.add_argument("--use-fake-device-for-media-stream")
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        
    def set_status(self, status):
        status_file = os.path.join(self.temp_dir_path, "Status.data")
        try:
            with open(status_file, "w", encoding="utf-8") as file:
                file.write(status)
        except Exception:
            pass

    def query_modifier(self, query):
        q = query.lower().strip()
        question_words = ["what", "which", "whose", "whom", "can you", "what's", "where's", "how's", "who", "where", "when", "why", "how"]
        punctuation = "?" if any(q.startswith(word) for word in question_words) else "."
        if q and q[-1] in ['.', '?', '!']:
            q = q[:-1] + punctuation
        else:
            q += punctuation
        return q.capitalize()

    def translate_to_english(self, text):
        try:
            return mt.translate(text, "en", "auto").capitalize()
        except Exception:
            return text.capitalize()

    def capture_speech(self):
        self.driver.get(self.html_file_url)
        wait = WebDriverWait(self.driver, 10)
        try:
            wait.until(EC.element_to_be_clickable((By.ID, "start"))).click()
        except Exception:
            print("Could not click start button.")
            return None
        max_attempts = 1000
        for _ in range(max_attempts):
            try:
                output = self.driver.find_element(By.ID, "output")
                text = output.text.strip()
                status_msgs = ["Click 'Start Listening'", "Ready to listen", "Listening...", "🎤", "❌"]
                if text and not any(msg in text for msg in status_msgs) and len(text) > 2:
                    end_btn = self.driver.find_element(By.ID, "end")
                    if end_btn.is_enabled(): end_btn.click()
                    print(f"📝 Raw speech: '{text}'")
                    if self.InputLanguage.lower().startswith("en"):
                        return self.query_modifier(text)
                    self.set_status("Translating...")
                    return self.query_modifier(self.translate_to_english(text))
            except Exception:
                pass
            time.sleep(0.1)
        print("⏰ Listening timeout - no speech detected")
        return None

    def cleanup(self):
        try:
            self.driver.quit()
        except Exception:
            pass

    def run(self):
        print("="*50)
        print("🎤 SPEECH-TO-TEXT SYSTEM STARTED")
        print("="*50)
        print(f"Input Language: {self.InputLanguage}")
        print("Press Ctrl+C to exit...")
        try:
            while True:
                recognized_text = self.capture_speech()
                if recognized_text:
                    print(f"✅ Final Output: {recognized_text}")
                else:
                    print("🔇 No speech detected, restarting listener...")
                print("-" * 50)
                time.sleep(2)
        except KeyboardInterrupt:
            print("\n🛑 Speech-to-Text System stopped.")
        finally:
            self.cleanup()

if __name__ == "__main__":
    SpeechToTextSystem().run()
