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

    r = requests.get(url, headers=headers, params=params)
    df = pd.DataFrame(r.json().get("data", []))

    if df.empty or len(df) < 60:
        return None, None

    df = df.sort_values("date")

    # ====================================
    # 均線
    # ====================================

    df["MA5"] = df["close"].rolling(5).mean()
    df["MA10"] = df["close"].rolling(10).mean()
    df["EMA20"] = df["close"].ewm(span=20).mean()
    df["EMA60"] = df["close"].ewm(span=60).mean()
    df["VOL_MA20"] = df["Trading_Volume"].rolling(20).mean()

    # ====================================
    # KDJ
    # ====================================

    low_n = df["min"].rolling(9).min()
    high_n = df["max"].rolling(9).max()

    df["RSV"] = ((df["close"] - low_n) / (high_n - low_n)) * 100
    df["RSV"] = df["RSV"].fillna(50)

    k = 50
    d = 50
    K_list = []
    D_list = []

    for rsv in df["RSV"]:

        k = (2 / 3) * k + (1 / 3) * rsv
        d = (2 / 3) * d + (1 / 3) * k

        K_list.append(k)
        D_list.append(d)

    df["K"] = K_list
    df["D"] = D_list
    df["J"] = 3 * df["K"] - 2 * df["D"]

    latest = df.iloc[-1]

    # ====================================
    # 近 5 日 K 棒
    # ====================================

    recent_5 = df.tail(5)

    red_count = (recent_5["close"] > recent_5["open"]).sum()
    black_count = (recent_5["close"] < recent_5["open"]).sum()

    # ====================================
    # 週漲跌
    # ====================================

    week_ago_close = df.iloc[-6]["close"]

    week_change = (
        (latest["close"] - week_ago_close)
        / week_ago_close
    ) * 100

    # ====================================
    # 乖離
    # ====================================

    bias_ma5 = (
        (latest["close"] - latest["MA5"])
        / latest["MA5"]
    ) * 100

    bias_ema20 = (
        (latest["close"] - latest["EMA20"])
        / latest["EMA20"]
    ) * 100

    vol_ratio = latest["Trading_Volume"] / latest["VOL_MA20"]

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
        requests.get(url, headers=headers, params=params).json().get("data", [])
    )

    foreign_3d = trust_3d = dealer_3d = 0
    foreign_week = trust_week = dealer_week = 0
    foreign_month = trust_month = dealer_month = 0

    if not inst.empty:

        inst = inst.sort_values("date")
        inst["date"] = pd.to_datetime(inst["date"])

        recent_inst = inst.tail(15)

        week_inst = inst[
            inst["date"] >= (
                pd.to_datetime(end_date) - pd.Timedelta(days=7)
            )
        ]

        latest_month = pd.to_datetime(end_date).month
        latest_year = pd.to_datetime(end_date).year

        month_inst = inst[
            (inst["date"].dt.month == latest_month)
            &
            (inst["date"].dt.year == latest_year)
        ]

        foreign_3d = net_buy(recent_inst, "Foreign_Investor")
        trust_3d = net_buy(recent_inst, "Investment_Trust")
        dealer_3d = net_buy(recent_inst, "Dealer")

        foreign_week = net_buy(week_inst, "Foreign_Investor")
        trust_week = net_buy(week_inst, "Investment_Trust")
        dealer_week = net_buy(week_inst, "Dealer")

        foreign_month = net_buy(month_inst, "Foreign_Investor")
        trust_month = net_buy(month_inst, "Investment_Trust")
        dealer_month = net_buy(month_inst, "Dealer")

    # ====================================
    # 支撐壓力
    # ====================================

    high_20 = df.tail(20)["max"].max()
    low_20 = df.tail(20)["min"].min()

    support_1 = latest["MA5"]
    support_2 = latest["EMA20"]
    support_3 = low_20

    resistance_1 = high_20

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

    if latest["K"] > 85:
        score -= 1

    # ====================================
    # 風險判斷
    # ====================================

    overheat = False

    if bias_ma5 > 8 or week_change > 20 or latest["K"] > 85:
        overheat = True

    # ====================================
    # 訊號判斷
    # ====================================

    signal = "WAIT"

    if (
        latest["close"] > latest["EMA20"]
        and latest["MA5"] > latest["EMA20"]
        and latest["K"] > latest["D"]
        and latest["K"] < 70
        and vol_ratio > 1.0
        and week_change < 12
        and bias_ma5 < 5
        and foreign_week > 0
    ):
        signal = "YES"

    elif (
        latest["close"] > latest["EMA20"]
        and latest["K"] > latest["D"]
        and latest["K"] >= 70
        and foreign_month > 0
    ):
        signal = "HOT"

    elif (
        latest["close"] > latest["EMA20"]
        and latest["K"] > latest["D"]
        and week_change < 15
        and bias_ma5 < 8
    ):
        signal = "EARLY"

    elif (
        latest["close"] < latest["EMA20"]
        and latest["K"] < latest["D"]
        and foreign_week < 0
        and trust_week < 0
    ):
        signal = "NO"

    # ====================================
    # 建議動作
    # ====================================

    if signal == "YES":
        action = "可觀察小倉，仍需看隔日續強"

    elif signal == "HOT":
        action = "強勢但可能偏熱，不追高，等回 MA5"

    elif signal == "EARLY":
        action = "剛轉強觀察，等放量或回測支撐"

    elif signal == "NO":
        action = "弱勢，不建議進場"

    else:
        action = "等待更明確訊號"

    return {
        "股票": stock_id,
        "日期": end_date,

        "收盤價": round(latest["close"], 2),
        "開盤": round(latest["open"], 2),
        "最高": round(latest["max"], 2),
        "最低": round(latest["min"], 2),

        "MA5": round(latest["MA5"], 2),
        "MA10": round(latest["MA10"], 2),
        "EMA20": round(latest["EMA20"], 2),
        "EMA60": round(latest["EMA60"], 2),

        "量比": round(vol_ratio, 2),
        "成交量": int(latest["Trading_Volume"]),
        "20日均量": int(latest["VOL_MA20"]),

        "K": round(latest["K"], 1),
        "D": round(latest["D"], 1),
        "J": round(latest["J"], 1),

        "本週%": round(week_change, 2),
        "MA5乖離%": round(bias_ma5, 2),
        "EMA20乖離%": round(bias_ema20, 2),

        "紅K數": int(red_count),
        "黑K數": int(black_count),

        "外資3日": int(foreign_3d),
        "投信3日": int(trust_3d),
        "自營3日": int(dealer_3d),

        "外資週": int(foreign_week),
        "投信週": int(trust_week),
        "自營週": int(dealer_week),

        "外資月": int(foreign_month),
        "投信月": int(trust_month),
        "自營月": int(dealer_month),

        "20日高": round(high_20, 2),
        "20日低": round(low_20, 2),

        "支撐1_MA5": round(support_1, 2),
        "支撐2_EMA20": round(support_2, 2),
        "支撐3_20日低": round(support_3, 2),
        "壓力_20日高": round(resistance_1, 2),

        "過熱": "YES" if overheat else "NO",
        "分數": int(score),
        "判斷": signal,
        "建議": action
    }, df

# ========================================
# K 線圖
# ========================================

def plot_kline(df, stock_id):

    fig = go.Figure()

    fig.add_trace(
        go.Candlestick(
            x=df["date"],
            open=df["open"],
            high=df["max"],
            low=df["min"],
            close=df["close"],
            name="K線"
        )
    )

    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["MA5"],
            mode="lines",
            name="MA5"
        )
    )

    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["EMA20"],
            mode="lines",
            name="EMA20"
        )
    )

    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["EMA60"],
            mode="lines",
            name="EMA60"
        )
    )

    fig.update_layout(
        title=f"{stock_id} K線圖",
        xaxis_rangeslider_visible=False,
        height=600
    )

    return fig

# ========================================
# 開始分析
# ========================================

if st.button("開始分析"):

    results = []
    chart_data = {}

    progress = st.progress(0)

    for idx, stock_id in enumerate(watchlist):

        try:

            result, df = analyze(stock_id)

            if result:
                results.append(result)
                chart_data[stock_id] = df

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

    df_result["排序"] = df_result["判斷"].map(order)

    df_result = df_result.sort_values(
        ["排序", "分數", "量比", "外資週"],
        ascending=[True, False, False, False]
    )

    st.session_state["df_result"] = df_result
    st.session_state["chart_data"] = chart_data

# ========================================
# 顯示資料
# ========================================

if "df_result" in st.session_state:

    df_result = st.session_state["df_result"]
    chart_data = st.session_state["chart_data"]

    # ====================================
    # 篩選後資料
    # ====================================

    filtered = df_result[
        (df_result["分數"] >= min_score)
        &
        (df_result["本週%"] <= max_week_gain)
        &
        (df_result["MA5乖離%"] <= max_ma5_bias)
        &
        (df_result["量比"] >= min_vol_ratio)
    ]

    # ====================================
    # 總覽
    # ====================================

    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric("股票數", len(df_result))
    c2.metric("YES", len(df_result[df_result["判斷"] == "YES"]))
    c3.metric("HOT", len(df_result[df_result["判斷"] == "HOT"]))
    c4.metric("EARLY", len(df_result[df_result["判斷"] == "EARLY"]))
    c5.metric("NO", len(df_result[df_result["判斷"] == "NO"]))

    st.divider()

    # ====================================
    # 分類顯示
    # ====================================

    st.subheader("🔥 YES｜低風險剛轉強")
    st.dataframe(
        df_result[df_result["判斷"] == "YES"].drop(columns=["排序"]),
        use_container_width=True
    )

    st.subheader("🔥 HOT｜主流強勢但注意追高")
    st.dataframe(
        df_result[df_result["判斷"] == "HOT"].drop(columns=["排序"]),
        use_container_width=True
    )

    st.subheader("🟢 EARLY｜提前觀察")
    st.dataframe(
        df_result[df_result["判斷"] == "EARLY"].drop(columns=["排序"]),
        use_container_width=True
    )

    st.subheader("⚪ WAIT｜等待訊號")
    st.dataframe(
        df_result[df_result["判斷"] == "WAIT"].drop(columns=["排序"]),
        use_container_width=True
    )

    st.subheader("❌ NO｜弱勢排除")
    st.dataframe(
        df_result[df_result["判斷"] == "NO"].drop(columns=["排序"]),
        use_container_width=True
    )

    st.subheader("📊 篩選後全部")
    st.dataframe(
        filtered.drop(columns=["排序"]),
        use_container_width=True
    )

    # ====================================
    # 單股圖表
    # ====================================

    st.divider()

    st.subheader("📈 單股 K 線圖")

    selected_stock = st.selectbox(
        "選擇股票查看 K 線",
        df_result["股票"].tolist()
    )

    if selected_stock in chart_data:

        fig = plot_kline(chart_data[selected_stock], selected_stock)

        st.plotly_chart(fig, use_container_width=True)

        stock_row = df_result[
            df_result["股票"] == selected_stock
        ].iloc[0]

        st.subheader("📌 單股重點")

        st.write(
            f"""
股票：{stock_row["股票"]}

判斷：{stock_row["判斷"]}

分數：{stock_row["分數"]}

建議：{stock_row["建議"]}

支撐：
- MA5：{stock_row["支撐1_MA5"]}
- EMA20：{stock_row["支撐2_EMA20"]}
- 20日低：{stock_row["支撐3_20日低"]}

壓力：
- 20日高：{stock_row["壓力_20日高"]}

追高風險：
- 過熱：{stock_row["過熱"]}
- MA5乖離：{stock_row["MA5乖離%"]}%
- 本週漲幅：{stock_row["本週%"]}%
"""
        )
