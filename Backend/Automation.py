# automation.py
import os
import sys
sys.stderr = open(os.devnull, 'w')
import time
import shlex
import platform
import subprocess
import webbrowser
from pathlib import Path
import pytz
from datetime import datetime

# Import your modules (assumes same directory)
from Model import FirstLayerDMM
from Chatbot import ChatBot, Assistantname
from RealtimeSearchEngine import RealtimeSearchEngine

from SpeechToText import SpeechToTextSystem
from TextToSpeech import TextToSpeech

os.environ["ELECTRON_ENABLE_LOGGING"] = "true"
os.environ["ANGLE_DEFAULT_PLATFORM"] = "swiftshader"


# Utility helpers -----------------------------------------------------------

IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"
IS_MAC = platform.system() == "Darwin"

def safe_print(tag, *args):
    print(f"[{tag}] ", *args)

def get_realtime_info():
    tz = pytz.timezone("Asia/Kolkata")
    current_date_time = datetime.now(tz)
    return f"{current_date_time.strftime('%d %B %Y')}\n{current_date_time.strftime('%H:%M:%S IST')}"

# Open an app or URL (best-effort)
def open_target(target: str):
    target = target.strip()
    safe_print("ACTION", f"open -> {target}")
    # If appears like a URL or contains '.' or startswith http, open browser
    if target.lower().startswith(("http://", "https://")) or "." in target or "www" in target.lower():
        try:
            url = target if target.lower().startswith(("http://", "https://")) else f"https://{target}"
            subprocess.Popen(["python", "-m", "webbrowser", "-t", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            return False

    # Try os.startfile (Windows)
    try:
        if IS_WINDOWS:
            try:
                os.startfile(target)
                return True
            except Exception:
                # Maybe it's an app name; try start via shell
                subprocess.Popen(["start", target], shell=True)
                return True
        else:
            # Try xdg-open / open
            if shutil_which("xdg-open"):
                subprocess.Popen(["xdg-open", target], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True
            elif shutil_which("open"):  # macOS
                subprocess.Popen(["open", target], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True
    except Exception as e:
        safe_print("ERROR", f"open_target exception: {e}")

    # As a fallback, try to open with webbrowser (search)
    try:
        webbrowser.open(f"https://www.google.com/search?q={shlex.quote(target)}")
        return True
    except Exception as e:
        safe_print("ERROR", f"fallback open failed: {e}")
        return False

# Close an app (best-effort)
def close_target(target: str):
    target = target.strip()
    safe_print("ACTION", f"close -> {target}")
    try:
        # On Windows use taskkill with image name or window title
        if IS_WINDOWS:
            # If user gave an app name like "chrome" or "notepad"
            image_name = target
            # try with .exe appended
            if not image_name.lower().endswith(".exe"):
                image_name_exe = image_name + ".exe"
            else:
                image_name_exe = image_name
            # Try to kill processes by name
            subprocess.run(["taskkill", "/F", "/IM", image_name_exe], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            # If that didn't do anything, try killing by name without .exe
            subprocess.run(["taskkill", "/F", "/IM", image_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        else:
            # Unix-like: use pkill
            subprocess.run(["pkill", "-f", target], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
    except Exception as e:
        safe_print("ERROR", f"close_target exception: {e}")
        return False

# small helper to test existence of commands
def shutil_which(cmd):
    from shutil import which
    return which(cmd) is not None

# Parse a single action string like "general tell me a joke" or "open youtube"
def handle_action(action: str, user_raw_query: str = ""):
    """
    action: one action item returned from FirstLayerDMM, e.g. 'general what is python?'
    user_raw_query: original user input (for context if needed)
    """
    if not action:
        return None

    action = action.strip()
    # sometimes model returns "generate ..." or "generate image ..." or "google search ..."
    # Normalize: lower-case for action type detection, but keep original tail
    parts = action.split()
    if len(parts) == 0:
        return None
    keyword = parts[0].lower()
    tail = action[len(parts[0]):].strip() if len(action) > len(parts[0]) else ""
    # EXIT
    if keyword == "exit":
        safe_print("SYSTEM", "Exit command received. Shutting down.")
        return "EXIT"

    # GENERAL -> Chatbot
    if keyword == "general":
        query = tail or user_raw_query
        safe_print("ROUTER", f"Routing to ChatBot: {query}")
        try:
            response = ChatBot(query)
            safe_print(Assistantname, response)
            # speak
            try:
                TextToSpeech(response)
            except Exception as e:
                safe_print("TTS", f"Error speaking response: {e}")
            return response
        except Exception as e:
            safe_print("ERROR", f"ChatBot failed: {e}")
            return None
    
    
    # REALTIME -> RealtimeSearchEngine
    if keyword == "realtime":
        query = tail or user_raw_query
        safe_print("ROUTER", f"Routing to RealtimeSearchEngine: {query}")
        try:
            response = RealtimeSearchEngine(query)
            safe_print(Assistantname, response)
            try:
                TextToSpeech(response)
            except Exception as e:
                safe_print("TTS", f"Error speaking realtime response: {e}")
            return response
        except Exception as e:
            safe_print("ERROR", f"RealtimeSearchEngine failed: {e}")
            return None


    # GOOGLE SEARCH -> open browser search or call RealtimeSearchEngine as well
    if keyword in ("google", "googlesearch", "google_search", "googlesearch"):
        query = tail or user_raw_query
        safe_print("ROUTER", f"Opening Google search for: {query}")
        try:
            webbrowser.open(f"https://www.google.com/search?q={webbrowser.quote(query) if hasattr(webbrowser, 'quote') else query}")
            return f"Opened Google search for: {query}"
        except Exception:
            try:
                webbrowser.open(f"https://www.google.com/search?q={query}")
                return f"Opened Google search for: {query}"
            except Exception as e:
                safe_print("ERROR", f"google search open failed: {e}")
                return None

    # YOUTUBE SEARCH or open youtube
    if keyword in ("youtube", "youtubesearch", "youtube_search", "youtube"):
        query = tail or user_raw_query
        if query:
            safe_print("ROUTER", f"Searching YouTube for: {query}")
            webbrowser.open(f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}")
            return f"Searched YouTube: {query}"
        else:
            webbrowser.open("https://www.youtube.com")
            return "Opened YouTube"

    # OPEN -> open app or website
    if keyword == "open":
        target = tail or user_raw_query
        if not target:
            return None
        success = open_target(target)
        return f"Opened {target}" if success else None

    # CLOSE -> close app
    if keyword == "close":
        target = tail or user_raw_query
        if not target:
            return None
        success = close_target(target)
        return f"Closed {target}" if success else None

    # PLAY -> open youtube or media; try to open YouTube search or use webbrowser
    if keyword == "play":
        target = tail or user_raw_query
        if not target:
            return None
        safe_print("ROUTER", f"Play requested: {target}")
        # If user wants a song -> open youtube search
        try:
            webbrowser.open(f"https://www.youtube.com/results?search_query={target.replace(' ', '+')}")
            return f"Playing {target} on YouTube"
        except Exception as e:
            safe_print("ERROR", f"Play failed: {e}")
            return None

    # SYSTEM commands (volume, mute, etc.) -> best-effort placeholders
    if keyword == "system":
        cmd = tail or user_raw_query
        safe_print("SYSTEM", f"System command requested: {cmd}")
        # We won't change system volume here; return acknowledgment
        try:
            TextToSpeech(f"Executing system command: {cmd}")
        except Exception:
            pass
        return f"Executed system command: {cmd}"

    # REMINDER -> Placeholder (store in file or integrate with OS scheduler)
    if keyword == "reminder":
        reminder_text = tail or user_raw_query
        # For now, write reminder to a simple file (append)
        try:
            os.makedirs("Data", exist_ok=True)
            with open("Data/reminders.txt", "a", encoding="utf-8") as f:
                f.write(reminder_text + "\n")
            import threading
            threading.Thread(target=TextToSpeech, args=("Reminder saved.",), daemon=True).start()
            return f"Reminder saved: {reminder_text}"
        except Exception as e:
            safe_print("ERROR", f"Reminder save failed: {e}")
            return None

    # DEFAULT fallback -> treat as general query
    safe_print("ROUTER", f"Unknown action '{keyword}', defaulting to general.")
    try:
        response = ChatBot(user_raw_query or action)
        safe_print(Assistantname, response)
        try:
            import threading
            threading.Thread(target=TextToSpeech, args=(response,), daemon=True).start()
        except Exception:
            pass
        return response
    except Exception as e:
        safe_print("ERROR", f"Fallback ChatBot failed: {e}")
        return None

# Main loop ---------------------------------------------------------------
def main():
    safe_print("SYSTEM", "Starting automation (Jarvis) ...")
    # Instantiate voice system but only start listening when requested
    speech_system = None
    try:
        speech_system = SpeechToTextSystem()
    except Exception as e:
        safe_print("SPEECH", f"Speech system initialization failed (voice disabled): {e}")
        speech_system = None

    mode = "text"  # default
    safe_print("SYSTEM", "Available modes: text, voice, both")
    safe_print("SYSTEM", "Type 'mode voice' or 'mode text' to switch. Type 'exit' to quit.\n")

    while True:
        try:
            if mode in ("voice", "both") and speech_system:
                safe_print("PROMPT", "Say something or type (prefix 't:' to type). Listening for voice input (press Ctrl+C to interrupt)...")
                try:
                    user_input = speech_system.capture_speech()
                except KeyboardInterrupt:
                    safe_print("SYSTEM", "Voice capture interrupted by user. Switching to typed input prompt.")
                    user_input = None
                except Exception as e:
                    safe_print("SPEECH", f"Error during capture: {e}")
                    user_input = None

                # If nothing captured, allow typed fallback
                if not user_input:
                    # fallback to typed input
                    typed = input("You (type, or 'mode text'/'mode voice'/'exit'): ").strip()
                    if typed.lower().startswith("mode"):
                        _, newmode = typed.split(maxsplit=1)
                        mode = newmode.strip().lower()
                        safe_print("SYSTEM", f"Mode switched to: {mode}")
                        continue
                    if typed.lower() in ("exit", "quit", "bye"):
                        safe_print("SYSTEM", "Exit requested.")
                        break
                    if typed:
                        # allow user to prefix typed input with t:
                        user_query = typed[2:].strip() if typed.startswith("t:") else typed
                    else:
                        continue
                else:
                    user_query = user_input

            else:
                # Text-only mode
                user_raw = input("You (type command, 'mode voice' to switch, 'exit' to quit): ").strip()
                if not user_raw:
                    continue
                if user_raw.lower().startswith("mode"):
                    # change mode
                    try:
                        _, newmode = user_raw.split(maxsplit=1)
                        mode = newmode.strip().lower()
                        safe_print("SYSTEM", f"Mode switched to: {mode}")
                    except Exception:
                        safe_print("SYSTEM", "Invalid mode command. Use 'mode voice' or 'mode text' or 'mode both'")
                    continue
                if user_raw.lower() in ("exit", "quit", "bye"):
                    safe_print("SYSTEM", "Exit requested.")
                    break
                # Let typed input be used
                user_query = user_raw

            # Get decisions from model
            decisions = FirstLayerDMM(user_query)
            safe_print("MODEL", f"Decisions: {decisions}")

            # Process each action sequentially
            for act in decisions:
                act = act.strip()
                if not act:
                    continue
                result = handle_action(act, user_query)
                if result == "EXIT":
                    raise KeyboardInterrupt
                # small delay between actions
                time.sleep(0.3)

        except KeyboardInterrupt:
            safe_print("SYSTEM", "Shutting down Jarvis. Goodbye!")
            break
        except Exception as e:
            safe_print("ERROR", f"Main loop error: {e}")
            # continue main loop

    # cleanup
    try:
        if speech_system:
            speech_system.cleanup()
    except Exception:
        pass

if __name__ == "__main__":
    main()
