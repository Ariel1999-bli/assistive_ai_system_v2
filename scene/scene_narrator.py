import threading
import time
from collections import Counter

import config


class SceneNarrator:
    """
    Narrateur de scène périodique.

    Toutes les VLM_NARRATOR_INTERVAL secondes, génère une description
    globale de la scène et l'envoie à l'AudioEngine.

    Deux modes :
    - Règles (défaut) : description construite à partir des objets trackés.
    - VLM (VLM_ENABLED=True) : délègue à un modèle vision-langage.
      → Brancher un modèle local ici (ex. Moondream2, MobileVLM)
        quand le hardware Hailo-8 / RPi5 est prêt.
    """

    def __init__(self, audio_engine):
        self.audio = audio_engine
        self.running = True

        self._last_frame = None
        self._last_objects = {}
        self._lock = threading.Lock()

        self._thread = threading.Thread(target=self._narrator_loop, daemon=True)
        self._thread.start()

    # ------------------------------------------------------------------
    # API principale (appelée chaque frame depuis main.py)
    # ------------------------------------------------------------------
    def update(self, frame, objects: dict) -> None:
        with self._lock:
            self._last_frame = frame
            self._last_objects = dict(objects)

    # ------------------------------------------------------------------
    # Description par règles
    # ------------------------------------------------------------------
    def _build_rule_description(self, objects: dict) -> str | None:
        visible = [
            o for o in objects.values()
            if o.get("missing_frames", 0) == 0
        ]
        if not visible:
            return None

        counts = Counter(o["label"] for o in visible)
        parts = []

        # Personnes en premier
        n_persons = counts.get("person", 0)
        if n_persons == 1:
            person = next(o for o in visible if o["label"] == "person")
            d = person.get("direction", "center")
            parts.append("one person ahead" if d == "center" else f"one person on your {d}")
        elif n_persons > 1:
            parts.append(f"{n_persons} persons around you")

        # Autres objets importants (max 2 pour ne pas surcharger)
        for label, count in counts.items():
            if label == "person" or len(parts) >= 3:
                continue
            obj = next(o for o in visible if o["label"] == label)
            d = obj.get("direction", "center")
            if count == 1:
                parts.append(f"a {label} ahead" if d == "center" else f"a {label} on your {d}")
            else:
                parts.append(f"{count} {label}s nearby")

        if not parts:
            return None

        return "Scene: " + ", ".join(parts)

    # ------------------------------------------------------------------
    # Description VLM (à implémenter quand le hardware est disponible)
    # ------------------------------------------------------------------
    def _build_vlm_description(self, frame) -> str | None:
        """
        Intégration VLM — remplacer ce stub par l'appel au modèle.

        Exemples de modèles compatibles RPi5 + Hailo-8 :
        - Moondream2 (1.7B) via llama.cpp
        - MobileVLM 1.7B
        - LLaVA-Phi 3B (quantisé 4-bit)

        Exemple d'appel (à décommenter et adapter) :
            response = vlm_model.query(
                frame,
                "Describe what is directly in front of me in one short sentence."
            )
            return response
        """
        return None  # stub : pas encore implémenté

    # ------------------------------------------------------------------
    # Boucle de fond
    # ------------------------------------------------------------------
    def _narrator_loop(self) -> None:
        print("[NARRATOR] started")

        while self.running:
            time.sleep(config.VLM_NARRATOR_INTERVAL)

            with self._lock:
                frame = self._last_frame
                objects = dict(self._last_objects)

            if frame is None:
                continue

            description = None

            if config.VLM_ENABLED:
                description = self._build_vlm_description(frame)

            if description is None:
                description = self._build_rule_description(objects)

            if description:
                print(f"[NARRATOR] {description}")
                self.audio.speak(description)

        print("[NARRATOR] stopped")

    def stop(self) -> None:
        self.running = False
