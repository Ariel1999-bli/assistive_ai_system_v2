from audio.audio_engine import AudioEngine
import time

audio = AudioEngine()

audio.speak("Test one")
time.sleep(2)

audio.speak("Test two")
time.sleep(2)

audio.speak("Left")
time.sleep(2)

audio.stop()