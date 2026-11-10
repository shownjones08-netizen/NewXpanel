#!/bin/bash
# SHOWN X PANEL v18.0-U1 — Auto Merge Script
# Run: bash MERGE_v18.sh

echo "Merging SHOWN X PANEL v18.0-U1..."

head -n -3 shownXpannel_v18_part1.py > shownXpannel_v18_final.py
tail -n +8 shownXpannel_v18_part2.py | head -n -1 >> shownXpannel_v18_final.py
tail -n +8 shownXpannel_v18_part3.py >> shownXpannel_v18_final.py

echo "✅ Merged → shownXpannel_v18_final.py"
echo "Lines: $(wc -l < shownXpannel_v18_final.py)"
echo ""
echo "Next: set your BOT_TOKEN in the file or export it:"
echo "  export BOT_TOKEN=your_token_here"
echo "  pip install python-telegram-bot==21.5 aiohttp==3.10.5"
echo "  python shownXpannel_v18_final.py"
