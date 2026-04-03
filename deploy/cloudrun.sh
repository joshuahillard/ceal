#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Céal — GCP Cloud Run Deployment
# ---------------------------------------------------------------------------
set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:?Set GCP_PROJECT_ID}"
REGION="${GCP_REGION:-us-east1}"
SERVICE_NAME="ceal"
IMAGE="us-docker.pkg.dev/${PROJECT_ID}/ceal/ceal:latest"
CLOUD_SQL_INSTANCE="${CLOUD_SQL_INSTANCE:?Set CLOUD_SQL_INSTANCE}"

echo "=== Céal Cloud Run Deployment ==="
echo "Project: ${PROJECT_ID}"
echo "Region:  ${REGION}"
echo "Image:   ${IMAGE}"
echo ""

echo "Building Docker image..."
docker build -t "${IMAGE}" .

echo "Pushing to Artifact Registry..."
docker push "${IMAGE}"

echo "Deploying to Cloud Run..."
gcloud run deploy "${SERVICE_NAME}" \
    --image="${IMAGE}" \
    --region="${REGION}" \
    --platform=managed \
    --allow-unauthenticated \
    --port=8000 \
    --memory=512Mi \
    --cpu=1 \
    --min-instances=0 \
    --max-instances=3 \
    --set-env-vars="PORT=8000" \
    --set-secrets="LLM_API_KEY=LLM_API_KEY:latest" \
    --set-secrets="DATABASE_URL=DATABASE_URL:latest" \
    --add-cloudsql-instances="${CLOUD_SQL_INSTANCE}"

echo ""
echo "=== Deployment Complete ==="
SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" \
    --region="${REGION}" --format="value(status.url)")
echo "Service URL: ${SERVICE_URL}"
echo "Health check: ${SERVICE_URL}/health"
