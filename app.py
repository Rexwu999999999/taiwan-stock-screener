import streamlit as st
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import re
import plotly.graph_objects as go

# ========================================
# 頁面設定
# ========================================

st.set_page_config(
    page_title="台股波段選股儀表板",
    layout="wide"
)

st.title("🔥 台股波段選股儀表板")

# ========================================
# Cache 清除
# ========================================

if st.button("🔄 強制更新資料"):

    st.cache_data.clear()

    st.success("Cache 已清除，下次分析會重新抓資料")

# ========================================
# Secrets
# ========================================

FINMIND_TOKEN = st.secrets["FINMIND_TOKEN"]

headers = {
    "Authorization": f"Bearer {FINMIND_TOKEN}"
}

url = "https://api.finmindtrade.com/api/v4/data"

# ========================================
# 股票輸入
# ========================================

stock_text = st.text_area(
    "輸入股票代號（空白或換行分隔）",
    value="""2327 3260 2376 6873
3357 1503 8110 2308
2421 2451 4938 2449""",
    height=120
)

watchlist = re.findall(r"\d{4}", stock_text)

# ========================================
# 側邊欄篩選
# ========================================

st.sidebar.header("篩選條件")

min_score = st.sidebar.slider("最低分數", 0, 15, 0)
max_week_gain = st.sidebar.slider("本週漲幅上限 %", 0, 50, 30)
max_ma5_bias = st.sidebar.slider("MA5 乖離上限 %", 0, 30, 15)
min_vol_ratio = st.sidebar.slider("最低量比", 0.0, 5.0, 0.0, 0.1)

# ========================================
# 找最近交易日
# ========================================

@st.cache_data(ttl=3600)

def get_valid_date(stock_id):

    for i in range(10):

        d = (
            datetime.today() - timedelta(days=i)
        ).strftime("%Y-%m-%d")

        params = {
            "dataset": "TaiwanStockPrice",
            "data_id": stock_id,
            "start_date": d,
            "end_date": d
        }

        r = requests.get(url, headers=headers, params=params)

        data = r.json().get("data", [])

        if len(data) > 0:
            return d

    return None

# ========================================
# 法人淨買超
# ========================================

def net_buy(data, name):

    x = data[data["name"] == name]

    if x.empty:
        return 0

    return (x["buy"] - x["sell"]).sum()

# ========================================
# 單股分析
# ========================================

@st.cache_data(ttl=3600)

def analyze(stock_id):

    end_date = get_valid_date(stock_id)

    if end_date is None:
        return None, None

    start_date = (
        datetime.strptime(end_date, "%Y-%m-%d")
        - timedelta(days=365)
    ).strftime("%Y-%m-%d")

    params = {
        "dataset": "TaiwanStockPrice",
        "data_id": stock_id,
        "start_date": start_date,
        "end_date": end_date
    }

    r = requests.get(
        url,
        headers=headers,
        params=params
    )

    df = pd.DataFrame(r.json().get("data", []))

    if df.empty or len(df) < 60:
        return None, None

    df = df.sort_values("date")

    # ====================================
    # 技術指標
    # ====================================

    df["MA5"] = df["close"].rolling(5).mean()
    df["MA10"] = df["close"].rolling(10).mean()

    df["EMA20"] = (
        df["close"]
        .ewm(span=20)
        .mean()
    )

    df["EMA60"] = (
        df["close"]
        .ewm(span=60)
        .mean()
    )

    df["VOL_MA20"] = (
        df["Trading_Volume"]
        .rolling(20)
        .mean()
    )

    # ====================================
    # KDJ
    # ====================================

    low_n = df["min"].rolling(9).min()
    high_n = df["max"].rolling(9).max()

    df["RSV"] = (
        (df["close"] - low_n)
        / (high_n - low_n)
    ) * 100

    df["RSV"] = df["RSV"].fillna(50)

    k = 50
    d = 50

    K_list = []
    D_list = []

    for rsv in df["RSV"]:

        k = (2/3)*k + (1/3)*rsv
        d = (2/3)*d + (1/3)*k

        K_list.append(k)
        D_list.append(d)

    df["K"] = K_list
    df["D"] = D_list

    latest = df.iloc[-1]

    vol_ratio = (
        latest["Trading_Volume"]
        / latest["VOL_MA20"]
    )

    week_ago_close = df.iloc[-6]["close"]

    week_change = (
        (latest["close"] - week_ago_close)
        / week_ago_close
    ) * 100

    bias_ma5 = (
        (latest["close"] - latest["MA5"])
        / latest["MA5"]
    ) * 100

    bias_ema20 = (
        (latest["close"] - latest["EMA20"])
        / latest["EMA20"]
    ) * 100

    recent_5 = df.tail(5)

    red_count = (
        recent_5["close"] > recent_5["open"]
    ).sum()

    score = 0

    if latest["close"] > latest["EMA20"]:
        score += 2

    if latest["EMA20"] > latest["EMA60"]:
        score += 2

    if latest["K"] > latest["D"]:
        score += 1

    if vol_ratio > 1.2:
        score += 1

    if week_change > 0:
        score += 1

    if bias_ma5 > 8:
        score -= 2

    signal = "WAIT"

    if (
        latest["close"] > latest["EMA20"]
        and latest["K"] > latest["D"]
        and latest["K"] < 70
        and vol_ratio > 1
        and week_change < 12
        and bias_ma5 < 5
    ):
        signal = "YES"

    elif (
        latest["close"] > latest["EMA20"]
        and latest["K"] > latest["D"]
    ):
        signal = "EARLY"

    elif (
        latest["close"] < latest["EMA20"]
        and latest["K"] < latest["D"]
    ):
        signal = "NO"

    return {

        "股票": stock_id,
        "收盤價": round(latest["close"], 2),

        "MA5": round(latest["MA5"], 2),
        "EMA20": round(latest["EMA20"], 2),
        "EMA60": round(latest["EMA60"], 2),

        "量比": round(vol_ratio, 2),

        "K": round(latest["K"], 1),
        "D": round(latest["D"], 1),

        "本週%": round(week_change, 2),

        "MA5乖離%": round(bias_ma5, 2),
        "EMA20乖離%": round(bias_ema20, 2),

        "紅K數": int(red_count),

        "分數": int(score),

        "判斷": signal

    }, df
