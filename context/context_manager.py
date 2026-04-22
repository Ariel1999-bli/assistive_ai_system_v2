import time
import config


class ContextManager:
    """
    Context Manager fusionné :
    - filtre le spam final
    - accepte aussi les messages du narrator
    - ralentit légèrement les descriptions globales
    - réduit les répétitions de Close... et Two persons...
    """

    def __init__(self):
        self.last_message = None
        self.last_message_time = 0.0

        self.last_scene_signature = None
        self.pending_scene_signature = None
        self.pending_scene_since = None

        self.MIN_SPEAK_INTERVAL = config.CTX_MIN_SPEAK_INTERVAL
        self.SAME_MESSAGE_INTERVAL = config.CTX_SAME_MESSAGE_INTERVAL
        self.SCENE_STABILITY_TIME = config.CTX_SCENE_STABILITY_TIME
        self.NARRATION_EXTRA_DELAY = config.CTX_NARRATION_EXTRA_DELAY

        self.last_priority = 0
        self.has_spoken_once = False

    # ------------------------------------------------------
    # Priorité message
    # ------------------------------------------------------
    def _message_priority(self, message: str) -> int:
        if not message:
            return 0

        msg = message.lower()

        if "warning" in msg:
            return 4

        if "very close" in msg:
            return 4

        if "close" in msg:
            return 3

        if "two persons" in msg:
            return 3

        if "approaching" in msg:
            return 3

        if "person" in msg or "clear" in msg:
            return 2

        if msg.startswith("scene:"):
            return 1

        return 1

    def _is_narration_message(self, message: str) -> bool:
        if not message:
            return False
        return message.lower().startswith("scene:")

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
            proximity = round(obj.get("proximity_score", 0.0), 1)

            if label == "person":
                persons.append((direction, proximity))
            else:
                others.append((label, direction))

        persons.sort()
        others.sort()

        return (tuple(persons), tuple(others[:3]))

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
    # Commit
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
        is_narration = self._is_narration_message(message)
        lowered = message.lower()

        if not self.has_spoken_once:
            self.has_spoken_once = True
            self._commit(message, scene_signature, priority, now)
            return message

        # warnings critiques
        if priority >= 4:
            if (
                message == self.last_message
                and (now - self.last_message_time) < 2.2
            ):
                return None

            self._commit(message, scene_signature, priority, now)
            return message

        # close / two persons / approaching
        if priority >= 3 and not is_narration:
            repeat_block = 2.2

            if lowered.startswith("two persons"):
                repeat_block = 4.0
            elif lowered.startswith("close"):
                repeat_block = 2.8
            elif "approaching" in lowered:
                repeat_block = 2.3

            if (
                message == self.last_message
                and scene_signature == self.last_scene_signature
                and (now - self.last_message_time) < repeat_block
            ):
                return None

            # si la scène n'a pas bougé du tout, on calme encore plus
            if (
                message == self.last_message
                and scene_signature == self.last_scene_signature
                and (now - self.last_message_time) < (repeat_block + 0.8)
            ):
                return None

            self._commit(message, scene_signature, priority, now)
            return message

        # stabilisation légère
        if not self.is_scene_stable(scene_signature):
            return None

        # délai supplémentaire pour la narration globale
        if is_narration:
            if (now - self.last_message_time) < (self.MIN_SPEAK_INTERVAL + self.NARRATION_EXTRA_DELAY):
                return None

        # anti-répétition général
        if (
            scene_signature == self.last_scene_signature
            and message == self.last_message
            and (now - self.last_message_time) < self.SAME_MESSAGE_INTERVAL
        ):
            return None

        # cooldown global
        if (now - self.last_message_time) < self.MIN_SPEAK_INTERVAL:
            if priority <= self.last_priority:
                return None

        self._commit(message, scene_signature, priority, now)
        return message