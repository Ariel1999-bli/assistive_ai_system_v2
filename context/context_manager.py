import time


class ContextManager:
    """
    Context Manager v2.1

    Rôle :
    - filtrer le spam final
    - laisser passer les messages utiles
    - ne pas devenir trop silencieux
    - ne pas modifier le sens du message
    """

    def __init__(self):
        self.last_message = None
        self.last_message_time = 0.0

        self.last_scene_signature = None
        self.pending_scene_signature = None
        self.pending_scene_since = None

        self.MIN_SPEAK_INTERVAL = 1.2
        self.SAME_MESSAGE_INTERVAL = 3.0
        self.SCENE_STABILITY_TIME = 0.5

        self.last_priority = 0
        self.has_spoken_once = False

    # ------------------------------------------------------
    # Priorité message
    # ------------------------------------------------------
    def _message_priority(self, message: str) -> int:
        if not message:
            return 0

        msg = message.lower()

        if "close" in msg:
            return 3

        if "two persons" in msg:
            return 3

        if "person" in msg or "clear" in msg:
            return 2

        return 1

    # ------------------------------------------------------
    # Signature scène
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

            if label == "person":
                persons.append(direction)
            else:
                others.append((label, direction))

        persons.sort()
        others.sort()

        return (tuple(persons), tuple(others[:2]))

    # ------------------------------------------------------
    # Stabilité scène
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
    # Mise à jour de l'état interne
    # ------------------------------------------------------
    def _commit(self, message, scene_signature, priority, now):
        self.last_message = message
        self.last_message_time = now
        self.last_scene_signature = scene_signature
        self.last_priority = priority

    # ------------------------------------------------------
    # Process
    # ------------------------------------------------------
    def process(self, objects, message):
        now = time.time()

        if not message:
            return None

        scene_signature = self.build_scene_signature(objects)
        priority = self._message_priority(message)

        # 1. premier message -> autorisé
        if not self.has_spoken_once:
            self.has_spoken_once = True
            self._commit(message, scene_signature, priority, now)
            return message

        # 2. close et two persons : passent plus facilement
        if priority >= 3:
            if (
                message == self.last_message
                and (now - self.last_message_time) < 2.0
            ):
                return None

            self._commit(message, scene_signature, priority, now)
            return message

        # 3. légère stabilisation
        if not self.is_scene_stable(scene_signature):
            return None

        # 4. anti-répétition stricte
        if (
            scene_signature == self.last_scene_signature
            and message == self.last_message
            and (now - self.last_message_time) < self.SAME_MESSAGE_INTERVAL
        ):
            return None

        # 5. cooldown global
        if (now - self.last_message_time) < self.MIN_SPEAK_INTERVAL:
            if priority <= self.last_priority:
                return None

        self._commit(message, scene_signature, priority, now)
        return message