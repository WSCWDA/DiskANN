#!/usr/bin/env bash
set -euo pipefail
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
cat > "$tmp/mock" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$MOCK_LOG"
EOF
chmod +x "$tmp/mock"
export MOCK_LOG="$tmp/log" SEARCH_BIN="$tmp/mock" INDEX_PREFIX=x QUERY_FILE=x GT_FILE=x OUT="$tmp/out" REPEATS=1 GROUP_SIZES="64 512" POOL_SIZES="1024"
bash scripts/qshape/run_grouping_sensitivity.sh
[[ $(wc -l < "$MOCK_LOG") == 12 ]]
[[ $(grep -c -- '--qshape-group-size 64 --qshape-candidate-pool 512' "$MOCK_LOG") == 3 ]]
[[ $(grep -c -- '--qshape-group-size 512 --qshape-candidate-pool 512' "$MOCK_LOG") == 3 ]]
[[ $(grep -c -- '--qshape-group-size 256 --qshape-candidate-pool 1024' "$MOCK_LOG") == 3 ]]
echo PASS
