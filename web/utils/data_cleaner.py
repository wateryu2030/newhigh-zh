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


def clean_duplicate_columns(df: pd.DataFrame, keep_first: bool = True) -> pd.DataFrame:
    """
    清理 DataFrame 中重复的列名，保留第一列或使用dict.fromkeys保持顺序。
    
    :param df: pandas.DataFrame
    :param keep_first: 如果为True，保留第一个出现的列；如果为False，使用dict.fromkeys保持顺序（推荐）
    :return: 清理后的 DataFrame
    """
    if df is None or df.empty:
        return df
    
    # 首先检查是否有重复列
    if not df.columns.duplicated().any():
        # 没有重复列，直接返回
        return df
    
    # 有重复列，需要清理
    if keep_first:
        # 方法1：使用pandas的duplicated()方法，保留第一个
        df = df.loc[:, ~df.columns.duplicated()]
    else:
        # 方法2：使用dict.fromkeys保持顺序（推荐，更可靠）
        unique_cols = list(dict.fromkeys(df.columns))
        if len(unique_cols) != len(df.columns):
            # 如果有重复，重建DataFrame
            # 确保数据列数匹配
            num_cols = len(unique_cols)
            num_rows = len(df)
            if num_cols > 0:
                # 获取唯一列对应的数据
                seen = {}
                col_indices = []
                for i, col in enumerate(df.columns):
                    if col not in seen:
                        seen[col] = i
                        col_indices.append(i)
                
                # 确保索引数量正确
                if len(col_indices) == num_cols:
                    df = df.iloc[:, col_indices]
                    df.columns = unique_cols
                else:
                    # 如果索引不匹配，使用values重建
                    df = pd.DataFrame(df.values[:, :num_cols], columns=unique_cols)
            else:
                df = pd.DataFrame(columns=unique_cols)
        else:
            # 即使没有重复，也确保列名唯一
            df = df[unique_cols]
    
    # 最终验证：确保绝对没有重复列
    if df.columns.duplicated().any():
        # 如果还有重复，强制重建
        unique_cols = list(dict.fromkeys(df.columns))
        df = pd.DataFrame(df.values[:, :len(unique_cols)], columns=unique_cols)
    
    logger.info(f"✅ 已移除重复列，当前字段数量: {len(df.columns)}")
    return df


def normalize_column_names(df: pd.DataFrame, lowercase: bool = False) -> pd.DataFrame:
    """
    统一列名格式（去除多余空格，可选统一小写）
    
    :param df: pandas.DataFrame
    :param lowercase: 是否将列名转为小写（默认False，保持原样）
    :return: 标准化后的 DataFrame
    """
    if df is None or df.empty:
        return df
    
    original = df.columns.tolist()
    if lowercase:
        df.columns = [col.strip().lower() for col in df.columns]
    else:
        df.columns = [col.strip() for col in df.columns]
    
    logger.info(f"🧩 标准化列名: {len(original)} → {len(set(df.columns))}")
    return clean_duplicate_columns(df, keep_first=False)


def safe_dataframe(df: pd.DataFrame, normalize: bool = False, lowercase: bool = False) -> pd.DataFrame:
    """
    综合清理函数：去重 + 可选标准化
    
    :param df: pandas.DataFrame
    :param normalize: 是否标准化列名（去除空格）
    :param lowercase: 是否将列名转为小写（仅在normalize=True时生效）
    :return: 清理后的 DataFrame
    """
    if df is None or df.empty:
        logger.warning("⚠️ 输入 DataFrame 为空，跳过清理。")
        return df
    
    if normalize:
        df = normalize_column_names(df, lowercase=lowercase)
    else:
        # 只做去重，保持列名原样
        df = clean_duplicate_columns(df, keep_first=False)
    
    return df


# 示例使用：
if __name__ == "__main__":
    # 模拟重复列 DataFrame
    import pandas as pd
    
    data = {
        "stock_code": [1, 2],
        "stock_name": ["A", "B"],
    }
    df = pd.DataFrame(data)
    # 手动添加重复列（通过直接修改columns）
    df.columns = ['stock_code', 'stock_name', 'price', 'volume', 'volume']  # 最后一个volume是重复的
    
    print("原始列:", df.columns.tolist())
    print("是否有重复:", df.columns.duplicated().any())

    df_clean = safe_dataframe(df, normalize=False)
    print("清理后列:", df_clean.columns.tolist())
    print("是否有重复:", df_clean.columns.duplicated().any())

