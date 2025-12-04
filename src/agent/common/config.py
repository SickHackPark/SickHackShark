import logging
import sys
import os
from logging.handlers import RotatingFileHandler
from functools import lru_cache

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI


def setup_logging():
    """
    初始化日志配置
    """
    load_dotenv(os.getenv("ENV_FILE_PATH"))
    # Configure logging
    # 创建 logs 目录（如果不存在）
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # 设置日志处理器，包括控制台和文件输出
    handlers = [
        logging.StreamHandler(sys.stdout),
        RotatingFileHandler(
            filename=os.path.join(log_dir, "app.log"),
            maxBytes=100*1024*1024,  # 500MB
            backupCount=5
        )
    ]

    env_file_path = os.getenv("ENV_FILE_PATH", "")
    openai_model_name = os.getenv("OPENAI_MODEL", "")
    run_agent_name = os.getenv("RUN_AGENT", "")
    logging.basicConfig(
        level=logging.INFO,
        format=f"{env_file_path} - {openai_model_name} - {run_agent_name} " + " %(asctime)s [%(levelname)s] %(filename)s:%(lineno)d (%(funcName)s) - %(message)s",
        handlers=handlers
    )

    # Create a logger instance
    logger = logging.getLogger(__name__)
    return logger


@lru_cache(maxsize=None)
def get_logger():
    """
    获取配置好的 logger 实例
    
    Returns:
        logging.Logger: 配置好的 logger 实例
    """
    return setup_logging()


@lru_cache(maxsize=None)
def get_models():
    """
    获取主备模型实例
    
    Returns:
        tuple: (main_model, backup_model) 主模型和备用模型实例
    """
    main_model = ChatOpenAI(
        temperature=float(os.getenv("MAIN_MODEL_TEMPERATURE", "0.5")),
        model=os.getenv("MAIN_OPENAI_MODEL"),
        base_url=os.getenv("MAIN_OPENAI_BASE_URL"),
        api_key=os.getenv("MAIN_OPENAI_API_KEY")
    )
    
    backup_model = ChatOpenAI(
        temperature=float(os.getenv("BACKUP_MODEL_TEMPERATURE", "0.5")),
        model=os.getenv("BACKUP_OPENAI_MODEL"),
        base_url=os.getenv("BACKUP_OPENAI_BASE_URL"),
        api_key=os.getenv("BACKUP_OPENAI_API_KEY")
    )
    
    return main_model, backup_model