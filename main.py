
import asyncio
import requests
import json

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = "8809469360:AAES0Lddoz_slfBDbmi51tJBWaIhfsvp0vE"


BYBIT_URL = "https://api.bytick.com/v5/market/tickers"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Bybit Signal Bot работает!\n"
        "Напиши /price для проверки рынка."
    )


async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Получаю цену BTCUSDT...")

    try:
        response = await asyncio.to_thread(
            requests.get,
            BYBIT_URL,
            params={
                "category": "linear",
                "symbol": "BTCUSDT"
            },
            timeout=15
        )

        response.raise_for_status()

        try:
            data = response.json()
        except json.JSONDecodeError:
            raise ValueError(
                f"Bybit вернул не JSON: {response.text[:200]}"
            )

        if data.get("retCode") != 0:
            raise ValueError(
                f"Ошибка Bybit: {data.get('retMsg', 'Неизвестная ошибка')}"
            )

        ticker_list = data.get("result", {}).get("list", [])

        if not ticker_list:
            raise ValueError("Bybit не вернул данные BTCUSDT")

        current_price = ticker_list[0].get("lastPrice")

        if not current_price:
            raise ValueError("Цена отсутствует в ответе Bybit")

        await update.message.reply_text(
            f"₿ BTCUSDT\n"
            f"Текущая цена: {current_price} USDT\n"
            f"✅ Данные получены с Bybit"
        )

    except Exception as e:
        await update.message.reply_text(
            f"❌ Ошибка получения цены:\n{str(e)[:500]}"
        )


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
