#!/usr/bin/env python3
"""
拉取A股基础资料
使用AkShare获取A股股票基本信息并保存为CSV
"""

from pathlib import Path
import pandas as pd
import sys
import os

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    import akshare as ak
except ImportError:
    print("❌ 错误: 未安装 akshare，请运行: pip install akshare")
    sys.exit(1)

OUT = Path("data/stock_basic.csv")
OUT.parent.mkdir(parents=True, exist_ok=True)


def fetch_cn_stock_basic() -> pd.DataFrame:
    """
    获取A股股票基本信息
    
    Returns:
        pd.DataFrame: 包含股票代码、名称、最新价、市值等信息
    """
    print("📥 开始拉取A股基础资料...")
    
    try:
        # 获取股票代码与名称
        print("  - 获取股票代码与名称...")
        code_name = ak.stock_info_a_code_name()
        print(f"  ✅ 获取到 {len(code_name)} 条股票代码")
        
        # 获取实时股票信息，包括最新价、市值等
        print("  - 获取实时股票信息...")
        spot = ak.stock_zh_a_spot_em()
        print(f"  ✅ 获取到 {len(spot)} 条实时信息")
        
        # 合并数据
        print("  - 合并数据...")
        df = code_name.merge(
            spot, 
            left_on="code", 
            right_on="代码", 
            how="left"
        )
        
        # 字段清洗，重命名
        keep = {
            "code": "code",
            "name": "name",
            "最新价": "price",
            "总市值": "market_cap",
            "流通市值": "float_cap",
            "市盈率": "pe",
            "市净率": "pb",
            "市销率": "ps",
            "市现率": "pcf",
            "涨跌幅": "change_pct",
            "成交量": "volume",
            "成交额": "turnover",
        }
        
        # 确保所需的列存在
        available_columns = df.columns.tolist()
        rename_dict = {}
        for old_col, new_col in keep.items():
            if old_col in available_columns:
                rename_dict[old_col] = new_col
            elif new_col in available_columns:
                # 如果已经是目标名称，跳过
                pass
        
        df = df.rename(columns=rename_dict)
        
        # 尝试获取财务指标（ROE等）
        print("  - 尝试获取财务指标（ROE等）...")
        try:
            # 使用akshare获取基本面数据
            for idx, row in df.head(100).iterrows():  # 先测试前100只股票
                code = row.get("code", "")
                if not code:
                    continue
                try:
                    # 获取股票财务指标
                    basic_info = ak.stock_individual_info_em(symbol=code)
                    if not basic_info.empty and "净资产收益率" in basic_info.values:
                        # 这里可以添加ROE等财务指标
                        pass
                except:
                    pass
        except Exception as e:
            print(f"  ⚠️ 财务指标获取部分失败（不影响主流程）: {e}")
        
        # 选择需要的列
        columns_to_keep = [col for col in keep.values() if col in df.columns]
        df = df[columns_to_keep]
        
        # 数据清洗
        df = df.dropna(subset=["code", "name"]).drop_duplicates(subset=["code"])
        
        # 数值列转换
        numeric_columns = ["price", "market_cap", "float_cap"]
        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        
        print(f"  ✅ 数据清洗完成，共 {len(df)} 条有效记录")
        return df
        
    except Exception as e:
        print(f"❌ 下载失败: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    try:
        df = fetch_cn_stock_basic()
        
        # 保存到CSV
        df.to_csv(OUT, index=False, encoding="utf-8-sig")  # 使用utf-8-sig确保Excel能正确打开
        print(f"✅ 已保存 {len(df)} 条记录到 {OUT.absolute()}")
        
        # 显示前几条数据
        print("\n📊 数据预览:")
        print(df.head(10).to_string(index=False))
        
    except KeyboardInterrupt:
        print("\n⚠️ 用户中断下载")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 执行失败: {e}")
        sys.exit(1)

