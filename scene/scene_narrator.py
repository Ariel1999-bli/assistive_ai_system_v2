import threading
import time
from collections import Counter

import config

DANGER_KEYWORDS = {
    "car", "truck", "bus", "motorcycle", "bicycle", "bike",
    "dog", "stairs", "step", "hole", "crowd", "traffic",
    "road", "street", "vehicle", "obstacle"
}

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
                _moondream_model = md.vl(
                    local=True,
                    model="moondream-2b-int8",
                    device=device
                )
                print(f"[VLM] Moondream2 prêt sur {device.upper()}.")
                break
            except Exception:
                if device == "cuda":
                    print("[VLM] GPU indisponible, essai CPU...")
                else:
                    raise
        return True
    except Exception as e:
        print(f"[VLM] Erreur chargement Moondream2 : {e}")
        return False


class SceneNarrator:
    """
    Narrateur de scène périodique fusionné.

    Objectif ici :
    - parler moins pendant les transitions
    - attendre une scène plus stable
    - éviter les descriptions trop nerveuses pendant les mouvements caméra
    """

    def __init__(self):
        self.running = True

        self._last_frame = None
        self._last_objects = {}
        self._lock = threading.Lock()

        self._last_spoken = ""
        self._pending_message = None
        self._last_run_time = 0.0
        self._last_emit_time = 0.0

        # stabilité narrateur
        self._candidate_description = None
        self._candidate_since = 0.0
        self._candidate_count = 0

        self._thread = threading.Thread(target=self._narrator_loop, daemon=True)
        self._thread.start()

    # ------------------------------------------------------------------
    # API appelée depuis main.py
    # ------------------------------------------------------------------
    def update(self, frame, objects: dict) -> None:
        with self._lock:
            self._last_frame = frame.copy() if frame is not None else None
            self._last_objects = dict(objects)

    def get_message(self):
        with self._lock:
            message = self._pending_message
            self._pending_message = None
            return message

    # ------------------------------------------------------------------
    # Outils
    # ------------------------------------------------------------------
    def _direction_phrase(self, prefix: str, obj: dict) -> str:
        direction = obj.get("direction", "center")
        if direction == "center":
            return f"{prefix} ahead"
        return f"{prefix} on your {direction}"

    def _is_danger(self, description: str) -> bool:
        words = description.lower().split()
        return any(w.strip(".,:;!?") in DANGER_KEYWORDS for w in words)

    def _has_changed(self, current: str) -> bool:
        if not self._last_spoken:
            return True

        prev_words = set(self._last_spoken.lower().split())
        curr_words = set(current.lower().split())

        if not prev_words or not curr_words:
            return True

        similarity = len(prev_words & curr_words) / len(prev_words | curr_words)
        return similarity < config.NARRATOR_JACCARD_THRESHOLD

    def _is_human_warning_candidate(self, obj: dict) -> bool:
        """
        Pour une personne, on évite un ton trop alarmiste.
        On n'émet un warning humain que si la proximité / risque est vraiment marquée.
        """
        if obj.get("label") != "person":
            return False

        proximity = obj.get("proximity_score", 0.0)
        risk = obj.get("risk_score", 0.0)
        state = obj.get("state", "")

        return (
            proximity >= max(0.82, config.PERSON_CLOSE_THRESHOLD + 0.08)
            and risk >= config.RISK_HIGH_THRESHOLD
            and state == "APPROACHING"
        )

    def _candidate_is_stable_enough(self, description: str, now: float) -> bool:
        """
        La narration ordinaire doit confirmer la même description plusieurs fois
        et durer un petit temps avant émission.
        """
        if description != self._candidate_description:
            self._candidate_description = description
            self._candidate_since = now
            self._candidate_count = 1
            return False

        self._candidate_count += 1

        stable_time = now - self._candidate_since
        if (
            self._candidate_count >= config.NARRATOR_PENDING_CONFIRMATIONS
            and stable_time >= config.NARRATOR_STABILITY_REQUIRED
        ):
            return True

        return False

    def _reset_candidate(self):
        self._candidate_description = None
        self._candidate_since = 0.0
        self._candidate_count = 0

    # ------------------------------------------------------------------
    # Description rule-based
    # ------------------------------------------------------------------
    def _build_rule_description(self, objects: dict):
        visible = [
            o for o in objects.values()
            if o.get("missing_frames", 0) == 0
        ]

        if not visible:
            return None

        # 1. Danger non-humain prioritaire
        dangerous_non_humans = sorted(
            [
                o for o in visible
                if o.get("risk_score", 0.0) >= config.RISK_HIGH_THRESHOLD
                and o.get("label") != "person"
            ],
            key=lambda o: o.get("risk_score", 0.0),
            reverse=True
        )

        if dangerous_non_humans:
            obj = dangerous_non_humans[0]
            label = obj.get("label", "object")
            return f"Warning: {self._direction_phrase(label, obj)}"

        # 2. Cas humain proche : plus naturel, moins alarmiste
        dangerous_humans = sorted(
            [o for o in visible if self._is_human_warning_candidate(o)],
            key=lambda o: o.get("risk_score", 0.0),
            reverse=True
        )
        if dangerous_humans:
            obj = dangerous_humans[0]
            return f"Person very close {('ahead' if obj.get('direction', 'center') == 'center' else 'on your ' + obj.get('direction', 'center'))}"

        counts = Counter(o["label"] for o in visible)
        parts = []

        def first_by_label(label: str):
            for item in visible:
                if item["label"] == label:
                    return item
            return None

        # 3. Personnes seulement si scène globale
        n_persons = counts.get("person", 0)
        if n_persons >= 2:
            parts.append(f"{n_persons} persons around you")

        # 4. Autres objets importants
        sorted_visible = sorted(
            visible,
            key=lambda o: (
                o.get("label") == "person",
                o.get("risk_score", 0.0),
                o.get("proximity_score", 0.0)
            ),
            reverse=True
        )

        seen_labels = {"person"}
        for obj in sorted_visible:
            label = obj.get("label", "")
            if label in seen_labels:
                continue

            if label not in config.IMPORTANT_OBJECTS:
                continue

            parts.append(self._direction_phrase(f"a {label}", obj))
            seen_labels.add(label)

            if len(parts) >= 3:
                break

        # si un seul élément → doublon probable avec DecisionEngine
        if len(parts) < config.NARRATOR_MIN_PARTS:
            return None

        return "Scene: " + ", ".join(parts)

    # ------------------------------------------------------------------
    # Description VLM
    # ------------------------------------------------------------------
    def _build_vlm_description(self, frame):
        if not _load_moondream():
            return None

        try:
            import cv2
            from PIL import Image

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(rgb)

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
    # Boucle de fond
    # ------------------------------------------------------------------
    def _narrator_loop(self):
        print("[NARRATOR] started")

        while self.running:
            time.sleep(0.2)

            now = time.time()

            # fréquence de travail
            if (now - self._last_run_time) < config.VLM_NARRATOR_INTERVAL:
                continue

            # petit délai supplémentaire après une narration
            if (now - self._last_emit_time) < config.NARRATOR_POST_SPEAK_GRACE:
                continue

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

            self._last_run_time = now

            if not description:
                self._reset_candidate()
                continue

            danger = self._is_danger(description)
            changed = self._has_changed(description)

            # danger : peut passer plus vite
            if danger:
                with self._lock:
                    self._pending_message = description
                self._last_spoken = description
                self._last_emit_time = now
                self._reset_candidate()
                print(f"[NARRATOR GENERATED] {description}")
                continue

            # narration normale : attendre stabilité + changement réel
            if not changed:
                self._reset_candidate()
                print("[NARRATOR] muet — scène stable")
                continue

            if self._candidate_is_stable_enough(description, now):
                with self._lock:
                    self._pending_message = description
                self._last_spoken = description
                self._last_emit_time = now
                self._reset_candidate()
                print(f"[NARRATOR GENERATED] {description}")
            else:
                print("[NARRATOR] attente stabilisation narration")

        print("[NARRATOR] stopped")

    def stop(self):
        self.running = False