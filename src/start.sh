#!/bin/bash

echo "Worker Initiated"

# Link models and VAE
mkdir -p /runpod-volume/models/Stable-diffusion
mkdir -p /runpod-volume/models/VAE
ln -s /sd-models/sd_xl_base_1.0.safetensors /runpod-volume/models/Stable-diffusion/sd_xl_base_1.0.safetensors
ln -s /sd-models/sd_xl_refiner_1.0.safetensors /runpod-volume/models/Stable-diffusion/sd_xl_refiner_1.0.safetensors
ln -s /sd-models/sdxl_vae.safetensors /runpod-volume/models/VAE/sdxl_vae.safetensors

# Create logs directory
mkdir -p /ComfyUI/logs

echo "Starting ComfyUI"
python /ComfyUI/main.py --listen 0.0.0.0 --port 3021 > /ComfyUI/logs/comfyui.log 2>&1 &
echo "ComfyUI started"
echo "Log file: /ComfyUI/logs/comfyui.log"

echo "Starting RunPod Handler"
python -u /handler.py
