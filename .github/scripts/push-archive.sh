#!/usr/bin/env bash
# Commit data/ and site/ to main.
# Rebase and retry when the other archive job pushed first.
set -euo pipefail

message="${1:-Update deals from the Telegram channel}"

git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git add data site

if git diff --staged --quiet; then
  echo "changed=false" >> "$GITHUB_OUTPUT"
  echo "No changes to commit"
  exit 0
fi

git commit -m "$message"

for attempt in 1 2 3 4 5; do
  if git pull --rebase origin main && git push origin HEAD:main; then
    echo "changed=true" >> "$GITHUB_OUTPUT"
    echo "Pushed on attempt ${attempt}"
    exit 0
  fi
  echo "Push attempt ${attempt} did not land. Retrying."
  git rebase --abort 2>/dev/null || true
  sleep $((attempt * 4))
done

echo "Could not push after 5 attempts."
exit 1
