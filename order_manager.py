import ccxt
import time
import decimal
from logger import logger
from config import CRYPTO_PAIR, BYBIT_API_KEY, BYBIT_API_SECRET


# Подключение к бирже Bybit
exchange = ccxt.bybit({
    'apiKey': BYBIT_API_KEY,
    'secret': BYBIT_API_SECRET,
    'enableRateLimit': True,
    'options': {'defaultType': 'future'}
})

def place_order(symbol, side, amount, params=None):
    """Создание ордера"""
    
    try:
        # Загружаем рынки перед проверкой символа
        exchange.load_markets()

        # Проверяем, поддерживает ли символ торговлю с плечом
        market = exchange.market(symbol)
        if market['type'] != 'linear':
            logger.error(f"❌ Ошибка: Рынок {symbol} не является 'linear', нельзя установить плечо!")
        else:
            # Установка изолированной маржи и плеча (только если 'linear')
            exchange.set_margin_mode("isolated", symbol)
            exchange.set_leverage(1, symbol)

        # Создание рыночного ордера для бессрочного фьючерса
        order = exchange.create_market_order(symbol, side, amount, params={'type': 'swap'})

        logger.info(f"✅ Ордер {side.upper()} выполнен с объемом {amount} контрактов.")
        logger.info(f"✅ Ордер {side.upper()} выполнен!\n"
                    f"Пара: {symbol}\n"
                    f"Количество: {amount}\n"
                    f"Плечо: 1x\n")
        return order
    except Exception as e:
        logger.error(f"❌ Ошибка при создании ордера: {e}", exc_info=True)
        return None

def place_tp_sl(symbol, side, entry_price):
    """Устанавливает тейк-профит и стоп-лосс на 3%."""
    try:
        tp_percent = decimal.Decimal("0.03")  # 3% для TP
        sl_percent = decimal.Decimal("0.03")  # 3% для SL

        entry_price = decimal.Decimal(entry_price)

        if side == "buy":
            take_profit_price = entry_price * (1 + tp_percent)  # TP выше на 3%
            stop_loss_price = entry_price * (1 - sl_percent)  # SL ниже на 3%
        else:  # sell
            take_profit_price = entry_price * (1 - tp_percent)  # TP ниже на 3%
            stop_loss_price = entry_price * (1 + sl_percent)  # SL выше на 3%

        # Устанавливаем тейк-профит
        tp_order = exchange.create_order(
            symbol=symbol,
            type="limit",
            side="sell" if side == "buy" else "buy",
            amount=10,  # Количество контрактов
            price=float(take_profit_price),
            params={"reduceOnly": True}  # Закрывает позицию, а не открывает новую
        )

        # Устанавливаем стоп-лосс
        sl_order = exchange.create_order(
            symbol=symbol,
            type="market",  # Стоп-лосс должен быть рыночным
            side="sell" if side == "buy" else "buy",
            amount=10,  # Количество контрактов
            params={
                "reduceOnly": True,
                "stopLossPrice": float(stop_loss_price)  # Правильный параметр для SL
            }
        )

        logger.info(f"✅ TP/SL установлены для {symbol} | TP: {take_profit_price}, SL: {stop_loss_price}")

        return tp_order, sl_order

    except Exception as e:
        logger.error(f"❌ Ошибка при установке TP/SL: {e}", exc_info=True)
        return None, None
