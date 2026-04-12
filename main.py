import cv2

from perception.detector import ObjectDetector
from scene.scene_memory import SceneMemory
from scene.state_machine import StateMachine
from scene.scene_narrator import SceneNarrator
from decision.decision_engine import DecisionEngine
from audio.audio_engine import AudioEngine
from context.context_manager import ContextManager


def draw_objects(frame, objects):
    """
    Affichage visuel pour debug.
    """
    for obj in objects.values():
        if obj.get("missing_frames", 0) > 0:
            continue

        x1, y1, x2, y2 = obj["bbox"]
        x1, y1, x2, y2 = map(int, [x1, y1, x2, y2])

        label = obj["label"]
        obj_id = obj["id"]
        state = obj["state"]
        direction = obj["direction"]
        risk = obj.get("risk_score", 0.0)

        text = f"{label} ID:{obj_id} {state} {direction} R:{risk:.2f}"

        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 255), 2)

        cv2.putText(
            frame,
            text,
            (x1, max(20, y1 - 10)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 255),
            2
        )


def main():
    print("🚀 Assistive AI v2 started")

    detector = ObjectDetector()
    memory = SceneMemory()
    state_machine = StateMachine()
    decision_engine = DecisionEngine()
    context_manager = ContextManager()
    audio = AudioEngine()
    narrator = SceneNarrator(audio)

    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("❌ Erreur : impossible d'ouvrir la caméra.")
        return

    try:
        while True:
            ret, frame = cap.read()

            if not ret:
                print("❌ Erreur : lecture frame impossible.")
                break

            # 1. Détection
            detections = detector.detect(frame)

            # 2. Mémoire
            objects = memory.update(detections)

            # 3. État
            objects = state_machine.update(objects)

            # 4. Décision
            messages = decision_engine.decide(objects)

            # 5. Contexte final
            for msg in messages:
                final_msg = context_manager.process(list(objects.values()), msg)

                if final_msg:
                    print(f"[FINAL SPEAK] {final_msg}")
                    audio.speak(final_msg)

            # 6. Narrateur de scène périodique (VLM / règles)
            narrator.update(frame, objects)

            # 7. Debug visuel
            draw_objects(frame, objects)

            cv2.imshow("Assistive AI v2", frame)

            # ESC pour quitter
            if cv2.waitKey(1) == 27:
                break

    finally:
        print("🛑 Stopping system...")
        cap.release()
        cv2.destroyAllWindows()
        narrator.stop()
        audio.stop()


if __name__ == "__main__":
    main()