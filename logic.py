import yfinance as yf
import ta
import pandas as pd
import google.generativeai as genai
import asyncio
import config
import re

genai.configure(api_key=config.GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-flash-latest')


def get_market_data(ticker, timeframe):
    try:
        df = yf.download(ticker, period="1mo", interval=timeframe, progress=False)
        if df.empty: return None

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        close_series = df['Close']
        if isinstance(close_series, pd.DataFrame):
            close_series = close_series.iloc[:, 0]

        if len(close_series) < 200:
            df['SMA_200'] = pd.Series([None] * len(close_series))
        else:
            df['SMA_200'] = ta.trend.sma_indicator(close_series, window=200)

        df['RSI'] = ta.momentum.rsi(close_series, window=14)

        last_price = close_series.iloc[-1]
        last_rsi = df['RSI'].iloc[-1]
        last_sma = df['SMA_200'].iloc[-1]

        if pd.isna(last_sma):
            trend = "НЕТ ДАННЫХ ⚪"
        else:
            trend = "UP 🟢" if last_price > last_sma else "DOWN 🔴"

        rsi_val = round(last_rsi, 2) if not pd.isna(last_rsi) else 50.0

        return {
            "price": round(last_price, 2),
            "rsi": rsi_val,
            "trend": trend
        }
    except Exception as e:
        print(f"Error {ticker}: {e}")
        return None


async def get_ai_analysis(symbol_name, symbol_data, dxy_data, user_text, timeframe):
    prompt = f"""
    Ты бот-аналитик.

    АКТИВ: {symbol_name} (Таймфрейм: {timeframe})
    Цена: {symbol_data['price']}, RSI: {symbol_data['rsi']}, Тренд: {symbol_data['trend']}

    ИНДЕКС ДОЛЛАРА (DXY): {dxy_data['price']}, Тренд: {dxy_data['trend']}

    СОСТОЯНИЕ ТРЕЙДЕРА: "{user_text}"

    ИНСТРУКЦИЯ (HTML):
    1. ИСПОЛЬЗУЙ ТОЛЬКО ТЕГИ: <b>жирный</b>, <i>курсив</i>, <code>код</code>.
    2. ЗАПРЕЩЕНО: <p>, markdown.
    3. Отвечай сжато.

    СТРУКТУРА:
    <b>📊 АНАЛИЗ {timeframe}:</b>
    (Техника + DXY).

    <b>🧠 ПСИХОЛОГИЯ:</b>
    (Совет).

    <b>ВЕРДИКТ:</b> <b>[ЛОНГ]</b> / <b>[ШОРТ]</b> / <b>[ЖДАТЬ]</b>
    """

    try:
        response = await asyncio.to_thread(model.generate_content, prompt)
        text = response.text

        text = text.replace("```html", "").replace("```", "").replace("**", "")
        text = text.replace("<p>", "").replace("</p>", "\n").replace("<br>", "\n")
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()
    except Exception as e:
        return f"⚠️ Ошибка нейросети: {e}"