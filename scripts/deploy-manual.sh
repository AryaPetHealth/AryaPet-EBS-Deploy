#!/usr/bin/env bash
#
# Deploys the current commit to the dev Elastic Beanstalk environment from a
# laptop, without GitHub Actions.
#
#   aws login            # first, if the session has expired
#   ./scripts/deploy-manual.sh
#
# Mirrors .github/workflows/deploy.yml step for step, so a manual deploy and a
# CI deploy produce the same application version and the same checks. Use it
# when Actions minutes are exhausted, or to ship without pushing.

set -euo pipefail

AWS_REGION="${AWS_REGION:-ap-south-1}"
EB_APPLICATION_NAME="${EB_APPLICATION_NAME:-arya-ebstalk-dev}"
EB_ENVIRONMENT_NAME="${EB_ENVIRONMENT_NAME:-arya-ebstalk-dev-env}"

step() { printf '\n\033[1m==> %s\033[0m\n' "$1"; }
fail() { printf '\033[31merror: %s\033[0m\n' "$1" >&2; exit 1; }

command -v aws >/dev/null || fail "aws CLI not found"

step "Checking AWS credentials"
aws sts get-caller-identity --query 'Arn' --output text \
  || fail "not authenticated — run 'aws login' first"

step "Checking the working tree is clean"
if [ -n "$(git status --porcelain)" ]; then
  echo "Uncommitted changes present:"
  git status --short
  # The version label is the commit sha, so deploying dirty would ship code that
  # doesn't match the label and can't be reproduced later.
  fail "commit or stash before deploying, so the version label matches what ships"
fi

VERSION_LABEL="$(git rev-parse HEAD)"
step "Deploying $VERSION_LABEL to $EB_ENVIRONMENT_NAME"

aws elasticbeanstalk describe-environments \
  --environment-names "$EB_ENVIRONMENT_NAME" --region "$AWS_REGION" \
  --query 'Environments[0].{Status:Status,Health:Health,Current:VersionLabel}' \
  --output table

step "Packaging source bundle"
BUNDLE="$(mktemp -d)/deploy.zip"
zip -qr "$BUNDLE" . \
  -x ".git/*" ".github/*" ".venv/*" "**/__pycache__/*" \
     "tests/*" ".pytest_cache/*" ".ruff_cache/*" "scripts/*"
echo "$(du -h "$BUNDLE" | cut -f1) bundle"

step "Uploading to EB's source bucket"
BUCKET="$(aws elasticbeanstalk create-storage-location \
  --region "$AWS_REGION" --query 'S3Bucket' --output text)"
aws s3 cp "$BUNDLE" "s3://$BUCKET/$EB_APPLICATION_NAME/$VERSION_LABEL.zip" \
  --region "$AWS_REGION"

step "Creating application version"
EXISTING="$(aws elasticbeanstalk describe-application-versions \
  --application-name "$EB_APPLICATION_NAME" \
  --version-labels "$VERSION_LABEL" --region "$AWS_REGION" \
  --query "ApplicationVersions[0].VersionLabel" --output text)"

if [ "$EXISTING" = "$VERSION_LABEL" ]; then
  echo "Version $VERSION_LABEL already exists, reusing it."
else
  aws elasticbeanstalk create-application-version \
    --application-name "$EB_APPLICATION_NAME" \
    --version-label "$VERSION_LABEL" \
    --source-bundle S3Bucket="$BUCKET",S3Key="$EB_APPLICATION_NAME/$VERSION_LABEL.zip" \
    --region "$AWS_REGION" >/dev/null
  echo "created."
fi

step "Updating the environment (this takes a few minutes)"
aws elasticbeanstalk update-environment \
  --environment-name "$EB_ENVIRONMENT_NAME" \
  --version-label "$VERSION_LABEL" \
  --region "$AWS_REGION" >/dev/null

aws elasticbeanstalk wait environment-updated \
  --environment-names "$EB_ENVIRONMENT_NAME" --region "$AWS_REGION"

step "Verifying"
HEALTH="$(aws elasticbeanstalk describe-environments \
  --environment-names "$EB_ENVIRONMENT_NAME" --region "$AWS_REGION" \
  --query 'Environments[0].Health' --output text)"
echo "environment health: $HEALTH"

CNAME="$(aws elasticbeanstalk describe-environments \
  --environment-names "$EB_ENVIRONMENT_NAME" --region "$AWS_REGION" \
  --query 'Environments[0].CNAME' --output text)"

# EB can report Green just as the container comes up, before it serves traffic —
# confirm with a real request rather than trusting the platform's status.
for attempt in 1 2 3 4 5 6; do
  CODE="$(curl -s -o /dev/null -w '%{http_code}' "http://$CNAME/health" || echo 000)"
  if [ "$CODE" = "200" ]; then
    printf '\n\033[32mdeployed — GET /health returned 200\033[0m\n'
    echo "next: ./scripts/smoke-extraction.sh <your.pdf>"
    exit 0
  fi
  echo "GET /health -> $CODE, retrying ($attempt/6)..."
  sleep 10
done

step "Health check never passed — recent environment events"
aws elasticbeanstalk describe-events \
  --environment-name "$EB_ENVIRONMENT_NAME" --region "$AWS_REGION" \
  --max-items 15 \
  --query 'Events[].{Time:EventDate,Severity:Severity,Message:Message}' \
  --output table || true
fail "environment did not come up healthy"
