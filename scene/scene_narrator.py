import threading
import time
from collections import Counter

import config

# Moondream2 chargé une seule fois au démarrage si VLM_ENABLED
_moondream_model = None
_moondream_tokenizer = None


def _load_moondream():
    global _moondream_model, _moondream_tokenizer
    if _moondream_model is not None:
        return True
    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer
        model_id = "vikhyatk/moondream2"
        revision = "2025-01-09"
        print("[VLM] Chargement de Moondream2...")
        _moondream_tokenizer = AutoTokenizer.from_pretrained(
            model_id, revision=revision
        )
        _moondream_model = AutoModelForCausalLM.from_pretrained(
            model_id,
            revision=revision,
            trust_remote_code=True,
        )
        _moondream_model.eval()
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

            # Encode l'image
            image_embeds = _moondream_model.encode_image(pil_image)

            # Requête orientée navigation pour malvoyant
            prompt = (
                "I am a visually impaired person wearing smart glasses. "
                "In one short sentence, describe only what is directly in front of me "
                "that I should be aware of to move safely."
            )

            answer = _moondream_model.answer_question(
                image_embeds,
                prompt,
                _moondream_tokenizer,
            )

            return answer.strip() if answer else None

        except Exception as e:
            print(f"[VLM_ERROR] {e}")
            return None

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
