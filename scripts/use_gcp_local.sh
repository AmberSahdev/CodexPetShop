#!/usr/bin/env bash

# Usage:
#   source scripts/use_gcp_local.sh
#
# Optional overrides before sourcing:
#   export GOOGLE_APPLICATION_CREDENTIALS="/abs/path/to/service-account.json"
#   export GOOGLE_CLOUD_PROJECT="codexpetshop"
#   export CPS_BUCKET="codexpetshop-pets"
#   export CPS_COLLECTION="pets"
#   export CPS_CANONICAL_HOST="www.codexpetshop.com"

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  echo "Run this with: source scripts/use_gcp_local.sh"
  exit 1
fi

export CPS_BACKEND="${CPS_BACKEND:-gcp}"
export GOOGLE_CLOUD_PROJECT="${GOOGLE_CLOUD_PROJECT:-codexpetshop}"
export CPS_BUCKET="${CPS_BUCKET:-codexpetshop-pets}"
export CPS_COLLECTION="${CPS_COLLECTION:-pets}"
export CPS_CANONICAL_HOST="${CPS_CANONICAL_HOST:-www.codexpetshop.com}"

if [[ -z "${GOOGLE_APPLICATION_CREDENTIALS:-}" ]]; then
  echo "GOOGLE_APPLICATION_CREDENTIALS is not set."
  echo "Set it first, for example:"
  echo '  export GOOGLE_APPLICATION_CREDENTIALS="$HOME/path/to/service-account.json"'
  return 1
fi

echo "Using GCP backend locally:"
echo "  CPS_BACKEND=$CPS_BACKEND"
echo "  GOOGLE_CLOUD_PROJECT=$GOOGLE_CLOUD_PROJECT"
echo "  CPS_BUCKET=$CPS_BUCKET"
echo "  CPS_COLLECTION=$CPS_COLLECTION"
echo "  CPS_CANONICAL_HOST=$CPS_CANONICAL_HOST"
echo "  GOOGLE_APPLICATION_CREDENTIALS=$GOOGLE_APPLICATION_CREDENTIALS"
