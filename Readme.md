
# Assistive AI v2
## A Context-Aware Real-Time Visual Mobility Assistant for the Visually Impaired

---

## Abstract

Assistive AI v2 is a real-time intelligent system designed to assist visually impaired individuals by providing context-aware audio feedback about their surroundings. Unlike traditional object detection systems that generate continuous and redundant descriptions, this project focuses on **selective communication**, **temporal reasoning**, and **context-aware decision-making**.

The system transforms raw visual perception into **minimal, actionable, and user-relevant information**, aiming to reduce cognitive overload while improving situational awareness. The architecture integrates object detection, scene memory, temporal state modeling, decision logic, and cognitive filtering to produce adaptive and human-centered behavior.

---

## 1. Introduction

Most existing assistive vision systems rely on direct mapping between perception and speech, leading to excessive, redundant, and often unusable outputs.

This project addresses a fundamental question:

> How can an AI system decide **what to say, when to say it, and when to remain silent?**

Assistive AI v2 proposes a shift from:

- frame-based perception  
to  
- **context-aware temporal understanding**

and from:

- exhaustive description  
to  
- **intelligent selective communication**

---

## 2. Problem Statement

Traditional systems suffer from:

- high redundancy in output
- lack of temporal awareness
- inability to prioritize information
- cognitive overload for the user

Therefore, the challenge is not only to detect objects, but to:

- interpret their relevance
- track their evolution over time
- communicate only critical information

---

## 3. System Overview

The system follows a modular cognitive pipeline:

```

Perception → Memory → State → Decision → Context → Audio

```

This pipeline models a simplified form of human perception and reasoning.

---

## 4. Architecture

### 4.1 Perception Layer

- Real-time object detection using YOLO
- Outputs bounding boxes, labels, and spatial information

---

### 4.2 Scene Memory

- Tracks objects across frames
- Assigns persistent IDs
- Maintains temporal information:
  - position history
  - proximity estimation
  - stability over time

---

### 4.3 State Machine

Each object is modeled using discrete temporal states:

- NEW
- STABLE
- APPROACHING
- GONE

This enables the system to reason about **object dynamics** rather than static detections.

---

### 4.4 Decision Engine

The Decision Engine is responsible for:

- selecting relevant objects
- prioritizing critical elements (e.g., humans, obstacles)
- generating concise messages

Examples:

- "Person ahead"
- "Person approaching on your left"
- "Close ahead"

It operates under a **minimalist and reactive design philosophy**.

---

### 4.5 Context Manager

The Context Manager is the **core cognitive component**.

It ensures:

- reduction of redundant messages
- temporal consistency
- prioritization of significant changes
- suppression of irrelevant outputs

It decides whether:

> the system should speak or remain silent.

---

### 4.6 Audio Engine

- Asynchronous text-to-speech system
- Non-blocking communication
- Real-time feedback

---

## 5. Behavioral Modes

The system supports multiple operational modes:

### Navigation Mode
- Focus on safety and mobility
- Minimal communication
- Emphasis on proximity and obstacles

---

### Human Priority Mode
- Focus on human presence
- Increased sensitivity to people
- More expressive descriptions

---

### Exploration Mode
- Focus on environmental understanding
- Descriptive behavior
- Reduced urgency in alerts

---

## 6. Key Contributions

This project introduces:

- **Context-aware decision-making for assistive AI**
- **Temporal scene modeling in real-time systems**
- **Cognitive filtering for human-centered interaction**
- **Selective communication as a design paradigm**
- **Multi-mode adaptive behavior**

---

## 7. System Behavior Example

### Raw Detection System

```

Person ahead
Person ahead
Person ahead
Bottle on your left
Chair on your right

```

---

### Assistive AI v2

```

Person ahead
(silence — stable scene)
Person approaching on your left
(silence)
Close ahead

```

---

## 8. Current Limitations

- Sensitivity to detection noise (YOLO limitations)
- Approximate distance estimation
- Occasional false multi-person detection
- Exploration mode not fully optimized

---

## 9. Future Work

- Event-based reasoning (EAD-inspired logic)
- Integration of Vision-Language Models (VLM)
- Improved risk prediction
- Embedded deployment (Raspberry Pi / Jetson)
- Real-world testing with visually impaired users
- Multilingual support

---

## 10. Research Perspective

This work contributes to the intersection of:

- computer vision
- human-centered AI
- assistive technologies
- real-time intelligent systems

It aligns with emerging research directions focusing on:

- **reducing redundancy in AI outputs**
- **temporal awareness in perception systems**
- **efficient human-AI interaction**

---

## 11. Author

Ariel Kamdem  
Master’s Student in Artificial Intelligence & Big Data

---

## 12. License

This project is developed for academic and research purposes.

---

## Final Insight

> A truly intelligent assistive system does not describe everything it sees.  
> It communicates only what is necessary, at the right time.
```
