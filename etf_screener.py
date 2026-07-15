#!/usr/bin/env python3

"""
ETF technical screener.

ETFs screened:
- VTI
- VOO
- VEA
- VWO
- IWM

Criteria:
1. Latest closing price is at least 5% below the trailing 52-week high.
2. Daily RSI(14) is below 35.
3. Latest closing price is at or below the 200-day simple moving average.

Discord behavior:
- Scheduled runs send a message only when at least one criterion is met.
- Manual test runs can force a Discord message using TEST_DISCORD=true.
"""

from __future__ import annotations

import math
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import yfinance as yf


# ------------------------------------------------------------
# SETTINGS
# ------------------------------------------------------------

TICKERS = ("VTI", "VOO", "VEA", "VWO", "IWM")

DRAWDOWN_TRIGGER_PCT = 5.0
RSI_TRIGGER = 35.0

RSI_PERIOD = 14
SMA_PERIOD = 200
TRADING_DAYS_52_WEEK = 252

DOWNLOAD_ATTEMPTS = 3
DOWNLOAD_RETRY_DELAY_SECONDS = 8
DISCORD_TIMEOUT_SECONDS = 20

EASTERN_TIME = ZoneInfo("America/New_York")


# ------------------------------------------------------------
# RESULT OBJECT
# ------------------------------------------------------------

@dataclass(frozen=True)
class ScreeningResult:
    ticker: str
    as_of: str

    close: float
    high_52w: float
    below_high_pct: float

    rsi_14: float

    sma_200: float
    vs_sma_pct: float

    drawdown_met: bool
    rsi_met: bool
    sma_met: bool

    @property
    def criteria_count(self) -> int:
        """Return the number of criteria met, from 0 to 3."""
        return sum(
            (
                self.drawdown_met,
                self.rsi_met,
                self.sma_met,
            )
        )

    @property
    def price_vs_sma_text(self) -> str:
        """Create readable text describing price versus SMA(200)."""
        if math.isclose(self.vs_sma_pct, 0.0, abs_tol=0.05):
            return "About at SMA(200)"

        direction = "above" if self.vs_sma_pct > 0 else "below"

        return f"About {abs(self.vs_sma_pct):.1f}% {direction}"


# ------------------------------------------------------------
# INDICATOR CALCULATIONS
# ------------------------------------------------------------

def calculate_rsi_wilder(
    closing_prices: pd.Series,
    period: int = 14,
) -> pd.Series:
    """
    Calculate RSI using Wilder's smoothing method.

    This is the standard daily RSI method used by many charting platforms.
    """
    price_changes = closing_prices.diff()

    gains = price_changes.clip(lower=0)
    losses = -price_changes.clip(upper=0)

    average_gain = gains.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period,
    ).mean()

    average_loss = losses.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period,
    ).mean()

    relative_strength = average_gain / average_loss

    rsi = 100 - (100 / (1 + relative_strength))

    # Handle unusual cases involving uninterrupted gains or losses.
    rsi = rsi.where(average_loss != 0, 100.0)
    rsi = rsi.where(average_gain != 0, 0.0)

    return rsi


# ------------------------------------------------------------
# MARKET DATA
# ------------------------------------------------------------

def download_history(ticker: str) -> pd.DataFrame:
    """
    Download two years of daily price history from Yahoo Finance.

    Two years provides enough data for:
    - SMA(200)
    - RSI(14)
    - trailing 52-week high
    """
    last_error: Exception | None = None

    for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
        try:
            data = yf.download(
                ticker,
                period="2y",
                interval="1d",
                auto_adjust=False,
                progress=False,
                actions=False,
                threads=False,
                timeout=30,
            )

            if data.empty:
                raise RuntimeError("Yahoo Finance returned no data.")

            # yfinance may return MultiIndex columns.
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)

            required_columns = {"High", "Close"}
            missing_columns = required_columns.difference(data.columns)

            if missing_columns:
                raise RuntimeError(
                    f"Missing required columns: {sorted(missing_columns)}"
                )

            data = data[["High", "Close"]].copy()

            data["High"] = pd.to_numeric(
                data["High"],
                errors="coerce",
            )

            data["Close"] = pd.to_numeric(
                data["Close"],
                errors="coerce",
            )

            data = data.dropna()

            if len(data) < SMA_PERIOD:
                raise RuntimeError(
                    f"Only {len(data)} valid trading days were returned. "
                    f"At least {SMA_PERIOD} are required."
                )

            return data

        except Exception as error:
            last_error = error

            if attempt < DOWNLOAD_ATTEMPTS:
                delay = DOWNLOAD_RETRY_DELAY_SECONDS * attempt

                print(
                    f"{ticker} download attempt {attempt} failed. "
                    f"Retrying in {delay} seconds..."
                )

                time.sleep(delay)

    raise RuntimeError(
        f"{ticker} download failed after "
        f"{DOWNLOAD_ATTEMPTS} attempts: {last_error}"
    )


# ------------------------------------------------------------
# ETF SCREENING
# ------------------------------------------------------------

def screen_ticker(ticker: str) -> ScreeningResult:
    """Calculate all three screening criteria for one ETF."""
    data = download_history(ticker)

    closing_prices = data["Close"]
    daily_highs = data["High"]

    latest_close = float(closing_prices.iloc[-1])

    sma_series = closing_prices.rolling(
        window=SMA_PERIOD,
        min_periods=SMA_PERIOD,
    ).mean()

    latest_sma_200 = float(sma_series.iloc[-1])

    rsi_series = calculate_rsi_wilder(
        closing_prices,
        RSI_PERIOD,
    )

    latest_rsi_14 = float(rsi_series.iloc[-1])

    trailing_52_week_high = float(
        daily_highs.tail(TRADING_DAYS_52_WEEK).max()
    )

    below_high_pct = (
        (trailing_52_week_high - latest_close)
        / trailing_52_week_high
        * 100
    )

    vs_sma_pct = (
        (latest_close - latest_sma_200)
        / latest_sma_200
        * 100
    )

    values_to_check = (
        latest_close,
        latest_sma_200,
        latest_rsi_14,
        trailing_52_week_high,
        below_high_pct,
        vs_sma_pct,
    )

    if not all(math.isfinite(value) for value in values_to_check):
        raise RuntimeError(
            f"{ticker} produced an invalid indicator value."
        )

    return ScreeningResult(
        ticker=ticker,
        as_of=pd.Timestamp(data.index[-1]).date().isoformat(),
        close=latest_close,
        high_52w=trailing_52_week_high,
        below_high_pct=below_high_pct,
        rsi_14=latest_rsi_14,
        sma_200=latest_sma_200,
        vs_sma_pct=vs_sma_pct,
        drawdown_met=(
            below_high_pct >= DRAWDOWN_TRIGGER_PCT
        ),
        rsi_met=(
            latest_rsi_14 < RSI_TRIGGER
        ),
        sma_met=(
            latest_close <= latest_sma_200
        ),
    )


# ------------------------------------------------------------
# TABLE FORMATTING
# ------------------------------------------------------------

def create_results_dataframe(
    results: list[ScreeningResult],
) -> pd.DataFrame:
    """Create the table printed in the GitHub Actions log."""
    rows = []

    for result in results:
        rows.append(
            {
                "ETF": result.ticker,
                "Approx. below 52-week high": (
                    f"{result.below_high_pct:.1f}%"
                ),
                "RSI(14)": f"{result.rsi_14:.1f}",
                "Price vs. SMA(200)": (
                    result.price_vs_sma_text
                ),
                "Criteria met": (
                    f"{result.criteria_count}/3"
                ),
            }
        )

    return pd.DataFrame(rows)


def create_markdown_table(
    results: list[ScreeningResult],
) -> str:
    """Create a Discord-compatible Markdown table."""
    lines = [
        (
            "| ETF | Approx. below 52-week high | "
            "RSI(14) | Price vs. SMA(200) | Criteria met |"
        ),
        "|---|---:|---:|---:|---:|",
    ]

    for result in results:
        lines.append(
            f"| {result.ticker} "
            f"| {result.below_high_pct:.1f}% "
            f"| {result.rsi_14:.1f} "
            f"| {result.price_vs_sma_text} "
            f"| {result.criteria_count}/3 |"
        )

    return "\n".join(lines)


def create_trigger_description(
    result: ScreeningResult,
) -> str:
    """Describe which criteria were triggered for one ETF."""
    triggers = []

    if result.drawdown_met:
        triggers.append(
            f"{result.below_high_pct:.1f}% below "
            f"its 52-week high"
        )

    if result.rsi_met:
        triggers.append(
            f"RSI(14) is {result.rsi_14:.1f}, "
            f"below {RSI_TRIGGER:.0f}"
        )

    if result.sma_met:
        triggers.append(
            f"price ${result.close:.2f} is at or below "
            f"SMA(200) ${result.sma_200:.2f}"
        )

    return "; ".join(triggers)


# ------------------------------------------------------------
# DISCORD
# ------------------------------------------------------------

def send_discord_message(
    results: list[ScreeningResult],
    test_mode: bool,
) -> None:
    """Send the screening table to the configured Discord webhook."""
    webhook_url = os.getenv(
        "DISCORD_WEBHOOK",
        "",
    ).strip()

    if not webhook_url:
        raise RuntimeError(
            "DISCORD_WEBHOOK is missing from GitHub secrets."
        )

    triggered_results = [
        result
        for result in results
        if result.criteria_count > 0
    ]

    latest_data_date = max(
        result.as_of
        for result in results
    )

    if test_mode:
        heading = "🧪 **Discord webhook test — ETF screener**"
    else:
        heading = "📊 **ETF buying-opportunity alert**"

    if triggered_results:
        trigger_lines = "\n".join(
            (
                f"• **{result.ticker}:** "
                f"{create_trigger_description(result)}"
            )
            for result in triggered_results
        )
    else:
        trigger_lines = (
            "No ETF currently meets any criteria. "
            "This message was sent because test mode was enabled."
        )

    message = (
        f"{heading}\n\n"
        f"Data through: **{latest_data_date}**\n\n"
        f"**Today's screening**\n"
        f"{create_markdown_table(results)}\n\n"
        f"**Triggered criteria**\n"
        f"{trigger_lines}\n\n"
        "_Criteria: at least 5% below the 52-week high; "
        "RSI(14) below 35; or closing price at or below SMA(200). "
        "Technical signals do not guarantee future returns._"
    )

    # Discord limits a standard webhook message to 2,000 characters.
    if len(message) > 1990:
        message = message[:1987] + "..."

    response = requests.post(
        webhook_url,
        json={
            "content": message,
            "allowed_mentions": {
                "parse": [],
            },
        },
        timeout=DISCORD_TIMEOUT_SECONDS,
    )

    response.raise_for_status()


# ------------------------------------------------------------
# MAIN PROGRAM
# ------------------------------------------------------------

def main() -> int:
    now_eastern = datetime.now(EASTERN_TIME)

    print(
        f"Current Eastern time: "
        f"{now_eastern:%Y-%m-%d %I:%M:%S %p %Z}"
    )

    test_discord = (
        os.getenv("TEST_DISCORD", "false")
        .strip()
        .lower()
        == "true"
    )

    if test_discord:
        print("Discord test mode is enabled.")

    results: list[ScreeningResult] = []
    errors: list[str] = []

    for ticker in TICKERS:
        print(f"Screening {ticker}...")

        try:
            result = screen_ticker(ticker)
            results.append(result)

        except Exception as error:
            errors.append(
                f"{ticker}: {error}"
            )

    if errors:
        print(
            "\nScreening failed. "
            "No partial Discord message was sent.",
            file=sys.stderr,
        )

        for error in errors:
            print(
                f"- {error}",
                file=sys.stderr,
            )

        return 1

    results_table = create_results_dataframe(results)

    print("\nToday's screening")
    print(
        results_table.to_string(
            index=False,
        )
    )

    criteria_triggered = any(
        result.criteria_count > 0
        for result in results
    )

    if criteria_triggered or test_discord:
        send_discord_message(
            results=results,
            test_mode=test_discord,
        )

        if test_discord:
            print(
                "\nDiscord test notification sent successfully."
            )
        else:
            print(
                "\nDiscord buying-opportunity notification "
                "sent successfully."
            )

    else:
        print(
            "\nNo criteria were met. "
            "No Discord notification was sent."
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
