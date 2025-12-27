#!/usr/bin/env bash
set -euo pipefail

printf "IMAGE_PROVIDER=%s\n" "${IMAGE_PROVIDER:-auto}"
if [[ -z "${GCP_PROJECT:-}" ]]; then
  echo "GCP_PROJECT fehlt"
else
  echo "GCP_PROJECT=${GCP_PROJECT}"
fi

cred_path=${GOOGLE_APPLICATION_CREDENTIALS:-}
if [[ -n "$cred_path" ]]; then
  if [[ -f "$cred_path" ]]; then
    echo "GOOGLE_APPLICATION_CREDENTIALS vorhanden: $cred_path"
  else
    echo "GOOGLE_APPLICATION_CREDENTIALS zeigt auf fehlende Datei: $cred_path"
  fi
else
  echo "GOOGLE_APPLICATION_CREDENTIALS nicht gesetzt"
fi

if [[ -n "${GOOGLE_APPLICATION_CREDENTIALS_JSON:-}" ]]; then
  echo "GOOGLE_APPLICATION_CREDENTIALS_JSON gesetzt (inline)"
else
  echo "GOOGLE_APPLICATION_CREDENTIALS_JSON nicht gesetzt"
fi
