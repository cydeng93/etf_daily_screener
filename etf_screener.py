#!/usr/bin/env python3
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

TICKERS = ("VTI", "VOO", "VEA", "VWO", "IWM")
DRAWDOWN_TRIGGER_PCT = 5.0
RSI_TRIGGER = 35.0
SMA_PERIOD = 200
RSI_PERIOD = 14
TRADING_DAYS_52_WEEK = 252
EASTERN = ZoneInfo("America/New_York")


@dataclass(frozen=True)
class Result:
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
        return sum((self.drawdown_met, self.rsi_met, self.sma_met))

    @property
    def vs_sma_text(self) -> str:
        if math.isclose(self.vs_sma_pct, 0.0, abs_tol=0.05):
            return "About at SMA(200)"
        direction = "above" if self.vs_sma_pct > 0 else "below"
        return f"About {abs(self.vs_sma_pct):.1f}% {direction}"


def rsi_wilder(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)
    avg_gain = gains.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = losses.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    rsi = rsi.where(avg_loss != 0, 100.0)
    rsi = rsi.where(avg_gain != 0, 0.0)
    return rsi


def download_history(ticker: str) -> pd.DataFrame:
    last_error = None
    for attempt in range(1, 4):
        try:
            df = yf.download(
                ticker,
                period="2y",
                interval="1d",
                auto_adjust=False,
                progress=False,
                actions=False,
                threads=False,
                timeout=30,
            )
            if df.empty:
                raise RuntimeError("No rows returned")
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df = df[["High", "Close"]].apply(pd.to_numeric, errors="coerce").dropna()
            if len(df) < SMA_PERIOD:
                raise RuntimeError(f"Only {len(df)} valid rows")
            return df
        except Exception as exc:
            last_error = exc
            if attempt < 3:
                time.sleep(8 * attempt)
    raise RuntimeError(f"{ticker} download failed after retries: {last_error}")


def screen(ticker: str) -> Result:
    df = download_history(ticker)
    close = df["Close"]
    latest_close = float(close.iloc[-1])
    high_52w = float(df["High"].tail(TRADING_DAYS_52_WEEK).max())
    sma_200 = float(close.rolling(SMA_PERIOD).mean().iloc[-1])
    rsi_14 = float(rsi_wilder(close, RSI_PERIOD).iloc[-1])
    below_high_pct = (high_52w - latest_close) / high_52w * 100
    vs_sma_pct = (latest_close - sma_200) / sma_200 * 100

    return Result(
        ticker=ticker,
        as_of=pd.Timestamp(df.index[-1]).date().isoformat(),
        close=latest_close,
        high_52w=high_52w,
        below_high_pct=below_high_pct,
        rsi_14=rsi_14,
        sma_200=sma_200,
        vs_sma_pct=vs_sma_pct,
        drawdown_met=below_high_pct >= DRAWDOWN_TRIGGER_PCT,
        rsi_met=rsi_14 < RSI_TRIGGER,
        sma_met=latest_close <= sma_200,
    )


def markdown_table(results: list[Result]) -> str:
    lines = [
        "| ETF | Approx. below 52-week high | RSI(14) | Price vs. SMA(200) | Criteria met |",
        "|---|---:|---:|---:|---:|",
    ]
    for r in results:
        lines.append(
            f"| {r.ticker} | {r.below_high_pct:.1f}% | {r.rsi_14:.1f} | "
            f"{r.vs_sma_text} | {r.criteria_count}/3 |"
        )
    return "\n".join(lines)


def trigger_text(r: Result) -> str:
    items = []
    if r.drawdown_met:
        items.append(f"{r.below_high_pct:.1f}% below 52-week high")
    if r.rsi_met:
        items.append(f"RSI(14) {r.rsi_14:.1f}")
    if r.sma_met:
        items.append(f"price ${r.close:.2f} at/below SMA(200) ${r.sma_200:.2f}")
    return "; ".join(items)


def notify_discord(results: list[Result]) -> None:
    webhook = os.getenv("DISCORD_WEBHOOK", "").strip()
    if not webhook:
        raise RuntimeError("DISCORD_WEBHOOK is missing")

    triggered = [r for r in results if r.criteria_count > 0]
    as_of = max(r.as_of for r in results)
    details = "\n".join(f"• **{r.ticker}:** {trigger_text(r)}" for r in triggered)
    message = (
        f"**ETF screen — data through {as_of}**\n\n"
        f"{markdown_table(results)}\n\n"
        f"**Triggered:**\n{details}\n\n"
        "_Criteria: ≥5% below 52-week high; RSI(14) <35; or close ≤ SMA(200)._"
    )
    response = requests.post(webhook, json={"content": message[:1990]}, timeout=20)
    response.raise_for_status()


def main() -> int:
    print(f"Run time: {datetime.now(EASTERN):%Y-%m-%d %I:%M:%S %p %Z}")
    results, errors = [], []

    for ticker in TICKERS:
        try:
            results.append(screen(ticker))
        except Exception as exc:
            errors.append(str(exc))

    if errors:
        print("Screen failed; no partial Discord alert was sent.", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    rows = [{
        "ETF": r.ticker,
        "Approx. below 52-week high": f"{r.below_high_pct:.1f}%",
        "RSI(14)": f"{r.rsi_14:.1f}",
        "Price vs. SMA(200)": r.vs_sma_text,
        "Criteria met": f"{r.criteria_count}/3",
    } for r in results]

    print("\nToday's screening")
    print(pd.DataFrame(rows).to_string(index=False))

    if any(r.criteria_count > 0 for r in results):
        notify_discord(results)
        print("\nDiscord notification sent.")
    else:
        print("\nNo criteria met; no Discord notification sent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
