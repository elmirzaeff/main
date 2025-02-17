import pandas as pd
import os
from config import DATA_FILE
from logger import logger

def save_data(df: pd.DataFrame):
    """Сохраняет данные в CSV."""
    try:
        #df.to_csv(DATA_FILE, index=False)
        df[["timestamp", "open", "high", "low", "close", "volume", "ATR"]].to_csv(DATA_FILE, index=False)
        logger.info(f"Данные успешно сохранены в {DATA_FILE}")
    except Exception as e:
        logger.error(f"Ошибка сохранения данных в {DATA_FILE}: {e}", exc_info=True)


def load_data() -> pd.DataFrame:
    """Загружает данные из CSV, если файл существует."""
    try:
        if os.path.exists(DATA_FILE):
            df = pd.read_csv(DATA_FILE, parse_dates=["timestamp"])
            logger.info(f"Загружены данные из {DATA_FILE}, {len(df)} записей.")
            return df
        else:
            logger.warning(f"Файл {DATA_FILE} не найден. Создаётся новый DataFrame.")
            return pd.DataFrame()
    except Exception as e:
        logger.error(f"Ошибка загрузки данных из {DATA_FILE}: {e}", exc_info=True)
        return pd.DataFrame()