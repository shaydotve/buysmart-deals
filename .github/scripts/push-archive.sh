#!/usr/bin/env bash
# Commit data/ and site/ to main.
# A content conflict in the archive is merged by post id and retried.
# Exit 0 on success, 1 if the push still failed (caller may re-queue), 2 if fatal.
set -u

message="${1:-Update deals from the Telegram channel}"

git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git add data site

if git diff --staged --quiet; then
  echo "changed=false" >> "$GITHUB_OUTPUT"
  echo "status=ok" >> "$GITHUB_OUTPUT"
  echo "No changes to commit"
  exit 0
fi

git commit -m "$message"

finish_ok() {
  echo "changed=true" >> "$GITHUB_OUTPUT"
  echo "status=ok" >> "$GITHUB_OUTPUT"
  echo "Pushed on attempt ${1}"
  exit 0
}

fail_transient() {
  echo "status=transient" >> "$GITHUB_OUTPUT"
  echo "Could not push after retries. The next backfill run can retry this batch."
  exit 1
}

fail_fatal() {
  echo "status=fatal" >> "$GITHUB_OUTPUT"
  echo "Fatal archive conflict. Not retrying automatically."
  exit 2
}

for attempt in 1 2 3 4 5 6; do
  git fetch origin main
  if git merge-base --is-ancestor origin/main HEAD; then
    if git push origin HEAD:main; then
      finish_ok "$attempt"
    fi
    echo "Push attempt ${attempt} was rejected. Retrying."
  elif git rebase origin/main; then
    if git push origin HEAD:main; then
      finish_ok "$attempt"
    fi
    echo "Push attempt ${attempt} was rejected after rebase. Retrying."
  else
    echo "Rebase conflict on attempt ${attempt}. Merging archive records."
    python -m scraper.resolve_rebase
    resolve_status=$?
    if [ "$resolve_status" -eq 2 ]; then
      git rebase --abort 2>/dev/null || true
      fail_fatal
    fi
    if [ "$resolve_status" -ne 0 ]; then
      git rebase --abort 2>/dev/null || true
      echo "Resolver failed on attempt ${attempt}."
    elif GIT_EDITOR=true git rebase --continue; then
      if git push origin HEAD:main; then
        finish_ok "$attempt"
      fi
      echo "Push attempt ${attempt} was rejected after resolving. Retrying."
    elif git diff --quiet && git diff --cached --quiet; then
      echo "Resolved commit is already on main. Skipping it."
      git rebase --skip || git rebase --abort 2>/dev/null || true
      if git push origin HEAD:main; then
        finish_ok "$attempt"
      fi
    else
      echo "rebase --continue failed on attempt ${attempt}."
      git rebase --abort 2>/dev/null || true
    fi
  fi
  sleep $((attempt * 5))
done

fail_transient
