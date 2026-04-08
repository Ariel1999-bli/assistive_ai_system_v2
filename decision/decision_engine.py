import time
import config


class DecisionEngine:

    def __init__(self):
        self.last_global_message = None
        self.last_global_time = 0.0

        self.global_cooldown = 0.8
        self.same_message_cooldown = 2.5
        self.long_reannounce_cooldown = 6.0
        self.silence_after_speak = 1.5

        self.current_focus_id = None
        self.focus_locked_until = 0.0
        self.focus_lock_duration = 2.5

        # 🔥 MULTI PERSON STABILITY
        self.multi_person_anchor = None
        self.multi_person_anchor_until = 0.0
        self.multi_person_anchor_duration = 5.0

    # =========================================================
    # NORMALISATION
    # =========================================================
    def _normalize_objects(self, objects):
        if objects is None:
            return []

        if isinstance(objects, dict):
            candidates = list(objects.values())
        elif isinstance(objects, list):
            candidates = objects
        else:
            return []

        return [o for o in candidates if isinstance(o, dict) and "label" in o]

    def _compute_size(self, obj):
        bbox = obj.get("bbox")
        if not bbox or len(bbox) != 4:
            return 0.0
        x1, y1, x2, y2 = bbox
        return max(0.0, x2 - x1) * max(0.0, y2 - y1)

    def _priority_key(self, obj):
        label = obj.get("label", "")
        proximity = obj.get("proximity_score", 0.0)
        size = self._compute_size(obj)

        if label == "person":
            return (100, proximity, size)

        return (config.OBJECT_PRIORITIES.get(label, 0), proximity, size)

    def _filter_semantic_objects(self, visible_objects):
        return [
            obj for obj in visible_objects
            if obj.get("label") not in config.IGNORE_OBJECTS
        ]

    # =========================================================
    # HELPERS
    # =========================================================
    def _pretty_label(self, label):
        return label.replace("_", " ")

    def _direction_rank(self, d):
        return {"left": 0, "center": 1, "right": 2}.get(d, 1)

    def _get_visible_people(self, objs):
        return [o for o in objs if o.get("label") == "person"]

    def _is_close_object(self, obj):
        if obj.get("label") == "person":
            return obj.get("proximity_score", 0) >= config.PERSON_CLOSE_THRESHOLD
        return obj.get("proximity_score", 0) >= config.OBJECT_CLOSE_THRESHOLD

    # =========================================================
    # MULTI PERSON MESSAGE
    # =========================================================
    def _build_multi_person_message(self, people):

        people = sorted(
            people,
            key=lambda o: (
                self._direction_rank(o.get("direction")),
                -o.get("proximity_score", 0)
            )
        )

        d1 = people[0].get("direction")
        d2 = people[1].get("direction")

        # 👉 SIMPLIFICATION VOLONTAIRE (clé UX)
        if d1 == "center" or d2 == "center":
            return "Two persons ahead"

        if d1 == "left" and d2 == "right":
            return "Two persons, one on your left and one on your right"

        return "Two persons ahead"

    # =========================================================
    # MESSAGE BUILD
    # =========================================================
    def _build_initial_message(self, obj):
        label = self._pretty_label(obj.get("label"))
        direction = obj.get("direction", "center")

        if direction == "center":
            return f"{label} ahead"
        return f"{label} on your {direction}"

    def _build_update_message(self, obj):

        if obj.get("state") == "APPROACHING":
            if obj.get("label") != "person":
                return None

            if not self._is_close_object(obj):
                return None

            direction = obj.get("direction", "center")

            if direction == "center":
                return "Close ahead"
            return f"Close on your {direction}"

        return None

    def _build_clear_message(self, obj):
        if obj.get("label") == "person":
            return "Clear"
        return None

    # =========================================================
    # CONTROLES
    # =========================================================
    def _can_emit_globally(self, message, now):

        if (now - self.last_global_time) < self.silence_after_speak:
            return False

        if (now - self.last_global_time) < self.global_cooldown:
            return False

        if message == self.last_global_message:
            if (now - self.last_global_time) < self.same_message_cooldown:
                return False

        return True

    def _can_emit_for_object(self, obj, message, now):

        if obj.get("state") == "STABLE":
            return False

        if obj.get("last_announcement") != message:
            return True

        return (now - obj.get("last_announcement_time", 0)) > self.long_reannounce_cooldown

    # =========================================================
    # FOCUS
    # =========================================================
    def _select_focus_object(self, visible_objects, now):

        if self.current_focus_id and now <= self.focus_locked_until:
            for obj in visible_objects:
                if obj.get("id") == self.current_focus_id:
                    return obj

        obj = visible_objects[0]
        self.current_focus_id = obj.get("id")
        self.focus_locked_until = now + self.focus_lock_duration
        return obj

    # =========================================================
    # MAIN
    # =========================================================
    def decide(self, objects):

        now = time.time()
        objects = self._normalize_objects(objects)

        if not objects:
            return []

        visible = [o for o in objects if o.get("missing_frames", 0) == 0]
        visible = self._filter_semantic_objects(visible)

        if not visible:
            return []

        visible = sorted(visible, key=self._priority_key, reverse=True)

        # =====================================================
        # 🔥 MULTI PERSON FINAL (STABLE)
        # =====================================================
        people = self._get_visible_people(visible)

        if len(people) >= 2:

            # 🔒 maintien du message pendant X secondes
            if now < self.multi_person_anchor_until:
                return []

            message = self._build_multi_person_message(people)

            if message == self.multi_person_anchor:
                return []

            if self._can_emit_globally(message, now):

                self.multi_person_anchor = message
                self.multi_person_anchor_until = now + self.multi_person_anchor_duration

                self.last_global_message = message
                self.last_global_time = now

                return [message]

            return []

        # =====================================================
        # SINGLE OBJECT
        # =====================================================
        obj = self._select_focus_object(visible, now)

        if obj is None:
            return []

        state = obj.get("state")

        if state == "NEW":
            if not obj.get("already_announced"):
                msg = self._build_initial_message(obj)
            else:
                return []

        elif state == "APPROACHING":
            msg = self._build_update_message(obj)

        elif state == "GONE":
            msg = self._build_clear_message(obj)

        else:
            return []

        if not msg:
            return []

        if not self._can_emit_for_object(obj, msg, now):
            return []

        if not self._can_emit_globally(msg, now):
            return []

        obj["already_announced"] = True
        obj["last_announcement"] = msg
        obj["last_announcement_time"] = now

        self.last_global_message = msg
        self.last_global_time = now

        return [msg]