#!/bin/bash
set -euo pipefail

BACKUP_DIR="/backup"
DATE=$(date +%Y-%m-%d)
FILENAME="stockradar_${DATE}.sql.gz"

mkdir -p "$BACKUP_DIR"

PGPASSWORD="$POSTGRES_PASSWORD" pg_dump \
  -h postgres \
  -U "$POSTGRES_USER" \
  -d "$POSTGRES_DB" \
  | gzip > "${BACKUP_DIR}/${FILENAME}"

echo "[$(date)] Backup complete: ${FILENAME}"

# Retain last 7 days
find "$BACKUP_DIR" -name "stockradar_*.sql.gz" -mtime +7 -delete
echo "[$(date)] Old backups pruned."
