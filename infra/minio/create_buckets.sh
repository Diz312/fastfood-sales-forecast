#!/bin/sh
set -e

# Wait for MinIO to be ready
until mc alias set local http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" 2>/dev/null; do
  echo "Waiting for MinIO..."
  sleep 2
done

# Create buckets
mc mb --ignore-existing local/mlflow-artifacts
mc mb --ignore-existing local/forecast-outputs

echo "MinIO buckets created successfully."
