#!/bin/bash
# Count core agent lines (excluding channels/, cli/, api/, providers/ adapters,
# and the high-level Python SDK facade)
cd "$(dirname "$0")" || exit 1

echo "adkbot core agent line count"
echo "================================"
echo ""

for dir in agent agent/tools bus config cron heartbeat session utils; do
  count=$(find "adkbot/$dir" -maxdepth 1 -name "*.py" -exec cat {} + | wc -l)
  printf "  %-16s %5s lines\n" "$dir/" "$count"
done

root=$(cat adkbot/__init__.py adkbot/__main__.py | wc -l)
printf "  %-16s %5s lines\n" "(root)" "$root"

echo ""
total=$(find adkbot -name "*.py" ! -path "*/channels/*" ! -path "*/cli/*" ! -path "*/api/*" ! -path "*/command/*" ! -path "*/providers/*" ! -path "*/skills/*" ! -path "adkbot/adkbot.py" | xargs cat | wc -l)
echo "  Core total:     $total lines"
echo ""
echo "  (excludes: channels/, cli/, api/, command/, providers/, skills/, adkbot.py)"
