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
        query = f"{symbol} news"
        results = DDGS().text(keywords=query, region='wt-wt', safesearch='off', timelimit='d', max_results=3)
        news_summary = ""
        if results:
            for res in results:
                news_summary += f"- {res['title']}\n"
        return news_summary if news_summary else "Новостей нет."
    except Exception:
        return "Не удалось загрузить новости."


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
            trend_str = "НЕТ ДАННЫХ"

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


async def get_ai_analysis(symbol_name, symbol_data, dxy_data, user_text, timeframe):
    news_text = await asyncio.to_thread(get_news_sentiment, symbol_name)

    system_prompt = """
        Ты — строгий риск-менеджер хедж-фонда. Твоя цель — защита капитала.

        ПРАВИЛА:
        1. Будь краток. Без воды.
        2. Используй только HTML теги: <b>жирный</b>, <code>код</code>, <i>курсив</i>.
        3. НИКАКОГО Markdown (символов ** или ##).
        4. Если Техника противоречит Новостям — рекомендуй [ЖДАТЬ].
        5. Всегда рассчитывай Стоп-Лосс.
        """

    user_prompt = f"""
    АКТИВ: {symbol_name} ({timeframe}) | Цена: {symbol_data['price']}
    Техника: RSI {symbol_data['rsi']}, Тренд {symbol_data['trend']}, ATR {symbol_data['atr']}
    Боллинджер: {symbol_data['bb_status']}
    Новости: {news_text}
    Индекс доллара: {dxy_data['price']}
    Вопрос: "{user_text}"

    Дай сигнал с учетом ATR для стоп-лосса.
    Формат:
    <b>🗞 ФОН:</b> ...
    <b>⚙️ ТЕХНИКА:</b> ...
    <b>🎯 ВЕРДИКТ:</b> [ЛОНГ]/[ШОРТ]/[ЖДАТЬ]
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
        return response.choices[0].message.content
    except Exception as e:
        return f"⚠️ Ошибка Groq: {e}"