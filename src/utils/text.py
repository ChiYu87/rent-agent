"""文本处理工具"""
import re


def truncate(text: str, max_len: int = 500) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len - 3] + "..."


def extract_numbers(text: str) -> list[float]:
    """从文本中提取数字（金额、面积等）"""
    # 匹配中文数字格式: 3000元/月, 3千, 1.5万
    pattern = r'(\d+\.?\d*)\s*(万|千|块|元|㎡|平|米)?'
    matches = re.findall(pattern, text)
    results = []
    for num, unit in matches:
        val = float(num)
        if unit == '万':
            val *= 10000
        elif unit == '千':
            val *= 1000
        results.append(val)
    return results


def extract_address(text: str) -> str:
    """粗提取地址"""
    pattern = r'([\u4e00-\u9fa5]{2,}(?:省|市|区|路|街|巷|号|弄|栋|楼|室)[\u4e00-\u9fa5\d]*)'
    matches = re.findall(pattern, text)
    return matches[0] if matches else ""


def normalize_price(price_str: str) -> float:
    """标准化价格字符串为月租金额"""
    price_str = price_str.replace(",", "").replace("，", "")
    if '万' in price_str:
        return float(re.search(r'(\d+\.?\d*)', price_str).group(1)) * 10000
    elif '千' in price_str:
        return float(re.search(r'(\d+\.?\d*)', price_str).group(1)) * 1000
    else:
        match = re.search(r'(\d+\.?\d*)', price_str)
        return float(match.group(1)) if match else 0.0


def format_money(amount: float) -> str:
    """格式化金额"""
    if amount >= 10000:
        return f"{amount / 10000:.1f}万"
    return f"{amount:.0f}元"
