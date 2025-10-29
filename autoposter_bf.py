name: Bluesky Auto Reposter (Beautyfan)

on:
  schedule:
    - cron: "0 */4 * * *"  # elke 4 uur uitvoeren
  workflow_dispatch:        # handmatig starten mogelijk

jobs:
  run:
    runs-on: ubuntu-latest

    steps:
      - name: 📦 Checkout repository
        uses: actions/checkout@v4

      - name: 🐍 Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: ⚙️ Install dependencies
        run: |
          pip install atproto

      - name: 🚀 Run autoposter (Beautyfan)
        env:
          BSKY_USERNAME: ${{ secrets.BSKY_USERNAME_BF }}
          BSKY_PASSWORD: ${{ secrets.BSKY_PASSWORD_BF }}
        run: |
          echo "🚀 Start Beautyfan autoposter run..."
          python autoposter_bf.py > autoposter_output.log 2>&1
          echo "📄 --- Begin output ---"
          cat autoposter_output.log
          echo "📄 --- End output ---"
          echo "✅ Run voltooid."