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

👉 The goal is to transform raw visual perception into **useful, minimal, and actionable information**.

---

## 🎯 Project Vision

The system evolves from:

> ❌ “An object detection system that speaks”

to:

> ✅ **A real-time contextual visual mobility assistant**

This means:

* Not everything detected is spoken
* The system **decides what matters**
* It behaves closer to **human perception and reasoning**

---

## 🧱 System Architecture

The system is modular and follows a cognitive pipeline:

```
Perception → Memory → State → Decision → Context → Audio
```

### 📂 Project Structure

```
perception/        # Object detection (YOLO)
scene/             # Scene memory and tracking
decision/          # Decision logic (message generation)
context/           # Context manager (cognitive filtering)
audio/             # Text-to-speech system
main.py            # Main pipeline
config.py          # System parameters
```

---

## ⚙️ Core Components

### 1. 🎥 Perception (Object Detection)

* YOLO-based real-time detection
* Bounding boxes, labels, and coordinates
* Works on live camera input

---

### 2. 🧠 Scene Memory

* Tracks objects across frames
* Assigns unique IDs
* Stores:

  * position history
  * proximity score
  * temporal persistence

---

### 3. 🔄 State Machine

Defines object states:

* `NEW`
* `STABLE`
* `APPROACHING`
* `GONE`

👉 Reduces noise and stabilizes perception.

---

### 4. 🎯 Decision Engine

* Selects relevant objects
* Prioritizes:

  * 👤 people
  * ⚠ obstacles
* Generates messages like:

  * `"Person ahead"`
  * `"Two persons ahead"`
  * `"Close ahead"`

---

### 5. 🧠 Context Manager (Core Innovation)

The **Context Manager** is the key component that transforms the system into an intelligent assistant.

It:

* filters repetitive messages
* stabilizes scene interpretation
* applies temporal reasoning
* prioritizes important information

👉 It ensures:

> The system speaks **only when necessary**

---

### 6. 🔊 Audio Engine

* Asynchronous speech system
* Non-blocking audio output
* Smooth real-time interaction

---

## 🚀 Features

* ✅ Real-time object detection
* ✅ Multi-object tracking
* ✅ Context-aware decision-making
* ✅ Reduced cognitive overload
* ✅ Intelligent audio feedback
* ✅ Multi-person detection support
* ✅ Scene stability modeling

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
(silence)
Close ahead
```

---

## 🔧 Installation

### 1. Clone the repository

```bash
git clone https://github.com/Ariel1999-bli/assistive_ai_system_v2.git
cd assistive-ai-v2
```

---

### 2. Create environment (recommended)

```bash
conda create -n assistive-ai python=3.10
conda activate assistive-ai
```

---

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

---

### 4. Run the system

```bash
python main.py
```

---

## 📸 Requirements

* Python 3.9+
* Webcam
* GPU (optional but recommended)

---

## 🧠 Research Contributions

This project introduces:

* **Temporal Scene Modeling**
* **Context-Aware Decision Systems**
* **Cognitive Filtering for AI Assistants**
* **Real-time Human-Centered AI Interaction**

👉 It bridges the gap between:

* computer vision
* and human perception

---

## ⚠️ Current Limitations

* Sensitivity to small movements
* Approximate distance estimation
* No explicit danger classification (yet)

---

## 🔮 Future Work

* 🚧 Danger detection (collision risk)
* 🚧 Natural language narration
* 🚧 Embedded deployment (Raspberry Pi / Jetson)
* 🚧 User testing with visually impaired individuals
* 🚧 Multi-language support

---

## 👨‍💻 Author

**Ariel Kamdem**
Master’s Student in Artificial Intelligence & Big Data

---

## 🤝 Contributions

Contributions are welcome!

You can:

* improve detection
* optimize context logic
* enhance audio interaction
* propose new features

---

## 📜 License

This project is for academic and research purposes.

---

## 💡 Final Thought

> “The goal is not to make AI see more,
> but to make it **say less, and say better**.”
