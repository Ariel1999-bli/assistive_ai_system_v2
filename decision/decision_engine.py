import time
import math
import config


class DecisionEngine:
    """
    Decision Engine spécialisé par mode :
    - navigation      : sécurité / proximité / changements utiles
    - human_priority  : priorité forte aux humains, ton plus humain
    - exploration     : description d'environnement, moins de logique "danger"

    Objectifs :
    - réduire les répétitions inutiles
    - rendre les 3 modes réellement différents
    - garder une bonne stabilité temporelle
    """

    def __init__(self):
        self.last_global_message = None
        self.last_global_time = 0.0

        self.current_focus_id = None
        self.focus_locked_until = 0.0
        self.focus_lock_duration = 2.0

        # anti-oscillation multi-personnes
        self.multi_person_anchor = None
        self.multi_person_anchor_until = 0.0
        self.multi_person_anchor_duration = 4.0

        # confirmation multi-personnes
        self.pending_multi_signature = None
        self.pending_multi_since = 0.0
        self.pending_multi_count = 0
        self.multi_person_min_confirmations = 4
        self.multi_person_min_stable_time = 1.5

        # seuils utiles
        self.approach_delta_threshold = 0.035
        self.meaningful_proximity_delta = 0.08

        # ré-annonce lente
        self.navigation_reminder_interval = 6.0
        self.human_priority_reminder_interval = 5.0
        self.exploration_reminder_interval = 5.5

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

    def _bbox_iou(self, box_a, box_b):
        ax1, ay1, ax2, ay2 = box_a
        bx1, by1, bx2, by2 = box_b

        inter_x1 = max(ax1, bx1)
        inter_y1 = max(ay1, by1)
        inter_x2 = min(ax2, bx2)
        inter_y2 = min(ay2, by2)

        inter_w = max(0.0, inter_x2 - inter_x1)
        inter_h = max(0.0, inter_y2 - inter_y1)
        inter_area = inter_w * inter_h

        area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
        area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)

        union_area = area_a + area_b - inter_area
        if union_area <= 0.0:
            return 0.0

        return inter_area / union_area

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
            return label in config.EXPLORATION_OBJECTS or label in config.IMPORTANT_OBJECTS

        if mode == "human_priority":
            return label in config.EXPLORATION_OBJECTS or label in config.IMPORTANT_OBJECTS

        return label in config.IMPORTANT_OBJECTS

    def _priority_key(self, obj, mode):
        label = obj.get("label", "")
        proximity = obj.get("proximity_score", 0.0)
        risk = obj.get("risk_score", 0.0)
        size = self._compute_size(obj)
        base_priority = config.OBJECT_PRIORITIES.get(label, 0)

        if mode == "navigation":
            if label == "person":
                return (100, risk, proximity, size)
            return (base_priority, risk, proximity, size)

        if mode == "human_priority":
            if label == "person":
                return (200, proximity, risk, size)
            return (base_priority, risk, proximity, size)

        # exploration :
        # on favorise davantage les objets de scène et la diversité descriptive
        if label == "person":
            return (60, proximity, risk, size)
        return (base_priority + 5, size, proximity, risk)

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

    def _get_visible_people(self, objs):
        return [o for o in objs if o.get("label") == "person"]

    def _is_close_object(self, obj):
        label = obj.get("label", "")
        proximity = obj.get("proximity_score", 0.0)
        risk = obj.get("risk_score", 0.0)

        if risk >= config.RISK_HIGH_THRESHOLD:
            return True

        if label == "person":
            return proximity >= config.PERSON_CLOSE_THRESHOLD

        return proximity >= config.OBJECT_CLOSE_THRESHOLD

    def _direction_changed(self, obj):
        current_direction = obj.get("direction", "center")
        previous_direction = obj.get("previous_direction", None)

        if previous_direction is None:
            return False

        return current_direction != previous_direction

    def _proximity_delta(self, obj):
        current_proximity = obj.get("proximity_score")
        previous_proximity = obj.get("previous_proximity_score")

        if current_proximity is None or previous_proximity is None:
            return 0.0

        return current_proximity - previous_proximity

    def _has_meaningful_approach(self, obj):
        return self._proximity_delta(obj) >= self.approach_delta_threshold

    def _has_meaningful_proximity_change(self, obj):
        return abs(self._proximity_delta(obj)) >= self.meaningful_proximity_delta

    def _close_zone_changed(self, obj):
        """
        Détecte un vrai changement utile pour les messages Close...
        Ignore les micro-variations du tracking.
        """
        current_direction = obj.get("direction", "center")
        previous_direction = obj.get("previous_direction", None)

        if previous_direction is not None and current_direction != previous_direction:
            return True

        delta = self._proximity_delta(obj)
        if abs(delta) >= 0.12:
            return True

        return False

    def _person_pair_is_real(self, people):
        """
        Valide si deux personnes semblent réellement distinctes.
        Réduit les faux 'two persons'.
        """
        if len(people) < 2:
            return False

        p1, p2 = people[0], people[1]

        bbox1 = p1["bbox"]
        bbox2 = p2["bbox"]

        iou = self._bbox_iou(bbox1, bbox2)

        c1 = p1.get("smoothed_center", p1["center"])
        c2 = p2.get("smoothed_center", p2["center"])
        dist = math.sqrt((c1[0] - c2[0]) ** 2 + (c1[1] - c2[1]) ** 2)

        prox1 = p1.get("proximity_score", 0.0)
        prox2 = p2.get("proximity_score", 0.0)
        prox_diff = abs(prox1 - prox2)

        if iou >= 0.30 and prox_diff <= 0.10:
            return False

        if dist < 80 and prox_diff <= 0.08:
            return False

        return True

    def _multi_person_signature(self, people):
        selected = sorted(
            people[:2],
            key=lambda p: (
                p.get("direction", "center"),
                round(p.get("proximity_score", 0.0), 2)
            )
        )
        return tuple(
            (p.get("direction", "center"), round(p.get("proximity_score", 0.0), 2))
            for p in selected
        )

    def _confirm_multi_person_scene(self, people, now):
        signature = self._multi_person_signature(people)

        if signature != self.pending_multi_signature:
            self.pending_multi_signature = signature
            self.pending_multi_since = now
            self.pending_multi_count = 1
            return False

        self.pending_multi_count += 1

        stable_time = now - self.pending_multi_since
        return (
            self.pending_multi_count >= self.multi_person_min_confirmations
            and stable_time >= self.multi_person_min_stable_time
        )

    def _reset_multi_person_candidate(self):
        self.pending_multi_signature = None
        self.pending_multi_since = 0.0
        self.pending_multi_count = 0

    def _build_direction_message(self, label, direction):
        if direction == "center":
            return f"{label} ahead"
        return f"{label} on your {direction}"

    # =========================================================
    # MODE-SPECIFIC REMINDERS
    # =========================================================
    def _should_emit_navigation_reminder(self, obj, mode, now):
        if mode != "navigation":
            return False
        if obj.get("label") != "person":
            return False
        if obj.get("state") != "STABLE":
            return False
        if self._direction_changed(obj):
            return False
        if self._is_close_object(obj):
            return False
        if self._has_meaningful_approach(obj):
            return False

        last_time = obj.get("last_announcement_time", 0.0)
        return (now - last_time) >= self.navigation_reminder_interval

    def _should_emit_human_priority_reminder(self, obj, mode, now):
        if mode != "human_priority":
            return False
        if obj.get("label") != "person":
            return False
        if obj.get("state") not in ("STABLE", "MOVING_LEFT", "MOVING_RIGHT"):
            return False
        if self._is_close_object(obj):
            return False
        if self._has_meaningful_approach(obj):
            return False

        last_time = obj.get("last_announcement_time", 0.0)
        return (now - last_time) >= self.human_priority_reminder_interval

    def _should_emit_exploration_reminder(self, obj, mode, now):
        if mode != "exploration":
            return False

        if obj.get("state") != "STABLE":
            return False

        if self._direction_changed(obj):
            return False

        if self._has_meaningful_approach(obj):
            return False

        # en exploration, on laisse davantage le narrator parler,
        # donc rappel réactif plus rare
        last_time = obj.get("last_announcement_time", 0.0)
        return (now - last_time) >= self.exploration_reminder_interval

    # =========================================================
    # MESSAGE BUILDERS
    # =========================================================
    def _build_multi_person_message(self, people, mode):
        directions = sorted([p.get("direction", "center") for p in people[:2]])

        if mode == "human_priority":
            if directions == ["left", "right"]:
                return "Two persons around you, one on your left and one on your right"
            return "Two persons around you"

        if mode == "exploration":
            if directions == ["left", "right"]:
                return "Two persons visible, one on your left and one on your right"
            return "Two persons visible"

        if directions == ["left", "right"]:
            return "Two persons, one on your left and one on your right"

        return "Two persons ahead"

    def _build_initial_message(self, obj, mode):
        label = self._pretty_label(obj.get("label", "object"))
        direction = obj.get("direction", "center")
        raw_label = obj.get("label", "")

        if mode == "human_priority" and raw_label == "person":
            if direction == "center":
                return "Person ahead"
            return f"Person on your {direction}"

        if mode == "exploration":
            return self._build_direction_message(label, direction)

        return self._build_direction_message(label, direction)

    def _build_person_approach_message(self, obj, mode):
        direction = obj.get("direction", "center")

        if self._is_close_object(obj):
            if mode == "human_priority":
                if direction == "center":
                    return "Person very close ahead"
                return f"Person very close on your {direction}"

            if mode == "exploration":
                if direction == "center":
                    return "Person approaching ahead"
                return f"Person approaching on your {direction}"

            if direction == "center":
                return "Close ahead"
            return f"Close on your {direction}"

        if self._has_meaningful_approach(obj):
            if direction == "center":
                return "Person approaching ahead"
            return f"Person approaching on your {direction}"

        return None

    def _build_navigation_reminder_message(self, obj):
        direction = obj.get("direction", "center")
        if direction == "center":
            return "Person ahead"
        return f"Person on your {direction}"

    def _build_human_priority_reminder_message(self, obj):
        direction = obj.get("direction", "center")
        if direction == "center":
            return "Person ahead"
        return f"Person on your {direction}"

    def _build_exploration_reminder_message(self, obj):
        label = self._pretty_label(obj.get("label", "object"))
        direction = obj.get("direction", "center")
        return self._build_direction_message(label, direction)

    def _build_update_message_navigation(self, obj, now):
        state = obj.get("state", "STABLE")
        direction = obj.get("direction", "center")
        label = self._pretty_label(obj.get("label", "object"))
        raw_label = obj.get("label", "")

        if self._direction_changed(obj):
            if raw_label == "person" and self._is_close_object(obj):
                if direction == "center":
                    return "Close ahead"
                return f"Close on your {direction}"

            return self._build_direction_message(label, direction)

        if raw_label == "person":
            if state == "APPROACHING":
                msg = self._build_person_approach_message(obj, "navigation")
                if msg:
                    return msg

            if self._has_meaningful_approach(obj) and self._is_close_object(obj):
                if direction == "center":
                    return "Close ahead"
                return f"Close on your {direction}"

            if self._should_emit_navigation_reminder(obj, "navigation", now):
                return self._build_navigation_reminder_message(obj)

        if state == "APPROACHING":
            return None

        if raw_label == "person" and self._is_close_object(obj):
            if self._close_zone_changed(obj):
                if direction == "center":
                    return "Close ahead"
                return f"Close on your {direction}"

        return None

    def _build_update_message_human_priority(self, obj, now):
        state = obj.get("state", "STABLE")
        direction = obj.get("direction", "center")
        raw_label = obj.get("label", "")

        if raw_label != "person":
            return None

        if self._direction_changed(obj):
            if self._is_close_object(obj):
                if direction == "center":
                    return "Person very close ahead"
                return f"Person very close on your {direction}"

            if direction == "center":
                return "Person ahead"
            return f"Person on your {direction}"

        if state == "APPROACHING":
            msg = self._build_person_approach_message(obj, "human_priority")
            if msg:
                return msg

        if self._has_meaningful_approach(obj) and self._is_close_object(obj):
            if direction == "center":
                return "Person very close ahead"
            return f"Person very close on your {direction}"

        if self._should_emit_human_priority_reminder(obj, "human_priority", now):
            return self._build_human_priority_reminder_message(obj)

        return None

    def _build_update_message_exploration(self, obj, now):
        """
        Exploration = mode descriptif.
        On veut :
        - décrire les objets utiles
        - laisser le narrator prendre la main pour les descriptions globales
        - éviter que 'close' domine le mode
        """
        state = obj.get("state", "STABLE")
        direction = obj.get("direction", "center")
        raw_label = obj.get("label", "")
        label = self._pretty_label(raw_label)

        # 1. changement de direction -> description simple
        if self._direction_changed(obj):
            return self._build_direction_message(label, direction)

        # 2. humain en approche réelle -> on informe, mais sans ton navigation
        if raw_label == "person":
            if state == "APPROACHING" and self._has_meaningful_approach(obj):
                if direction == "center":
                    return "Person approaching ahead"
                return f"Person approaching on your {direction}"

            # proximité très marquée seulement
            if self._is_close_object(obj) and self._close_zone_changed(obj):
                if direction == "center":
                    return "Person close ahead"
                return f"Person close on your {direction}"

            # rappel descriptif lent
            if self._should_emit_exploration_reminder(obj, "exploration", now):
                return self._build_exploration_reminder_message(obj)

            return None

        # 3. objets non humains : description > danger
        if state in ("NEW", "STABLE", "MOVING_LEFT", "MOVING_RIGHT"):
            if self._should_emit_exploration_reminder(obj, "exploration", now):
                return self._build_exploration_reminder_message(obj)

            return None

        if state == "APPROACHING":
            # en exploration on garde une description simple, pas "close" agressif
            if self._is_close_object(obj):
                return self._build_direction_message(label, direction)
            return None

        return None

    def _build_update_message(self, obj, mode, now):
        if mode == "navigation":
            return self._build_update_message_navigation(obj, now)

        if mode == "human_priority":
            return self._build_update_message_human_priority(obj, now)

        if mode == "exploration":
            return self._build_update_message_exploration(obj, now)

        return None

    def _build_clear_message(self, obj, mode):
        if obj.get("label") != "person":
            return None

        if mode == "human_priority":
            return "Person no longer detected"

        return "Clear"

    # =========================================================
    # EMISSION CONTROL
    # =========================================================
    def _can_emit_globally(self, message, now, mode):
        effective_same_cooldown = 3.0
        lowered = message.lower() if message else ""

        if lowered.startswith("two persons"):
            effective_same_cooldown = 4.5
        elif lowered.startswith("person very close"):
            effective_same_cooldown = 3.4
        elif lowered.startswith("close"):
            effective_same_cooldown = 3.8
        elif lowered.startswith("person approaching"):
            effective_same_cooldown = 2.8
        elif lowered.startswith("person close"):
            effective_same_cooldown = 3.2
        elif lowered.startswith("person "):
            effective_same_cooldown = 4.0

        if mode == "exploration":
            # exploration plus descriptif, plus espacé
            if lowered.endswith("ahead") or " on your " in lowered:
                effective_same_cooldown = 4.0

        if (now - self.last_global_time) < 1.0:
            return False

        if message == self.last_global_message:
            if (now - self.last_global_time) < effective_same_cooldown:
                return False

        return True

    def _can_emit_for_object(self, obj, message, now, mode):
        lowered = message.lower() if message else ""

        if self._direction_changed(obj):
            return True

        if "approaching" in lowered:
            return True

        if lowered.startswith("close") or lowered.startswith("person very close") or lowered.startswith("person close"):
            if self._close_zone_changed(obj):
                return True

            wait_time = 5.0
            if mode == "exploration":
                wait_time = 6.0

            return (now - obj.get("last_announcement_time", 0.0)) > wait_time

        if lowered.startswith("person "):
            reminder = self.navigation_reminder_interval
            if mode == "human_priority":
                reminder = self.human_priority_reminder_interval
            elif mode == "exploration":
                reminder = self.exploration_reminder_interval

            return (now - obj.get("last_announcement_time", 0.0)) > reminder

        if obj.get("last_announcement") != message:
            return True

        return (now - obj.get("last_announcement_time", 0.0)) > 4.5

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
            self._reset_multi_person_candidate()
            return []

        visible = [o for o in objects if o.get("missing_frames", 0) == 0]
        if not visible:
            self._reset_multi_person_candidate()
            return []

        visible = self._filter_objects_by_mode(visible, mode)
        if not visible:
            self._reset_multi_person_candidate()
            return []

        visible = sorted(
            visible,
            key=lambda obj: self._priority_key(obj, mode),
            reverse=True
        )

        # MULTI-PERSON PRIORITY
        people = self._get_visible_people(visible)

        if len(people) >= 2 and self._person_pair_is_real(people):
            confirmed = self._confirm_multi_person_scene(people, now)

            if confirmed:
                message = self._build_multi_person_message(people, mode)

                if now < self.multi_person_anchor_until and message == self.multi_person_anchor:
                    return []

                if self._can_emit_globally(message, now, mode):
                    self.multi_person_anchor = message
                    self.multi_person_anchor_until = now + self.multi_person_anchor_duration
                    self.last_global_message = message
                    self.last_global_time = now
                    return [message]

                return []
        else:
            self._reset_multi_person_candidate()

        # SINGLE OBJECT
        obj = self._select_focus_object(visible, now)
        if obj is None:
            return []

        state = obj.get("state")
        msg = None

        if state == "NEW":
            if not obj.get("already_announced"):
                msg = self._build_initial_message(obj, mode)
            else:
                msg = self._build_update_message(obj, mode, now)

        elif state in ("APPROACHING", "STABLE", "MOVING_LEFT", "MOVING_RIGHT"):
            msg = self._build_update_message(obj, mode, now)

        elif state == "GONE":
            msg = self._build_clear_message(obj, mode)

        if not msg:
            return []

        if not self._can_emit_for_object(obj, msg, now, mode):
            return []

        if not self._can_emit_globally(msg, now, mode):
            return []

        obj["already_announced"] = True
        obj["last_announcement"] = msg
        obj["last_announcement_time"] = now

        self.last_global_message = msg
        self.last_global_time = now

        return [msg]