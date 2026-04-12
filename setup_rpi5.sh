#!/bin/bash
# =============================================================
# Setup script — Assistive AI v2 sur Raspberry Pi 5 + Hailo-8
# =============================================================
# Usage :
#   chmod +x setup_rpi5.sh
#   ./setup_rpi5.sh

set -e

echo "=== [1/5] Mise à jour système ==="
sudo apt update && sudo apt upgrade -y

echo "=== [2/5] Installation HailoRT (SDK Hailo-8) ==="
# Installe le driver Hailo, HailoRT et les bindings Python
sudo apt install -y hailo-all

# Vérification
echo "Version HailoRT installée :"
hailortcli fw-control identify

echo "=== [3/5] Dépendances système ==="
sudo apt install -y \
    python3-pip \
    python3-venv \
    espeak \
    libopencv-dev \
    python3-opencv

echo "=== [4/5] Environnement Python ==="
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements_rpi5.txt

echo "=== [5/5] Téléchargement du modèle Hailo ==="
mkdir -p models

# YOLOv8n pré-compilé pour Hailo-8 (depuis Hailo Model Zoo)
# Option A : téléchargement direct depuis le Model Zoo officiel
HAILO_MODEL_URL="https://hailo-model-zoo.s3.eu-west-2.amazonaws.com/ModelZoo/Compiled/v2.13/hailo8/yolov8n.hef"

if [ ! -f "models/yolov8n.hef" ]; then
    echo "Téléchargement de yolov8n.hef..."
    wget -q --show-progress -O models/yolov8n.hef "$HAILO_MODEL_URL"
    echo "Modèle téléchargé : models/yolov8n.hef"
else
    echo "models/yolov8n.hef déjà présent."
fi

echo ""
echo "=== Setup terminé ==="
echo "Pour lancer le système :"
echo "  source .venv/bin/activate"
echo "  python main.py"
echo ""
echo "Pour activer Hailo-8, mettre dans config.py :"
echo "  USE_HAILO = True"
