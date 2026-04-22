# config.py

YOLO_MODEL_PATH = "models/yolov8n.pt"
CONF_THRESHOLD = 0.4

FRAME_WIDTH = 640
FRAME_HEIGHT = 480

# ==============================
# SYSTEM MODE
# ==============================
# Options:
# - "navigation"
# - "exploration"
# - "human_priority"
SYSTEM_MODE = "navigation"

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
STATE_MOVE_THRESHOLD_PX = 18.0

# ==============================
# SEMANTIC FILTERING
# ==============================
IMPORTANT_OBJECTS = {
    "person",
    "car",
    "bicycle",
    "chair",
    "bed",
    "couch",
    "dining table",
}

EXPLORATION_OBJECTS = {
    "person",
    "chair",
    "bed",
    "couch",
    "dining table",
    "bottle",
    "cup",
    "book",
    "cell phone",
    "remote",
    "tv",
    "laptop",
    "keyboard",
    "mouse",
    "oven",
    "sink",
    "refrigerator",
}

IGNORE_OBJECTS = {
    "fork",
    "spoon",
    "bowl",
    "donut",
    "wine glass",
}

OBJECT_PRIORITIES = {
    "person": 10,
    "car": 8,
    "bicycle": 8,

    "chair": 4,
    "bed": 4,
    "couch": 4,
    "dining table": 3,

    "bottle": 2,
    "cup": 2,
    "book": 2,
    "cell phone": 2,
    "remote": 2,
    "tv": 2,
    "laptop": 2,
    "keyboard": 2,
    "mouse": 2,
    "oven": 2,
    "sink": 2,
    "refrigerator": 2,
}

# ==============================
# MULTI-PERSON / CLOSE LOGIC
# ==============================
PERSON_CLOSE_THRESHOLD = 0.72
OBJECT_CLOSE_THRESHOLD = 0.82

# ==============================
# AUDIO
# ==============================
TTS_RATE = 210
SPEAK_COOLDOWN = 0.3

# ==============================
# SMOOTHING
# ==============================
SMOOTHING_ALPHA = 0.3

# ==============================
# RISK SCORING
# ==============================
RISK_WEIGHTS = {
    "car": 3.0,
    "bicycle": 2.0,
    "person": 1.5,
    "default": 1.0,
}
RISK_HIGH_THRESHOLD = 0.7

# ==============================
# NARRATOR
# ==============================
NARRATOR_ENABLED = True
VLM_NARRATOR_INTERVAL = 7.0
VLM_ENABLED = False
NARRATOR_JACCARD_THRESHOLD = 0.6
NARRATOR_MIN_PARTS = 2

# Ralentissement pendant transitions
NARRATOR_STABILITY_REQUIRED = 1.3
NARRATOR_PENDING_CONFIRMATIONS = 2
NARRATOR_POST_SPEAK_GRACE = 2.2

# ==============================
# CONTEXT FILTER
# ==============================
CTX_MIN_SPEAK_INTERVAL = 1.2
CTX_SAME_MESSAGE_INTERVAL = 3.0
CTX_SCENE_STABILITY_TIME = 0.5
CTX_NARRATION_EXTRA_DELAY = 1.0

# ==============================
# HAILO-8
# ==============================
USE_HAILO = False
HAILO_MODEL_PATH = "models/yolov8n.hef"