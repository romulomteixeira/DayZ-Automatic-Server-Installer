import logging
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

LOG_DIR = os.path.join(BASE_DIR, "logs")

os.makedirs(LOG_DIR, exist_ok=True)

logfile = os.path.join(
    LOG_DIR,
    "bootstrap_"+datetime.now().strftime("%Y-%m-%d_%H-%M")+".log"
)

logging.basicConfig(
    filename=logfile,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def log(msg):
    print(msg)
    logging.info(msg)