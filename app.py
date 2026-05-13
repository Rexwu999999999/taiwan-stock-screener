import streamlit as st
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import re
from openai import OpenAI

# ========================================
# 頁面設定
# ========================================

st.set_page_config(
    page_title="台股波段選股系統 AI版",
    layout="wide"
)

st.title("🔥 台股波段選股系統 AI版")

# ========================================
# Secrets
# ========================================

OPENAI_KEY = st.secrets["OPENAI_API_KEY"]
TOKEN = st.secrets["FINMIND_TOKEN"]

# ========================================
# Headers
# ========================================

headers = {
    "Authorization": f"Bearer {TOKEN}"
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
# 找有效交易日
# ========================================

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
# 分析函數
# ========================================

def analyze(stock_id):

    end_date = get_valid_date(stock_id)

    if end_date is None:
        return None

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

    df = pd.DataFrame(r.json()["data"])

    if df.empty:
        return None

    df = df.sort_values("date")

    if len(df) < 60:
        return None

    # ====================================
    # 技術指標
    # ====================================

    df["MA5"] = df["close"].rolling(5).mean()

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
    # 量比
    # ====================================

    vol_ratio = (
        latest["Trading_Volume"]
        / latest["VOL_MA20"]
    )

    # ====================================
    # 本週漲跌
    # ====================================

    week_ago_close = df.iloc[-6]["close"]

    week_change = (
        (latest["close"] - week_ago_close)
        / week_ago_close
    ) * 100

    # ====================================
    # 紅K
    # ====================================

    recent_5 = df.tail(5)

    red_count = (
        recent_5["close"] > recent_5["open"]
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
        ).json()["data"]
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

        def net_buy(data, name):

            x = data[data["name"] == name]

            if x.empty:
                return 0

            return (x["buy"] - x["sell"]).sum()

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
    # 乖離率
    # ====================================

    bias_ma5 = (
        (latest["close"] - latest["MA5"])
        / latest["MA5"]
    ) * 100

    bias_ema20 = (
        (latest["close"] - latest["EMA20"])
        / latest["EMA20"]
    ) * 100

    # ====================================
    # 判斷
    # ====================================

    signal = "WAIT"

    # YES
    if (

        latest["close"] > latest["EMA20"]

        and latest["MA5"] > latest["EMA20"]

        and latest["K"] > latest["D"]

        and latest["K"] < 70

        and vol_ratio > 1.0

        and week_change < 12

        and bias_ma5 < 5

        and bias_ema20 < 10

        and foreign_week > 0

    ):

        signal = "YES"

    # HOT
    elif (

        latest["close"] > latest["EMA20"]

        and latest["K"] > latest["D"]

        and latest["K"] >= 70

        and vol_ratio > 0.8

        and foreign_month > 0

    ):

        signal = "HOT"

    # EARLY
    elif (

        latest["close"] > latest["EMA20"]

        and latest["K"] > latest["D"]

        and latest["K"] < 75

        and vol_ratio > 0.8

        and week_change < 15

        and bias_ma5 < 8

    ):

        signal = "EARLY"

    # NO
    elif (

        latest["close"] < latest["EMA20"]

        and latest["K"] < latest["D"]

        and foreign_week < 0

        and trust_week < 0

    ):

        signal = "NO"

    else:

        signal = "WAIT"

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

        "外資週": int(foreign_week),

        "投信週": int(trust_week),

        "外資月": int(foreign_month),

        "投信月": int(trust_month),

        "判斷": signal
    }

# ========================================
# 開始分析
# ========================================

if st.button("開始分析"):

    results = []

    progress = st.progress(0)

    for idx, stock_id in enumerate(watchlist):

        try:

            result = analyze(stock_id)

            if result:
                results.append(result)

        except Exception as e:
            st.error(f"{stock_id} 錯誤：{e}")

        progress.progress((idx + 1) / len(watchlist))

    df_result = pd.DataFrame(results)

    if df_result.empty:
        st.warning("沒有資料")
        st.stop()

    order = {
        "YES": 0,
        "HOT": 1,
        "EARLY": 2,
        "WAIT": 3,
        "NO": 4
    }

    df_result["排序"] = (
        df_result["判斷"]
        .map(order)
    )

    df_result = df_result.sort_values(
        ["排序", "量比", "外資週"],
        ascending=[True, False, False]
    )

    # ====================================
    # 顯示
    # ====================================

    st.subheader("🔥 YES")
    st.dataframe(
        df_result[
            df_result["判斷"] == "YES"
        ],
        use_container_width=True
    )

    st.subheader("🔥 HOT")
    st.dataframe(
        df_result[
            df_result["判斷"] == "HOT"
        ],
        use_container_width=True
    )

    st.subheader("🟢 EARLY")
    st.dataframe(
        df_result[
            df_result["判斷"] == "EARLY"
        ],
        use_container_width=True
    )

    st.subheader("⚪ WAIT")
    st.dataframe(
        df_result[
            df_result["判斷"] == "WAIT"
        ],
        use_container_width=True
    )

    st.subheader("❌ NO")
    st.dataframe(
        df_result[
            df_result["判斷"] == "NO"
        ],
        use_container_width=True
    )

    st.subheader("📊 全部")
    st.dataframe(
        df_result.drop(columns=["排序"]),
        use_container_width=True
    )

    # ====================================
    # AI 分析
    # ====================================

    st.subheader("🤖 AI 股票分析")

    selected_stock = st.selectbox(
        "選擇股票",
        df_result["股票"]
    )

    if st.button("開始 AI 分析"):

        client = OpenAI(api_key=OPENAI_KEY)

        stock_data = df_result[
            df_result["股票"] == selected_stock
        ].iloc[0]

        prompt = f'''
請分析以下台股：

股票：{stock_data["股票"]}

收盤價：{stock_data["收盤價"]}
MA5：{stock_data["MA5"]}
EMA20：{stock_data["EMA20"]}
EMA60：{stock_data["EMA60"]}

量比：{stock_data["量比"]}

K：{stock_data["K"]}
D：{stock_data["D"]}

本週漲幅：{stock_data["本週%"]}

外資週：{stock_data["外資週"]}
投信週：{stock_data["投信週"]}

判斷：{stock_data["判斷"]}

請用繁體中文分析：

1. 趨勢
2. 強弱
3. 是否適合追
4. 支撐壓力
5. 風險
'''

        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        ai_text = response.choices[0].message.content

        st.write(ai_text)
