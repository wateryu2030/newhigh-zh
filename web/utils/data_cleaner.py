"""
通用数据清洗模块，用于检测和清理 DataFrame 中的重复列，防止 PyArrow、Streamlit 报错。
"""

import pandas as pd
import logging

# 初始化日志
logger = logging.getLogger("data_cleaner")
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    logger.addHandler(ch)


def detect_duplicate_columns(df: pd.DataFrame) -> list:
    """
    检测 DataFrame 中的重复列名
    :param df: pandas.DataFrame
    :return: 重复列名列表
    """
    dup_cols = df.columns[df.columns.duplicated()].tolist()
    if dup_cols:
        logger.warning(f"⚠️ 检测到重复字段: {dup_cols}")
    return dup_cols


def clean_duplicate_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    清理 DataFrame 中重复的列名，保留第一列。
    :param df: pandas.DataFrame
    :return: 清理后的 DataFrame
    """
    dup_cols = detect_duplicate_columns(df)
    if dup_cols:
        df = df.loc[:, ~df.columns.duplicated()]
        logger.info(f"✅ 已移除重复列，当前字段数量: {len(df.columns)}")
    return df


def normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """
    统一列名格式（去除多余空格、统一小写）
    :param df: pandas.DataFrame
    :return: 标准化后的 DataFrame
    """
    original = df.columns.tolist()
    df.columns = [col.strip().lower() for col in df.columns]
    logger.info(f"🧩 标准化列名: {len(original)} → {len(set(df.columns))}")
    return clean_duplicate_columns(df)


def safe_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    综合清理函数：去重 + 标准化 + 重命名
    :param df: pandas.DataFrame
    :return: 清理后的 DataFrame
    """
    if df is None or df.empty:
        logger.warning("⚠️ 输入 DataFrame 为空，跳过清理。")
        return df
    df = normalize_column_names(df)
    df = clean_duplicate_columns(df)
    return df


# 示例使用：
if __name__ == "__main__":
    # 模拟重复列 DataFrame
    data = {
        "stock_code": [1, 2],
        "stock_name": ["A", "B"],
        "price": [10, 20],
        "price": [11, 22],
        "volume": [1000, 2000],
        "volume": [1000, 2000]
    }
    df = pd.DataFrame(data)
    print("原始列:", df.columns.tolist())

    df_clean = safe_dataframe(df)
    print("清理后列:", df_clean.columns.tolist())

