# Mining command notes

Authentication and rate-limit checks:

```bash
gh auth status
gh api rate_limit --jq '.resources.core | {remaining,reset}'
python3 scripts/miner.py owner/repo /tmp/pr-review-data.json --limit 50
```

Never print token values while diagnosing authentication. Use `--all-comments` only when imperative filtering produced too little evidence; it materially increases noise.
