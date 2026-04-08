import time
import config


class StateMachine:
    """
    Machine d'états contextuelle pour les objets mémorisés.

    États gérés :
    - NEW
    - STABLE
    - MOVING_LEFT
    - MOVING_RIGHT
    - APPROACHING
    - GONE

    Rôle :
    - interpréter l'évolution d'un objet dans le temps
    - stabiliser le comportement du système
    - préparer une prise de décision intelligente
    """

    def __init__(self):
        pass

    def _compute_horizontal_delta(self, obj):
        """
        Variation horizontale entre la position actuelle et la précédente.
        """
        current_center = obj.get("center")
        previous_center = obj.get("previous_center")

        if current_center is None or previous_center is None:
            return 0.0

        return current_center[0] - previous_center[0]

    def _compute_proximity_delta(self, obj):
        """
        Variation de proximité entre l'état actuel et le précédent.
        """
        current_proximity = obj.get("proximity_score")
        previous_proximity = obj.get("previous_proximity_score")

        if current_proximity is None or previous_proximity is None:
            return 0.0

        return current_proximity - previous_proximity

    def _set_state(self, obj, new_state, now):
        """
        Change l'état seulement si nécessaire.
        """
        if obj.get("state") != new_state:
            obj["state"] = new_state
            obj["last_state_change"] = now

    def update(self, objects):
        """
        Met à jour l'état de chaque objet de la scène.
        """
        now = time.time()

        for obj in objects.values():
            missing_frames = obj.get("missing_frames", 0)
            current_state = obj.get("state", "NEW")
            created_at = obj.get("created_at", now)
            last_state_change = obj.get("last_state_change", created_at)

            time_in_state = now - last_state_change
            age = now - created_at

            horizontal_delta = self._compute_horizontal_delta(obj)
            proximity_delta = self._compute_proximity_delta(obj)

            # --------------------------------------------------
            # 1. Objet disparu
            # --------------------------------------------------
            if missing_frames > 0:
                if missing_frames >= config.MAX_MISSING_FRAMES:
                    self._set_state(obj, "GONE", now)
                # si l'objet est juste momentanément absent, on garde son état
                continue

            # --------------------------------------------------
            # 2. Objet nouveau
            # --------------------------------------------------
            if current_state == "NEW":
                # on garde l'état NEW très brièvement pour laisser
                # le moteur de décision faire une première annonce
                if age >= 0.15:
                    self._set_state(obj, "STABLE", now)
                continue

            # --------------------------------------------------
            # 3. Approche prioritaire
            # --------------------------------------------------
            if proximity_delta >= config.STATE_APPROACH_THRESHOLD:
                self._set_state(obj, "APPROACHING", now)
                continue

            # --------------------------------------------------
            # 4. Mouvement horizontal
            # --------------------------------------------------
            # seuil simple pour éviter d'interpréter du bruit comme mouvement
            move_threshold_px = 18.0

            if horizontal_delta <= -move_threshold_px:
                self._set_state(obj, "MOVING_LEFT", now)
                continue

            if horizontal_delta >= move_threshold_px:
                self._set_state(obj, "MOVING_RIGHT", now)
                continue

            # --------------------------------------------------
            # 5. Retour vers STABLE
            # --------------------------------------------------
            # si l'objet n'a plus de variation forte pendant un petit moment
            if time_in_state >= config.STATE_STABLE_TIME:
                self._set_state(obj, "STABLE", now)

        return objects