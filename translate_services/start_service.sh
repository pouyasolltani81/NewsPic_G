#!/bin/bash

# Disable PyTorch's CUDA graphs (causing the AssertionError)
export PYTORCH_DISABLE_CUDA_GRAPHS=1
export TORCH_CUDNN_V8_API_DISABLED=1

# CUDA error prevention
export CUDA_LAUNCH_BLOCKING=1
export TORCH_USE_CUDA_DSA=1
export PYTORCH_CUDA_ALLOC_CONF="max_split_size_mb:512"

# Force single GPU
export CUDA_VISIBLE_DEVICES=0

# Disable PyTorch compile mode
export TORCH_COMPILE_DISABLE=1

# Python settings
export PYTHONUNBUFFERED=1
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1

# Start the service
exec /home/anews/pytorch/bin/python -u /home/anews/pytorch/bin/uvicorn services:app \
    --host 0.0.0.0 \
    --port 8001 \
    --workers 1 \
    --loop asyncio \
    --log-level info \
    --no-access-log