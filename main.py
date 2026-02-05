import asyncio
import logging
import re
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ParseMode
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

import config
import logic

logging.basicConfig(level=logging.INFO)


class TradeStates(StatesGroup):
    waiting_for_ticker = State()
    waiting_for_timeframe = State()
    waiting_for_context = State()


bot = Bot(token=config.TELEGRAM_TOKEN)
dp = Dispatcher()


# --- КЛАВИАТУРЫ ---

def get_main_menu_keyboard():
    kb = [
        [KeyboardButton(text="💎 Крипта"), KeyboardButton(text="📈 Акции (US)")],
        [KeyboardButton(text="💱 Форекс"), KeyboardButton(text="🟡 Сырье (Gold/Oil)")],
        [KeyboardButton(text="🔍 Ручной ввод")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def get_crypto_keyboard():
    kb = [
        [KeyboardButton(text="BTC-USD"), KeyboardButton(text="ETH-USD")],
        [KeyboardButton(text="SOL-USD"), KeyboardButton(text="XRP-USD")],
        [KeyboardButton(text="BNB-USD"), KeyboardButton(text="DOGE-USD")],
        [KeyboardButton(text="🔙 Назад")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def get_stocks_keyboard():
    kb = [
        [KeyboardButton(text="AAPL"), KeyboardButton(text="TSLA"), KeyboardButton(text="NVDA")],
        [KeyboardButton(text="MSFT"), KeyboardButton(text="GOOGL"), KeyboardButton(text="AMZN")],
        [KeyboardButton(text="COIN"), KeyboardButton(text="MSTR"), KeyboardButton(text="AMD")],
        [KeyboardButton(text="🔙 Назад")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def get_forex_keyboard():
    kb = [
        [KeyboardButton(text="EURUSD=X"), KeyboardButton(text="GBPUSD=X")],
        [KeyboardButton(text="JPY=X")],
        [KeyboardButton(text="🔙 Назад")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def get_commodities_keyboard():
    kb = [
        [KeyboardButton(text="GC=F"), KeyboardButton(text="CL=F")],
        [KeyboardButton(text="SI=F"), KeyboardButton(text="NG=F")],
        [KeyboardButton(text="🔙 Назад")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def get_timeframe_keyboard():
    kb = [
        [KeyboardButton(text="15m"), KeyboardButton(text="30m"), KeyboardButton(text="1h")],
        [KeyboardButton(text="4h"), KeyboardButton(text="1d")],
        [KeyboardButton(text="1wk"), KeyboardButton(text="1mo")],
        [KeyboardButton(text="🔙 Назад")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


# --- ХЕНДЛЕРЫ ---

@dp.message(Command("start", "menu"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "👋 <b>Трейд-Бот готов!</b>\nВыберите категорию актива:",
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_menu_keyboard()
    )
    await state.set_state(TradeStates.waiting_for_ticker)


@dp.message(F.text.lower().in_({"🔙 назад", "назад"}))
async def go_back(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Главное меню:", reply_markup=get_main_menu_keyboard())
    await state.set_state(TradeStates.waiting_for_ticker)


# --- КАТЕГОРИИ ---
@dp.message(F.text == "💎 Крипта")
async def show_crypto(message: types.Message, state: FSMContext):
    await message.answer("Выберите монету:", reply_markup=get_crypto_keyboard())


@dp.message(F.text == "📈 Акции (US)")
async def show_stocks(message: types.Message, state: FSMContext):
    await message.answer("Выберите акцию:", reply_markup=get_stocks_keyboard())


@dp.message(F.text == "💱 Форекс")
async def show_forex(message: types.Message, state: FSMContext):
    await message.answer("Выберите пару:", reply_markup=get_forex_keyboard())


@dp.message(F.text == "🟡 Сырье (Gold/Oil)")
async def show_commodities(message: types.Message, state: FSMContext):
    await message.answer("Выберите актив:", reply_markup=get_commodities_keyboard())


@dp.message(F.text == "🔍 Ручной ввод")
async def manual_input_prompt(message: types.Message, state: FSMContext):
    kb = [[KeyboardButton(text="🔙 Назад")]]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

    await message.answer("✍️ Введите тикер (только латиница, например: <code>PEPE-USD</code>):",
                         parse_mode=ParseMode.HTML, reply_markup=keyboard)


# --- ВАЛИДАЦИЯ ТИКЕРА ---

@dp.message(StateFilter(TradeStates.waiting_for_ticker))
async def process_ticker(message: types.Message, state: FSMContext):
    text = message.text.strip()

    if text.lower() in ["🔙 назад", "назад"]:
        await message.answer("Главное меню:", reply_markup=get_main_menu_keyboard())
        await state.set_state(TradeStates.waiting_for_ticker)  # Сбрасываем стейт на начало
        return

    # Игнорируем нажатия категорий (если вдруг)
    if text in ["💎 Крипта", "📈 Акции (US)", "💱 Форекс", "🟡 Сырье (Gold/Oil)", "🔍 Ручной ввод"]:
        return

    ticker = text.upper()

    # --- ЗАЩИТА ОТ ДУРАКА (Валидация) ---

    if re.search('[а-яА-Я]', ticker):
        await message.answer(
            "⛔️ <b>Ошибка:</b> Тикер должен быть на английском языке!\nПример: <code>BTC-USD</code>, а не <code>БИТКОИН</code>.",
            parse_mode=ParseMode.HTML)
        return

    if not re.match(r'^[A-Z0-9\-\.\=]+$', ticker):
        await message.answer("⛔️ <b>Ошибка:</b> Недопустимые символы. Используйте только латиницу, цифры и тире.",
                             parse_mode=ParseMode.HTML)
        return

    if len(ticker) < 2 or len(ticker) > 20:
        await message.answer("⛔️ <b>Ошибка:</b> Слишком короткий или длинный тикер.", parse_mode=ParseMode.HTML)
        return

    await state.update_data(ticker=ticker)
    await message.answer(
        f"✅ Тикер принят: <b>{ticker}</b>.\nТеперь выбери таймфрейм:",
        parse_mode=ParseMode.HTML,
        reply_markup=get_timeframe_keyboard()
    )
    await state.set_state(TradeStates.waiting_for_timeframe)


# --- ОБРАБОТКА ТАЙМФРЕЙМА ---

@dp.message(StateFilter(TradeStates.waiting_for_timeframe))
async def process_timeframe(message: types.Message, state: FSMContext):
    timeframe = message.text.lower().strip()

    # Кнопка назад работает и здесь
    if timeframe in ["🔙 назад", "назад"]:
        await message.answer("Главное меню:", reply_markup=get_main_menu_keyboard())
        await state.set_state(TradeStates.waiting_for_ticker)
        return

    valid_timeframes = ['15m', '30m', '1h', '4h', '1d', '1wk', '1mo']

    if timeframe not in valid_timeframes:
        await message.answer("⚠️ Выберите таймфрейм из кнопок.")
        return

    data_store = await state.get_data()
    ticker = data_store['ticker']

    status_msg = await message.answer(f"⏳ <b>{ticker}</b>: Скачиваю данные...", parse_mode=ParseMode.HTML,
                                      reply_markup=ReplyKeyboardRemove())

    market_data = await asyncio.to_thread(logic.get_market_data, ticker, timeframe)

    if not market_data:
        await status_msg.delete()
        await message.answer(f"❌ Тикер <b>{ticker}</b> не найден на бирже.\nПопробуйте другой.",
                             parse_mode=ParseMode.HTML, reply_markup=get_main_menu_keyboard())
        await state.set_state(TradeStates.waiting_for_ticker)
        return

    await state.update_data(market_data=market_data, timeframe=timeframe)
    await status_msg.delete()

    await message.answer(
        f"📉 <b>{ticker} ({timeframe})</b> загружен.\n"
        f"Цена: {market_data['price']}\n\n"
        "Напиши свои мысли (или точку .):",
        parse_mode=ParseMode.HTML
    )
    await state.set_state(TradeStates.waiting_for_context)


# --- ФИНАЛ ---

@dp.message(StateFilter(TradeStates.waiting_for_context))
async def process_analysis(message: types.Message, state: FSMContext):
    user_text = message.text
    data = await state.get_data()

    ticker = data['ticker']
    market_data = data['market_data']
    timeframe = data['timeframe']

    wait_msg = await message.answer("🧠 <b>Анализирую...</b>", parse_mode=ParseMode.HTML)

    dxy = await asyncio.to_thread(logic.get_market_data, "DX-Y.NYB", timeframe)
    if not dxy: dxy = {"price": "N/A", "trend": "N/A"}

    ai_verdict = await logic.get_ai_analysis(ticker, market_data, dxy, user_text, timeframe)

    header = (
        f"📊 <b>{ticker} ({timeframe})</b>\n"
        f"💰 Цена: {market_data['price']}\n"
        f"📈 Тренд: {market_data['trend']} | ATR: {market_data['atr']}\n"
        f"──────────────────\n"
    )

    await wait_msg.delete()

    full_text = header + ai_verdict
    if len(full_text) > 4000: full_text = full_text[:4000]

    try:
        await message.answer(full_text, parse_mode=ParseMode.HTML)
    except Exception:
        await message.answer(full_text, parse_mode=None)

    await message.answer("\n🔄 <b>Главное меню:</b>", parse_mode=ParseMode.HTML, reply_markup=get_main_menu_keyboard())
    await state.set_state(TradeStates.waiting_for_ticker)


async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    print("Бот запущен...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Exit")