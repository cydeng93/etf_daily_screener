# ETF Screener with Discord Alerts

This GitHub project automatically screens five broad equity ETFs every two hours on weekdays:

* VTI — Vanguard Total Stock Market ETF
* VOO — Vanguard S&P 500 ETF
* VEA — Vanguard FTSE Developed Markets ETF
* VWO — Vanguard FTSE Emerging Markets ETF
* IWM — iShares Russell 2000 ETF

The screener calculates three technical indicators for each ETF and sends a Discord notification when at least one buying-opportunity criterion is met.

## Screening criteria

Each ETF receives one point for every condition it meets:

1. The latest closing price is at least 5% below its trailing 52-week high.
2. Daily RSI(14) is below 35.
3. The latest closing price is at or below its 200-day simple moving average.

Possible scores range from:

* `0/3` — no criteria met
* `1/3` — one criterion met
* `2/3` — two criteria met
* `3/3` — all three criteria met

These signals may help identify market pullbacks, but they do not guarantee that an ETF is undervalued or that its price will rise.

## Example screening output

```text
Today's screening

ETF  Approx. below 52-week high  RSI(14)  Price vs. SMA(200)  Criteria met
VTI  1.0%                        55.6     About 8.0% above     0/3
VOO  1.3%                        55.7     About 8.0% above     0/3
VEA  5.4%                        33.8     About 1.2% below     3/3
VWO  4.1%                        41.5     About 2.0% above     0/3
IWM  6.2%                        34.4     About 0.8% below     3/3
```

## Discord notification behavior

The script sends a Discord message when at least one ETF meets at least one criterion.

A normal scheduled run sends no Discord message when all ETFs score `0/3`.

The Discord message includes:

* The complete ETF screening table
* The latest market-data date
* Which ETFs triggered
* Which criteria were met
* Current price and SMA(200) values when applicable

## Manual Discord test mode

The GitHub Actions workflow includes a manual test option.

This allows you to send a Discord message even when no ETF currently meets any criteria.

To test Discord:

1. Open the repository on GitHub.
2. Click the **Actions** tab.
3. Select **ETF screen every two hours**.
4. Click **Run workflow**.
5. Turn on **Send a Discord test message even if no criteria are met**.
6. Click the green **Run workflow** button.

The test message should begin with:

```text
🧪 Discord webhook test — ETF screener
```

## Automatic schedule

The workflow runs every two hours from Monday through Friday.

The workflow uses:

```yaml
- cron: "0 */2 * * 1-5"
```

GitHub cron schedules use UTC. The script no longer requires a specific local execution time, so every scheduled run performs the complete ETF screen.

GitHub Actions may occasionally begin a scheduled run several minutes late.

## Project files

```text
etf_daily_screener/
├── .github/
│   └── workflows/
│       └── etf-screen.yml
├── etf_screener.py
├── requirements.txt
└── README.md
```

### `etf_screener.py`

The main Python program. It:

* Downloads ETF price history
* Calculates RSI(14)
* Calculates SMA(200)
* Calculates percentage below the trailing 52-week high
* Prints the screening table
* Sends qualifying alerts to Discord

### `.github/workflows/etf-screen.yml`

The GitHub Actions workflow. It:

* Runs automatically every two hours on weekdays
* Supports manual runs
* Supports manual Discord testing
* Installs Python and the required packages
* Runs `etf_screener.py`

### `requirements.txt`

Contains the required Python packages:

```text
pandas==2.3.1
requests==2.32.4
yfinance==0.2.65
```

## Market-data source

The script downloads daily price history from Yahoo Finance through the `yfinance` Python package.

It uses:

* Daily closing prices for RSI and SMA calculations
* Daily high prices for the trailing 52-week high
* Two years of historical data to provide enough observations for SMA(200)

The latest daily candle may represent:

* The current trading day after Yahoo Finance updates it, or
* The previous completed trading day

Values may differ slightly from Robinhood or another charting platform because of differences in timing, adjusted prices, calculation methods, and data providers.

## Indicator definitions

### Percentage below the 52-week high

The script compares the latest closing price with the highest daily price from the most recent 252 trading sessions.

The calculation is:

```text
52-week decline percentage =
(52-week high − latest close) ÷ 52-week high × 100
```

The criterion is met when the result is at least 5%.

### RSI(14)

RSI stands for Relative Strength Index.

The script calculates daily RSI over 14 trading sessions using Wilder’s smoothing method.

The criterion is met when:

```text
RSI(14) < 35
```

A low RSI indicates strong recent selling, but it does not prove that the market has reached its bottom.

### SMA(200)

SMA stands for simple moving average.

The 200-day SMA is the average closing price over the most recent 200 trading sessions.

The criterion is met when:

```text
latest close <= SMA(200)
```

The output also shows approximately how far the ETF is above or below the moving average.

## GitHub secret setup

The Discord webhook must be stored as a GitHub Actions secret.

Do not paste the webhook directly into the Python script or workflow file.

To add the secret:

1. Open the GitHub repository.
2. Click **Settings**.
3. Click **Secrets and variables**.
4. Click **Actions**.
5. Click **New repository secret**.
6. Enter this exact name:

```text
DISCORD_WEBHOOK
```

7. Paste the complete Discord webhook URL into the secret value.
8. Click **Add secret**.

The name is case-sensitive and must not contain spaces.

## Initial setup

1. Upload the following items to the root of the repository:

```text
.github
etf_screener.py
requirements.txt
README.md
```

2. Confirm that the workflow file is located at:

```text
.github/workflows/etf-screen.yml
```

3. Add the `DISCORD_WEBHOOK` repository secret.
4. Open the **Actions** tab.
5. Select **ETF screen every two hours**.
6. Run the workflow manually once with Discord test mode enabled.
7. Confirm that the Discord message arrives.
8. Run it again with test mode disabled to confirm the actual screening behavior.

## Viewing screening results

Every run prints the complete screening table in the GitHub Actions log, even when no Discord message is sent.

To view it:

1. Open the repository.
2. Click **Actions**.
3. Select the latest workflow run.
4. Open the `screen` job.
5. Expand **Run ETF screener**.

The log will show each ticker being screened followed by the completed table.

## Error handling

The script retries failed Yahoo Finance downloads up to three times.

If one or more ETFs cannot be downloaded or calculated reliably:

* The workflow fails with an error.
* The specific ticker error appears in the GitHub Actions log.
* No partial Discord alert is sent.

This prevents the script from sending an incomplete comparison that could be misleading.

## Repeated notifications

Because the workflow runs every two hours, an ETF that continues meeting a criterion may trigger another Discord message on later runs.

For example, if VEA remains below its SMA(200) throughout the day, the script may send repeated notifications every two hours.

This version does not save previous alert states or suppress duplicate alerts.

## Important limitations

This screener is an informational technical-analysis tool.

It does not consider:

* ETF valuation
* Expense ratios
* Taxes
* Portfolio allocation
* Interest rates
* Earnings expectations
* Currency risk
* Personal time horizon
* Personal risk tolerance
* Whether you already own overlapping investments

An ETF meeting all three criteria can continue falling. An ETF meeting none of the criteria can continue rising.

Technical indicators should not be treated as guaranteed buy signals or personalized financial advice.
