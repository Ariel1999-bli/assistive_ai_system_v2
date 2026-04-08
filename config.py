# config.py

YOLO_MODEL_PATH = "models/yolov8n.pt"
CONF_THRESHOLD = 0.4

FRAME_WIDTH = 640
FRAME_HEIGHT = 480

# ==============================
# TRACKING
# ==============================

MAX_DISTANCE = 140
MAX_MISSING_FRAMES = 30
TRACK_MATCH_MIN_IOU = 0.08
TRACK_MATCH_SCORE_THRESH = 0.18
TRACK_RECENCY_BONUS = 0.12

# ==============================
# STATE MACHINE
# ==============================

STATE_STABLE_TIME = 1.5
STATE_APPROACH_THRESHOLD = 0.12

# ==============================
# PRIORITÉ / FILTRAGE SÉMANTIQUE
# ==============================

IMPORTANT_OBJECTS = {
    "person",
    "car",
    "bicycle",
    "chair",
    "bed",
    "couch",
    "dining table"
}

IGNORE_OBJECTS = {
    "bottle",
    "cup",
    "fork",
    "spoon",
    "bowl",
    "donut",
    "remote",
    "cell phone",
    "wine glass",
    "oven",
    "tv"
}

OBJECT_PRIORITIES = {
    "person": 10,
    "car": 8,
    "bicycle": 8,

    "chair": 4,
    "bed": 4,
    "couch": 4,
    "dining table": 3,
}

# ==============================
# MULTI-PERSON / CLOSE LOGIC
# ==============================

MULTI_PERSON_CENTER_ONLY = False
MULTI_PERSON_DIRECTION_GAP = 0.18

PERSON_CLOSE_THRESHOLD = 0.72
OBJECT_CLOSE_THRESHOLD = 0.82

# ==============================
# AUDIO
# ==============================

TTS_RATE = 210
SPEAK_COOLDOWN = 0.3