from loguru import logger
import sys

def setup_logger(log_file: str):
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    logger.add(log_file, rotation="10 MB", retention=5, level="INFO", enqueue=True)
    return logger
