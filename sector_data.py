import akshare as ak
import pandas as pd
from typing import List, Dict, Optional

def get_em_sector_constituents(sector_name: str) -> List[str]:
    """
    获取东方财富行业板块成分股代码列表
    
    Args:
        sector_name: 板块名称（如"航天航空"）
    
    Returns:
        List[str]: 股票代码列表
    """
    try:
        df = ak.stock_board_industry_cons_em(symbol=sector_name)
        if not df.empty and '代码' in df.columns:
            return df['代码'].tolist()
        return []
    except Exception as e:
        print(f"获取东方财富板块成分股失败: {e}")
        return []

def get_ths_sector_constituents(sector_code: str) -> List[str]:
    """
    获取同花顺概念板块成分股代码列表
    
    Args:
        sector_code: 板块代码（如"BK0480"）
    
    Returns:
        List[str]: 股票代码列表
    """
    try:
        # 尝试多种同花顺接口
        try:
            df = ak.stock_board_concept_cons_ths(symbol=sector_code)
            if not df.empty and '代码' in df.columns:
                return df['代码'].tolist()
        except:
            pass
            
        # 备用方案：通过板块名称获取
        try:
            board_list = ak.stock_board_concept_name_ths()
            sector_row = board_list[board_list['代码'] == sector_code]
            if not sector_row.empty:
                sector_name = sector_row.iloc[0]['名称']
                df = ak.stock_board_concept_cons_ths(symbol=sector_name)
                if not df.empty and '代码' in df.columns:
                    return df['代码'].tolist()
        except:
            pass
            
        return []
    except Exception as e:
        print(f"获取同花顺板块成分股失败: {e}")
        return []

def get_all_em_sectors() -> pd.DataFrame:
    """
    获取东方财富所有行业板块列表
    
    Returns:
        DataFrame: 包含板块名称、代码等信息
    """
    try:
        return ak.stock_board_industry_name_em()
    except Exception as e:
        print(f"获取东方财富板块列表失败: {e}")
        return pd.DataFrame()

def get_all_ths_sectors() -> pd.DataFrame:
    """
    获取同花顺所有概念板块列表
    
    Returns:
        DataFrame: 包含板块名称、代码等信息
    """
    try:
        return ak.stock_board_concept_name_ths()
    except Exception as e:
        print(f"获取同花顺板块列表失败: {e}")
        return pd.DataFrame()

# 示例使用
if __name__ == "__main__":
    # 获取航天航空板块成分股（东方财富）
    em_stocks = get_em_sector_constituents("航天航空")
    print(f"东方财富航天航空成分股: {em_stocks[:5]}...")
    
    # 获取BK0480板块成分股（同花顺）
    ths_stocks = get_ths_sector_constituents("886078")
    print(f"同花顺BK0480成分股: {ths_stocks[:5]}...")