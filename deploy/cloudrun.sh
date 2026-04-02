#!/usr/bin/env bash
# Céal — Deploy to GCP Cloud Run
#
# Prerequisites:
#   - gcloud CLI installed and authenticated
#   - GCP project set: gcloud config set project YOUR_PROJECT_ID
#   - Artifact Registry repo created:
#     gcloud artifacts repositories create ceal --repository-format=docker --location=us-east1
#
# Usage:
#   ./deploy/cloudrun.sh
#
# Environment variables (required):
#   GCP_PROJECT_ID  — Your GCP project ID
#   LLM_API_KEY     — Anthropic API key (will be stored in Secret Manager)

set -euo pipefail

# Configuration
REGION="us-east1"
SERVICE_NAME="ceal"
IMAGE_NAME="us-east1-docker.pkg.dev/${GCP_PROJECT_ID}/ceal/ceal"

# Validate required env vars
if [ -z "${GCP_PROJECT_ID:-}" ]; then
    echo "ERROR: GCP_PROJECT_ID is not set"
    exit 1
fi

echo "=== Building Docker image ==="
docker build -t "${IMAGE_NAME}:latest" .

echo "=== Pushing to Artifact Registry ==="
docker push "${IMAGE_NAME}:latest"

echo "=== Deploying to Cloud Run ==="
gcloud run deploy "${SERVICE_NAME}" \
    --image "${IMAGE_NAME}:latest" \
    --region "${REGION}" \
    --platform managed \
    --port 8000 \
    --memory 512Mi \
    --cpu 1 \
    --min-instances 0 \
    --max-instances 3 \
    --set-env-vars "PYTHONPATH=." \
    --set-secrets "LLM_API_KEY=ceal-llm-api-key:latest" \
    --allow-unauthenticated \
    --quiet

echo "=== Deployment complete ==="
gcloud run services describe "${SERVICE_NAME}" --region "${REGION}" --format="value(status.url)"
