import os
import time
import math
import requests
import pandas as pd
import yfinance as yf
from datetime import datetime

os.makedirs("cache", exist_ok=True)

CHUNK_SIZE = 80
SLEEP_SECONDS = 1
PERIOD = "9mo"
INTERVAL = "1d"
OUTPUT_PATH = "cache/latest.csv"


def fetch_json(url):
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        return r.json()
    except:
        return []


INDUSTRY_MAP = {
    "01": "水泥工業",
    "02": "食品工業",
    "03": "塑膠工業",
    "04": "紡織纖維",
    "05": "電機機械",
    "06": "電器電纜",
    "07": "化學生技醫療",
    "08": "玻璃陶瓷",
    "09": "造紙工業",
    "10": "鋼鐵工業",
    "11": "橡膠工業",
    "12": "汽車工業",
    "14": "建材營造",
    "15": "航運業",
    "16": "觀光餐旅",
    "17": "金融保險",
    "18": "貿易百貨",
    "20": "其他",
    "21": "化學工業",
    "22": "生技醫療",
    "23": "油電燃氣",
    "24": "半導體",
    "25": "電腦及週邊",
    "26": "光電",
    "27": "通信網路",
    "28": "電子零組件",
    "29": "電子通路",
    "30": "資訊服務",
    "31": "其他電子",
    "32": "文化創意",
    "33": "農業科技",
    "34": "電子商務",
    "35": "綠能環保",
    "36": "數位雲端",
    "37": "運動休閒",
    "38": "居家生活",
}


def normalize_industry(raw):
    raw = str(raw).strip()

    if raw in INDUSTRY_MAP:
        return INDUSTRY_MAP[raw]

    if raw.zfill(2) in INDUSTRY_MAP:
        return INDUSTRY_MAP[raw.zfill(2)]

    if raw == "" or raw.lower() == "nan":
        return "其他"

    return raw


def get_twse_listed_stocks():
    url = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
    data = fetch_json(url)
    rows = []

    for item in data:
        stock_id = str(item.get("公司代號", "")).strip()
        stock_name = str(item.get("公司名稱", "")).strip()
        industry = normalize_industry(item.get("產業別", "上市"))

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
        industry = normalize_industry(item.get("產業別", "上櫃"))

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


def safe_round(value, digits=2):
    try:
        if pd.isna(value) or math.isinf(value):
            return 0
        return round(float(value), digits)
    except:
        return 0


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
    volume_ratio = safe_round(volume / avg_volume_20, 2) if avg_volume_20 > 0 else 0

    high_60 = df["Close"].tail(60).max()
    low_20 = df["Close"].tail(20).min()

    resistance = safe_round(high_60, 2)
    support = safe_round(low_20, 2)

    distance_high = safe_round(((high_60 - close_price) / high_60) * 100, 2) if high_60 > 0 else 0

    reward = resistance - close_price
    risk = close_price - support
    rr = safe_round(reward / risk, 2) if risk > 0 else 0

    trading_value = safe_round(close_price * volume / 100000000, 2)

    k, d = calc_kd(df)
    macd, signal = calc_macd(df)

    k_value = safe_round(k.iloc[-1], 2)
    d_value = safe_round(d.iloc[-1], 2)
    macd_value = safe_round(macd.iloc[-1], 2)
    signal_value = safe_round(signal.iloc[-1], 2)

    day_change_percent = 0

    try:
        prev_close = float(df.iloc[-2]["Close"])

        if prev_close > 0:
            day_change_percent = round(((close_price - prev_close) / prev_close) * 100, 2)

    except:
        pass

    theme = normalize_theme(stock_id, industry)

    ai_score = 0

    if trading_value >= 300:
        ai_score += 12
    elif trading_value >= 200:
        ai_score += 10
    elif trading_value >= 100:
        ai_score += 8
    elif trading_value >= 50:
        ai_score += 6
    elif trading_value >= 20:
        ai_score += 4
    elif trading_value >= 10:
        ai_score += 2

    if day_change_percent >= 8:
        ai_score += 8
    elif day_change_percent >= 6:
        ai_score += 6
    elif day_change_percent >= 4:
        ai_score += 4
    elif day_change_percent >= 2:
        ai_score += 2

    if volume_ratio >= 5:
        ai_score += 8
    elif volume_ratio >= 3:
        ai_score += 6
    elif volume_ratio >= 2:
        ai_score += 4
    elif volume_ratio >= 1.5:
        ai_score += 2

    hot_themes = [
        "AI",
        "半導體",
        "電子零組件",
        "電腦及週邊",
        "光電",
        "通信網路",
        "散熱",
        "CPO",
        "ASIC",
        "重電",
        "電機機械",
        "生技",
        "生技醫療",
        "綠能環保",
    ]

    if theme in hot_themes:
        ai_score += 5

    if close_price > ma5:
        ai_score += 1

    if close_price > ema20:
        ai_score += 1

    if k_value > d_value:
        ai_score += 1

    if macd_value > signal_value:
        ai_score += 1

    if rr >= 3:
        ai_score += 3
    elif rr >= 2:
        ai_score += 2
    elif rr >= 1:
        ai_score += 1

    if distance_high <= 1:
        ai_score -= 3
    elif distance_high <= 3:
        ai_score -= 1

    if trading_value < 3:
        ai_score -= 10

    quality = "偏弱"

    if ai_score >= 25:
        quality = "超級熱門"
    elif ai_score >= 18:
        quality = "熱門強勢"
    elif ai_score >= 12:
        quality = "可觀察"
    elif ai_score >= 6:
        quality = "普通"

    return {
        "股票": stock_id,
        "名稱": stock_name,
        "市場": market,
        "族群": theme,
        "日期": datetime.now().strftime("%Y-%m-%d"),
        "收盤價": close_price,
        "漲幅%": day_change_percent,
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

    except:
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

            except:
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
            "量比",
            "漲幅%"
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