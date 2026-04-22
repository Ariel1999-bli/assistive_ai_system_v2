import time
from collections import Counter


class EnvironmentChangeDetector:
    """
    Détecteur léger de changement d'environnement (EAD simplifié).

    Rôle :
    - observer la scène sur plusieurs cycles
    - éviter de considérer les micro-variations comme de vrais changements
    - fournir un signal simple :
        * scene_changed
        * scene_stable
        * current_signature
    """

    def __init__(self):
        self.last_confirmed_signature = None

        self.pending_signature = None
        self.pending_since = 0.0
        self.pending_count = 0

        self.min_confirmations = 3
        self.min_stable_time = 0.8

        self.last_change_time = 0.0

    # ---------------------------------------------------------
    # Signature de scène
    # ---------------------------------------------------------
    def _proximity_bucket(self, score: float) -> str:
        if score >= 0.82:
            return "very_close"
        if score >= 0.68:
            return "close"
        if score >= 0.42:
            return "mid"
        return "far"

    def _build_signature(self, objects) -> tuple:
        """
        Signature compacte et robuste de la scène.
        On ne garde que les objets visibles.
        """
        if objects is None:
            return tuple()

        visible = [
            o for o in objects
            if isinstance(o, dict) and o.get("missing_frames", 0) == 0
        ]

        if not visible:
            return tuple()

        people = []
        others = []

        for obj in visible:
            label = obj.get("label", "")
            direction = obj.get("direction", "center")
            prox_bucket = self._proximity_bucket(obj.get("proximity_score", 0.0))

            if label == "person":
                people.append((direction, prox_bucket))
            else:
                others.append((label, direction))

        people.sort()
        others.sort()

        counts = Counter([o.get("label", "") for o in visible])

        # Compte global utile pour stabiliser les cas multi-personnes
        count_signature = tuple(sorted(
            (label, count)
            for label, count in counts.items()
            if count > 0
        ))

        # Limiter le bruit des objets secondaires
        return (
            tuple(people[:3]),
            tuple(others[:3]),
            count_signature
        )

    # ---------------------------------------------------------
    # Logique de confirmation
    # ---------------------------------------------------------
    def update(self, objects):
        now = time.time()
        signature = self._build_signature(objects)

        # première signature connue
        if self.last_confirmed_signature is None:
            self.last_confirmed_signature = signature
            self.pending_signature = signature
            self.pending_since = now
            self.pending_count = 1

            return {
                "scene_changed": True,
                "scene_stable": True,
                "current_signature": signature,
                "last_change_time": now,
            }

        # pas de changement confirmé
        if signature == self.last_confirmed_signature:
            self.pending_signature = signature
            self.pending_since = now
            self.pending_count = 0

            return {
                "scene_changed": False,
                "scene_stable": True,
                "current_signature": signature,
                "last_change_time": self.last_change_time,
            }

        # nouvelle signature candidate
        if signature != self.pending_signature:
            self.pending_signature = signature
            self.pending_since = now
            self.pending_count = 1

            return {
                "scene_changed": False,
                "scene_stable": False,
                "current_signature": signature,
                "last_change_time": self.last_change_time,
            }

        # même signature candidate -> on confirme progressivement
        self.pending_count += 1
        stable_time = now - self.pending_since

        if (
            self.pending_count >= self.min_confirmations
            and stable_time >= self.min_stable_time
        ):
            self.last_confirmed_signature = signature
            self.last_change_time = now

            return {
                "scene_changed": True,
                "scene_stable": True,
                "current_signature": signature,
                "last_change_time": self.last_change_time,
            }

        return {
            "scene_changed": False,
            "scene_stable": False,
            "current_signature": signature,
            "last_change_time": self.last_change_time,
        }