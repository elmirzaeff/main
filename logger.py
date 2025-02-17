import logging
from config import LOG_FILE
import os

# Устанавливаем текущую директорию как рабочую
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Настройка логирования
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    encoding="utf-8"
)

logger = logging.getLogger()