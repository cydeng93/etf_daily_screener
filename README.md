# ETF Screener

This script checks:

* VTI
* VOO
* VEA
* VWO
* IWM

It runs every two hours through GitHub Actions.

A Discord alert is sent when an ETF meets at least one of these criteria:

1. At least 5% below its 52-week high
2. RSI(14) below 35
3. Price at or below the 200-day moving average

## Files

```text
etf_screener.py
.github/workflows/etf_screener.yml
data/etf_screening_history.csv
```

The history CSV is created after the first successful run.

## View Past Results

Open:

```text
data/etf_screening_history.csv
```

GitHub will show the CSV in a table-like view.

## Discord Setup

Add this GitHub Actions secret:

```text
DISCORD_WEBHOOK
```

Go to:

```text
Settings → Secrets and variables → Actions
```

## Run Manually

Go to:

```text
Actions → ETF Screener → Run workflow
```

You can enable test mode to send a Discord message even if no criteria are met.

## Disclaimer

For informational purposes only. This is not financial advice.
