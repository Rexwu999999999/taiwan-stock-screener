import os
import time
import math
import requests
import pandas as pd
import yfinance as yf

from datetime import datetime


os.makedirs("cache", exist_ok=True)


# =========================
# 基本設定
# =========================

CHUNK_SIZE = 80
SLEEP_SECONDS = 1
PERIOD = "9mo"
INTERVAL = "1d"

OUTPUT_PATH = "cache/latest.csv"


# =========================
# 股票清單：TWSE + TPEx
# =========================

def fetch_json(url):
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception:
        return []


def get_twse_listed_stocks():
    url = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
    data = fetch_json(url)

    rows = []

    for item in data:
        stock_id = str(item.get("公司代號", "")).strip()
        stock_name = str(item.get("公司名稱", "")).strip()
        industry = str(item.get("產業別", "上市")).strip()

        if stock_id.isdigit() and len(stock_id) == 4:
            rows.append({
                "股票": stock_id,
                "名稱": stock_name,
                "族群": industry,
                "市場": "上市",
                "yf_ticker": f"{stock_id}.TW"
            })

    return rows


def get_tpex_otc_stocks():
    url = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O"
    data = fetch_json(url)

    rows = []

    for item in data:
        stock_id = str(item.get("公司代號", "")).strip()
        stock_name = str(item.get("公司名稱", "")).strip()
        industry = str(item.get("產業別", "上櫃")).strip()

        if stock_id.isdigit() and len(stock_id) == 4:
            rows.append({
                "股票": stock_id,
                "名稱": stock_name,
                "族群": industry,
                "市場": "上櫃",
                "yf_ticker": f"{stock_id}.TWO"
            })

    return rows


def get_stock_list():
    rows = []
    rows.extend(get_twse_listed_stocks())
    rows.extend(get_tpex_otc_stocks())

    df = pd.DataFrame(rows)

    if df.empty:
        return pd.DataFrame(columns=["股票", "名稱", "族群", "市場", "yf_ticker"])

    df = df.drop_duplicates(subset=["股票"])
    df = df.sort_values("股票")

    return df


# =========================
# 主流族群修正
# =========================

def normalize_theme(stock_id, industry):
    theme_map = {
        "2308": "AI",
        "2376": "AI",
        "2327": "AI",
        "2382": "AI",
        "3017": "AI",
        "3231": "AI",
        "6669": "AI",

        "1503": "重電",
        "1504": "重電",
        "1519": "重電",

        "4938": "散熱",
        "3014": "散熱",

        "8110": "生技",

        "2330": "半導體",
        "2454": "半導體",
        "2303": "半導體",

        "3324": "CPO",
        "4908": "CPO",
    }

    return theme_map.get(stock_id, industry if industry else "其他")


# =========================
# 指標計算
# =========================

def calc_kd(df):
    low9 = df["Low"].rolling(9).min()
    high9 = df["High"].rolling(9).max()

    rsv = ((df["Close"] - low9) / (high9 - low9)) * 100

    k = rsv.ewm(com=2, adjust=False).mean()
    d = k.ewm(com=2, adjust=False).mean()

    return k, d


def calc_macd(df):
    ema12 = df["Close"].ewm(span=12, adjust=False).mean()
    ema26 = df["Close"].ewm(span=26, adjust=False).mean()

    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()

    return macd, signal


def safe_round(value, digits=2):
    try:
        if pd.isna(value) or math.isinf(value):
            return 0
        return round(float(value), digits)
    except Exception:
        return 0


# =========================
# 單股分析
# =========================

def analyze_stock(stock_row, df):
    stock_id = stock_row["股票"]
    stock_name = stock_row["名稱"]
    market = stock_row["市場"]
    industry = stock_row["族群"]

    if df.empty:
        return None

    df = df.copy()
    df = df.dropna(subset=["Close", "Volume"])

    if len(df) < 60:
        return None

    latest = df.iloc[-1]

    close_price = safe_round(latest["Close"], 2)
    volume = int(latest["Volume"])

    if close_price <= 0 or volume <= 0:
        return None

    df["MA5"] = df["Close"].rolling(5).mean()
    df["EMA20"] = df["Close"].ewm(span=20, adjust=False).mean()

    ma5 = safe_round(df.iloc[-1]["MA5"], 2)
    ema20 = safe_round(df.iloc[-1]["EMA20"], 2)

    avg_volume_20 = df["Volume"].tail(20).mean()

    volume_ratio = 0

    if avg_volume_20 > 0:
        volume_ratio = safe_round(volume / avg_volume_20, 2)

    high_60 = df["Close"].tail(60).max()
    low_20 = df["Close"].tail(20).min()

    resistance = safe_round(high_60, 2)
    support = safe_round(low_20, 2)

    distance_high = 0

    if high_60 > 0:
        distance_high = safe_round(((high_60 - close_price) / high_60) * 100, 2)

    reward = resistance - close_price
    risk = close_price - support

    rr = 0

    if risk > 0:
        rr = safe_round(reward / risk, 2)

    trading_value = safe_round(close_price * volume / 100000000, 2)

    k, d = calc_kd(df)
    macd, signal = calc_macd(df)

    k_value = safe_round(k.iloc[-1], 2)
    d_value = safe_round(d.iloc[-1], 2)
    macd_value = safe_round(macd.iloc[-1], 2)
    signal_value = safe_round(signal.iloc[-1], 2)

    ai_score = 0

    if close_price > ma5:
        ai_score += 2

    if close_price > ema20:
        ai_score += 2

    if volume_ratio > 1.5:
        ai_score += 2

    if macd_value > signal_value:
        ai_score += 2

    if k_value > d_value:
        ai_score += 1

    if rr >= 2:
        ai_score += 2

    elif rr < 0.5:
        ai_score -= 1

    if distance_high < 2:
        ai_score -= 1

    if trading_value >= 30:
        ai_score += 2

    elif trading_value >= 10:
        ai_score += 1

    quality = "偏弱"

    if ai_score >= 10:
        quality = "熱門強勢"

    elif ai_score >= 7:
        quality = "可觀察"

    elif ai_score >= 4:
        quality = "普通"

    theme = normalize_theme(stock_id, industry)

    return {
        "股票": stock_id,
        "名稱": stock_name,
        "市場": market,
        "族群": theme,
        "日期": datetime.now().strftime("%Y-%m-%d"),
        "收盤價": close_price,
        "MA5": ma5,
        "EMA20": ema20,
        "KD-K": k_value,
        "KD-D": d_value,
        "MACD": macd_value,
        "SIGNAL": signal_value,
        "成交量": volume,
        "量比": volume_ratio,
        "成交值(億)": trading_value,
        "60日高點": resistance,
        "20日支撐": support,
        "距離前高%": distance_high,
        "RR": rr,
        "AI分數": ai_score,
        "交易品質": quality,
    }


# =========================
# 批次抓 yfinance
# =========================

def download_batch(tickers):
    try:
        data = yf.download(
            tickers=tickers,
            period=PERIOD,
            interval=INTERVAL,
            group_by="ticker",
            auto_adjust=False,
            threads=True,
            progress=False
        )

        return data

    except Exception:
        return pd.DataFrame()


def extract_single_df(batch_data, ticker):
    if batch_data.empty:
        return pd.DataFrame()

    if isinstance(batch_data.columns, pd.MultiIndex):
        if ticker not in batch_data.columns.get_level_values(0):
            return pd.DataFrame()

        df = batch_data[ticker].copy()

    else:
        df = batch_data.copy()

    needed = ["Open", "High", "Low", "Close", "Volume"]

    for col in needed:
        if col not in df.columns:
            return pd.DataFrame()

    return df[needed].dropna()


# =========================
# 主程式
# =========================

def main():
    print("START")

    stock_list = get_stock_list()

    print("STOCK_COUNT", len(stock_list))

    if stock_list.empty:
        print("NO_STOCK_LIST")
        return

    results = []

    total = len(stock_list)

    for start in range(0, total, CHUNK_SIZE):
        end = min(start + CHUNK_SIZE, total)

        chunk = stock_list.iloc[start:end].copy()
        tickers = chunk["yf_ticker"].tolist()

        print("PROGRESS", start, "/", total)

        batch_data = download_batch(tickers)

        for _, row in chunk.iterrows():
            ticker = row["yf_ticker"]

            try:
                df_price = extract_single_df(batch_data, ticker)

                result = analyze_stock(row, df_price)

                if result is not None:
                    results.append(result)

            except Exception:
                pass

        time.sleep(SLEEP_SECONDS)

    final_df = pd.DataFrame(results)

    if final_df.empty:
        print("NO_RESULT")
        return

    final_df = final_df.sort_values(
        by=[
            "AI分數",
            "成交值(億)",
            "量比"
        ],
        ascending=False
    )

    final_df["熱門排行"] = range(1, len(final_df) + 1)

    final_df.to_csv(
        OUTPUT_PATH,
        index=False,
        encoding="utf-8-sig"
    )

    print("DONE")
    print("RESULT_COUNT", len(final_df))


if __name__ == "__main__":
    main()
