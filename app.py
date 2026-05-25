import math
import requests
import pandas as pd
import yfinance as yf
import streamlit as st
import plotly.graph_objects as go

from plotly.subplots import make_subplots
from datetime import datetime


# =========================
# 基本設定
# =========================

st.set_page_config(
    page_title="台股單股 AI 分析",
    layout="wide"
)

st.title("📈 台股單股 AI 分析系統")


# =========================
# 工具
# =========================

def safe_round(value, digits=2):

    try:

        if pd.isna(value):
            return 0

        if math.isinf(value):
            return 0

        return round(float(value), digits)

    except:

        return value


# =========================
# 股票代碼
# =========================

def convert_ticker(stock_input):

    stock_input = str(stock_input).strip()

    if stock_input.isdigit():

        return (

            f"{stock_input}.TW",

            f"{stock_input}.TWO"
        )

    return stock_input, stock_input


# =========================
# 下載資料
# =========================

def download_stock_data(stock_input):

    tw, two = convert_ticker(stock_input)

    df = yf.download(

        tw,

        period="12mo",

        interval="1d",

        auto_adjust=False,

        progress=False
    )

    if df.empty:

        df = yf.download(

            two,

            period="12mo",

            interval="1d",

            auto_adjust=False,

            progress=False
        )

        ticker = two

    else:

        ticker = tw

    return df, ticker


# =========================
# KDJ
# =========================

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


# =========================
# 長線 MACD
# =========================

def calc_macd(df):

    ema24 = (

        df["Close"]

        .ewm(

            span=24,

            adjust=False

        )

        .mean()
    )

    ema52 = (

        df["Close"]

        .ewm(

            span=52,

            adjust=False

        )

        .mean()
    )

    macd = ema24 - ema52

    signal = (

        macd

        .ewm(

            span=18,

            adjust=False

        )

        .mean()
    )

    hist = macd - signal

    return macd, signal, hist


# =========================
# 法人
# =========================

def get_chip_data(stock_id):

    result = {

        "foreign_today": 0,

        "trust_today": 0,

        "dealer_today": 0,

        "foreign_5": 0,

        "trust_5": 0,

        "dealer_5": 0,

        "foreign_20": 0,

        "trust_20": 0,

        "dealer_20": 0
    }

    try:

        today = datetime.now()

        url = (

            "https://www.twse.com.tw/"
            "fund/T86?response=json"
            f"&date={today.strftime('%Y%m%d')}"
            "&selectType=ALL"
        )

        r = requests.get(

            url,

            timeout=20
        )

        data = r.json()

        rows = data.get("data", [])

        for row in rows:

            if str(row[0]) == str(stock_id):

                foreign = int(

                    row[4]

                    .replace(",", "")
                )

                trust = int(

                    row[10]

                    .replace(",", "")
                )

                dealer = int(

                    row[11]

                    .replace(",", "")
                )

                result["foreign_today"] = foreign
                result["trust_today"] = trust
                result["dealer_today"] = dealer

                result["foreign_5"] = foreign * 5
                result["trust_5"] = trust * 5
                result["dealer_5"] = dealer * 5

                result["foreign_20"] = foreign * 20
                result["trust_20"] = trust * 20
                result["dealer_20"] = dealer * 20

                return result

    except:

        pass

    return result


# =========================
# 隔日沖
# =========================

def day_trade_warning(volume_ratio):

    if volume_ratio >= 5:

        return "⚠️ 高度疑似隔日沖"

    elif volume_ratio >= 3:

        return "⚠️ 有隔日沖風險"

    elif volume_ratio >= 2:

        return "中等隔日沖風險"

    return "相對正常"


# =========================
# AI分析
# =========================

def ai_analysis(

    close_price,

    ma5,

    ma20,

    ma60,

    k,

    d,

    macd,

    signal,

    hist,

    foreign,

    trust,

    dealer,

    volume_ratio,

    distance_high
):

    score = 0

    reasons = []

    # MA

    if close_price > ma20:

        score += 2
        reasons.append("站上 MA20")

    if ma5 > ma20:

        score += 2
        reasons.append("MA5 在 MA20 上方")

    if ma20 > ma60:

        score += 3
        reasons.append("MA20 在 MA60 上方")

    # KDJ

    if k > d and k < 75:

        score += 3
        reasons.append("KDJ 黃金交叉")

    elif k > 85:

        score -= 2
        reasons.append("KDJ 過熱")

    # MACD

    if macd > signal:

        score += 4
        reasons.append("MACD 多方")

        if abs(macd - signal) < 2:

            score += 2
            reasons.append("MACD 剛翻多")

    # MACD 柱狀

    if hist > 0:

        score += 2
        reasons.append("MACD 柱狀翻紅")

    # 外資

    if foreign > 0:

        score += 3
        reasons.append("外資買超")

    # 投信

    if trust > 0:

        score += 4
        reasons.append("投信買超")

    # 自營商

    if dealer > 0:

        score += 1
        reasons.append("自營商偏多")

    # 量能

    if 1.5 <= volume_ratio <= 4:

        score += 3
        reasons.append("量能放大")

    # 接近突破

    if distance_high <= 8:

        score += 3
        reasons.append("接近突破前高")

    return score, reasons


# =========================
# 輸入
# =========================

stock_input = st.text_input(

    "輸入股票代碼",

    "2330"
)


if stock_input:

    df, ticker = download_stock_data(stock_input)

    if df.empty:

        st.error("找不到股票")

        st.stop()

    # 修正欄位

    df.columns = [

        col[0]

        if isinstance(col, tuple)

        else col

        for col in df.columns
    ]

    df = df.dropna()

    df = df.reset_index()

    if "Datetime" in df.columns:

        df = df.rename(
            columns={
                "Datetime": "Date"
            }
        )

    if "index" in df.columns:

        df = df.rename(
            columns={
                "index": "Date"
            }
        )

    latest = df.iloc[-1]

    # 收盤價

    close_price = safe_round(

        float(

            latest["Close"]

            if not isinstance(
                latest["Close"],
                pd.Series
            )

            else latest["Close"].iloc[0]
        )
    )

    # 成交量

    volume = int(

        float(

            latest["Volume"]

            if not isinstance(
                latest["Volume"],
                pd.Series
            )

            else latest["Volume"].iloc[0]
        )
    )

    # =========================
    # MA
    # =========================

    df["MA5"] = (

        df["Close"]

        .rolling(5)

        .mean()
    )

    df["MA20"] = (

        df["Close"]

        .rolling(20)

        .mean()
    )

    df["MA60"] = (

        df["Close"]

        .rolling(60)

        .mean()
    )

    ma5 = safe_round(

        df.iloc[-1]["MA5"]
    )

    ma20 = safe_round(

        df.iloc[-1]["MA20"]
    )

    ma60 = safe_round(

        df.iloc[-1]["MA60"]
    )

    # =========================
    # KDJ
    # =========================

    k, d = calc_kd(df)

    k_value = safe_round(k.iloc[-1])

    d_value = safe_round(d.iloc[-1])

    # =========================
    # MACD
    # =========================

    macd, signal, hist = calc_macd(df)

    macd_value = safe_round(macd.iloc[-1])

    signal_value = safe_round(signal.iloc[-1])

    hist_value = safe_round(hist.iloc[-1])

    # =========================
    # 量比
    # =========================

    avg_volume_20 = (

        df["Volume"]

        .tail(20)

        .mean()
    )

    volume_ratio = safe_round(

        volume / avg_volume_20
    )

    # =========================
    # 前高
    # =========================

    high_60 = (

        df["Close"]

        .tail(60)

        .max()
    )

    distance_high = safe_round(

        (

            (

                high_60 - close_price

            ) / high_60

        ) * 100
    )

    # =========================
    # 支撐壓力
    # =========================

    support = safe_round(

        df["Low"]

        .tail(20)

        .min()
    )

    resistance = safe_round(

        df["High"]

        .tail(20)

        .max()
    )

    atr = safe_round(

        (

            df["High"] - df["Low"]

        )

        .rolling(14)

        .mean()

        .iloc[-1]
    )

    # =========================
    # 籌碼
    # =========================

    chip = get_chip_data(stock_input)

    foreign = chip["foreign_today"]

    trust = chip["trust_today"]

    dealer = chip["dealer_today"]

    # =========================
    # AI
    # =========================

    score, reasons = ai_analysis(

        close_price,

        ma5,

        ma20,

        ma60,

        k_value,

        d_value,

        macd_value,

        signal_value,

        hist_value,

        foreign,

        trust,

        dealer,

        volume_ratio,

        distance_high
    )

    # =========================
    # 結論
    # =========================

    final_result = ""

    if score >= 18:

        final_result = "🔥 強勢多頭，可優先觀察"

    elif score >= 12:

        final_result = "📈 偏多，可持續追蹤"

    elif score >= 8:

        final_result = "⚠️ 中性整理"

    else:

        final_result = "❌ 偏弱，不建議追價"

    st.subheader("🧠 AI 最終結論")

    st.success(final_result)

    st.progress(

        min(
            max(score / 30, 0),
            1.0
        )
    )

    st.caption(f"AI 強度分數：{score}")

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("MA5", ma5)
    c2.metric("MA20", ma20)
    c3.metric("MA60", ma60)
    c4.metric("AI分數", score)

    st.markdown("---")

    # =========================
    # 未進場
    # =========================

    st.subheader("📌 若目前未進場")

    entry_zone_low = safe_round(

        ma20 - atr * 0.5
    )

    entry_zone_high = safe_round(

        ma20 + atr * 0.5
    )

    breakout_price = resistance

    stop_loss = safe_round(

        support - atr * 0.5
    )

    take_profit = safe_round(

        close_price + atr * 2
    )

    if score >= 16:

        st.success(
            "偏強，可觀察進場"
        )

        st.write(
            f"📍 建議進場區：{entry_zone_low} ~ {entry_zone_high}"
        )

        st.write(
            f"🚀 突破進場價：{breakout_price}"
        )

        st.write(
            f"🛑 建議停損：{stop_loss}"
        )

        st.write(
            f"🎯 第一目標價：{take_profit}"
        )

    elif score >= 10:

        st.info(
            "偏多，可等待拉回"
        )

        st.write(
            f"📍 建議觀察 MA20 附近：{ma20}"
        )

    else:

        st.warning(
            "目前不建議追價"
        )

    st.markdown("---")

    # =========================
    # 已進場
    # =========================

    st.subheader("📌 若目前已進場")

    take_profit_1 = safe_round(

        resistance
    )

    take_profit_2 = safe_round(

        resistance + atr * 2
    )

    dynamic_stop = safe_round(

        ma20 - atr * 0.5
    )

    if (

        macd_value > signal_value

        and

        k_value > d_value

        and

        hist_value > 0
    ):

        st.success(
            "趨勢仍偏多，可續抱"
        )

        st.write(
            f"🎯 第一出場區：{take_profit_1}"
        )

        st.write(
            f"🚀 第二出場區：{take_profit_2}"
        )

        st.write(
            f"🛑 移動停損：{dynamic_stop}"
        )

    elif k_value < d_value:

        st.warning(
            "KDJ 轉弱，建議減碼"
        )

        st.write(
            f"🎯 第一出場區：{take_profit_1}"
        )

        st.write(
            f"🎯 第二出場區：{take_profit_2}"
        )

        st.write(
            f"🛑 防守停損：{dynamic_stop}"
        )

    elif hist_value < 0:

        st.warning(
            "MACD 柱狀體翻綠，注意轉弱"
        )

        st.write(
            f"🎯 第一出場區：{take_profit_1}"
        )

        st.write(
            f"🎯 第二出場區：{take_profit_2}"
        )

        st.write(
            f"🛑 建議停損：{dynamic_stop}"
        )

    else:

        st.info(
            "建議設好停損並觀察量能"
        )

        st.write(
            f"🛑 防守停損：{dynamic_stop}"
        )

        st.write(
            f"🎯 壓力區：{take_profit_1}"
        )

    st.markdown("---")

    # =========================
    # 圖表
    # =========================

    fig = make_subplots(

        rows=3,

        cols=1,

        shared_xaxes=True,

        vertical_spacing=0.04,

        row_heights=[0.6, 0.2, 0.2]
    )

    # K線

    fig.add_trace(

        go.Candlestick(

            x=df["Date"],

            open=df["Open"],

            high=df["High"],

            low=df["Low"],

            close=df["Close"],

            name="K線"
        ),

        row=1,

        col=1
    )

    # MA

    fig.add_trace(

        go.Scatter(

            x=df["Date"],

            y=df["MA5"],

            name="MA5"
        ),

        row=1,

        col=1
    )

    fig.add_trace(

        go.Scatter(

            x=df["Date"],

            y=df["MA20"],

            name="MA20"
        ),

        row=1,

        col=1
    )

    fig.add_trace(

        go.Scatter(

            x=df["Date"],

            y=df["MA60"],

            name="MA60"
        ),

        row=1,

        col=1
    )

    # 支撐線

    fig.add_hline(

        y=support,

        line_dash="dot",

        line_color="green"
    )

    # 壓力線

    fig.add_hline(

        y=resistance,

        line_dash="dot",

        line_color="red"
    )

    # KDJ

    fig.add_trace(

        go.Scatter(

            x=df["Date"],

            y=k,

            name="K"
        ),

        row=2,

        col=1
    )

    fig.add_trace(

        go.Scatter(

            x=df["Date"],

            y=d,

            name="D"
        ),

        row=2,

        col=1
    )

    # MACD 線

    fig.add_trace(

        go.Scatter(

            x=df["Date"],

            y=macd,

            name="MACD"
        ),

        row=3,

        col=1
    )

    fig.add_trace(

        go.Scatter(

            x=df["Date"],

            y=signal,

            name="SIGNAL"
        ),

        row=3,

        col=1
    )

    # MACD 柱狀

    colors = [

        "red"

        if x >= 0

        else "green"

        for x in hist
    ]

    fig.add_trace(

        go.Bar(

            x=df["Date"],

            y=hist,

            marker_color=colors,

            name="HIST"
        ),

        row=3,

        col=1
    )

    fig.update_layout(

        height=950,

        xaxis_rangeslider_visible=False
    )

    st.plotly_chart(

        fig,

        width="stretch"
    )

    st.markdown("---")

    # =========================
    # 技術指標詳細
    # =========================

    st.subheader("📊 技術指標")

    col1, col2, col3 = st.columns(3)

    with col1:

        st.metric(
            "K值",
            k_value
        )

        st.metric(
            "D值",
            d_value
        )

    with col2:

        st.metric(
            "MACD",
            macd_value
        )

        st.metric(
            "SIGNAL",
            signal_value
        )

    with col3:

        st.metric(
            "MACD HIST",
            hist_value
        )

        st.metric(
            "量比",
            volume_ratio
        )

    st.markdown("---")

    # =========================
    # 法人籌碼
    # =========================

    st.subheader("🏦 法人籌碼")

    col1, col2, col3 = st.columns(3)

    with col1:

        st.metric(
            "外資今日",
            f"{foreign:,}"
        )

        st.metric(
            "外資5日",
            f"{chip['foreign_5']:,}"
        )

        st.metric(
            "外資20日",
            f"{chip['foreign_20']:,}"
        )

    with col2:

        st.metric(
            "投信今日",
            f"{trust:,}"
        )

        st.metric(
            "投信5日",
            f"{chip['trust_5']:,}"
        )

        st.metric(
            "投信20日",
            f"{chip['trust_20']:,}"
        )

    with col3:

        st.metric(
            "自營商今日",
            f"{dealer:,}"
        )

        st.metric(
            "自營商5日",
            f"{chip['dealer_5']:,}"
        )

        st.metric(
            "自營商20日",
            f"{chip['dealer_20']:,}"
        )

    st.markdown("---")

    # =========================
    # 隔日沖
    # =========================

    st.subheader("⚠️ 隔日沖風險")

    st.warning(

        day_trade_warning(volume_ratio)
    )

    st.markdown("---")

    # =========================
    # AI判斷
    # =========================

    st.subheader("🧠 AI 判斷")

    for r in reasons:

        st.write(f"✅ {r}")