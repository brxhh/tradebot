import yfinance as yf
import ta
import pandas as pd
from openai import OpenAI
import asyncio
import config
import warnings
from duckduckgo_search import DDGS

warnings.filterwarnings("ignore")

client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=config.GROQ_API_KEY
)


def get_period_for_timeframe(timeframe):
    tf_map = {
        '15m': '1mo', '30m': '1mo',
        '1h': '1y', '4h': '2y', '1d': '5y', '1wk': '5y', '1mo': 'max'
    }
    return tf_map.get(timeframe, '1mo')


def get_news_sentiment(symbol):
    try:
        # Убираем лишнее из тикера для поиска
        search_term = symbol.split('=')[0]
        query = f"{search_term} market news"
        results = DDGS().text(keywords=query, region='wt-wt', safesearch='off', timelimit='d', max_results=3)

        news_summary = ""
        if results:
            for res in results:
                news_summary += f"- {res['title']}\n"
        return news_summary if news_summary else "Значимых новостей нет."
    except Exception:
        return "Ошибка загрузки новостей."


def get_market_data(ticker, timeframe):
    try:
        period = get_period_for_timeframe(timeframe)
        df = yf.download(ticker, period=period, interval=timeframe, progress=False, multi_level_index=False)

        if df.empty or len(df) < 50: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)

        close = df['Close']
        high = df['High']
        low = df['Low']

        if len(close) >= 200:
            trend_val = ta.trend.sma_indicator(close, window=200).iloc[-1]
            trend_str = "UP 🟢" if close.iloc[-1] > trend_val else "DOWN 🔴"
        else:
            trend_str = "Н/Д"

        rsi = ta.momentum.rsi(close, window=14)
        bb = ta.volatility.BollingerBands(close, window=20)
        atr = ta.volatility.average_true_range(high, low, close, window=14)

        last_price = close.iloc[-1]

        if last_price >= bb.bollinger_hband().iloc[-1]:
            bb_status = "⚠️ ПЕРЕКУПЛЕН"
        elif last_price <= bb.bollinger_lband().iloc[-1]:
            bb_status = "⚠️ ПЕРЕПРОДАН"
        else:
            bb_status = "Норма"

        return {
            "price": round(float(last_price), 4),
            "rsi": round(rsi.iloc[-1], 2),
            "trend": trend_str,
            "bb_status": bb_status,
            "support": round(close.tail(50).min(), 4),
            "resistance": round(close.tail(50).max(), 4),
            "atr": round(atr.iloc[-1], 4)
        }
    except Exception:
        return None


def clean_ai_response(text):
    text = text.replace("**", "")
    text = text.replace("###", "")
    text = text.replace("```html", "").replace("```", "")
    return text.strip()


async def get_ai_analysis(symbol_name, symbol_data, dxy_data, user_text, timeframe):
    news_text = await asyncio.to_thread(get_news_sentiment, symbol_name)

    system_prompt = """
    Ты — строгий риск-менеджер хедж-фонда. 
    Твоя задача — не просто угадать направление, а дать грамотный совет по управлению позицией.

    ПРАВИЛА:
    1. Будь краток.
    2. Используй HTML теги: <b>жирный</b>, <code>код</code>, <i>курсив</i>.
    3. НИКАКОГО Markdown (** или ##).
    4. Всегда рассчитывай Стоп-Лосс (2 * ATR).
    """

    user_prompt = f"""
    АКТИВ: {symbol_name} ({timeframe}) | Цена: {symbol_data['price']}

    ТЕХНИКА: 
    • RSI: {symbol_data['rsi']} (Если >70 перекуплен, <30 перепродан)
    • Тренд: {symbol_data['trend']}
    • ATR: {symbol_data['atr']}
    • Bollinger: {symbol_data['bb_status']}
    • Поддержка/Сопр: {symbol_data['support']} / {symbol_data['resistance']}

    НОВОСТИ: {news_text}
    DXY (Индекс доллара): {dxy_data['price']}
    Мысли трейдера: "{user_text}"

    ЗАДАЧА:
    Дай прогноз, рассчитай стоп-лосс и дай совет по психологии/риску.

    ФОРМАТ ОТВЕТА (СТРОГО):
    <b>🗞 ФОН:</b> ...

    <b>⚙️ ТЕХНИКА:</b> ...

    <b>🧠 СОВЕТ:</b> (Оцени риск/прибыль, стоит ли ждать подтверждения, психология момента)

    <b>🎯 ВЕРДИКТ:</b> [ЛОНГ]/[ШОРТ]/[ЖДАТЬ] (Стоп-лосс: <code>Цена</code>)
    """

    try:
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3
        )
        return clean_ai_response(response.choices[0].message.content)
    except Exception as e:
        return f"⚠️ Ошибка Groq: {e}"