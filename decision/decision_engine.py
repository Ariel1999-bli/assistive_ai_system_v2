import time
import config


class DecisionEngine:
    """
    V2 intelligente :
    - modes : navigation / exploration / human_priority
    - ré-annonce si direction change
    - ré-annonce si proximité change significativement
    - gestion multi-personnes plus dynamique
    """

    def __init__(self):
        self.last_global_message = None
        self.last_global_time = 0.0

        self.global_cooldown = 0.7
        self.same_message_cooldown = 2.0
        self.long_reannounce_cooldown = 3.5
        self.silence_after_speak = 0.8

        self.current_focus_id = None
        self.focus_locked_until = 0.0
        self.focus_lock_duration = 1.5

        self.multi_person_anchor = None
        self.multi_person_anchor_until = 0.0
        self.multi_person_anchor_duration = 1.5

        self.proximity_delta_threshold = 0.08

    # =========================================================
    # NORMALIZATION
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

    # =========================================================
    # MODE LOGIC
    # =========================================================
    def _is_allowed_in_mode(self, obj, mode):
        label = obj.get("label", "")

        if label in config.IGNORE_OBJECTS:
            return False

        if mode == "navigation":
            return label in config.IMPORTANT_OBJECTS

        if mode == "exploration":
            return label in config.EXPLORATION_OBJECTS

        if mode == "human_priority":
            return label in config.EXPLORATION_OBJECTS or label in config.IMPORTANT_OBJECTS

        return label in config.IMPORTANT_OBJECTS

    def _priority_key(self, obj, mode):
        label = obj.get("label", "")
        proximity = obj.get("proximity_score", 0.0)
        size = self._compute_size(obj)

        if label == "person":
            return (100, proximity, size)

        base_priority = config.OBJECT_PRIORITIES.get(label, 0)

        if mode == "exploration":
            return (base_priority, size, proximity)

        return (base_priority, proximity, size)

    def _filter_objects_by_mode(self, visible_objects, mode):
        filtered = [
            obj for obj in visible_objects
            if self._is_allowed_in_mode(obj, mode)
        ]

        if mode == "human_priority":
            people = [o for o in filtered if o.get("label") == "person"]
            if people:
                return people

        return filtered

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
        label = obj.get("label", "")
        proximity = obj.get("proximity_score", 0.0)

        if label == "person":
            return proximity >= config.PERSON_CLOSE_THRESHOLD

        return proximity >= config.OBJECT_CLOSE_THRESHOLD

    def _direction_changed(self, obj):
        current_direction = obj.get("direction", "center")
        previous_direction = obj.get("previous_direction", None)

        if previous_direction is None:
            return False

        return current_direction != previous_direction

    def _proximity_changed_significantly(self, obj):
        current_proximity = obj.get("proximity_score", None)
        previous_proximity = obj.get("previous_proximity_score", None)

        if current_proximity is None or previous_proximity is None:
            return False

        return abs(current_proximity - previous_proximity) >= self.proximity_delta_threshold

    def _has_meaningful_change(self, obj):
        return self._direction_changed(obj) or self._proximity_changed_significantly(obj)

    # =========================================================
    # MULTI PERSON
    # =========================================================
    def _build_multi_person_message(self, people, mode):
        people = sorted(
            people[:2],
            key=lambda p: (
                self._direction_rank(p.get("direction", "center")),
                -p.get("proximity_score", 0.0)
            )
        )

        directions = sorted([p.get("direction", "center") for p in people])

        if mode == "navigation":
            if directions == ["left", "right"]:
                return "Two persons, one on your left and one on your right"
            return "Two persons ahead"

        if mode == "human_priority":
            if directions == ["left", "right"]:
                return "Two persons, one on your left and one on your right"
            return "Two persons ahead"

        # exploration : un peu plus descriptif
        if directions == ["left", "right"]:
            return "Two persons, one on your left and one on your right"

        if directions == ["center", "center"]:
            return "Two persons ahead"

        if "center" in directions and "left" in directions:
            return "Person ahead and another on your left"

        if "center" in directions and "right" in directions:
            return "Person ahead and another on your right"

        return "Two persons ahead"

    def _multi_person_scene_signature(self, people):
        directions = sorted([p.get("direction", "center") for p in people[:2]])
        return tuple(directions)

    # =========================================================
    # MESSAGE BUILDERS
    # =========================================================
    def _build_initial_message(self, obj):
        label = self._pretty_label(obj.get("label", "object"))
        direction = obj.get("direction", "center")

        if direction == "center":
            return f"{label} ahead"
        return f"{label} on your {direction}"

    def _build_update_message(self, obj, mode):
        state = obj.get("state", "STABLE")
        direction = obj.get("direction", "center")
        raw_label = obj.get("label", "")
        label = self._pretty_label(raw_label)

        # 1. Changement direction / proximité
        if self._has_meaningful_change(obj):
            if raw_label == "person":
                if self._is_close_object(obj):
                    if direction == "center":
                        return "Close ahead"
                    return f"Close on your {direction}"

            if direction == "center":
                return f"{label} ahead"
            return f"{label} on your {direction}"

        # 2. Approche
        if state == "APPROACHING":
            if raw_label == "person":
                if not self._is_close_object(obj):
                    return None

                if direction == "center":
                    return "Close ahead"
                return f"Close on your {direction}"

            if mode == "exploration":
                if not self._is_close_object(obj):
                    return None
                if direction == "center":
                    return "Close ahead"
                return f"Close on your {direction}"

            return None

        # 3. Exploration : mouvements simples
        if mode == "exploration":
            if state == "MOVING_LEFT":
                return "Left"
            if state == "MOVING_RIGHT":
                return "Right"

        return None

    def _build_clear_message(self, obj):
        if obj.get("label") == "person":
            return "Clear"
        return None

    # =========================================================
    # EMISSION CONTROL
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
        if self._has_meaningful_change(obj):
            return True

        if obj.get("last_announcement") != message:
            return True

        return (now - obj.get("last_announcement_time", 0.0)) > self.long_reannounce_cooldown

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
        mode = getattr(config, "SYSTEM_MODE", "navigation")

        objects = self._normalize_objects(objects)
        if not objects:
            return []

        visible = [o for o in objects if o.get("missing_frames", 0) == 0]
        if not visible:
            return []

        visible = self._filter_objects_by_mode(visible, mode)
        if not visible:
            return []

        visible = sorted(
            visible,
            key=lambda obj: self._priority_key(obj, mode),
            reverse=True
        )

        # -----------------------------------------------------
        # MULTI-PERSON PRIORITY
        # -----------------------------------------------------
        people = self._get_visible_people(visible)
        if len(people) >= 2:
            message = self._build_multi_person_message(people, mode)
            current_signature = self._multi_person_scene_signature(people)

            if now < self.multi_person_anchor_until:
                if current_signature == self.multi_person_anchor:
                    return []

            if self._can_emit_globally(message, now):
                self.multi_person_anchor = current_signature
                self.multi_person_anchor_until = now + self.multi_person_anchor_duration

                self.last_global_message = message
                self.last_global_time = now

                return [message]

            return []

        # -----------------------------------------------------
        # SINGLE OBJECT
        # -----------------------------------------------------
        obj = self._select_focus_object(visible, now)
        if obj is None:
            return []

        state = obj.get("state")
        msg = None

        if state == "NEW":
            if not obj.get("already_announced"):
                msg = self._build_initial_message(obj)
            else:
                msg = self._build_update_message(obj, mode)

        elif state in ("APPROACHING", "STABLE", "MOVING_LEFT", "MOVING_RIGHT"):
            msg = self._build_update_message(obj, mode)

        elif state == "GONE":
            msg = self._build_clear_message(obj)

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