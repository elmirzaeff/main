import os

# Bybit API Credentials (Загрузка из переменных окружения)
BYBIT_API_KEY = os.getenv("BYBIT_API_KEY")
BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET")

# Telegram
TELEGRAM_TOKEN_2 = os.getenv("TELEGRAM_TOKEN_2")  # Лучше использовать переменные окружения
CHAT_ID = None  # ID чата (можно сохранять в файл, чтобы не терялся после перезапуска)

# Биржа
CRYPTO_PAIR = "PONKE/USDT:USDT"  # Криптопара для анализа
TIMEFRAME = "1m"  # Таймфрейм анализа (1 минута)

# Данные
DATA_FILE = "candles.csv"  # Файл для сохранения исторических данных

# Часовой пояс
TARGET_TIMEZONE = "Europe/Moscow"

# Лог-файл
LOG_FILE = "bot.log"
