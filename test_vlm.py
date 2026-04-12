"""
test_vlm.py — Test standalone VLM (description de scène pour malvoyant)

Backend utilisé :
  - Windows / CPU : BLIP (Salesforce) via transformers — simple, léger, sans GPU
  - RPi5 / Production : Moondream2 via scene_narrator.py

Modes :
  1. Image statique : python test_vlm.py --image chemin/image.jpg
  2. Webcam live    : python test_vlm.py --webcam
  3. Webcam capture : python test_vlm.py --webcam --capture

Installation :
  pip install transformers Pillow
"""

import argparse
import sys
import threading
import time


# ──────────────────────────────────────────────
# Synthèse vocale (non bloquante)
# ──────────────────────────────────────────────
def speak(text: str):
    def _run():
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", 180)
            engine.setProperty("volume", 1.0)
            engine.say(text)
            engine.runAndWait()
            engine.stop()
        except Exception as e:
            print(f"[TTS_ERROR] {e}")

    threading.Thread(target=_run, daemon=True).start()


# ──────────────────────────────────────────────
# Chargement BLIP (CPU, Windows compatible)
# ──────────────────────────────────────────────
def load_model():
    try:
        import torch
        from transformers import BlipProcessor, BlipForConditionalGeneration
    except ImportError:
        print("[ERREUR] transformers non installé.")
        print("  → pip install transformers Pillow")
        sys.exit(1)

    model_id = "Salesforce/blip-image-captioning-base"
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[VLM] Chargement de BLIP sur {device.upper()} (première fois = ~900MB)...")
    t0 = time.time()

    try:
        processor = BlipProcessor.from_pretrained(model_id)
        model = BlipForConditionalGeneration.from_pretrained(model_id).to(device)
        model.eval()
        print(f"[VLM] BLIP prêt sur {device.upper()} en {time.time() - t0:.1f}s")
        return model, processor
    except Exception as e:
        print(f"[ERREUR] Chargement échoué : {e}")
        sys.exit(1)


# ──────────────────────────────────────────────
# Inférence
# ──────────────────────────────────────────────
# Mots-clés déclenchant une alerte immédiate (danger potentiel)
DANGER_KEYWORDS = {
    "car", "truck", "bus", "motorcycle", "bicycle", "bike",
    "dog", "stairs", "step", "hole", "crowd", "traffic",
    "road", "street", "vehicle", "obstacle"
}


def query(model, processor, pil_image) -> tuple:
    import torch

    device = next(model.parameters()).device
    t0 = time.time()
    # Pas de préfixe → caption naturelle sans "a photo showing"
    inputs = processor(pil_image, return_tensors="pt")
    inputs = {k: v.to(device) for k, v in inputs.items()}

    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=40)

    caption = processor.decode(out[0], skip_special_tokens=True)
    elapsed = time.time() - t0
    return caption.strip(), elapsed


def is_danger(caption: str) -> bool:
    words = caption.lower().split()
    return any(w in DANGER_KEYWORDS for w in words)


def has_changed(prev: str, current: str) -> bool:
    """Retourne True si la scène a significativement changé."""
    if not prev:
        return True
    prev_words = set(prev.lower().split())
    curr_words = set(current.lower().split())
    # Similarité Jaccard : parle seulement si < 60% de mots en commun
    if not prev_words or not curr_words:
        return True
    intersection = prev_words & curr_words
    union = prev_words | curr_words
    similarity = len(intersection) / len(union)
    return similarity < 0.6


# ──────────────────────────────────────────────
# Mode image statique
# ──────────────────────────────────────────────
def test_image(model, processor, path: str):
    from PIL import Image

    print(f"\n[TEST] Image : {path}")
    try:
        img = Image.open(path).convert("RGB")
    except FileNotFoundError:
        print(f"[ERREUR] Fichier introuvable : {path}")
        sys.exit(1)

    answer, elapsed = query(model, processor, img)
    print(f"[RÉPONSE] {answer}")
    print(f"[TEMPS]   {elapsed:.2f}s")
    speak(answer)
    time.sleep(5)  # laisser le temps à la voix de parler


# ──────────────────────────────────────────────
# Mode webcam
# ──────────────────────────────────────────────
def test_webcam(model, processor, capture_mode: bool):
    import cv2
    from PIL import Image

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[ERREUR] Impossible d'ouvrir la webcam.")
        sys.exit(1)

    print("\n[WEBCAM] Démarré.")
    if capture_mode:
        print("  → Appuie sur ESPACE pour analyser une frame, ESC pour quitter.")
    else:
        print("  → Analyse automatique toutes les 7s. ESC pour quitter.")

    last_query_time = 0
    last_answer = ""
    last_spoken = ""

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        now = time.time()
        run_query = False

        if capture_mode:
            cv2.putText(frame, "ESPACE = analyser | ESC = quitter",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        else:
            remaining = max(0, 7 - (now - last_query_time))
            cv2.putText(frame, f"Analyse dans {remaining:.0f}s | ESC = quitter",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            if now - last_query_time >= 7:
                run_query = True

        if last_answer:
            color = (0, 0, 255) if is_danger(last_answer) else (0, 200, 255)
            cv2.putText(frame, last_answer[:80], (10, frame.shape[0] - 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)

        cv2.imshow("Test VLM — BLIP", frame)
        key = cv2.waitKey(1)

        if key == 27:  # ESC
            break
        if key == 32 and capture_mode:  # ESPACE
            run_query = True

        if run_query:
            last_query_time = now
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(rgb)

            answer, elapsed = query(model, processor, pil_image)
            last_answer = answer

            danger = is_danger(answer)
            changed = has_changed(last_spoken, answer)

            print(f"[SCÈNE]   {answer}  ({elapsed:.2f}s)"
                  + (" ⚠ DANGER" if danger else "")
                  + (" → muet (scène stable)" if not changed and not danger else ""))

            # Parle seulement si danger OU si la scène a changé
            if danger or changed:
                last_spoken = answer
                speak(answer)

    cap.release()
    cv2.destroyAllWindows()


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test VLM (BLIP) pour Assistive AI")
    parser.add_argument("--image", type=str, help="Chemin vers une image statique")
    parser.add_argument("--webcam", action="store_true", help="Mode webcam live")
    parser.add_argument("--capture", action="store_true",
                        help="Analyse sur ESPACE (défaut = auto toutes les 7s)")
    args = parser.parse_args()

    if not args.image and not args.webcam:
        print("Usage :")
        print("  python test_vlm.py --image photo.jpg")
        print("  python test_vlm.py --webcam")
        print("  python test_vlm.py --webcam --capture")
        sys.exit(0)

    model, processor = load_model()

    if args.image:
        test_image(model, processor, args.image)
    elif args.webcam:
        test_webcam(model, processor, capture_mode=args.capture)
