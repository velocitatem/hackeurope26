#!/usr/bin/env bash
# demo-flow.sh -- End-to-end green scheduling demo
#
# Demonstrates the full pipeline:
#   1. Submit a GitHub repo for preparation (clone + CodeCarbon integration)
#   2. Poll until the agent finishes preparing the job
#   3. Inspect the prepared job (analysis, patch, dockerfile, manifest)
#   4. Review changed files
#   5. Execute the prepared job (triggers Rails webhook scheduling)
#   6. Poll until scheduling decision is returned
#   7. Display the final scheduling decision and OpenShift job spec
#
# Usage:
#   ./scripts/demo-flow.sh [API_URL]
#
# Requires: curl, jq

set -euo pipefail

API="${1:-http://localhost:9812}"
REPO="https://github.com/velocitatem/mnist"
BRANCH="main"
GEOS='["FR","DE","ES"]'
POLL_INTERVAL=5
MAX_POLL="${MAX_POLL:-240}"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

log()  { printf "\n\033[1;34m>>> %s\033[0m\n" "$*"; }
info() { printf "    \033[0;36m%s\033[0m\n" "$*"; }
err()  { printf "\033[1;31mERROR: %s\033[0m\n" "$*" >&2; exit 1; }

json_field() {
    local result
    result=$(echo "$1" | jq -r ".$2 // empty" 2>/dev/null) || result=""
    echo "$result"
}

safe_jq() {
    # Run jq, return empty/fallback on parse error
    jq "$@" 2>/dev/null || echo ""
}

poll_status() {
    local job_id="$1"
    local target="$2"
    local elapsed=0
    local status=""
    local resp=""

    while [ "$elapsed" -lt "$MAX_POLL" ]; do
        resp=$(curl -sS --fail "${API}/jobs/${job_id}" 2>/dev/null) || resp=""

        # Guard against non-JSON responses
        if [ -z "$resp" ] || ! echo "$resp" | jq -e . >/dev/null 2>&1; then
            info "(waiting for API response...  ${elapsed}s elapsed)"
            sleep "$POLL_INTERVAL"
            elapsed=$((elapsed + POLL_INTERVAL))
            continue
        fi

        status=$(json_field "$resp" "status")
        info "status = ${status}  (${elapsed}s elapsed)"

        case "$status" in
            "$target"|dispatched|dispatch_planned|failed)
                echo "$resp"
                return 0
                ;;
        esac

        sleep "$POLL_INTERVAL"
        elapsed=$((elapsed + POLL_INTERVAL))
    done

    err "timed out waiting for job ${job_id} to reach '${target}' (last status: ${status})"
}

# ---------------------------------------------------------------------------
# Step 1: Submit repo for preparation
# ---------------------------------------------------------------------------

log "Step 1: Submitting ${REPO} for preparation"

PREPARE_RESP=$(curl -sS -X POST "${API}/prepare" \
    -H "Content-Type: application/json" \
    -d "{
        \"repo_url\": \"${REPO}\",
        \"branch\": \"${BRANCH}\",
        \"allowed_geos\": ${GEOS},
        \"timeout\": 600,
        \"verbose\": false
    }")

JOB_ID=$(json_field "$PREPARE_RESP" "job_id")
IMAGE=$(json_field "$PREPARE_RESP" "selected_image")
TASK_ID=$(json_field "$PREPARE_RESP" "celery_task_id")

[ -z "$JOB_ID" ] && err "failed to get job_id from /prepare response"

info "job_id:   ${JOB_ID}"
info "image:    ${IMAGE}"
info "task_id:  ${TASK_ID}"

# ---------------------------------------------------------------------------
# Step 2: Poll until prepared
# ---------------------------------------------------------------------------

log "Step 2: Waiting for agent to finish preparation (cloning, CodeCarbon, Dockerfile)..."
info "(this typically takes 2-4 minutes while the AI agent analyzes and modifies the repo)"

PREPARED_RESP=$(poll_status "$JOB_ID" "prepared")
PREPARED_STATUS=$(json_field "$PREPARED_RESP" "status")

if [ "$PREPARED_STATUS" = "failed" ]; then
    err "job failed during preparation: $(json_field "$PREPARED_RESP" "error")"
fi

info "preparation complete"

# ---------------------------------------------------------------------------
# Step 3: Inspect prepared job
# ---------------------------------------------------------------------------

log "Step 3: Inspecting prepared job"

FRAMEWORK=$(echo "$PREPARED_RESP" | safe_jq -r '.analysis.framework // "unknown"')
ENTRYPOINT=$(echo "$PREPARED_RESP" | safe_jq -r '.analysis.entrypoint // "unknown"')
GPU_COUNT=$(echo "$PREPARED_RESP" | safe_jq -r '.analysis.gpu_count // 0')
EST_HOURS=$(echo "$PREPARED_RESP" | safe_jq -r '.analysis.estimated_hours // "?"')
DEPS=$(echo "$PREPARED_RESP" | safe_jq -r '.analysis.dependencies // [] | join(", ")')
CC_SUMMARY=$(echo "$PREPARED_RESP" | safe_jq -r '.codecarbon_integration.codecarbon_summary // "n/a"')

info "framework:    ${FRAMEWORK}"
info "entrypoint:   ${ENTRYPOINT}"
info "gpu_count:    ${GPU_COUNT}"
info "est. hours:   ${EST_HOURS}"
info "dependencies: ${DEPS}"
info ""
info "CodeCarbon:   ${CC_SUMMARY}"

# ---------------------------------------------------------------------------
# Step 4: Review changed files and patch
# ---------------------------------------------------------------------------

log "Step 4: Changed files"

CHANGED=$(echo "$PREPARED_RESP" | safe_jq -r '.changed_files // [] | .[]')
if [ -n "$CHANGED" ]; then
    echo "$CHANGED" | while read -r f; do info "  - ${f}"; done
else
    info "(no files changed)"
fi

log "Step 4b: Generated Dockerfile"
echo "$PREPARED_RESP" | safe_jq -r '.dockerfile_content // "n/a"' | head -25

log "Step 4c: Generated patch (first 40 lines)"
echo "$PREPARED_RESP" | safe_jq -r '.generated_patch // "n/a"' | head -40

# ---------------------------------------------------------------------------
# Step 5: Retrieve prepared files from VFS
# ---------------------------------------------------------------------------

log "Step 5: Prepared file tree"

FILES_RESP=$(curl -sS --fail "${API}/jobs/${JOB_ID}/files?stage=prepared" 2>/dev/null) || FILES_RESP="{}"
FILE_COUNT=$(json_field "$FILES_RESP" "file_count")
info "total files in prepared VFS: ${FILE_COUNT:-0}"
echo "$FILES_RESP" | safe_jq -r '.tree // [] | .[]' | head -20

# ---------------------------------------------------------------------------
# Step 6: Execute (triggers Rails webhook + OpenShift dispatch)
# ---------------------------------------------------------------------------

log "Step 6: Executing prepared job (scheduling + dispatch)"

EXEC_RESP=$(curl -sS -X POST "${API}/jobs/${JOB_ID}/execute" \
    -H "Content-Type: application/json" \
    -d "{
        \"image\": \"${IMAGE}\",
        \"namespace\": \"drosel-ieu2022-dev\"
    }")

EXEC_STATUS=$(json_field "$EXEC_RESP" "status")
EXEC_TASK=$(json_field "$EXEC_RESP" "celery_task_id")
info "execute status: ${EXEC_STATUS}"
info "task_id:        ${EXEC_TASK}"

# ---------------------------------------------------------------------------
# Step 7: Poll until dispatch decision
# ---------------------------------------------------------------------------

log "Step 7: Waiting for scheduling decision..."

FINAL_RESP=$(poll_status "$JOB_ID" "dispatched")
FINAL_STATUS=$(json_field "$FINAL_RESP" "status")

# ---------------------------------------------------------------------------
# Step 8: Display final result
# ---------------------------------------------------------------------------

log "Step 8: Final result"

info "status:          ${FINAL_STATUS}"
info "scheduling_mode: $(json_field "$FINAL_RESP" "scheduling_mode")"

DECISION=$(echo "$FINAL_RESP" | safe_jq '.scheduling_decision // {}')
info ""
info "--- Scheduling Decision ---"
echo "$DECISION" | safe_jq -r 'to_entries[] | "    \(.key): \(.value)"'

OPENSHIFT_JOB=$(echo "$FINAL_RESP" | safe_jq '.openshift_job // {}')
info ""
info "--- OpenShift Job ---"
echo "$OPENSHIFT_JOB" | safe_jq -r 'to_entries[] | "    \(.key): \(.value)"'

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

GEO=$(echo "$DECISION" | safe_jq -r '.geo // "n/a"')
PROVIDER=$(echo "$DECISION" | safe_jq -r '.provider // "n/a"')
REGION=$(echo "$DECISION" | safe_jq -r '.region // "n/a"')
SCORE=$(echo "$DECISION" | safe_jq -r '.score // "n/a"')
JOB_NAME=$(echo "$OPENSHIFT_JOB" | safe_jq -r '.job_name // "n/a"')
NAMESPACE=$(echo "$OPENSHIFT_JOB" | safe_jq -r '.namespace // "n/a"')

log "Demo complete"
info ""
info "Pipeline: submit -> clone -> agent (CodeCarbon) -> prepare -> confirm -> execute"
info "  scheduling_mode = prepared"
info "  Rails webhook returned: geo=${GEO}, provider=${PROVIDER}, region=${REGION}"
info "  Score: ${SCORE}"
info "  Job: ${JOB_NAME} in namespace ${NAMESPACE}"
info ""
info "To switch to admission mode (requires cluster-admin):"
info "  export SCHEDULING_MODE=admission"
