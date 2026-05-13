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
# 顯示資料時間
# ========================================

today_str = datetime.today().strftime("%Y-%m-%d %H:%M")

st.caption(f"系統查詢時間：{today_str}")

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

start_btn = st.button("🚀 開始分析")

# ========================================
# 側邊欄篩選
# ========================================

st.sidebar.header("篩選條件")

min_score = st.sidebar.slider(
    "最低分數",
    0,
    15,
    0
)

max_week_gain = st.sidebar.slider(
    "本週漲幅上限 %",
    0,
    50,
    30
)

max_ma5_bias = st.sidebar.slider(
    "MA5 乖離上限 %",
    0,
    30,
    15
)

min_vol_ratio = st.sidebar.slider(
    "最低量比",
    0.0,
    5.0,
    0.0,
    0.1
)

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

        r = requests.get(
            url,
            headers=headers,
            params=params
        )

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
# 股票分析
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

    # ====================================
    # 股價資料
    # ====================================

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

    # ====================================
    # 基礎數值
    # ====================================

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

    black_count = (
        recent_5["close"] < recent_5["open"]
    ).sum()

    # ====================================
    # 法人資料
    # ====================================

    params = {
        "dataset": "TaiwanStockInstitutionalInvestorsBuySell",
        "data_id": stock_id,
        "start_date": start_date,
        "end_date": end_date
    }

    inst = pd.DataFrame(
        requests.get(
            url,
            headers=headers,
            params=params
        ).json().get("data", [])
    )

    foreign_week = 0
    trust_week = 0

    foreign_month = 0
    trust_month = 0

    if not inst.empty:

        inst = inst.sort_values("date")

        inst["date"] = pd.to_datetime(inst["date"])

        week_inst = inst[
            inst["date"]
            >= (
                pd.to_datetime(end_date)
                - pd.Timedelta(days=7)
            )
        ]

        latest_month = pd.to_datetime(end_date).month
        latest_year = pd.to_datetime(end_date).year

        month_inst = inst[
            (inst["date"].dt.month == latest_month)
            &
            (inst["date"].dt.year == latest_year)
        ]

        foreign_week = net_buy(
            week_inst,
            "Foreign_Investor"
        )

        trust_week = net_buy(
            week_inst,
            "Investment_Trust"
        )

        foreign_month = net_buy(
            month_inst,
            "Foreign_Investor"
        )

        trust_month = net_buy(
            month_inst,
            "Investment_Trust"
        )

    # ====================================
    # 分數
    # ====================================

    score = 0

    if latest["close"] > latest["EMA20"]:
        score += 2

    if latest["EMA20"] > latest["EMA60"]:
        score += 2

    if latest["close"] > latest["MA5"]:
        score += 1

    if latest["K"] > latest["D"]:
        score += 1

    if 35 <= latest["K"] <= 75:
        score += 1

    if vol_ratio >= 1.2:
        score += 1

    if foreign_week > 0:
        score += 2

    if trust_week > 0:
        score += 2

    if foreign_month > 0:
        score += 1

    if trust_month > 0:
        score += 1

    if week_change > 0:
        score += 1

    if bias_ma5 > 8:
        score -= 2

    if week_change > 20:
        score -= 2

    # ====================================
    # 回檔分數
    # ====================================

    pullback_score = 0

    if abs(bias_ema20) <= 3:
        pullback_score += 1

    if abs(bias_ma5) <= 5:
        pullback_score += 1

    if latest["K"] > latest["D"]:
        pullback_score += 1

    if latest["K"] < 75:
        pullback_score += 1

    if latest["close"] > latest["EMA20"]:
        pullback_score += 1

    # ====================================
    # FOMO風險
    # ====================================

    fomo = 0

    if week_change > 15:
        fomo += 1

    if bias_ma5 > 8:
        fomo += 1

    if latest["K"] > 85:
        fomo += 1

    if red_count >= 4:
        fomo += 1

    risk = "低"

    if fomo == 1:
        risk = "中"

    elif fomo >= 2:
        risk = "高"

    # ====================================
    # 波段階段
    # ====================================

    stage = "整理"

    if (
        latest["close"] > latest["EMA20"]
        and latest["K"] > latest["D"]
        and latest["K"] < 55
    ):
        stage = "剛轉強"

    elif (
        latest["close"] > latest["EMA20"]
        and latest["K"] >= 55
        and latest["K"] < 75
    ):
        stage = "主升段"

    elif (
        latest["K"] >= 75
        or week_change > 15
    ):
        stage = "過熱"

    elif (
        latest["close"] < latest["EMA20"]
        and latest["K"] < latest["D"]
    ):
        stage = "轉弱"

    # ====================================
    # 型態分類
    # ====================================

    setup = "整理"

    if pullback_score >= 4:
        setup = "回檔轉強"

    elif stage == "剛轉強":
        setup = "突破起漲"

    elif stage == "主升段":
        setup = "主升延續"

    elif stage == "過熱":
        setup = "末升段"

    elif stage == "轉弱":
        setup = "轉弱"

    # ====================================
    # 訊號判斷
    # ====================================

    signal = "WAIT"

    if (
        latest["close"] > latest["EMA20"]
        and latest["MA5"] > latest["EMA20"]
        and latest["K"] > latest["D"]
        and latest["K"] >= 45
        and latest["K"] <= 65
        and vol_ratio > 1
        and week_change < 8
        and bias_ma5 < 5
        and foreign_week > 0
    ):
        signal = "YES"

    elif (
        setup == "回檔轉強"
        and foreign_week > 0
        and risk != "高"
    ):
        signal = "YES"

    elif (
        latest["close"] > latest["EMA20"]
        and latest["K"] > latest["D"]
        and latest["K"] >= 70
        and week_change < 18
        and bias_ma5 < 10
    ):
        signal = "HOT"

    elif (
        latest["close"] > latest["EMA20"]
        and latest["K"] > latest["D"]
        and latest["K"] < 65
        and week_change < 8
        and bias_ma5 < 5
    ):
        signal = "EARLY"

    elif (
        latest["close"] < latest["EMA20"]
        and latest["K"] < latest["D"]
    ):
        signal = "NO"

    # ====================================
    # 建議
    # ====================================

    action = "等待"

    if signal == "YES":
        action = "最佳波段區，可觀察進場"

    elif signal == "HOT":
        action = "主流強勢但避免追高"

    elif signal == "EARLY":
        action = "剛轉強觀察"

    elif signal == "NO":
        action = "弱勢避免"

    # ====================================
    # 入場區間
    # ====================================

    entry_zone = "等待"

    if signal == "YES":

        lower = round(latest["EMA20"] * 0.99, 2)
        upper = round(latest["EMA20"] * 1.02, 2)

        entry_zone = f"{lower} ~ {upper}"

    elif signal == "EARLY":

        lower = round(latest["EMA20"] * 0.98, 2)
        upper = round(latest["EMA20"] * 1.01, 2)

        entry_zone = f"{lower} ~ {upper}"

    elif signal == "HOT":

        lower = round(latest["MA5"] * 0.97, 2)
        upper = round(latest["EMA20"] * 1.00, 2)

        entry_zone = f"等回檔 {lower} ~ {upper}"

    elif signal == "NO":

        entry_zone = "不建議進場"

    # ====================================
    # 階段燈號
    # ====================================

    stage_color = "⚪"

    if stage == "剛轉強":
        stage_color = "🟢"

    elif stage == "主升段":
        stage_color = "🟡"

    elif stage == "過熱":
        stage_color = "🔴"

    elif stage == "轉弱":
        stage_color = "⚫"

    return {

        "股票": stock_id,
        "收盤價": round(latest["close"], 2),
        "MA5": round(latest["MA5"], 2),
        "MA10": round(latest["MA10"], 2),
        "EMA20": round(latest["EMA20"], 2),
        "EMA60": round(latest["EMA60"], 2),
        "量比": round(vol_ratio, 2),
        "K": round(latest["K"], 1),
        "D": round(latest["D"], 1),
        "本週%": round(week_change, 2),
        "MA5乖離%": round(bias_ma5, 2),
        "EMA20乖離%": round(bias_ema20, 2),
        "紅K數": int(red_count),
        "黑K數": int(black_count),
        "外資週": int(foreign_week),
        "投信週": int(trust_week),
        "外資月": int(foreign_month),
        "投信月": int(trust_month),
        "分數": int(score),
        "回檔分數": int(pullback_score),
        "判斷": signal,
        "建議": action,
        "入場區間": entry_zone,
        "型態": setup,
        "波段階段": stage,
        "階段燈號": stage_color,
        "FOMO風險": int(fomo),
        "風險": risk,
        "資料日期": end_date

    }, df
