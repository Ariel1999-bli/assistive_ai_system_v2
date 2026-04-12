import queue
import threading
import time

import pyttsx3
import config


class AudioEngine:
    """
    Moteur audio robuste pour Windows.
    - file d'attente audio
    - thread dédié
    - nouvelle instance pyttsx3 par message
    """

    def __init__(self):
        self.queue = queue.Queue(maxsize=5)
        self.running = True

        self.last_spoken_message = None
        self.last_spoken_time = 0.0

        self.worker = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker.start()

    def speak(self, message: str):
        """
        Ajoute un message à la file audio.
        """
        if not message:
            return

        message = message.strip()
        if not message:
            return

        try:
            if self.queue.full():
                self._drain_queue()

            self.queue.put_nowait(message)
            print(f"[AUDIO_QUEUE] {message}")
        except queue.Full:
            print(f"[AUDIO_DROP] {message}")

    def _drain_queue(self) -> str | None:
        """
        Vide la file et retourne le dernier message (le plus récent), ou None.
        Utilisé à deux endroits : avant ajout si pleine, et dans le worker.
        """
        latest = None
        while not self.queue.empty():
            try:
                latest = self.queue.get_nowait()
                self.queue.task_done()
            except (queue.Empty, ValueError):
                break
        return latest

    def _can_speak(self, message: str, now: float) -> bool:
        """
        Anti-répétition très simple.
        """
        if now - self.last_spoken_time < config.SPEAK_COOLDOWN:
            return False

        if self.last_spoken_message == message and (now - self.last_spoken_time) < 1.2:
            return False

        return True

    def _speak_once(self, message: str):
        """
        Lecture réelle d'un message avec une instance pyttsx3 fraîche.
        """
        engine = None
        try:
            engine = pyttsx3.init()
            engine.setProperty("rate", config.TTS_RATE)
            engine.setProperty("volume", 1.0)

            print(f"[AUDIO_SPEAK] {message}")
            engine.say(message)
            engine.runAndWait()

        except Exception as e:
            print(f"[AUDIO_ERROR] {e}")

        finally:
            if engine is not None:
                try:
                    engine.stop()
                except Exception:
                    pass

    def _worker_loop(self):
        print("[AUDIO] worker started")

        while self.running:
            try:
                message = self.queue.get(timeout=0.1)
            except queue.Empty:
                continue

            try:
                # latest-useful behavior : on garde le plus récent
                latest = self._drain_queue()
                if latest is not None:
                    message = latest
                now = time.time()

                if self._can_speak(message, now):
                    self._speak_once(message)
                    self.last_spoken_message = message
                    self.last_spoken_time = time.time()

            finally:
                try:
                    self.queue.task_done()
                except ValueError:
                    pass

        print("[AUDIO] worker stopped")

    def stop(self):
        self.running = False
        if self.worker.is_alive():
            self.worker.join(timeout=2.0)