# Daily ETF screener

Screens VTI, VOO, VEA, VWO, and IWM at 9:00 AM Eastern every weekday.

## Criteria

- At least 5% below the trailing 52-week high
- RSI(14) below 35
- Latest close at or below SMA(200)

The complete table is printed to the GitHub Actions log. Discord is notified only when at least one ETF meets at least one criterion.

## Setup

1. Upload these files to the default branch of your GitHub repository.
2. Go to Settings → Secrets and variables → Actions.
3. Confirm the repository secret is named exactly `DISCORD_WEBHOOK`.
4. Go to Actions → Daily ETF screen → Run workflow to test it manually.

At 9:00 AM, the latest completed daily bar will normally be the previous trading day's close.
