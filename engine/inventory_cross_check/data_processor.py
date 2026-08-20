import pandas as pd
from core.data_sanitizer import clean_sku_series

def normalize_article(reading, master_base, master_set):
    if pd.isna(reading):
        return None
    reading_upper = str(reading).upper().strip()
    if reading_upper in master_set:
        return reading_upper
    matches = [art for art in master_base if reading_upper.startswith(str(art).upper())]
    if not matches:
        return f"REVISAR | {reading}"
    matches.sort(key=len, reverse=True)
    return matches[0]

def calculate_difference(stock: float, count: float) -> float:
    if stock < 0 and count > 0:
        return float(count)
    return float(count - stock)
