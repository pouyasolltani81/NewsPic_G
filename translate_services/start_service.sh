#!/bin/bash

# ============================================================================
# TRANSLATION SERVICE - 2 MODEL INSTANCES ON GPU
# ============================================================================

export CUDA_VISIBLE_DEVICES=0
export PYTORCH_CUDA_ALLOC_CONF="max_split_size_mb:256,expandable_segments:True"
export PYTORCH_DISABLE_CUDA_GRAPHS=1
export TORCH_CUDNN_V8_API_DISABLED=1
export TORCH_COMPILE_DISABLE=1
export TORCHINDUCTOR_DISABLE=1
export PYTHONUNBUFFERED=1
export OMP_NUM_THREADS=4
export MKL_NUM_THREADS=4

PORT=${PORT:-8001}

echo "============================================"
echo "Translation Service - 2 GPU Instances"
echo "============================================"
echo "GPU: $(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null)"
echo "Port: $PORT"
echo "Instances: 2"
echo "============================================"

exec /home/anews/pytorch/bin/python -u /home/anews/pytorch/bin/uvicorn \
    model_service:app \
    --host 0.0.0.0 \
    --port $PORT \
    --workers 1 \
    --loop asyncio \
    --log-level info