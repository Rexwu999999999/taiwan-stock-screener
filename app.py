import streamlit as st
import requests
import pandas as pd
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

today_str = datetime.today().strftime("%Y-%m-%d %H:%M")
st.caption(f"系統查詢時間：{today_str}")

# ========================================
# Session 初始化
# ========================================

if "df_result" not in st.session_state:
    st.session_state["df_result"] = pd.DataFrame()

if "chart_data" not in st.session_state:
    st.session_state["chart_data"] = {}

# ========================================
# Cache 清除
# ========================================

if st.button("🔄 強制更新資料"):
    st.cache_data.clear()
    st.session_state["df_result"] = pd.DataFrame()
    st.session_state["chart_data"] = {}
    st.success("Cache 已清除，請重新按開始分析")

# ========================================
# API
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
# Sidebar
# ========================================

st.sidebar.header("篩選條件")

min_score = st.sidebar.slider("最低分數", 0, 15, 0)
max_week_gain = st.sidebar.slider("本週漲幅上限 %", 0, 50, 30)
max_ma5_bias = st.sidebar.slider("MA5 乖離上限 %", 0, 30, 15)
min_vol_ratio = st.sidebar.slider("最低量比", 0.0, 5.0, 0.0, 0.1)

# ========================================
# 最近交易日
# ========================================

@st.cache_data(ttl=3600)
def get_valid_date(stock_id):

    for i in range(10):

        d = (
            datetime.today()
            - timedelta(days=i)
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
# 法人趨勢
# ========================================

def investor_trend(inst, investor_name):

    trend = "中立"

    if inst.empty:
        return trend

    only = inst[
        inst["name"] == investor_name
    ].copy()

    if only.empty:
        return trend

    only["net"] = (
        only["buy"]
        - only["sell"]
    )

    recent = (
        only["net"]
        .tail(5)
        .tolist()
    )

    positive_days = sum(x > 0 for x in recent)
    negative_days = sum(x < 0 for x in recent)

    if positive_days >= 4:
        trend = "連買"

    elif negative_days >= 4:
        trend = "連賣"

    elif positive_days > negative_days:
        trend = "偏多"

    elif negative_days > positive_days:
        trend = "偏空"

    return trend

# ========================================
# 分析
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
    # 股價
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

    df = pd.DataFrame(
        r.json().get("data", [])
    )

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

        k = (2 / 3) * k + (1 / 3) * rsv
        d = (2 / 3) * d + (1 / 3) * k

        K_list.append(k)
        D_list.append(d)

    df["K"] = K_list
    df["D"] = D_list

    latest = df.iloc[-1]

    # ====================================
    # 數值
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
        recent_5["close"]
        > recent_5["open"]
    ).sum()

    black_count = (
        recent_5["close"]
        < recent_5["open"]
    ).sum()

    # ====================================
    # 法人
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

    foreign_trend = "中立"
    trust_trend = "中立"

    if not inst.empty:

        inst = inst.sort_values("date")

        inst["date"] = pd.to_datetime(
            inst["date"]
        )

        week_inst = inst[
            inst["date"]
            >= (
                pd.to_datetime(end_date)
                - pd.Timedelta(days=7)
            )
        ]

        latest_month = pd.to_datetime(
            end_date
        ).month

        latest_year = pd.to_datetime(
            end_date
        ).year

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

        foreign_trend = investor_trend(
            inst,
            "Foreign_Investor"
        )

        trust_trend = investor_trend(
            inst,
            "Investment_Trust"
        )

    # ====================================
    # 主力方向
    # ====================================

    main_force = "混合"

    if (
        foreign_trend in ["連買", "偏多"]
        and trust_trend in ["連買", "偏多"]
    ):
        main_force = "雙法人偏多"

    elif foreign_trend in ["連買", "偏多"]:
        main_force = "外資主導"

    elif trust_trend in ["連買", "偏多"]:
        main_force = "投信主導"

    elif (
        foreign_trend in ["連賣", "偏空"]
        and trust_trend in ["連賣", "偏空"]
    ):
        main_force = "雙法人偏空"

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

    if foreign_trend == "連買":
        score += 3

    elif foreign_trend == "偏多":
        score += 1

    elif foreign_trend == "連賣":
        score -= 3

    elif foreign_trend == "偏空":
        score -= 1

    if trust_trend == "連買":
        score += 3

    elif trust_trend == "偏多":
        score += 1

    elif trust_trend == "連賣":
        score -= 3

    elif trust_trend == "偏空":
        score -= 1

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
    # 追高風險
    # ====================================

    chase_risk = 0

    if week_change > 10:
        chase_risk += 2

    if latest["K"] > 80:
        chase_risk += 2

    if bias_ma5 > 8:
        chase_risk += 2

    if vol_ratio > 3:
        chase_risk += 2

    # ====================================
    # FOMO
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
    # 主升段 / 健康回檔 / 假強勢
    # ====================================

    main_uptrend = False

    if (
        latest["close"] > latest["EMA20"]
        and latest["EMA20"] > latest["EMA60"]
        and latest["K"] > latest["D"]
    ):
        main_uptrend = True

    healthy_pullback = False

    if (
        bias_ema20 > -3
        and latest["close"] > latest["EMA20"]
        and latest["K"] > 35
    ):
        healthy_pullback = True

    fake_strength = False

    if (
        week_change > 15
        and latest["K"] > 85
        and foreign_trend in ["連買", "偏多"]
    ):
        fake_strength = True

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
    # 型態
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
    # 訊號
    # ====================================

    signal = "WAIT"

    if (
        latest["close"] > latest["EMA20"]
        and latest["MA5"] > latest["EMA20"]
        and latest["K"] > latest["D"]
        and latest["K"] >= 45
        and latest["K"] <= 65
        and vol_ratio > 0.6
        and week_change < 8
        and bias_ma5 < 5
        and foreign_trend in ["連買", "偏多"]
        and trust_trend != "連賣"
    ):
        signal = "YES"

    elif (
        setup == "回檔轉強"
        and foreign_trend in ["連買", "偏多", "中立"]
        and trust_trend != "連賣"
        and risk != "高"
    ):
        signal = "YES"

    elif (
        latest["close"] > latest["EMA20"]
        and latest["K"] > latest["D"]
        and latest["K"] >= 80
        and week_change < 18
        and bias_ma5 < 10
        and foreign_trend != "連賣"
        and trust_trend != "連賣"
    ):
        signal = "HOT"

    elif (
        latest["close"] > latest["EMA20"]
        and latest["K"] > latest["D"]
        and latest["K"] < 65
        and week_change < 8
    ):
        signal = "EARLY"

    elif (
        latest["close"] < latest["EMA20"]
        and latest["K"] < latest["D"]
    ):
        signal = "NO"

    # ====================================
    # 波段燈號
    # ====================================

    signal_light = "⚪"

    if signal == "YES":
        signal_light = "🟢"

    elif signal == "HOT":
        signal_light = "🔥"

    elif signal == "EARLY":
        signal_light = "🟡"

    elif signal == "NO":
        signal_light = "🔴"

    # ====================================
    # 強度燈號
    # ====================================

    strength_light = "⚪"

    if score >= 10:
        strength_light = "🔥"

    elif score >= 7:
        strength_light = "🟢"

    elif score >= 4:
        strength_light = "🟡"

    else:
        strength_light = "🔴"

    # ====================================
    # 建議 / 操作策略
    # ====================================

    action = "等待"
    strategy_text = "等待更明確訊號"

    if signal == "YES":

        action = "最佳波段區"
        strategy_text = "可等待 EMA20 附近止穩分批"

    elif signal == "HOT":

        action = "主流強勢避免追高"
        strategy_text = "主流股但避免追高，等回檔再看"

    elif signal == "EARLY":

        action = "剛轉強觀察"
        strategy_text = "剛轉強可提前觀察，等量能確認"

    elif signal == "NO":

        action = "弱勢避免"
        strategy_text = "弱勢股避免進場"

    if fake_strength:
        action = "高檔過熱避免追價"
        strategy_text = "疑似假強勢或高檔過熱，不追價"

    # ====================================
    # 入場區
    # ====================================

    entry_zone = "等待"

    if signal == "YES":

        lower = round(
            latest["EMA20"] * 0.99,
            2
        )

        upper = round(
            latest["EMA20"] * 1.02,
            2
        )

        entry_zone = f"{lower} ~ {upper}"

    elif signal == "EARLY":

        lower = round(
            latest["EMA20"] * 0.98,
            2
        )

        upper = round(
            latest["EMA20"] * 1.01,
            2
        )

        entry_zone = f"{lower} ~ {upper}"

    elif signal == "HOT":

        lower = round(
            latest["MA5"] * 0.97,
            2
        )

        upper = round(
            latest["EMA20"],
            2
        )

        entry_zone = f"等回檔 {lower} ~ {upper}"

    elif signal == "NO":

        entry_zone = "不建議"

    # ====================================
    # 主力成本區
    # ====================================

    cost_zone_low = round(
        latest["EMA20"] * 0.98,
        2
    )

    cost_zone_high = round(
        latest["EMA20"] * 1.02,
        2
    )

    cost_zone = f"{cost_zone_low} ~ {cost_zone_high}"

    # ====================================
    # RR
    # ====================================

    stop_loss = round(
        recent_5["min"].min(),
        2
    )

    recent_high = (
        df.tail(60)["max"]
        .max()
    )

    target_price = round(
        recent_high,
        2
    )

    risk_amt = (
        latest["close"]
        - stop_loss
    )

    reward_amt = (
        target_price
        - latest["close"]
    )

    rr = 0

    if risk_amt > 0:
        rr = round(
            reward_amt / risk_amt,
            2
        )

    rr_level = "差"

    if rr >= 3:
        rr_level = "極佳"

    elif rr >= 2:
        rr_level = "優"

    elif rr >= 1:
        rr_level = "普通"

    # ====================================
    # 熱門分數
    # ====================================

    hot_score = 0

    hot_score += min(
        max(week_change, 0),
        20
    )

    hot_score += min(
        vol_ratio * 3,
        10
    )

    hot_score += min(
        latest["K"] / 10,
        10
    )

    if foreign_trend == "連買":
        hot_score += 10

    elif foreign_trend == "偏多":
        hot_score += 4

    if trust_trend == "連買":
        hot_score += 8

    elif trust_trend == "偏多":
        hot_score += 4

    # ====================================
    # 視覺化
    # ====================================

    score_clamped = max(
        0,
        min(score, 10)
    )

    score_bar = (
        "🟩" * score_clamped
    ) + (
        "⬛" * (10 - score_clamped)
    )

    heat = 0

    heat += min(
        max(week_change, 0),
        10
    )

    heat += min(
        max(bias_ma5, 0),
        10
    )

    heat_score = int(heat)

    heat_bar = (
        "🔥"
        * min(heat_score // 3, 5)
    )

    risk_icon = "🟢"

    if risk == "中":
        risk_icon = "🟡"

    elif risk == "高":
        risk_icon = "🔴"

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
        "外資趨勢": foreign_trend,
        "投信趨勢": trust_trend,
        "主力方向": main_force,
        "分數": int(score),
        "分數條": f"{score_bar} {score}/10",
        "強度燈號": strength_light,
        "熱門分數": round(hot_score, 1),
        "回檔分數": int(pullback_score),
        "波段燈號": signal_light,
        "判斷": signal,
        "建議": action,
        "操作策略": strategy_text,
        "入場區間": entry_zone,
        "主力成本區": cost_zone,
        "健康回檔": "是" if healthy_pullback else "否",
        "主升": "是" if main_uptrend else "否",
        "假強勢": "是" if fake_strength else "否",
        "追高風險": int(chase_risk),
        "停損價": stop_loss,
        "目標價": target_price,
        "RR": rr,
        "RR評級": rr_level,
        "型態": setup,
        "波段階段": stage,
        "階段燈號": stage_color,
        "熱度": heat_bar,
        "FOMO風險": int(fomo),
        "風險視覺": risk_icon,
        "風險": risk,
        "資料日期": end_date

    }, df

# ========================================
# K線圖
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
        height=650,
        template="plotly_dark"
    )

    return fig

# ========================================
# 開始分析
# ========================================

if start_btn:

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

        progress.progress(
            (idx + 1)
            / len(watchlist)
        )

    df_result = pd.DataFrame(results)

    if not df_result.empty:

        latest_trade_date = (
            df_result["資料日期"]
            .max()
        )

        st.success(
            f"最新交易日：{latest_trade_date}"
        )

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

        # ====================================
        # 排除原因
        # ====================================

        df_result["排除原因"] = ""

        for idx, row in df_result.iterrows():

            reasons = []

            if row["分數"] < min_score:
                reasons.append("分數不足")

            if row["本週%"] > max_week_gain:
                reasons.append("本週漲幅過高")

            if row["MA5乖離%"] > max_ma5_bias:
                reasons.append("MA5乖離過高")

            if row["量比"] < min_vol_ratio:
                reasons.append("量比不足")

            if len(reasons) == 0:

                df_result.at[
                    idx,
                    "排除原因"
                ] = "通過"

            else:

                df_result.at[
                    idx,
                    "排除原因"
                ] = "、".join(reasons)

        df_result = df_result.sort_values(
            ["排序", "分數", "回檔分數", "熱門分數"],
            ascending=[
                True,
                False,
                False,
                False
            ]
        )

        st.session_state[
            "df_result"
        ] = df_result

        st.session_state[
            "chart_data"
        ] = chart_data

# ========================================
# 顯示
# ========================================

df_result = st.session_state["df_result"]
chart_data = st.session_state["chart_data"]

if not df_result.empty:

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
    # 統計卡片
    # ====================================

    c1, c2, c3, c4, c5, c6 = st.columns(6)

    c1.metric("股票數", len(df_result))
    c2.metric("YES", len(df_result[df_result["判斷"] == "YES"]))
    c3.metric("HOT", len(df_result[df_result["判斷"] == "HOT"]))
    c4.metric("EARLY", len(df_result[df_result["判斷"] == "EARLY"]))
    c5.metric("WAIT", len(df_result[df_result["判斷"] == "WAIT"]))
    c6.metric("NO", len(df_result[df_result["判斷"] == "NO"]))

    # ====================================
    # 主表
    # ====================================

    st.subheader("📊 波段分析結果")

    st.dataframe(
        filtered.drop(columns=["排序"]),
        use_container_width=True,
        height=700
    )

    # ====================================
    # 被排除
    # ====================================

    if "排除原因" in df_result.columns:

        excluded = df_result[
            df_result["排除原因"] != "通過"
        ]

        if not excluded.empty:

            st.divider()

            st.subheader("🚫 被篩選排除")

            st.dataframe(
                excluded[
                    [
                        "股票",
                        "分數",
                        "本週%",
                        "MA5乖離%",
                        "量比",
                        "排除原因"
                    ]
                ],
                use_container_width=True
            )

    # ====================================
    # TOP5
    # ====================================

    st.divider()

    st.subheader("🏆 TOP5 真強勢股")

    top5 = (
        filtered
        .sort_values(
            ["分數", "熱門分數", "回檔分數"],
            ascending=[False, False, False]
        )
        .head(5)
    )

    cols = st.columns(5)

    for idx, (_, row) in enumerate(top5.iterrows()):

        with cols[idx]:

            st.markdown(
                f"""
### {row['股票']} {row['波段燈號']}

**{row['判斷']}**

收盤：{row['收盤價']}

強度：{row['強度燈號']}

分數：{row['分數']}

{row['分數條']}

熱門分數：{row['熱門分數']}

主力：{row['主力方向']}

外資：{row['外資趨勢']}

投信：{row['投信趨勢']}

入場：  
{row['入場區間']}

成本區：  
{row['主力成本區']}

RR：{row['RR']}（{row['RR評級']}）

策略：  
{row['操作策略']}
"""
            )

    # ====================================
    # K線圖
    # ====================================

    st.divider()

    st.subheader("📈 K線圖")

    selected_stock = st.selectbox(
        "選擇股票",
        filtered["股票"].tolist()
    )

    if selected_stock in chart_data:

        fig = plot_kline(
            chart_data[selected_stock],
            selected_stock
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

        stock_row = df_result[
            df_result["股票"] == selected_stock
        ].iloc[0]

        st.subheader("📌 單股重點")

        st.write(
            f"""
股票：{stock_row["股票"]}

波段燈號：{stock_row["波段燈號"]}

強度燈號：{stock_row["強度燈號"]}

判斷：{stock_row["判斷"]}

型態：{stock_row["型態"]}

波段階段：{stock_row["階段燈號"]} {stock_row["波段階段"]}

主升：{stock_row["主升"]}

健康回檔：{stock_row["健康回檔"]}

假強勢：{stock_row["假強勢"]}

主力方向：{stock_row["主力方向"]}

外資趨勢：{stock_row["外資趨勢"]}

投信趨勢：{stock_row["投信趨勢"]}

分數：{stock_row["分數"]}

熱門分數：{stock_row["熱門分數"]}

入場區間：{stock_row["入場區間"]}

主力成本區：{stock_row["主力成本區"]}

停損價：{stock_row["停損價"]}

目標價：{stock_row["目標價"]}

RR：{stock_row["RR"]}（{stock_row["RR評級"]}）

追高風險：{stock_row["追高風險"]}

FOMO風險：{stock_row["FOMO風險"]}

風險：{stock_row["風險視覺"]} {stock_row["風險"]}

操作策略：{stock_row["操作策略"]}

建議：{stock_row["建議"]}
"""
        )
# ========================================
# app.py
# ========================================

import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import re
import plotly.graph_objects as go

# ========================================
# 頁面
# ========================================

st.set_page_config(
    page_title="台股波段選股儀表板",
    layout="wide"
)

st.title("🔥 台股波段選股儀表板")

today_str = datetime.today().strftime("%Y-%m-%d %H:%M")

st.caption(f"系統時間：{today_str}")

# ========================================
# Session
# ========================================

if "df_result" not in st.session_state:
    st.session_state["df_result"] = pd.DataFrame()

if "chart_data" not in st.session_state:
    st.session_state["chart_data"] = {}

# ========================================
# 清除 cache
# ========================================

if st.button("🔄 強制更新資料"):

    st.cache_data.clear()

    st.session_state["df_result"] = pd.DataFrame()
    st.session_state["chart_data"] = {}

    st.success("已清除 cache")

# ========================================
# API
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
    value="""2327 3260 2308
3017 2382 8110
2454 1519 3324""",
    height=120
)

watchlist = re.findall(r"\d{4}", stock_text)

start_btn = st.button("🚀 開始分析")

# ========================================
# Sidebar
# ========================================

st.sidebar.header("篩選條件")

min_score = st.sidebar.slider(
    "最低分數",
    0,
    15,
    5
)

max_week_gain = st.sidebar.slider(
    "本週漲幅上限 %",
    0,
    50,
    25
)

max_ma5_bias = st.sidebar.slider(
    "MA5 乖離上限 %",
    0,
    30,
    12
)

min_vol_ratio = st.sidebar.slider(
    "最低量比",
    0.0,
    5.0,
    0.5,
    0.1
)

# ========================================
# 最近交易日
# ========================================

@st.cache_data(ttl=3600)
def get_valid_date(stock_id):

    for i in range(10):

        d = (
            datetime.today()
            - timedelta(days=i)
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
# 法人趨勢
# ========================================

def investor_trend(inst, investor_name):

    trend = "中立"

    if inst.empty:
        return trend

    only = inst[
        inst["name"] == investor_name
    ].copy()

    if only.empty:
        return trend

    only["net"] = (
        only["buy"]
        - only["sell"]
    )

    recent = (
        only["net"]
        .tail(5)
        .tolist()
    )

    positive_days = sum(x > 0 for x in recent)
    negative_days = sum(x < 0 for x in recent)

    if positive_days >= 4:
        trend = "連買"

    elif negative_days >= 4:
        trend = "連賣"

    elif positive_days > negative_days:
        trend = "偏多"

    elif negative_days > positive_days:
        trend = "偏空"

    return trend

# ========================================
# 分析
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
    # 股價
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

    df = pd.DataFrame(
        r.json().get("data", [])
    )

    if df.empty or len(df) < 80:
        return None, None

    df = df.sort_values("date")

    # ====================================
    # 技術指標
    # ====================================

    df["MA5"] = (
        df["close"]
        .rolling(5)
        .mean()
    )

    df["MA10"] = (
        df["close"]
        .rolling(10)
        .mean()
    )

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

    low_n = (
        df["min"]
        .rolling(9)
        .min()
    )

    high_n = (
        df["max"]
        .rolling(9)
        .max()
    )

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

        k = (2 / 3) * k + (1 / 3) * rsv
        d = (2 / 3) * d + (1 / 3) * k

        K_list.append(k)
        D_list.append(d)

    df["K"] = K_list
    df["D"] = D_list

    latest = df.iloc[-1]

    # ====================================
    # 數值
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
        recent_5["close"]
        > recent_5["open"]
    ).sum()

    # ====================================
    # 法人
    # ====================================

    params = {
        "dataset":
        "TaiwanStockInstitutionalInvestorsBuySell",
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

    foreign_trend = "中立"
    trust_trend = "中立"

    if not inst.empty:

        inst = inst.sort_values("date")

        foreign_trend = investor_trend(
            inst,
            "Foreign_Investor"
        )

        trust_trend = investor_trend(
            inst,
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

    if latest["K"] > latest["D"]:
        score += 2

    if vol_ratio > 1.2:
        score += 1

    if foreign_trend == "連買":
        score += 3

    elif foreign_trend == "偏多":
        score += 1

    if trust_trend == "連買":
        score += 3

    elif trust_trend == "偏多":
        score += 1

    if week_change > 0:
        score += 1

    if bias_ma5 > 10:
        score -= 2

    # ====================================
    # 主升段
    # ====================================

    main_uptrend = False

    if (
        latest["close"] > latest["EMA20"]
        and latest["EMA20"] > latest["EMA60"]
        and latest["K"] > latest["D"]
    ):
        main_uptrend = True

    # ====================================
    # 健康回檔
    # ====================================

    healthy_pullback = False

    if (
        bias_ema20 > -3
        and latest["close"] > latest["EMA20"]
        and latest["K"] > 35
    ):
        healthy_pullback = True

    # ====================================
    # 假強勢
    # ====================================

    fake_strength = False

    if (
        week_change > 15
        and latest["K"] > 85
        and foreign_trend in ["連買", "偏多"]
    ):
        fake_strength = True

    # ====================================
    # 訊號
    # ====================================

    signal = "WAIT"

    if (
        score >= 9
        and healthy_pullback
    ):
        signal = "YES"

    elif (
        score >= 7
    ):
        signal = "EARLY"

    elif (
        fake_strength
    ):
        signal = "HOT"

    elif (
        latest["close"] < latest["EMA20"]
    ):
        signal = "NO"

    # ====================================
    # 波段燈號
    # ====================================

    signal_light = "⚪"

    if signal == "YES":
        signal_light = "🟢"

    elif signal == "HOT":
        signal_light = "🔥"

    elif signal == "EARLY":
        signal_light = "🟡"

    elif signal == "NO":
        signal_light = "🔴"

    # ====================================
    # 主力成本區
    # ====================================

    cost_zone_low = round(
        latest["EMA20"] * 0.98,
        2
    )

    cost_zone_high = round(
        latest["EMA20"] * 1.02,
        2
    )

    cost_zone = (
        f"{cost_zone_low}"
        f" ~ "
        f"{cost_zone_high}"
    )

    # ====================================
    # 回測
    # ====================================

    backtest_return_5d = 0
    backtest_return_10d = 0
    backtest_return_20d = 0

    win_5d = 0
    win_10d = 0
    win_20d = 0

    max_drawdown = 0

    avg_hold_days = 0

    historical_returns_5 = []
    historical_returns_10 = []
    historical_returns_20 = []

    wins_5 = 0
    wins_10 = 0
    wins_20 = 0

    total_signals = 0

    hold_days_list = []
    drawdowns = []

    for i in range(60, len(df) - 20):

        row = df.iloc[i]

        signal_trigger = False

        if (
            row["close"] > row["EMA20"]
            and row["EMA20"] > row["EMA60"]
            and row["K"] > row["D"]
            and row["K"] >= 45
            and row["K"] <= 75
        ):
            signal_trigger = True

        if signal_trigger:

            total_signals += 1

            entry_price = df.iloc[i + 1]["open"]

            future_5 = df.iloc[i + 5]["close"]
            future_10 = df.iloc[i + 10]["close"]
            future_20 = df.iloc[i + 20]["close"]

            r5 = (
                (future_5 - entry_price)
                / entry_price
            ) * 100

            r10 = (
                (future_10 - entry_price)
                / entry_price
            ) * 100

            r20 = (
                (future_20 - entry_price)
                / entry_price
            ) * 100

            historical_returns_5.append(r5)
            historical_returns_10.append(r10)
            historical_returns_20.append(r20)

            if r5 > 0:
                wins_5 += 1

            if r10 > 0:
                wins_10 += 1

            if r20 > 0:
                wins_20 += 1

            future_lows = df.iloc[
                i + 1 : i + 21
            ]["min"]

            worst_low = future_lows.min()

            dd = (
                (worst_low - entry_price)
                / entry_price
            ) * 100

            drawdowns.append(dd)

            exit_day = 20

            for j in range(1, 21):

                tmp_close = df.iloc[
                    i + j
                ]["close"]

                tmp_return = (
                    (tmp_close - entry_price)
                    / entry_price
                ) * 100

                if tmp_return >= 10:
                    exit_day = j
                    break

                if tmp_return <= -5:
                    exit_day = j
                    break

            hold_days_list.append(exit_day)

    if total_signals > 0:

        backtest_return_5d = round(
            sum(historical_returns_5)
            / len(historical_returns_5),
            2
        )

        backtest_return_10d = round(
            sum(historical_returns_10)
            / len(historical_returns_10),
            2
        )

        backtest_return_20d = round(
            sum(historical_returns_20)
            / len(historical_returns_20),
            2
        )

        win_5d = round(
            wins_5 / total_signals * 100,
            1
        )

        win_10d = round(
            wins_10 / total_signals * 100,
            1
        )

        win_20d = round(
            wins_20 / total_signals * 100,
            1
        )

        max_drawdown = round(
            min(drawdowns),
            2
        )

        avg_hold_days = round(
            sum(hold_days_list)
            / len(hold_days_list),
            1
        )

    # ====================================
    # 回測評級
    # ====================================

    backtest_grade = "普通"

    if (
        win_10d >= 65
        and backtest_return_10d >= 5
    ):
        backtest_grade = "極佳"

    elif (
        win_10d >= 55
        and backtest_return_10d >= 2
    ):
        backtest_grade = "優"

    elif (
        win_10d < 45
    ):
        backtest_grade = "差"

    backtest_light = "⚪"

    if backtest_grade == "極佳":
        backtest_light = "🔥"

    elif backtest_grade == "優":
        backtest_light = "🟢"

    elif backtest_grade == "普通":
        backtest_light = "🟡"

    elif backtest_grade == "差":
        backtest_light = "🔴"

    # ====================================
    # return
    # ====================================

    return {

        "股票": stock_id,
        "收盤價": round(latest["close"], 2),
        "量比": round(vol_ratio, 2),
        "K": round(latest["K"], 1),
        "D": round(latest["D"], 1),

        "本週%": round(week_change, 2),

        "外資趨勢": foreign_trend,
        "投信趨勢": trust_trend,

        "分數": score,

        "判斷": signal,

        "波段燈號": signal_light,

        "主升": "是" if main_uptrend else "否",

        "健康回檔":
        "是" if healthy_pullback else "否",

        "假強勢":
        "是" if fake_strength else "否",

        "主力成本區": cost_zone,

        "5日報酬": backtest_return_5d,
        "10日報酬": backtest_return_10d,
        "20日報酬": backtest_return_20d,

        "5日勝率": win_5d,
        "10日勝率": win_10d,
        "20日勝率": win_20d,

        "最大回撤": max_drawdown,

        "平均持有": avg_hold_days,

        "回測評級": backtest_grade,

        "回測燈號": backtest_light,

        "資料日期": end_date

    }, df

# ========================================
# K線圖
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
        height=650,
        template="plotly_dark"
    )

    return fig

# ========================================
# 開始分析
# ========================================

if start_btn:

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

        progress.progress(
            (idx + 1)
            / len(watchlist)
        )

    df_result = pd.DataFrame(results)

    if not df_result.empty:

        df_result = df_result.sort_values(
            [
                "分數",
                "10日勝率",
                "10日報酬"
            ],
            ascending=False
        )

        st.session_state[
            "df_result"
        ] = df_result

        st.session_state[
            "chart_data"
        ] = chart_data

# ========================================
# 顯示
# ========================================

df_result = st.session_state["df_result"]
chart_data = st.session_state["chart_data"]

if not df_result.empty:

    filtered = df_result[
        (df_result["分數"] >= min_score)
        &
        (df_result["本週%"] <= max_week_gain)
        &
        (df_result["量比"] >= min_vol_ratio)
    ]

    st.subheader("📊 波段分析結果")

    st.dataframe(
        filtered,
        use_container_width=True,
        height=700
    )

    # ====================================
    # TOP5
    # ====================================

    st.divider()

    st.subheader("🏆 TOP5")

    top5 = filtered.head(5)

    cols = st.columns(5)

    for idx, (_, row) in enumerate(top5.iterrows()):

        with cols[idx]:

            st.markdown(
                f"""
### {row['股票']} {row['波段燈號']}

分數：
{row['分數']}

主升：
{row['主升']}

回測：
{row['回測燈號']} {row['回測評級']}

10日報酬：
{row['10日報酬']}%

10日勝率：
{row['10日勝率']}%

最大回撤：
{row['最大回撤']}%

成本區：
{row['主力成本區']}
"""
            )

    # ====================================
    # K線
    # ====================================

    st.divider()

    st.subheader("📈 K線圖")

    selected_stock = st.selectbox(
        "選擇股票",
        filtered["股票"].tolist()
    )

    if selected_stock in chart_data:

        fig = plot_kline(
            chart_data[selected_stock],
            selected_stock
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )
