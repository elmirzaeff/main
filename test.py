import time
import ccxt
import pandas as pd
import os
import pytz
import threading
import subprocess
import decimal
from config import TELEGRAM_TOKEN_2, TARGET_TIMEZONE, CRYPTO_PAIR, TIMEFRAME, DATA_FILE, LOG_FILE
from logger import logger
from data_handler import save_data, load_data
from telegram_bot import bot, send_message
from order_manager import place_order, place_tp_sl

# Делает текущую директорию рабочей
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Настройка точности Decimal
DECIMAL_CTX = decimal.getcontext()
DECIMAL_CTX.prec = 10  # Достаточная точность для расчетов

# Инициализация биржи
exchange = ccxt.bybit({
    'enableRateLimit': True,
})

# Глобальная переменная для ID чата
chat_id = None

last_cross_time = None  # Глобальная переменная для отслеживания последнего пересечения
last_entry_price = None  # Цена последнего пересечения вверх
atr_at_entry = None  # ATR на момент входа

# Функция для получения данных
def fetch_candles(pair, timeframe):
    """Получение свечей с биржи и загрузка в DataFrame."""
    try:
        logger.info(f"Запрашиваем данные {pair} на таймфрейме {timeframe}...")

        candles = exchange.fetch_ohlcv(pair, timeframe, limit=500, params={"timeout": 10})
        df = pd.DataFrame(candles, columns=["timestamp", "open", "high", "low", "close", "volume"])

        # Преобразование временного штампа в указанный часовой пояс
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        local_tz = pytz.timezone(TARGET_TIMEZONE)
        df["timestamp"] = df["timestamp"].dt.tz_localize("UTC").dt.tz_convert(local_tz).dt.tz_localize(None)

        logger.info(f"Успешно получены данные: {len(df)} свечей.")
        return df
    except Exception as e:
        logger.error(f"Ошибка при запросе данных с биржи для {pair}: {e}", exc_info=True)
        return pd.DataFrame()

# Расчёт скользящих средних
def calculate_sma(df, period):
    """Расчёт скользящей средней."""
    return df["close"].rolling(window=period).mean()


# Расчет ATR
def calculate_atr(df, period=50):
    """Расчет ATR (Average True Range)"""
    df["high_low"] = df["high"] - df["low"]
    df["high_close"] = (df["high"] - df["close"].shift()).abs()
    df["low_close"] = (df["low"] - df["close"].shift()).abs()

    df["true_range"] = df[["high_low", "high_close", "low_close"]].max(axis=1)
    df["ATR"] = df["true_range"].rolling(window=period).mean()
    return df


# Проверка пересечений
def check_crossing(df):
    """Проверка пересечения SMA-50 и SMA-200."""
    df["SMA_50"] = calculate_sma(df, 50)
    df["SMA_200"] = calculate_sma(df, 200)

    # Проверяем пересечения
    df["cross"] = (df["SMA_50"] > df["SMA_200"]).astype(int)
    df["cross_shift"] = df["cross"].shift(1)
    crossings = df[(df["cross"] != df["cross_shift"]) & (df["cross_shift"].notnull())]
    return crossings

# Основной процесс мониторинга
def monitor_crypto():

    global chat_id, last_cross_time, last_entry_price, atr_at_entry

    # Загружаем исторические данные, если они есть
    df = load_data()
    logger.info("Загружаем исторические данные...")

    # Если данных недостаточно, запрашиваем новые свечи
    if df.empty or len(df) < 200:
        df = fetch_candles(CRYPTO_PAIR, TIMEFRAME)
        df = calculate_atr(df)
        save_data(df)  # Сохраняем данные

    logger.info("Бот запущен и мониторинг начат!")
    logger.info("Запускаем основной цикл мониторинга...")
    

    level_up_reached = False  # Флаг достижения +3ATR
    level_down_reached = False  # Флаг достижения -1ATR

    while True:
        try:
            # Получаем новые данные
            new_data = fetch_candles(CRYPTO_PAIR, TIMEFRAME)
            logger.info(f"Получены новые данные: {new_data.tail(1)}")

            # Обновляем DataFrame и сохраняем данные
            df = pd.concat([df, new_data]).drop_duplicates(subset="timestamp").reset_index(drop=True)
            df = calculate_atr(df)
            save_data(df)

            # Проверяем пересечения
            crossings = check_crossing(df)
            logger.info(f"Проверка пересечений, найдено: {len(crossings)}")

            if not crossings.empty:
                last_crossing = crossings.iloc[-1]
                cross_time = last_crossing["timestamp"]

                # Отправляем сообщение только при новом пересечении
                if last_cross_time != cross_time:
                    last_cross_time = cross_time

                    if last_crossing["SMA_50"] > last_crossing["SMA_200"]:  # Пересечение ВВЕРХ
                        direction = "Вверх"

                        # Выставляем ордер на покупку, TP, SL
                        try:
                            order = place_order(CRYPTO_PAIR, "buy", 10) 

                            if order:
                                try:
                                    entry_price = exchange.fetch_ticker(CRYPTO_PAIR)['last']  # Получаем текущую цену входа
                                    place_tp_sl(CRYPTO_PAIR, "buy", entry_price)
                                except Exception as e:
                                    logger.error(f"❌ Ошибка при получении цены входа: {e}", exc_info=True)

                        except Exception as e:
                            logger.error(f"❌ Ошибка при размещении ордера: {e}", exc_info=True)
                            order = None  # Чтобы код дальше выполнялся

                        last_entry_price = last_crossing["close"]  # Запоминаем цену пересечения
                        atr_at_entry = last_crossing["ATR"]  # Запоминаем ATR на момент входа
                    else:
                        continue  # Пересечение вниз – ничего не делаем, пропускаем

                    current_price = last_crossing["close"]
                    #previous_price = last_crossing["close"] if len(crossings) < 2 else crossings.iloc[-2]["close"]

                    message = (
                        f"Пересечение обнаружено!\n"
                        f"Пара: {CRYPTO_PAIR}\n"
                        f"Направление: {direction}\n"
                        f"Время: {last_cross_time}\n"
                        #f"Прошлая цена: {previous_price}\n"
                        f"Текущая цена: {current_price}\n"
                        f"3ATR: {(last_entry_price + 3 * atr_at_entry):.4f}\n"
                        f"-1ATR: {(last_entry_price - 1 * atr_at_entry):.4f}"
                    )
                    send_message(message)
                    logger.info(f"Отправлено сообщение: {message}")

            if last_entry_price is not None and atr_at_entry is not None:
                level_up = last_entry_price + 3 * atr_at_entry  # Уровень 3ATR вверх
                level_down = last_entry_price - 1 * atr_at_entry   # Уровень -ATR вниз
                current_price = df.iloc[-1]["close"]  # Текущая цена

                if current_price >= level_up:
                    achievement_price = level_up  # Фиксируем цену достижения
                    achievement_time = df.iloc[-1]["timestamp"]  # Фиксируем время
                    send_message(
                        f"Цена достигла +3ATR!\n"
                        f"Цена срабатывания: {achievement_price:.4f}\n"
                        f"Время: {achievement_time}"
                        )
                    last_entry_price = None  # Сбрасываем отслеживание
                    atr_at_entry = None

                elif current_price <= level_down:
                    achievement_price = level_down  # Фиксируем цену достижения
                    achievement_time = df.iloc[-1]["timestamp"]  # Фиксируем время
                    send_message(
                        f"Цена достигла -1ATR!\n"
                        f"Цена срабатывания: {achievement_price:.4f}\n"
                        f"Время: {achievement_time}"
                        )
                    last_entry_price = None  # Сбрасываем отслеживание
                    atr_at_entry = None

            logger.info("Ожидание 30 секунд перед следующим циклом...")
            time.sleep(30)  # Проверяем каждые 30 секунд
        except Exception as e:
            logger.error(f"Ошибка: {e}", exc_info=True)
            time.sleep(60)  # Пауза перед повторной попыткой


# Запуск бота
if __name__ == "__main__":
    import threading
    threading.Thread(target=monitor_crypto).start()

# Запускаем мониторинг криптовалюты в отдельном потоке
threading.Thread(target=monitor_crypto, daemon=True).start()

# Запускаем telegram_bot.py в отдельном процессе
logger.info("Запуск Telegram-бота...")
subprocess.Popen(["python", "telegram_bot.py"])

logger.info("Основной процесс test.py запущен.")