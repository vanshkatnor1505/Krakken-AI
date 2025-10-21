import pygame
import asyncio
import edge_tts
import os
import threading
import time
import uuid

POST_PLAYBACK_DELAY = 0.05  # 50 ms
tts_is_playing = threading.Event()

DATA_DIR = os.path.join(os.path.dirname(__file__), "Data")
os.makedirs(DATA_DIR, exist_ok=True)

pygame.mixer.init()
playback_thread = None
playback_stop_event = threading.Event()

def generate_unique_filepath():
    return os.path.join(DATA_DIR, f"speech_{uuid.uuid4().hex}.mp3")

async def create_tts_audio(text, filepath):
    AssistantVoice = "en-CA-LiamNeural"  # or load from .env as before
    communicate = edge_tts.Communicate(text, AssistantVoice, pitch='+5Hz', rate='+13%')
    await communicate.save(filepath)

def play_audio(filepath, stop_event, on_complete=None):
    try:
        if pygame.mixer.music.get_busy():
            pygame.mixer.music.stop()
        pygame.mixer.music.load(filepath)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            if stop_event.is_set():
                pygame.mixer.music.stop()
                break
            pygame.time.Clock().tick(30)
    except Exception as e:
        print(f"Playback error: {e}")
    finally:
        time.sleep(POST_PLAYBACK_DELAY)
        try:
            if pygame.mixer.get_init():
                pygame.mixer.music.unload()
        except Exception as e:
            print(f"Failed to unload music: {e}")
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except Exception as e:
            print(f"Failed to delete audio file {filepath}: {e}")
        if on_complete:
            on_complete()

def TTS(text, func=lambda: True, on_complete=None):
    global playback_thread, playback_stop_event, tts_is_playing

    if tts_is_playing.is_set():
        print("TTS is already playing; skipping this request.")
        return False

    try:
        tts_is_playing.set()

        if playback_thread and playback_thread.is_alive():
            playback_stop_event.set()
            playback_thread.join()

        playback_stop_event = threading.Event()
        audio_file = generate_unique_filepath()

        try:
            asyncio.run(create_tts_audio(text, audio_file))
        except Exception as e:
            print(f"Error generating speech: {e}")
            return False

        playback_thread = threading.Thread(target=play_audio, args=(audio_file, playback_stop_event, on_complete))
        playback_thread.start()

        while playback_thread.is_alive():
            if func() is False:
                playback_stop_event.set()
                playback_thread.join()
                break
            pygame.time.Clock().tick(30)

        return True
    finally:
        tts_is_playing.clear()

def TextToSpeech(text, on_complete=None):
    TTS(text, on_complete=on_complete)
