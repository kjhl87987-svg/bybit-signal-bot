
import asyncio
import requests
import time
import math

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = "8809469360:AAES0Lddoz_slfBDbmi51tJBWaIhfsvp0vE"

HEADERS = {"User-Agent": "Mozilla/5.0"}

TIMEFRAMES = {
    "5m": ("5m", 1),
    "15m": ("15m", 2),
    "1h": ("1H", 3),
    "4h": ("4H", 4)
}


def get_json(url, params=None):
    r = requests.get(
        url, params=params, headers=HEADERS, timeout=15
    )
    r.raise_for_status()
    return r.json()


def okx_candles(tf):
    data = get_json(
        "https://www.okx.com/api/v5/market/candles",
        {
            "instId": "BTC-USDT-SWAP",
            "bar": tf,
            "limit": "200"
        }
    )

    if data.get("code") != "0":
        raise ValueError(data.get("msg", "OKX error"))

    candles = []

    for x in data["data"]:
        if len(x) < 9 or x[8] != "1":
            continue

        candles.append({
            "t": int(x[0]),
            "o": float(x[1]),
            "h": float(x[2]),
            "l": float(x[3]),
            "c": float(x[4]),
            "v": float(x[5])
        })

    candles.sort(key=lambda x: x["t"])

    if len(candles) < 50:
        raise ValueError("Недостаточно свечей OKX")

    return candles, "OKX"


def gate_candles(tf):
    seconds = {
        "5m": 300,
        "15m": 900,
        "1H": 3600,
        "4H": 14400
    }[tf]

    data = get_json(
        "https://api.gateio.ws/api/v4/futures/usdt/candlesticks",
        {
            "contract": "BTC_USDT",
            "interval": tf.lower(),
            "limit": 200
        }
    )

    candles = []

    for x in data:
        if int(x["t"]) + seconds > time.time():
            continue

        candles.append({
            "t": int(x["t"]),
            "o": float(x["o"]),
            "h": float(x["h"]),
            "l": float(x["l"]),
            "c": float(x["c"]),
            "v": float(x["v"])
        })

    candles.sort(key=lambda x: x["t"])

    if len(candles) < 50:
        raise ValueError("Недостаточно свечей Gate")

    return candles, "Gate.io"


def get_candles(tf):
    try:
        return okx_candles(tf)
    except Exception:
        return gate_candles(tf)


def ema_series(values, period):
    if len(values) < period:
        return []

    result = [values[0]]
    k = 2 / (period + 1)

    for value in values[1:]:
        result.append(
            value * k + result[-1] * (1 - k)
        )

    return result


def rsi(values, period=14):
    changes = [
        values[i] - values[i - 1]
        for i in range(1, len(values))
    ]

    gains = [max(x, 0) for x in changes[-period:]]
    losses = [max(-x, 0) for x in changes[-period:]]

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def macd(values):
    fast = ema_series(values, 12)
    slow = ema_series(values, 26)

    line = [
        fast[i] - slow[i]
        for i in range(len(values))
    ]

    signal = ema_series(line, 9)

    return line[-1], signal[-1]


def atr(candles, period=14):
    ranges = []

    for i in range(1, len(candles)):
        c = candles[i]
        prev = candles[i - 1]["c"]

        ranges.append(max(
            c["h"] - c["l"],
            abs(c["h"] - prev),
            abs(c["l"] - prev)
        ))

    return sum(ranges[-period:]) / period


def bollinger(values, period=20):
    sample = values[-period:]
    middle = sum(sample) / period

    variance = sum(
        (x - middle) ** 2 for x in sample
    ) / period

    deviation = math.sqrt(variance)

    return (
        middle,
        middle + 2 * deviation,
        middle - 2 * deviation
    )


def market_structure(candles):
    highs = []
    lows = []

    for i in range(2, len(candles) - 2):
        h = candles[i]["h"]
        l = candles[i]["l"]

        if all(
            h > candles[j]["h"]
            for j in [i-2, i-1, i+1, i+2]
        ):
            highs.append(h)

        if all(
            l < candles[j]["l"]
            for j in [i-2, i-1, i+1, i+2]
        ):
            lows.append(l)

    if len(highs) < 2 or len(lows) < 2:
        return "Не определена", 0, None, None

    hh = highs[-1] > highs[-2]
    hl = lows[-1] > lows[-2]

    if hh and hl:
        return "HH + HL (бычья)", 2, lows[-1], highs[-1]

    if not hh and not hl:
        return "LH + LL (медвежья)", -2, lows[-1], highs[-1]

    return "Боковая / смешанная", 0, lows[-1], highs[-1]


def find_fvg(candles):
    result = None

    for i in range(max(2, len(candles) - 60), len(candles)):
        first = candles[i - 2]
        third = candles[i]

        if third["l"] > first["h"]:
            result = (
                "Bullish FVG",
                first["h"],
                third["l"]
            )

        elif third["h"] < first["l"]:
            result = (
                "Bearish FVG",
                third["h"],
                first["l"]
            )

    return result


def analyze(candles):
    closes = [x["c"] for x in candles]
    volumes = [x["v"] for x in candles]

    price = closes[-1]

    e20 = ema_series(closes, 20)[-1]
    e50 = ema_series(closes, 50)[-1]
    e200 = ema_series(closes, 200)[-1] if len(closes) >= 200 else None

    r = rsi(closes)
    m, ms = macd(closes)
    middle, upper, lower = bollinger(closes)
    volatility = atr(candles)

    volume_avg = sum(volumes[-21:-1]) / 20
    volume_ratio = (
        volumes[-1] / volume_avg if volume_avg else 0
    )

    structure, structure_score, support, resistance = (
        market_structure(candles)
    )

    score = 0

    if price > e20 > e50:
        score += 2
    elif price < e20 < e50:
        score -= 2

    if e200 is not None:
        score += 1 if price > e200 else -1

    score += 1 if m > ms else -1

    if 52 < r < 70:
        score += 1
    elif 30 < r < 48:
        score -= 1

    score += structure_score

    if volume_ratio > 1.2:
        if candles[-1]["c"] > candles[-1]["o"]:
            score += 1
        elif candles[-1]["c"] < candles[-1]["o"]:
            score -= 1

    if price > middle:
        score += 1
    elif price < middle:
        score -= 1

    fvg = find_fvg(candles)

    return {
        "price": price,
        "ema20": e20,
        "ema50": e50,
        "ema200": e200,
        "rsi": r,
        "macd": m,
        "macd_signal": ms,
        "bb_upper": upper,
        "bb_lower": lower,
        "volume_ratio": volume_ratio,
        "structure": structure,
        "support": support,
        "resistance": resistance,
        "fvg": fvg,
        "atr": volatility,
        "score": score
    }


def fmt(value):
    return f"{value:,.2f}" if value is not None else "нет"


def build_report(results):
    weights = {
        "5m": 1,
        "15m": 2,
        "1h": 3,
        "4h": 4
    }

    total = 0
    max_score = 0
    lines = ["📊 BTCUSDT — ТЕХНИЧЕСКИЙ АНАЛИЗ\n"]

    for tf, data in results.items():
        a = data["analysis"]
        score = a["score"]
        total += score * weights[tf]
        max_score += 9 * weights[tf]

        direction = (
            "LONG" if score > 0
            else "SHORT" if score < 0
            else "NEUTRAL"
        )

        lines.append(
            f"\n⏱ {tf} | {direction} ({score:+d})\n"
            f"RSI: {a['rsi']:.1f}\n"
            f"EMA20: {fmt(a['ema20'])}\n"
            f"EMA50: {fmt(a['ema50'])}\n"
            f"EMA200: {fmt(a['ema200'])}\n"
            f"MACD: {'↑' if a['macd'] > a['macd_signal'] else '↓'}\n"
            f"Структура: {a['structure']}\n"
            f"Объём: {a['volume_ratio']:.2f}x\n"
            f"Источник: {data['source']}"
        )

        if a["fvg"]:
            name, low, high = a["fvg"]
            lines.append(
                f"\nFVG: {name} {fmt(low)}–{fmt(high)}"
            )
        else:
            lines.append("\nFVG: не найден")

    higher = (
        results.get("1h", {}).get("analysis", {}).get("score", 0)
        + results.get("4h", {}).get("analysis", {}).get("score", 0)
    )

    strength = (
        abs(total) / max_score * 100
        if max_score else 0
    )

    if total >= 15 and higher > 0:
        signal = "LONG 🟢"
    elif total <= -15 and higher < 0:
        signal = "SHORT 🔴"
    else:
        signal = "WAIT 🟡"

    lines.append(
        f"\n\n🎯 ИТОГОВЫЙ СИГНАЛ: {signal}"
    )
    lines.append(
        f"Согласованность факторов: {strength:.0f}%"
    )
    lines.append(
        "Это оценка совпадения индикаторов, не вероятность прибыли."
    )

    if signal.startswith(("LONG", "SHORT")):
        entry = results.get("15m", results.get("1h"))["analysis"]["price"]
        volatility = results.get("1h", results.get("15m"))["analysis"]["atr"]

        if signal.startswith("LONG"):
            sl = entry - 1.5 * volatility
            tp1 = entry + 1.5 * volatility
            tp2 = entry + 2.5 * volatility
            tp3 = entry + 3.5 * volatility
        else:
            sl = entry + 1.5 * volatility
            tp1 = entry - 1.5 * volatility
            tp2 = entry - 2.5 * volatility
            tp3 = entry - 3.5 * volatility

        lines.append(
            f"\nВход (ориентир): {fmt(entry)}"
            f"\nStop Loss: {fmt(sl)}"
            f"\nTP1: {fmt(tp1)}"
            f"\nTP2: {fmt(tp2)}"
            f"\nTP3: {fmt(tp3)}"
        )

    one_hour = results.get("1h")
    if one_hour:
        a = one_hour["analysis"]
        lines.append(
            f"\n\n📍 Поддержка 1h: {fmt(a['support'])}"
            f"\n📍 Сопротивление 1h: {fmt(a['resistance'])}"
            f"\nBollinger верх: {fmt(a['bb_upper'])}"
            f"\nBollinger низ: {fmt(a['bb_lower'])}"
        )

    lines.append(
        "\n\n⚠️ Аналитический сигнал, не гарантия сделки. "
        "Проверяй уровень и риск перед входом."
    )

    return "\n".join(lines)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Bybit Signal Bot работает!\n\n"
        "/price — цены бирж\n"
        "/signal — полный анализ BTCUSDT"
    )


async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Проверяю биржи...")

    providers = {
        "Bybit": lambda: get_json(
            "https://api.bybit.com/v5/market/tickers",
            {"category": "linear", "symbol": "BTCUSDT"}
        )["result"]["list"][0]["lastPrice"],

        "Binance Futures": lambda: get_json(
            "https://fapi.binance.com/fapi/v1/ticker/price",
            {"symbol": "BTCUSDT"}
        )["price"],

        "OKX Swap": lambda: get_json(
            "https://www.okx.com/api/v5/market/ticker",
            {"instId": "BTC-USDT-SWAP"}
        )["data"][0]["last"],

        "Gate.io Futures": lambda: get_json(
            "https://api.gateio.ws/api/v4/futures/usdt/tickers",
            {"contract": "BTC_USDT"}
        )[0]["last"]
    }

    results = await asyncio.gather(*[
        asyncio.to_thread(func)
        for func in providers.values()
    ], return_exceptions=True)

    lines = ["₿ BTCUSDT — ЦЕНЫ\n"]
    prices = []

    for name, result in zip(providers, results):
        if isinstance(result, Exception):
            lines.append(f"❌ {name}: недоступна")
        else:
            value = float(result)
            prices.append(value)
            lines.append(f"✅ {name}: {value:,.2f} USDT")

    if prices:
        lines.append(
            f"\nСредняя цена: {sum(prices) / len(prices):,.2f} USDT"
        )

    await update.message.reply_text("\n".join(lines))


async def signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔎 Анализирую 4 таймфрейма...\n"
        "Получаю свечи и рассчитываю индикаторы."
    )

    try:
        tasks = {
            tf: asyncio.to_thread(get_candles, interval)
            for tf, (interval, weight) in TIMEFRAMES.items()
        }

        names = list(tasks.keys())
        values = await asyncio.gather(
            *tasks.values(), return_exceptions=True
        )

        results = {}
        errors = []

        for tf, result in zip(names, values):
            if isinstance(result, Exception):
                errors.append(f"{tf}: {str(result)[:100]}")
                continue

            candles, source = result

            results[tf] = {
                "source": source,
                "analysis": analyze(candles)
            }

        if not results:
            raise ValueError("Нет данных ни с одной биржи")

        report = build_report(results)

        if errors:
            report += "\n\n⚠️ Не получены данные:\n" + "\n".join(errors)

        await update.message.reply_text(report)

    except Exception as e:
        await update.message.reply_text(
            f"❌ Ошибка анализа: {str(e)[:500]}"
        )


async def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("price", price))
    app.add_handler(CommandHandler("signal", signal))

    print("Bybit Signal Bot started!")

    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
