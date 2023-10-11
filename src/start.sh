#!/bin/bash

echo "Worker Initiated"

# Sync ComfyUI to workspace to support Network volumes
echo "Syncing ComfyUI to workspace, please wait..."
mkdir -p /workspace/ComfyUI
rsync -au /ComfyUI/ /workspace/ComfyUI/
rm -rf /ComfyUI

# Link models and VAE
mkdir -p /workspace/models/Stable-diffusion
mkdir -p /workspace/models/VAE
ln -s /sd-models/sd_xl_base_1.0.safetensors /workspace/models/Stable-diffusion/sd_xl_base_1.0.safetensors
ln -s /sd-models/sd_xl_refiner_1.0.safetensors /workspace/models/Stable-diffusion/sd_xl_refiner_1.0.safetensors
ln -s /sd-models/sdxl_vae.safetensors /workspace/models/VAE/sdxl_vae.safetensors

# Create logs directory
mkdir -p /workspace/logs

echo "Starting ComfyUI"
python /workspace/ComfyUI/main.py --listen 0.0.0.0 --port 3021 > /workspace/logs/comfyui.log 2>&1 &
echo "ComfyUI started"
echo "Log file: /workspace/logs/comfyui.log"

echo "Starting RunPod Handler"
# python -u /handler.py

sleep infinity