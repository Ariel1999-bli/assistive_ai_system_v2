# 🚀 Assistive AI v2

## Context-Aware Visual Assistance System for the Visually Impaired

---

## 📌 Overview

**Assistive AI v2** is a real-time intelligent system designed to assist visually impaired individuals by providing **context-aware audio descriptions of their environment**.

Unlike traditional object detection systems, this project goes beyond simple detection by introducing:

* 🧠 Contextual understanding
* ⏱ Temporal reasoning
* 🎯 Intelligent decision-making
* 🔊 Human-centered audio feedback
* 🤖 Periodic scene narration via Vision-Language Model (VLM)

👉 The goal is to transform raw visual perception into **useful, minimal, and actionable information**.

---

## 🎯 Project Vision

The system evolves from:

> ❌ "An object detection system that speaks"

to:

> ✅ **A real-time contextual visual mobility assistant**

This means:

* Not everything detected is spoken
* The system **decides what matters**
* It speaks **only when the scene changes or danger is detected**
* It behaves closer to **human perception and reasoning**

---

## 🧱 System Architecture

```
Camera
  │
  ▼
Hailo-8 ──► YOLO (real-time, hardware accelerated)
  │
  ▼
SceneMemory + StateMachine   (tracking, states, smoothing, velocity)
  │
  ▼
DecisionEngine               (priority, risk scoring)
  │
  ├──► ContextManager ──────► TTS audio  (main loop, < 50ms)
  │
  └──► SceneNarrator ────────► TTS audio  (every 7s, VLM or rule-based)
```

### 📂 Project Structure

```
perception/
  detector.py        # Object detection — YOLO (CPU/GPU) or Hailo-8
scene/
  scene_memory.py    # Multi-object tracking, smoothing, velocity, risk score
  state_machine.py   # Object states: NEW, STABLE, APPROACHING, GONE
  scene_narrator.py  # Periodic scene description (VLM / rule-based)
decision/
  decision_engine.py # Object prioritization and message generation
context/
  context_manager.py # Cognitive filtering — speaks only when necessary
audio/
  audio_engine.py    # Asynchronous TTS engine
main.py              # Main pipeline
config.py            # All system parameters
test_vlm.py          # Standalone VLM test script (webcam or image)
setup_rpi5.sh        # Automated setup for Raspberry Pi 5 + Hailo-8
requirements.txt         # PC dependencies
requirements_rpi5.txt    # RPi5 ARM64 dependencies
```

---

## ⚙️ Core Components

### 1. 🎥 Perception — Dual Backend

* **YOLO** (default): runs on CPU or NVIDIA GPU via ultralytics
* **Hailo-8** (embedded): hardware-accelerated inference on RPi5
  * Set `USE_HAILO = True` in `config.py`
  * Requires `yolov8n.hef` (downloaded by `setup_rpi5.sh`)

---

### 2. 🧠 Scene Memory

* Tracks objects across frames with unique IDs
* **Exponential smoothing** on positions (`SMOOTHING_ALPHA = 0.3`)
* **Velocity** computed per frame (pixels/second)
* **Proximity score** = `bbox_height / frame_height`
* **Risk score** combining proximity, approach rate and object type

---

### 3. 🔄 State Machine

Defines object states:

* `NEW` → `STABLE` → `APPROACHING` → `GONE`
* `MOVING_LEFT` / `MOVING_RIGHT`

👉 Reduces noise and stabilizes perception.

---

### 4. 🎯 Decision Engine

* Filters objects by mode (`navigation`, `exploration`, `human_priority`)
* Prioritizes by **risk score** then proximity
* Generates contextual messages:
  * `"Person ahead"`
  * `"Close ahead"` (when proximity + risk are high)
  * `"Two persons, one on your left and one on your right"`

---

### 5. 🧠 Context Manager

* Filters repetitive messages
* Applies scene stability detection
* Speaks **only when necessary**
* Priority system: danger messages always pass through

---

### 6. 🎙 Scene Narrator

Runs in a background thread every `VLM_NARRATOR_INTERVAL` seconds (default: 7s).

Two modes:
* **Rule-based** (default): builds description from tracked objects
* **VLM** (`VLM_ENABLED = True`): uses Moondream2 for natural language narration

Speaks **only if**:
* A **danger keyword** is detected (car, dog, stairs, crowd...)
* The scene has **significantly changed** (Jaccard similarity < 60%)

---

### 7. 🔊 Audio Engine

* Asynchronous speech with dedicated thread
* Non-blocking — always keeps the latest message
* Anti-repetition cooldown

---

## 🚀 Features

* ✅ Real-time object detection (YOLO / Hailo-8)
* ✅ Multi-object tracking with smoothing
* ✅ Velocity and risk scoring
* ✅ Context-aware decision-making
* ✅ Danger keyword detection
* ✅ Intelligent audio — speaks only on change or danger
* ✅ Periodic VLM scene narration (Moondream2)
* ✅ Raspberry Pi 5 + Hailo-8 deployment ready

---

## 🧪 Example Behavior

### ❌ Before (raw system)

```
Person ahead
Person ahead
Person ahead
Left
Right
Bottle on your left
```

### ✅ After (Assistive AI v2)

```
Person ahead
(silence — scene stable)
Close ahead
(silence)
[NARRATOR] There is a car approaching on your left, be careful.
```

---

## 🔧 Installation — PC (Development)

### 1. Clone the repository

```bash
git clone https://github.com/Ariel1999-bli/assistive_ai_system_v2.git
cd assistive_ai_system_v2
```

### 2. Create environment

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run

```bash
python main.py
```

---

## 🧪 Test the VLM standalone

```bash
pip install transformers Pillow

# Webcam — auto analysis every 7s
python test_vlm.py --webcam

# Webcam — manual analysis on SPACE key
python test_vlm.py --webcam --capture

# Static image
python test_vlm.py --image photo.jpg
```

---

## 🍓 Deployment — Raspberry Pi 5 + Hailo-8

### 1. Copy project to RPi5

```bash
scp -r assistive_ai_system_v2 pi@<IP>:~/
```

### 2. Run setup script (once)

```bash
chmod +x setup_rpi5.sh
./setup_rpi5.sh
```

This installs HailoRT, Python dependencies, downloads `yolov8n.hef` and Moondream2.

### 3. Activate Hailo-8 + VLM

```python
# config.py
USE_HAILO = True
VLM_ENABLED = True
```

### 4. Run

```bash
source .venv/bin/activate
python main.py
```

---

## 📸 Requirements

| Component | PC (dev) | RPi5 (prod) |
|-----------|----------|-------------|
| Python | 3.10+ | 3.10+ |
| Camera | Webcam | USB / CSI |
| GPU | Optional (NVIDIA) | Hailo-8 (via M.2) |
| RAM | 8GB+ | 8GB |
| OS | Windows / Linux | Raspberry Pi OS 64-bit |

---

## ⚙️ Key Configuration (`config.py`)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `SYSTEM_MODE` | `"navigation"` | `navigation`, `exploration`, `human_priority` |
| `SMOOTHING_ALPHA` | `0.3` | Position smoothing (lower = smoother) |
| `RISK_HIGH_THRESHOLD` | `0.7` | Risk score triggering danger alert |
| `VLM_NARRATOR_INTERVAL` | `7.0` | Seconds between VLM scene descriptions |
| `VLM_ENABLED` | `False` | Enable Moondream2 narration |
| `USE_HAILO` | `False` | Enable Hailo-8 hardware inference |

---

## 🧠 Research Contributions

* **Temporal Scene Modeling** with exponential smoothing
* **Risk Scoring** combining proximity, velocity and object type
* **Context-Aware Decision Systems** — speaks only when it matters
* **Cognitive Filtering for AI Assistants**
* **VLM-based Scene Narration** with danger detection and change detection

---

## ⚠️ Current Limitations

* Distance estimation remains approximate (bbox-based)
* VLM narration requires ~1.7GB RAM on RPi5
* Hailo-8 VLM inference not yet validated on target hardware

---

## 🔮 Future Work

* 🚧 Explicit danger alert with priority interruption
* 🚧 Multi-language TTS support
* 🚧 User testing with visually impaired individuals
* 🚧 Fine-tuned VLM for navigation-specific descriptions
* 🚧 Stereoscopic depth estimation for precise distance

---

## 👨‍💻 Author

**Ariel Kamdem**
Master's Student in Artificial Intelligence & Big Data

---

## 🤝 Contributions

Contributions are welcome!

You can:

* improve detection accuracy
* optimize context and risk logic
* enhance VLM prompt engineering
* propose new features or hardware integrations

---

## 📜 License

This project is for academic and research purposes.

---

## 💡 Final Thought

> "The goal is not to make AI see more,
> but to make it **say less, and say better**."
