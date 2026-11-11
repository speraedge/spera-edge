name: SPERA EDGE Weekly Snapshot

on:
  schedule:
    # Runs every Friday at 18:00 UTC (11:30 PM IST)
    # Runs every Saturday at 18:00 UTC (11:30 PM IST) as a fallback
    - cron: '30 18 * * 5,6'
  workflow_dispatch: 

permissions:
  contents: write

jobs:
  snapshot:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run snapshot publisher
        env:
          UPSTOX_ACCESS_TOKEN: ${{ secrets.UPSTOX_ACCESS_TOKEN }}
          UPSTOX_ANALYTIC_TOKEN: ${{ secrets.UPSTOX_ANALYTIC_TOKEN }}
        run: |
          # ENSURE THIS FILENAME MATCHES YOUR ACTUAL SCRIPT IN THE TOOLS FOLDER
          python -m tools.publish_edge_snapshot

      - name: Commit and push snapshot
        run: |
          git config --global user.name "speraedge-bot"
          git config --global user.email "bot@speraedge.local"
          git add data/latest
          git commit -m "data: weekly research snapshot [skip ci]" || echo "No changes to commit"
          git push
