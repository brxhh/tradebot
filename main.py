import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ParseMode
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

import config
import logic


class TradeStates(StatesGroup):
    waiting_for_ticker = State()
    waiting_for_timeframe = State()
    waiting_for_context = State()


bot = Bot(token=config.TELEGRAM_TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)


def get_timeframe_keyboard():
    kb = [
        [KeyboardButton(text="5m"), KeyboardButton(text="15m"), KeyboardButton(text="30m")],
        [KeyboardButton(text="1h"), KeyboardButton(text="4h"), KeyboardButton(text="1d")],
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True, one_time_keyboard=True)


@dp.message(Command("cancel", "stop"))
@dp.message(F.text.lower().in_({"отмена", "стоп", "выход"}))
async def cmd_cancel(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "🛑 <b>Бот остановлен.</b> Нажми /start заново.",
        parse_mode=ParseMode.HTML,
        reply_markup=ReplyKeyboardRemove()
    )


@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "👋 <b>Привет!</b>\nВведи Тикер (например: <code>BTC-USD</code>, <code>ETH-USD</code>):",
        parse_mode=ParseMode.HTML,
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(TradeStates.waiting_for_ticker)


@dp.message(StateFilter(TradeStates.waiting_for_ticker))
async def process_ticker(message: types.Message, state: FSMContext):
    ticker = message.text.upper().strip()
    await state.update_data(ticker=ticker)

    await message.answer(
        f"✅ Тикер: <b>{ticker}</b>.\nТеперь выбери таймфрейм:",
        parse_mode=ParseMode.HTML,
        reply_markup=get_timeframe_keyboard()
    )
    await state.set_state(TradeStates.waiting_for_timeframe)


@dp.message(StateFilter(TradeStates.waiting_for_timeframe))
async def process_timeframe(message: types.Message, state: FSMContext):
    timeframe = message.text.lower().strip()

    if timeframe not in ['1m', '5m', '15m', '30m', '1h', '4h', '1d', '1wk', '1mo']:
        await message.answer("⚠️ Некорректный таймфрейм. Выбери из кнопок.")
        return

    data_store = await state.get_data()
    ticker = data_store['ticker']

    msg = await message.answer(f"🔎 Скачиваю данные <b>{ticker}</b> на <b>{timeframe}</b>...", parse_mode=ParseMode.HTML,
                               reply_markup=ReplyKeyboardRemove())

    market_data = logic.get_market_data(ticker, timeframe)

    if not market_data:
        await msg.delete()
        await message.answer(
            f"❌ Не нашел данные по <code>{ticker}</code>.\n"
            "Попробуй ввести тикер заново (/start)."
        )
        return

    await state.update_data(market_data=market_data)
    await state.update_data(timeframe=timeframe)

    await msg.delete()

    await message.answer(
        f"✅ <b>{ticker} ({timeframe})</b>\n"
        f"Цена: <code>${market_data['price']}</code>\n\n"
        "Напиши: <b>Как ты себя чувствуешь?</b>",
        parse_mode=ParseMode.HTML
    )
    await state.set_state(TradeStates.waiting_for_context)


@dp.message(StateFilter(TradeStates.waiting_for_context))
async def process_analysis(message: types.Message, state: FSMContext):
    user_text = message.text

    data = await state.get_data()
    ticker = data['ticker']
    market_data = data['market_data']
    timeframe = data['timeframe']

    status_msg = await message.answer("🧠 <b>Анализирую...</b>", parse_mode=ParseMode.HTML)

    dxy = logic.get_market_data("DX-Y.NYB", timeframe)
    if not dxy: dxy = {"price": "N/A", "trend": "N/A"}

    ai_verdict = await logic.get_ai_analysis(ticker, market_data, dxy, user_text, timeframe)

    header = (
        f"📊 <b>{ticker} ({timeframe})</b>\n"
        f"Цена: <code>{market_data['price']}</code> | RSI: {market_data['rsi']}\n"
        f"──────────────────\n"
    )

    await status_msg.delete()

    try:
        await message.answer(header + ai_verdict, parse_mode=ParseMode.HTML)
    except:
        await message.answer(header + ai_verdict)

    await message.answer("\n🔄 Новый анализ? Пиши тикер:", parse_mode=ParseMode.HTML)
    await state.set_state(TradeStates.waiting_for_ticker)


async def main():
    print("Бот запущен...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())