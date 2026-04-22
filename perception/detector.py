import config

# Classes COCO (YOLOv8 standard)
COCO_CLASSES = {
    0: "person", 1: "bicycle", 2: "car", 3: "motorcycle", 4: "airplane",
    5: "bus", 6: "train", 7: "truck", 8: "boat", 9: "traffic light",
    10: "fire hydrant", 11: "stop sign", 12: "parking meter", 13: "bench",
    14: "bird", 15: "cat", 16: "dog", 17: "horse", 18: "sheep", 19: "cow",
    20: "elephant", 21: "bear", 22: "zebra", 23: "giraffe", 24: "backpack",
    25: "umbrella", 26: "handbag", 27: "tie", 28: "suitcase", 29: "frisbee",
    30: "skis", 31: "snowboard", 32: "sports ball", 33: "kite",
    34: "baseball bat", 35: "baseball glove", 36: "skateboard", 37: "surfboard",
    38: "tennis racket", 39: "bottle", 40: "wine glass", 41: "cup",
    42: "fork", 43: "knife", 44: "spoon", 45: "bowl", 46: "banana",
    47: "apple", 48: "sandwich", 49: "orange", 50: "broccoli", 51: "carrot",
    52: "hot dog", 53: "pizza", 54: "donut", 55: "cake", 56: "chair",
    57: "couch", 58: "potted plant", 59: "bed", 60: "dining table",
    61: "toilet", 62: "tv", 63: "laptop", 64: "mouse", 65: "remote",
    66: "keyboard", 67: "cell phone", 68: "microwave", 69: "oven",
    70: "toaster", 71: "sink", 72: "refrigerator", 73: "book", 74: "clock",
    75: "vase", 76: "scissors", 77: "teddy bear", 78: "hair drier",
    79: "toothbrush",
}


class ObjectDetector:
    """
    Détecteur d'objets avec support double backend :
    - YOLO (ultralytics) : défaut, CPU/GPU
    - Hailo-8 : accéléré hardware via HailoRT (USE_HAILO=True dans config)

    Pour activer Hailo-8 :
    1. Installer HailoRT SDK sur le RPi5
    2. Convertir le modèle : yolov8n.pt → yolov8n.hef (via Hailo Model Zoo)
    3. Mettre USE_HAILO = True et HAILO_MODEL_PATH dans config.py
    """

    def __init__(self):
        if config.USE_HAILO:
            self._backend = "hailo"
            self._init_hailo()
        else:
            self._backend = "yolo"
            self._init_yolo()

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------
    def _init_yolo(self):
        from ultralytics import YOLO
        self._model = YOLO(config.YOLO_MODEL_PATH)
        print("[DETECTOR] Backend: YOLOv8 (CPU/GPU)")

    def _init_hailo(self):
        """
        Initialise le pipeline Hailo-8 via HailoRT.
        Repasse automatiquement sur YOLO si le SDK n'est pas installé.
        """
        try:
            from hailo_platform import (
                HEF, VDevice, InferVStreams,
                InputVStreamParams, OutputVStreamParams, FormatType,
            )
            self._hef = HEF(config.HAILO_MODEL_PATH)
            self._device = VDevice()
            network_groups = self._device.configure(self._hef)
            self._network_group = network_groups[0]
            self._input_params = InputVStreamParams.make(
                self._network_group, format_type=FormatType.UINT8
            )
            self._output_params = OutputVStreamParams.make(
                self._network_group, format_type=FormatType.FLOAT32
            )
            self._InferVStreams = InferVStreams
            print("[DETECTOR] Backend: Hailo-8 (HailoRT)")
        except ImportError:
            print("[DETECTOR] hailo_platform non trouvé → fallback YOLO")
            self._backend = "yolo"
            self._init_yolo()

    # ------------------------------------------------------------------
    # API principale
    # ------------------------------------------------------------------
    def detect(self, frame) -> list:
        if self._backend == "hailo":
            return self._detect_hailo(frame)
        return self._detect_yolo(frame)

    # ------------------------------------------------------------------
    # Backend YOLO
    # ------------------------------------------------------------------
    def _detect_yolo(self, frame) -> list:
        results = self._model.predict(
            frame, conf=config.CONF_THRESHOLD, verbose=False
        )[0]

        detections = []
        if results.boxes is None:
            return detections

        for box in results.boxes:
            cls_id = int(box.cls[0].item())
            label = self._model.names[cls_id]
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            detections.append({
                "label": label,
                "bbox": (x1, y1, x2, y2),
                "confidence": float(box.conf[0].item()),
            })

        return detections

    # ------------------------------------------------------------------
    # Backend Hailo-8
    # ------------------------------------------------------------------
    def _detect_hailo(self, frame) -> list:
        import numpy as np
        import cv2

        input_h, input_w = 640, 640
        resized = cv2.resize(frame, (input_w, input_h))
        input_data = np.expand_dims(resized, axis=0)  # (1, H, W, 3)

        detections = []

        try:
            with self._InferVStreams(
                self._network_group,
                self._input_params,
                self._output_params,
            ) as pipeline:
                input_name = self._hef.get_input_vstream_infos()[0].name
                output = pipeline.infer({input_name: input_data})

                # Format de sortie typique compilé Hailo :
                # [num_detections, 6] → (x1, y1, x2, y2, score, class_id)
                # (peut varier selon la version du .hef — ajuster si besoin)
                raw = list(output.values())[0][0]

                orig_h, orig_w = frame.shape[:2]
                scale_x = orig_w / input_w
                scale_y = orig_h / input_h

                for det in raw:
                    if len(det) < 6:
                        continue
                    x1, y1, x2, y2, score, cls_id = det[:6]
                    if score < config.CONF_THRESHOLD:
                        continue

                    label = COCO_CLASSES.get(int(cls_id), "unknown")
                    detections.append({
                        "label": label,
                        "bbox": (
                            x1 * scale_x,
                            y1 * scale_y,
                            x2 * scale_x,
                            y2 * scale_y,
                        ),
                        "confidence": float(score),
                    })

        except Exception as e:
            print(f"[HAILO_ERROR] {e}")

        return detections