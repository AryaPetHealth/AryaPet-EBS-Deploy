#!/usr/bin/env bash
#
# End-to-end check of the document extraction pipeline, without the iOS app.
#
#   ./scripts/smoke-extraction.sh path/to/report.pdf
#
# Drives the exact sequence the app performs — dev token, presigned upload, PUT to
# S3, submit OCR text, poll for the worker's result — so the pipeline can be tested
# from a laptop with no build, no TestFlight and no CI minutes.
#
# It deliberately submits *deliberately useless* OCR text. If the printed result
# still contains the full parameter list, that proves the extraction came from the
# PDF's own table geometry (app/services/pdf_table_extractor.py) rather than from
# the submitted text — which is the whole point of that change.
#
# Requires: curl, jq, and DEV_AUTH_ENABLED=true on the target environment.

set -euo pipefail

BASE_URL="${BASE_URL:-http://arya-ebstalk-dev-env.eba-bzvnegvp.ap-south-1.elasticbeanstalk.com}"
SUBJECT="${SUBJECT:-smoke-tester}"
POLL_ATTEMPTS="${POLL_ATTEMPTS:-20}"
POLL_INTERVAL="${POLL_INTERVAL:-3}"

PDF_PATH="${1:-}"
if [ -z "$PDF_PATH" ] || [ ! -f "$PDF_PATH" ]; then
  echo "usage: $0 <path-to-pdf>" >&2
  exit 1
fi

FILENAME="$(basename "$PDF_PATH")"
CONTENT_TYPE="application/pdf"

step() { printf '\n\033[1m==> %s\033[0m\n' "$1"; }

step "Checking $BASE_URL is up"
curl -fsS -o /dev/null -w 'GET /health -> %{http_code}\n' "$BASE_URL/health"

step "Minting a dev token (bypasses Cognito/Apple sign-in)"
ACCESS_TOKEN=$(curl -fsS -X POST "$BASE_URL/v1/auth/dev-token" \
  -H 'Content-Type: application/json' \
  -d "{\"subject\":\"$SUBJECT\",\"email\":\"$SUBJECT@example.com\"}" \
  | jq -r '.access_token')
[ -n "$ACCESS_TOKEN" ] && [ "$ACCESS_TOKEN" != "null" ] || { echo "no access_token returned" >&2; exit 1; }
echo "token acquired (${#ACCESS_TOKEN} chars)"

step "Requesting a presigned upload URL"
PRESIGN=$(curl -fsS -X POST "$BASE_URL/v1/documents/presign-upload" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H 'Content-Type: application/json' \
  -d "{\"filename\":\"$FILENAME\",\"content_type\":\"$CONTENT_TYPE\"}")

DOCUMENT_ID=$(jq -r '.document_id' <<<"$PRESIGN")
UPLOAD_URL=$(jq -r '.upload_url' <<<"$PRESIGN")
echo "document_id: $DOCUMENT_ID"

step "Uploading the PDF straight to S3"
# Content-Type must match what was presigned exactly, or S3 rejects the signature.
curl -fsS -X PUT "$UPLOAD_URL" \
  -H "Content-Type: $CONTENT_TYPE" \
  --data-binary "@$PDF_PATH" \
  -o /dev/null -w 'PUT s3 -> %{http_code}\n'

step "Submitting intentionally poor OCR text"
echo "(if the result below is still complete, it came from the PDF, not this text)"
curl -fsS -X POST "$BASE_URL/v1/documents/$DOCUMENT_ID/text" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"text":"LIVER FUNCTION TEST smudged illegible scan"}' \
  -o /dev/null -w 'POST /text -> %{http_code}\n'

step "Waiting for the worker"
for attempt in $(seq 1 "$POLL_ATTEMPTS"); do
  DOCUMENT=$(curl -fsS "$BASE_URL/v1/documents/$DOCUMENT_ID" \
    -H "Authorization: Bearer $ACCESS_TOKEN")
  STATUS=$(jq -r '.status' <<<"$DOCUMENT")
  if [ "$STATUS" != "processing" ] && [ "$STATUS" != "pending" ]; then
    break
  fi
  printf 'status=%s (%s/%s)\n' "$STATUS" "$attempt" "$POLL_ATTEMPTS"
  sleep "$POLL_INTERVAL"
done

step "Result"
echo "status: $STATUS"
if [ "$STATUS" = "failed" ]; then
  echo "failure_reason: $(jq -r '.failure_reason' <<<"$DOCUMENT")" >&2
  exit 1
fi

jq '.parsed_result' <<<"$DOCUMENT"

step "Summary"
jq -r '
  .parsed_result as $r
  | "strategy:    \($r.extraction.source // "?")/\($r.extraction.strategy // "?")",
    "sections:    \(($r.sections // []) | length)",
    "parameters:  \(([$r.sections // [] | .[].parameters | length] | add) // 0)",
    "abnormal:    \(([$r.sections // [] | .[].parameters[] | select(.abnormal)] | length))",
    "canonical:   \(([$r.sections // [] | .[].parameters[] | select(.canonical_name)] | length)) mapped"
' <<<"$DOCUMENT"
