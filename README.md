# ETF Screener

This project checks these ETFs every two hours on weekdays:

* VTI
* VOO
* VEA
* VWO
* IWM

It looks for three possible buying signals:

1. Price is at least 5% below the 52-week high
2. RSI(14) is below 35
3. Price is at or below the 200-day simple moving average

Each ETF receives a score from `0/3` to `3/3`.

## Discord alerts

The script sends a Discord message when at least one ETF meets at least two criterion.

If no ETF meets a criterion, no Discord message is sent.

The message includes:

* Percentage below the 52-week high
* RSI(14)
* Price versus SMA(200)
* Number of criteria met

## Test Discord

You can manually test the webhook even when no criteria are met.

1. Open the repository on GitHub
2. Click **Actions**
3. Select **ETF screen every two hours**
4. Click **Run workflow**
5. Turn on **Send a Discord test message even if no criteria are met**
6. Click **Run workflow**

## Schedule

The workflow runs every two hours from Monday through Friday.

```yaml
- cron: "0 */2 * * 1-5"
```

GitHub uses UTC for scheduled workflows.

## Files

```text
.github/workflows/etf-screen.yml
etf_screener.py
requirements.txt
README.md
```

## Required GitHub secret

Your Discord webhook must be saved as:

```text
DISCORD_WEBHOOK
```

Add it under:

**Settings → Secrets and variables → Actions**

## Requirements

```text
pandas==2.3.1
requests==2.32.4
yfinance==0.2.65
```

## Notes

The script uses Yahoo Finance data through `yfinance`.

The full screening table appears in the GitHub Actions log for every run.

An ETF may trigger repeated Discord alerts every two hours if it continues meeting the criteria.

These indicators do not guarantee that an ETF is a good investment or that the price has reached its bottom.
