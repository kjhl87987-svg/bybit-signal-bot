
import asyncio
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = "8809469360:AAES0Lddoz_slfBDbmi51tJBWaIhfsvp0vE"

HEADERS = {"User-Agent": "Mozilla/5.0"}

def get_json(url, params=None):
    r = requests.get(
        url, params=params, headers=HEADERS, timeout=12
    )
    r.raise_for_status()
    return r.json()

def bybit():
    errors = []
    for host in ["https://api.bybit.com", "https://api.bytick.com"]:
        try:
            d = get_json(
                host + "/v5/market/tickers",
                {"category": "linear", "symbol": "BTCUSDT"}
            )
            if d.get("retCode") != 0:
                raise ValueError(d.get("retMsg"))
            return float(d["result"]["list"][0]["lastPrice"])
        except Exception as e:
            errors.append(str(e))
    raise ValueError("Bybit: " + errors[-1])

def binance():
    d = get_json(
        "https://fapi.binance.com/fapi/v1/ticker/price",
        {"symbol": "BTCUSDT"}
    )
    return float(d["price"])

def okx():
    d = get_json(
        "https://www.okx.com/api/v5/market/ticker",
        {"instId": "BTC-USDT-SWAP"}
    )
    if d.get("code") != "0" or not d.get("data"):
        raise ValueError(d.get("msg", "OKX error"))
    return float(d["data"][0]["last"])

def gate():
    d = get_json(
        "https://api.gateio.ws/api/v4/futures/usdt/tickers",
        {"contract": "BTC_USDT"}
    )
    return float(d[0]["last"])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Bybit Signal Bot работает!\n"
        "Команды:\n"
        "/price — цены BTC на биржах"
    )

async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Проверяю 4 биржи...")

    exchanges = {
        "Bybit": bybit,
        "Binance Futures": binance,
        "OKX Swap": okx,
        "Gate.io Futures": gate
    }

    results = await asyncio.gather(*[
        asyncio.to_thread(func)
        for func in exchanges.values()
    ], return_exceptions=True)

    prices = []
    messages = ["₿ BTCUSDT — котировки фьючерсов\n"]

    for name, result in zip(exchanges.keys(), results):
        if isinstance(result, Exception):
            messages.append(f"❌ {name}: недоступна")
        else:
            prices.append(result)
            messages.append(f"✅ {name}: {result:,.2f} USDT")

    if prices:
        average = sum(prices) / len(prices)
        messages.append(
            f"\n📊 Средняя цена: {average:,.2f} USDT"
        )
        messages.append(
            f"Доступно бирж: {len(prices)}/4"
        )
    else:
        messages.append("\n❌ Все источники недоступны.")

    await update.message.reply_text("\n".join(messages))

async def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("price", price))

    print("Bybit Signal Bot started!")

    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
