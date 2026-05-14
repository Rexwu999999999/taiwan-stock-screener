import os
import time
import math
import requests
import pandas as pd
import yfinance as yf

from datetime import datetime, timedelta


os.makedirs("cache", exist_ok=True)

CHUNK_SIZE = 80
SLEEP_SECONDS = 1

PERIOD = "9mo"
INTERVAL = "1d"

OUTPUT_PATH = "cache/latest.csv"


# =========================
# API
# =========================

def fetch_json(url):

    try:

        r = requests.get(
            url,
            timeout=30
        )

        r.raise_for_status()

        return r.json()

    except:

        return []


# =========================
# 產業對照
# =========================

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


# =========================
# 股票清單
# =========================

def get_twse_listed_stocks():

    url = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"

    data = fetch_json(url)

    rows = []

    for item in data:

        stock_id = str(
            item.get("公司代號", "")
        ).strip()

        stock_name = str(
            item.get("公司名稱", "")
        ).strip()

        industry = normalize_industry(
            item.get("產業別", "上市")
        )

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

        stock_id = str(
            item.get("公司代號", "")
        ).strip()

        stock_name = str(
            item.get("公司名稱", "")
        ).strip()

        industry = normalize_industry(
            item.get("產業別", "上櫃")
        )

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

    rows.extend(
        get_twse_listed_stocks()
    )

    rows.extend(
        get_tpex_otc_stocks()
    )

    df = pd.DataFrame(rows)

    if df.empty:

        return pd.DataFrame()

    df = df.drop_duplicates(
        subset=["股票"]
    )

    return df.sort_values("股票")


# =========================
# 主流題材
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

        "4938": "散熱",
        "3014": "散熱",

        "3324": "CPO",
        "4908": "CPO",

        "1503": "重電",
        "1519": "重電",

        "2330": "半導體",
        "2454": "半導體",
    }

    return theme_map.get(
        stock_id,
        industry if industry else "其他"
    )


# =========================
# 法人資料
# =========================

def get_institutional_data(stock_id):

    try:

        end_date = datetime.now()

        start_date = end_date - timedelta(days=10)

        url = "https://api.finmindtrade.com/api/v4/data"

        params = {

            "dataset": "TaiwanStockInstitutionalInvestorsBuySell",

            "data_id": stock_id,

            "start_date": start_date.strftime("%Y-%m-%d"),

            "end_date": end_date.strftime("%Y-%m-%d")
        }

        r = requests.get(
            url,
            params=params,
            timeout=20
        )

        data = r.json().get("data", [])

        if len(data) == 0:

            return {

                "foreign_today": 0,
                "foreign_3d": 0,

                "trust_today": 0,
                "trust_3d": 0,
            }

        df = pd.DataFrame(data)

        result = {

            "foreign_today": 0,
            "foreign_3d": 0,

            "trust_today": 0,
            "trust_3d": 0,
        }

        # 外資
        foreign_df = df[
            df["name"] == "Foreign_Investor"
        ]

        if not foreign_df.empty:

            foreign_df["buy_sell"] = pd.to_numeric(
                foreign_df["buy_sell"],
                errors="coerce"
            )

            result["foreign_today"] = int(
                foreign_df.tail(1)["buy_sell"].sum()
            )

            result["foreign_3d"] = int(
                foreign_df.tail(3)["buy_sell"].sum()
            )

        # 投信
        trust_df = df[
            df["name"] == "Investment_Trust"
        ]

        if not trust_df.empty:

            trust_df["buy_sell"] = pd.to_numeric(
                trust_df["buy_sell"],
                errors="coerce"
            )

            result["trust_today"] = int(
                trust_df.tail(1)["buy_sell"].sum()
            )

            result["trust_3d"] = int(
                trust_df.tail(3)["buy_sell"].sum()
            )

        return result

    except:

        return {

            "foreign_today": 0,
            "foreign_3d": 0,

            "trust_today": 0,
            "trust_3d": 0,
        }


# =========================
# 指標
# =========================

def safe_round(value, digits=2):

    try:

        if pd.isna(value):
            return 0

        if math.isinf(value):
            return 0

        return round(
            float(value),
            digits
        )

    except:

        return 0


def calc_kd(df):

    low9 = df["Low"].rolling(9).min()

    high9 = df["High"].rolling(9).max()

    rsv = (
        (
            df["Close"] - low9
        ) /
        (
            high9 - low9
        )
    ) * 100

    k = (
        rsv
        .ewm(
            com=2,
            adjust=False
        )
        .mean()
    )

    d = (
        k
        .ewm(
            com=2,
            adjust=False
        )
        .mean()
    )

    return k, d


def calc_macd(df):

    ema12 = (
        df["Close"]
        .ewm(
            span=12,
            adjust=False
        )
        .mean()
    )

    ema26 = (
        df["Close"]
        .ewm(
            span=26,
            adjust=False
        )
        .mean()
    )

    macd = ema12 - ema26

    signal = (
        macd
        .ewm(
            span=9,
            adjust=False
        )
        .mean()
    )

    return macd, signal


# =========================
# 分析
# =========================

def analyze_stock(stock_row, df):

    if df.empty:
        return None

    stock_id = stock_row["股票"]

    stock_name = stock_row["名稱"]

    market = stock_row["市場"]

    industry = stock_row["族群"]

    df = df.copy()

    df = df.dropna(
        subset=["Close", "Volume"]
    )

    if len(df) < 60:
        return None

    latest = df.iloc[-1]

    close_price = safe_round(
        latest["Close"],
        2
    )

    volume = int(
        latest["Volume"]
    )

    if close_price <= 0 or volume <= 0:
        return None

    # =========================
    # 均線
    # =========================

    df["MA5"] = (
        df["Close"]
        .rolling(5)
        .mean()
    )

    df["EMA20"] = (
        df["Close"]
        .ewm(
            span=20,
            adjust=False
        )
        .mean()
    )

    ma5 = safe_round(
        df.iloc[-1]["MA5"]
    )

    ema20 = safe_round(
        df.iloc[-1]["EMA20"]
    )

    # =========================
    # KD
    # =========================

    k, d = calc_kd(df)

    k_value = safe_round(
        k.iloc[-1]
    )

    d_value = safe_round(
        d.iloc[-1]
    )

    # =========================
    # MACD
    # =========================

    macd, signal = calc_macd(df)

    macd_value = safe_round(
        macd.iloc[-1]
    )

    signal_value = safe_round(
        signal.iloc[-1]
    )

    # =========================
    # 成交值
    # =========================

    avg_volume_20 = (
        df["Volume"]
        .tail(20)
        .mean()
    )

    volume_ratio = 0

    if avg_volume_20 > 0:

        volume_ratio = safe_round(
            volume / avg_volume_20
        )

    trading_value = safe_round(
        close_price
        * volume
        / 100000000
    )

    # =========================
    # 前高
    # =========================

    high_60 = (
        df["Close"]
        .tail(60)
        .max()
    )

    low_20 = (
        df["Close"]
        .tail(20)
        .min()
    )

    resistance = safe_round(
        high_60
    )

    support = safe_round(
        low_20
    )

    distance_high = 0

    if high_60 > 0:

        distance_high = safe_round(
            (
                (
                    high_60 - close_price
                ) / high_60
            ) * 100
        )

    # =========================
    # RR
    # =========================

    reward = resistance - close_price

    risk = close_price - support

    rr = 0

    if risk > 0:

        rr = safe_round(
            reward / risk
        )

    # =========================
    # 漲幅
    # =========================

    day_change_percent = 0

    try:

        prev_close = float(
            df.iloc[-2]["Close"]
        )

        if prev_close > 0:

            day_change_percent = safe_round(
                (
                    (
                        close_price - prev_close
                    )
                    / prev_close
                ) * 100
            )

    except:
        pass

    # =========================
    # 主題
    # =========================

    theme = normalize_theme(
        stock_id,
        industry
    )

    # =========================
    # 法人
    # =========================

    chip = get_institutional_data(
        stock_id
    )

    foreign_today = chip["foreign_today"]
    foreign_3d = chip["foreign_3d"]

    trust_today = chip["trust_today"]
    trust_3d = chip["trust_3d"]

    # =========================
    # AI SCORE
    # =========================

    ai_score = 0

    # 成交值剛開始放大
    if trading_value >= 20 and volume_ratio >= 2:

        ai_score += 8

    elif trading_value >= 10 and volume_ratio >= 1.5:

        ai_score += 6

    elif trading_value >= 5 and volume_ratio >= 1.2:

        ai_score += 3

    # 量比
    if volume_ratio >= 3:

        ai_score += 6

    elif volume_ratio >= 2:

        ai_score += 4

    elif volume_ratio >= 1.5:

        ai_score += 2

    # 漲幅
    if 2 <= day_change_percent <= 7:

        ai_score += 6

    elif 0 <= day_change_percent < 2:

        ai_score += 3

    # MACD 剛翻多
    if macd_value > signal_value:

        ai_score += 5

    # KD
    if k_value > d_value and k_value < 80:

        ai_score += 4

    # EMA20
    if close_price > ema20:

        ai_score += 4

    # MA5
    if close_price > ma5:

        ai_score += 2

    # 接近突破
    if distance_high <= 3:

        ai_score += 5

    elif distance_high <= 8:

        ai_score += 3

    # RR
    if rr >= 2:

        ai_score += 3

    # 外資
    if foreign_today > 0:

        ai_score += 3

    if foreign_3d > 0:

        ai_score += 4

    # 投信
    if trust_today > 0:

        ai_score += 4

    if trust_3d > 0:

        ai_score += 5

    # 題材
    hot_themes = [

        "AI",
        "半導體",
        "散熱",
        "CPO",
        "ASIC",
        "重電",
        "電子零組件",
        "電腦及週邊",
        "通信網路",
        "生技"
    ]

    if theme in hot_themes:

        ai_score += 6

    # 過熱扣分
    if day_change_percent >= 9:

        ai_score -= 8

    if volume_ratio >= 8:

        ai_score -= 5

    # 流動性過低
    if trading_value < 2:

        ai_score -= 10

    # =========================
    # 品質
    # =========================

    quality = "普通"

    if ai_score >= 35:

        quality = "提前發動"

    elif ai_score >= 28:

        quality = "潛力強勢"

    elif ai_score >= 20:

        quality = "可觀察"

    # =========================
    # 回傳
    # =========================

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

        "外資今日": foreign_today,

        "外資3日": foreign_3d,

        "投信今日": trust_today,

        "投信3日": trust_3d,

        "AI分數": ai_score,

        "交易品質": quality,
    }


# =========================
# 批次下載
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

    except:

        return pd.DataFrame()


def extract_single_df(batch_data, ticker):

    if batch_data.empty:
        return pd.DataFrame()

    if isinstance(
        batch_data.columns,
        pd.MultiIndex
    ):

        if ticker not in batch_data.columns.get_level_values(0):

            return pd.DataFrame()

        df = batch_data[ticker].copy()

    else:

        df = batch_data.copy()

    needed = [

        "Open",
        "High",
        "Low",
        "Close",
        "Volume"
    ]

    for col in needed:

        if col not in df.columns:

            return pd.DataFrame()

    return df[needed].dropna()


# =========================
# MAIN
# =========================

def main():

    print("START")

    stock_list = get_stock_list()

    print(
        "STOCK_COUNT",
        len(stock_list)
    )

    if stock_list.empty:

        print("NO_STOCK_LIST")

        return

    results = []

    total = len(stock_list)

    for start in range(
        0,
        total,
        CHUNK_SIZE
    ):

        end = min(
            start + CHUNK_SIZE,
            total
        )

        chunk = stock_list.iloc[start:end].copy()

        tickers = chunk["yf_ticker"].tolist()

        print(
            "PROGRESS",
            start,
            "/",
            total
        )

        batch_data = download_batch(
            tickers
        )

        for _, row in chunk.iterrows():

            ticker = row["yf_ticker"]

            try:

                df_price = extract_single_df(
                    batch_data,
                    ticker
                )

                result = analyze_stock(
                    row,
                    df_price
                )

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
            "量比",
            "外資3日",
            "投信3日",
            "成交值(億)"
        ],

        ascending=False
    )

    final_df["熱門排行"] = range(
        1,
        len(final_df) + 1
    )

    final_df.to_csv(

        OUTPUT_PATH,

        index=False,

        encoding="utf-8-sig"
    )

    print("DONE")

    print(
        "RESULT_COUNT",
        len(final_df)
    )


if __name__ == "__main__":
    main()