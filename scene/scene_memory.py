import time
import math
from typing import Dict, List, Tuple, Optional

import config


class SceneMemory:
    """
    Mémoire persistante de scène.

    Rôle :
    - conserver les objets d'une frame à l'autre
    - réassocier les nouvelles détections aux objets existants
    - maintenir un identifiant stable
    - mémoriser direction, annonces, état, temps de dernière apparition
    - lisser la position
    - calculer vitesse et score de risque
    - réduire les faux doublons de personnes
    """

    def __init__(self):
        self.objects: Dict[int, dict] = {}
        self.next_id: int = 1

    # ------------------------------------------------------------------
    # Outils géométriques
    # ------------------------------------------------------------------
    @staticmethod
    def _bbox_center(bbox: Tuple[float, float, float, float]) -> Tuple[float, float]:
        x1, y1, x2, y2 = bbox
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)

    @staticmethod
    def _bbox_area(bbox: Tuple[float, float, float, float]) -> float:
        x1, y1, x2, y2 = bbox
        return max(0.0, x2 - x1) * max(0.0, y2 - y1)

    @staticmethod
    def _bbox_width(bbox: Tuple[float, float, float, float]) -> float:
        x1, _, x2, _ = bbox
        return max(0.0, x2 - x1)

    @staticmethod
    def _bbox_height(bbox: Tuple[float, float, float, float]) -> float:
        _, y1, _, y2 = bbox
        return max(0.0, y2 - y1)

    @staticmethod
    def _euclidean_distance(
        p1: Tuple[float, float],
        p2: Tuple[float, float]
    ) -> float:
        return math.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)

    @staticmethod
    def _bbox_iou(
        box_a: Tuple[float, float, float, float],
        box_b: Tuple[float, float, float, float]
    ) -> float:
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

    def _compute_direction(
        self,
        center: Tuple[float, float]
    ) -> str:
        x, _ = center

        left_limit = config.FRAME_WIDTH / 3.0
        right_limit = 2.0 * config.FRAME_WIDTH / 3.0

        if x < left_limit:
            return "left"
        if x > right_limit:
            return "right"
        return "center"

    def _compute_proximity_score(
        self,
        bbox: Tuple[float, float, float, float]
    ) -> float:
        """
        Score de proximité basé sur la hauteur de la bbox relative à la frame.
        bbox_height / frame_height → 0.0 (loin) à 1.0 (très proche).
        """
        bbox_height = self._bbox_height(bbox)
        return min(bbox_height / float(config.FRAME_HEIGHT), 1.0)

    def _compute_risk_score(self, obj: dict) -> float:
        """
        Score de risque combinant :
        - proximité (0.5)
        - approche (0.3)
        - vitesse (0.2)
        """
        label = obj.get("label", "")
        proximity = obj.get("proximity_score", 0.0)
        prev_proximity = obj.get("previous_proximity_score")
        vx, vy = obj.get("velocity", (0.0, 0.0))

        proximity_delta = (proximity - prev_proximity) if prev_proximity is not None else 0.0
        approach_factor = max(0.0, proximity_delta * 8.0)

        speed = math.sqrt(vx ** 2 + vy ** 2)
        speed_factor = min(speed / 300.0, 1.0)

        weight = config.RISK_WEIGHTS.get(label, config.RISK_WEIGHTS["default"])
        risk = weight * (0.5 * proximity + 0.3 * approach_factor + 0.2 * speed_factor)
        return min(risk, 1.0)

    # ------------------------------------------------------------------
    # Heuristiques anti-faux-doublons personnes
    # ------------------------------------------------------------------
    def _person_duplicate_score(self, p1: dict, p2: dict) -> float:
        """
        Score heuristique indiquant si deux objets 'person' ressemblent
        probablement à une double détection d'une seule personne.
        """
        bbox1 = p1["bbox"]
        bbox2 = p2["bbox"]

        iou = self._bbox_iou(bbox1, bbox2)
        c1 = p1.get("smoothed_center", p1["center"])
        c2 = p2.get("smoothed_center", p2["center"])
        dist = self._euclidean_distance(c1, c2)

        prox1 = p1.get("proximity_score", 0.0)
        prox2 = p2.get("proximity_score", 0.0)
        prox_diff = abs(prox1 - prox2)

        dir1 = p1.get("direction", "center")
        dir2 = p2.get("direction", "center")
        same_direction = dir1 == dir2

        w1 = self._bbox_width(bbox1)
        w2 = self._bbox_width(bbox2)
        h1 = self._bbox_height(bbox1)
        h2 = self._bbox_height(bbox2)

        avg_w = max((w1 + w2) / 2.0, 1.0)
        avg_h = max((h1 + h2) / 2.0, 1.0)

        horizontal_close = abs(c1[0] - c2[0]) <= max(55.0, 0.55 * avg_w)
        vertical_close = abs(c1[1] - c2[1]) <= max(70.0, 0.45 * avg_h)

        score = 0.0

        if iou >= 0.55:
            score += 1.0
        elif iou >= 0.35:
            score += 0.6

        if horizontal_close and vertical_close:
            score += 0.7

        if prox_diff <= 0.08:
            score += 0.4
        elif prox_diff <= 0.12:
            score += 0.2

        if same_direction:
            score += 0.2

        return score

    def _choose_person_to_keep(self, p1: dict, p2: dict) -> int:
        """
        Garde la détection la plus crédible / stable.
        """
        score1 = (
            2.0 * p1.get("times_seen", 1)
            + 4.0 * p1.get("confidence", 0.0)
            + 1.0 * self._bbox_area(p1["bbox"])
            + 30.0 * p1.get("proximity_score", 0.0)
        )
        score2 = (
            2.0 * p2.get("times_seen", 1)
            + 4.0 * p2.get("confidence", 0.0)
            + 1.0 * self._bbox_area(p2["bbox"])
            + 30.0 * p2.get("proximity_score", 0.0)
        )

        return p1["id"] if score1 >= score2 else p2["id"]

    def _merge_duplicate_persons(self) -> None:
        """
        Supprime certains faux doublons 'person' conservés par le tracking.
        Heuristique volontairement conservatrice.
        """
        visible_persons = [
            o for o in self.objects.values()
            if o.get("label") == "person" and o.get("missing_frames", 0) == 0
        ]

        if len(visible_persons) < 2:
            return

        to_delete = set()

        for i in range(len(visible_persons)):
            p1 = visible_persons[i]
            if p1["id"] in to_delete:
                continue

            for j in range(i + 1, len(visible_persons)):
                p2 = visible_persons[j]
                if p2["id"] in to_delete:
                    continue

                duplicate_score = self._person_duplicate_score(p1, p2)

                if duplicate_score >= 1.25:
                    keep_id = self._choose_person_to_keep(p1, p2)
                    remove_id = p2["id"] if keep_id == p1["id"] else p1["id"]
                    to_delete.add(remove_id)

        for obj_id in to_delete:
            if obj_id in self.objects:
                del self.objects[obj_id]

    # ------------------------------------------------------------------
    # Gestion d'objets
    # ------------------------------------------------------------------
    def _build_new_object(
        self,
        detection: dict,
        now: float
    ) -> dict:
        bbox = detection["bbox"]
        center = self._bbox_center(bbox)
        direction = self._compute_direction(center)
        proximity_score = self._compute_proximity_score(bbox)

        obj = {
            "id": self.next_id,
            "label": detection["label"],
            "bbox": bbox,
            "center": center,
            "smoothed_center": center,
            "previous_center": None,
            "confidence": detection["confidence"],

            # mémoire temporelle
            "created_at": now,
            "last_seen": now,
            "missing_frames": 0,

            # logique contextuelle
            "direction": direction,
            "previous_direction": None,
            "proximity_score": proximity_score,
            "previous_proximity_score": None,
            "state": "NEW",
            "last_state_change": now,

            # vélocité et risque
            "velocity": (0.0, 0.0),
            "risk_score": 0.0,

            # mémoire sémantique
            "already_announced": False,
            "last_announcement": None,
            "last_announcement_time": 0.0,

            # utile pour debug
            "times_seen": 1,
        }

        self.next_id += 1
        return obj

    def _update_existing_object(
        self,
        obj: dict,
        detection: dict,
        now: float
    ) -> dict:
        old_direction = obj["direction"]
        old_proximity = obj["proximity_score"]
        old_center = obj["center"]
        old_smoothed = obj.get("smoothed_center", old_center)

        bbox = detection["bbox"]
        center = self._bbox_center(bbox)
        direction = self._compute_direction(center)
        proximity_score = self._compute_proximity_score(bbox)

        alpha = config.SMOOTHING_ALPHA
        smoothed_center = (
            alpha * center[0] + (1.0 - alpha) * old_smoothed[0],
            alpha * center[1] + (1.0 - alpha) * old_smoothed[1],
        )

        dt = now - obj.get("last_seen", now)
        if dt > 0.0:
            vx = (smoothed_center[0] - old_smoothed[0]) / dt
            vy = (smoothed_center[1] - old_smoothed[1]) / dt
        else:
            vx, vy = obj.get("velocity", (0.0, 0.0))

        obj["bbox"] = bbox
        obj["previous_center"] = old_center
        obj["center"] = center
        obj["smoothed_center"] = smoothed_center
        obj["velocity"] = (vx, vy)
        obj["confidence"] = detection["confidence"]
        obj["last_seen"] = now
        obj["missing_frames"] = 0
        obj["times_seen"] += 1

        obj["previous_direction"] = old_direction
        obj["direction"] = direction

        obj["previous_proximity_score"] = old_proximity
        obj["proximity_score"] = proximity_score

        obj["risk_score"] = self._compute_risk_score(obj)

        return obj

    def _match_detection_to_object(
        self,
        detection: dict,
        used_ids: set
    ) -> Optional[int]:
        best_id = None
        best_score = -1.0

        det_bbox = detection["bbox"]
        det_center = self._bbox_center(det_bbox)
        det_label = detection["label"]

        for obj_id, obj in self.objects.items():
            if obj_id in used_ids:
                continue

            if obj["label"] != det_label:
                continue

            if obj["missing_frames"] > config.MAX_MISSING_FRAMES:
                continue

            obj_bbox = obj["bbox"]
            obj_center = obj["center"]

            dist = self._euclidean_distance(det_center, obj_center)
            iou = self._bbox_iou(det_bbox, obj_bbox)

            if dist > config.MAX_DISTANCE and iou < config.TRACK_MATCH_MIN_IOU:
                continue

            distance_score = max(0.0, 1.0 - (dist / float(config.MAX_DISTANCE)))
            match_score = (0.55 * iou) + (0.45 * distance_score)

            if obj["missing_frames"] == 0:
                match_score += config.TRACK_RECENCY_BONUS
            elif obj["missing_frames"] <= 2:
                match_score += config.TRACK_RECENCY_BONUS * 0.5

            if match_score > best_score:
                best_score = match_score
                best_id = obj_id

        if best_id is not None and best_score >= config.TRACK_MATCH_SCORE_THRESH:
            return best_id

        return None

    def _mark_missing_objects(self, matched_ids: set) -> None:
        for obj_id, obj in self.objects.items():
            if obj_id not in matched_ids:
                obj["missing_frames"] += 1

    def _remove_stale_objects(self) -> None:
        to_delete = []

        for obj_id, obj in self.objects.items():
            if obj["missing_frames"] > config.MAX_MISSING_FRAMES:
                to_delete.append(obj_id)

        for obj_id in to_delete:
            del self.objects[obj_id]

    # ------------------------------------------------------------------
    # API principale
    # ------------------------------------------------------------------
    def update(self, detections: List[dict]) -> Dict[int, dict]:
        now = time.time()
        used_ids = set()
        matched_ids = set()

        for detection in detections:
            matched_id = self._match_detection_to_object(detection, used_ids)

            if matched_id is not None:
                self.objects[matched_id] = self._update_existing_object(
                    self.objects[matched_id],
                    detection,
                    now
                )
                used_ids.add(matched_id)
                matched_ids.add(matched_id)
            else:
                new_obj = self._build_new_object(detection, now)
                self.objects[new_obj["id"]] = new_obj
                used_ids.add(new_obj["id"])
                matched_ids.add(new_obj["id"])

        self._mark_missing_objects(matched_ids)
        self._remove_stale_objects()
        self._merge_duplicate_persons()

        return self.objects