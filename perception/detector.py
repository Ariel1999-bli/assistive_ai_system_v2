from ultralytics import YOLO
import config

class ObjectDetector:
    def __init__(self):
        self.model = YOLO(config.YOLO_MODEL_PATH)

    def detect(self, frame):
        results = self.model.predict(frame, conf=config.CONF_THRESHOLD, verbose=False)[0]

        detections = []

        if results.boxes is None:
            return detections

        for box in results.boxes:
            cls_id = int(box.cls[0].item())
            label = self.model.names[cls_id]

            x1, y1, x2, y2 = box.xyxy[0].tolist()

            detections.append({
                "label": label,
                "bbox": (x1, y1, x2, y2),
                "confidence": float(box.conf[0].item())
            })

        return detections