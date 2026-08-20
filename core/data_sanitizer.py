import pandas as pd

def clean_sku_series(series: pd.Series) -> pd.Series:
    """
    Normalizes article codes, removes trailing '.0' from numeric float conversions,
    and strips unwanted whitespace.
    """
    if series.empty:
        return series
    return (
        series.astype(str)
        .str.strip()
        .str.replace(r'\.0$', '', regex=True)
        .replace(['nan', 'None', '<NA>'], '')
    )

def sanitize_dataframe(df: pd.DataFrame, text_cols=None) -> pd.DataFrame:
    """
    Cleans leading/trailing whitespaces from all string/object columns across the DataFrame.
    """
    if text_cols is None:
        text_cols = df.select_dtypes(include=['object', 'string']).columns
    for col in text_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()
    return df
