import yfinance as yf


def get_market_sentiment(symbol):
    try:
        ticker = yf.Ticker(symbol)

        news_list = ticker.news

        if not news_list:
            return "Новостей по этому активу не найдено."

        summary = ""
        for item in news_list[:3]:
            title = item.get('title', 'Без заголовка')
            publisher = item.get('publisher', 'Yahoo Finance')

            summary += f"- [{publisher}] {title}\n"

        return summary if summary else "Новостей нет."

    except Exception as e:
        return f"Ошибка загрузки новостей: {e}"