import time


class ContextManager:
    """
    V2 intelligente :
    - filtre le spam
    - laisse passer les vrais changements
    - prend en compte personnes + directions
    - moins rigide que la version précédente
    """

    def __init__(self):
        self.last_message = None
        self.last_message_time = 0.0

        self.last_scene_signature = None
        self.pending_scene_signature = None
        self.pending_scene_since = None

        self.MIN_SPEAK_INTERVAL = 1.0
        self.SAME_MESSAGE_INTERVAL = 2.5
        self.SCENE_STABILITY_TIME = 0.35

        self.last_priority = 0
        self.has_spoken_once = False

    # ------------------------------------------------------
    # Priority
    # ------------------------------------------------------
    def _message_priority(self, message: str) -> int:
        if not message:
            return 0

        msg = message.lower()

        if "close" in msg:
            return 4

        if "two persons" in msg or "person ahead and another" in msg:
            return 4

        if "person" in msg:
            return 3

        if "clear" in msg:
            return 3

        return 1

    # ------------------------------------------------------
    # Scene signature
    # ------------------------------------------------------
    def build_scene_signature(self, objects):
        if objects is None:
            return tuple()

        persons = []
        others = []

        for obj in objects:
            if not isinstance(obj, dict):
                continue
            if obj.get("missing_frames", 0) > 0:
                continue

            label = obj.get("label", "")
            direction = obj.get("direction", "center")
            proximity_bucket = self._proximity_bucket(obj.get("proximity_score", 0.0))

            if label == "person":
                persons.append((direction, proximity_bucket))
            else:
                others.append((label, direction))

        persons.sort()
        others.sort()

        return (tuple(persons), tuple(others[:2]))

    def _proximity_bucket(self, proximity_score):
        if proximity_score >= 0.85:
            return "very_close"
        if proximity_score >= 0.72:
            return "close"
        if proximity_score >= 0.45:
            return "medium"
        return "far"

    # ------------------------------------------------------
    # Stability
    # ------------------------------------------------------
    def is_scene_stable(self, new_scene_signature):
        now = time.time()

        if self.pending_scene_signature != new_scene_signature:
            self.pending_scene_signature = new_scene_signature
            self.pending_scene_since = now
            return False

        if self.pending_scene_since is None:
            self.pending_scene_since = now
            return False

        return (now - self.pending_scene_since) >= self.SCENE_STABILITY_TIME

    # ------------------------------------------------------
    # Main
    # ------------------------------------------------------
    def process(self, objects, message):
        now = time.time()

        if not message:
            return None

        scene_signature = self.build_scene_signature(objects)
        priority = self._message_priority(message)

        # premier message
        if not self.has_spoken_once:
            self.has_spoken_once = True
            self.last_message = message
            self.last_message_time = now
            self.last_scene_signature = scene_signature
            self.last_priority = priority
            return message

        # messages très importants passent plus facilement
        if priority >= 4:
            if (
                message == self.last_message
                and scene_signature == self.last_scene_signature
                and (now - self.last_message_time) < 1.8
            ):
                return None

            self.last_message = message
            self.last_message_time = now
            self.last_scene_signature = scene_signature
            self.last_priority = priority
            return message

        # stabilisation légère
        if not self.is_scene_stable(scene_signature):
            return None

        # anti-répétition
        if (
            message == self.last_message
            and scene_signature == self.last_scene_signature
            and (now - self.last_message_time) < self.SAME_MESSAGE_INTERVAL
        ):
            return None

        # cooldown global
        if (now - self.last_message_time) < self.MIN_SPEAK_INTERVAL:
            if priority <= self.last_priority:
                return None

        self.last_message = message
        self.last_message_time = now
        self.last_scene_signature = scene_signature
        self.last_priority = priority

        return message