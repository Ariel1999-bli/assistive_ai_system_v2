import threading
import time
from collections import Counter

import config

# Mots-clés déclenchant une alerte immédiate (danger potentiel)
DANGER_KEYWORDS = {
    "car", "truck", "bus", "motorcycle", "bicycle", "bike",
    "dog", "stairs", "step", "hole", "crowd", "traffic",
    "road", "street", "vehicle", "obstacle"
}

# Moondream2 chargé une seule fois au démarrage si VLM_ENABLED
_moondream_model = None


def _load_moondream():
    global _moondream_model
    if _moondream_model is not None:
        return True

    try:
        import moondream as md
    except ImportError:
        print("[VLM] moondream non installé → VLM désactivé.")
        return False

    try:
        print("[VLM] Chargement de Moondream2...")
        for device in ("cuda", "cpu"):
            try:
                _moondream_model = md.vl(local=True, model="moondream-2b-int8", device=device)
                print(f"[VLM] Moondream2 prêt sur {device.upper()}.")
                break
            except Exception as e:
                if device == "cuda":
                    print(f"[VLM] GPU indisponible, essai CPU...")
                else:
                    raise
        print("[VLM] Moondream2 prêt.")
        return True
    except Exception as e:
        print(f"[VLM] Erreur chargement Moondream2 : {e}")
        return False


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

        self._last_spoken = ""  # dernière description prononcée

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

        def _direction_phrase(prefix: str, obj: dict) -> str:
            d = obj.get("direction", "center")
            return f"{prefix} ahead" if d == "center" else f"{prefix} on your {d}"

        def _first_by_label(label: str) -> dict:
            return next(o for o in visible if o["label"] == label)

        # Personnes en premier
        n_persons = counts.get("person", 0)
        if n_persons == 1:
            parts.append(_direction_phrase("one person", _first_by_label("person")))
        elif n_persons > 1:
            parts.append(f"{n_persons} persons around you")

        # Autres objets importants (max 2 pour ne pas surcharger)
        for label, count in counts.items():
            if label == "person" or len(parts) >= 3:
                continue
            if count == 1:
                parts.append(_direction_phrase(f"a {label}", _first_by_label(label)))
            else:
                parts.append(f"{count} {label}s nearby")

        if not parts:
            return None

        return "Scene: " + ", ".join(parts)

    # ------------------------------------------------------------------
    # Description VLM — Moondream2
    # ------------------------------------------------------------------
    def _build_vlm_description(self, frame) -> str | None:
        """
        Génère une description de scène via Moondream2.
        Activer avec VLM_ENABLED = True dans config.py.
        Nécessite ~1.7GB RAM supplémentaire.
        """
        if not _load_moondream():
            return None

        try:
            import cv2
            from PIL import Image

            # Convertir la frame OpenCV (BGR) en PIL Image (RGB)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(rgb)

            # Encode l'image et interroge le modèle
            encoded = _moondream_model.encode_image(pil_image)
            prompt = (
                "I am a visually impaired person wearing smart glasses. "
                "In one short sentence, describe only what is directly in front of me "
                "that I should be aware of to move safely."
            )
            answer = _moondream_model.query(encoded, prompt)["answer"]
            return answer.strip() if answer else None

        except Exception as e:
            print(f"[VLM_ERROR] {e}")
            return None

    # ------------------------------------------------------------------
    # Filtrage intelligent
    # ------------------------------------------------------------------
    def _is_danger(self, description: str) -> bool:
        words = description.lower().split()
        return any(w in DANGER_KEYWORDS for w in words)

    def _has_changed(self, current: str) -> bool:
        """True si la scène a significativement changé (similarité Jaccard < 60%)."""
        if not self._last_spoken:
            return True
        prev_words = set(self._last_spoken.lower().split())
        curr_words = set(current.lower().split())
        if not prev_words or not curr_words:
            return True
        similarity = len(prev_words & curr_words) / len(prev_words | curr_words)
        return similarity < 0.6

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

            if not description:
                continue

            danger = self._is_danger(description)
            changed = self._has_changed(description)

            if danger or changed:
                print(f"[NARRATOR] {description}" + (" ⚠ DANGER" if danger else ""))
                self._last_spoken = description
                self.audio.speak(description)
            else:
                print(f"[NARRATOR] muet — scène stable")

        print("[NARRATOR] stopped")

    def stop(self) -> None:
        self.running = False
