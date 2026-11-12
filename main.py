import asyncio
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = "8809469360:AAES0Lddoz_slfBDbmi51tJBWaIhfsvp0vE"

BYBIT_URL = "https://api.bybit.com/v5/market/tickers"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Bybit Signal Bot работает!\n"
        "Напиши /price для проверки рынка."
    )

async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        response = requests.get(
            BYBIT_URL,
            params={"category": "linear", "symbol": "BTCUSDT"},
            timeout=10
        )
        data = response.json()

        ticker = data["result"]["list"][0]
        price = ticker["lastPrice"]

        await update.message.reply_text(
            f"₿ BTCUSDT\nТекущая цена: {price} USDT"
        )

    except Exception as e:
        await update.message.reply_text(f"Ошибка получения цены: {e}")

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
