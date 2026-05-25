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

        return round(
            float(value),
            digits
        )

    except:

        return 0


# =========================
# 股票代碼轉換
# =========================

def convert_ticker(stock_input):

    stock_input = str(
        stock_input
    ).strip()

    if stock_input.isdigit():

        tw = f"{stock_input}.TW"

        two = f"{stock_input}.TWO"

        return tw, two

    return stock_input, stock_input


# =========================
# 下載資料
# =========================

def download_stock_data(stock_input):

    tw, two = convert_ticker(
        stock_input
    )

    df = yf.download(

        tw,

        period="9mo",

        interval="1d",

        auto_adjust=False,

        progress=False
    )

    if df.empty:

        df = yf.download(

            two,

            period="9mo",

            interval="1d",

            auto_adjust=False,

            progress=False
        )

        ticker = two

    else:

        ticker = tw

    return df, ticker


# =========================
# KD
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
# MACD
# =========================

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

    hist = macd - signal

    return macd, signal, hist


# =========================
# 法人資料
# =========================

def get_chip_data(stock_id):

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

        if len(rows) == 0:

            return {

                "foreign": 0,
                "trust": 0,
                "dealer": 0
            }

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

                return {

                    "foreign": foreign,

                    "trust": trust,

                    "dealer": dealer
                }

    except:

        pass

    return {

        "foreign": 0,

        "trust": 0,

        "dealer": 0
    }


# =========================
# 隔日沖判斷
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
# AI 分析
# =========================

def ai_analysis(

    close_price,

    ma20,

    k,

    d,

    macd,

    signal,

    foreign,

    trust,

    dealer,

    volume_ratio,

    distance_high
):

    score = 0

    reasons = []

    # EMA20
    if close_price > ma20:

        score += 2

        reasons.append("站上 EMA20")

    # KD
    if k > d and k < 80:

        score += 2

        reasons.append("KD 黃金交叉")

    # MACD
    if macd > signal:

        score += 3

        reasons.append("MACD 多方")

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

    # 爆量
    if 1.5 <= volume_ratio <= 4:

        score += 3

        reasons.append("量能開始放大")

    # 接近突破
    if distance_high <= 8:

        score += 3

        reasons.append("接近突破前高")

    return score, reasons


# =========================
# 使用者輸入
# =========================

stock_input = st.text_input(
    "輸入股票代碼",
    "2330"
)


if stock_input:

    df, ticker = download_stock_data(
        stock_input
    )

    if df.empty:

        st.error("找不到股票")

        st.stop()

    df = df.dropna()

    latest = df.iloc[-1]

    close_price = safe_round(
        latest["Close"]
    )

    volume = int(
        latest["Volume"]
    )

    # EMA20
    df["EMA20"] = (
        df["Close"]
        .ewm(
            span=20,
            adjust=False
        )
        .mean()
    )

    ema20 = safe_round(
        df.iloc[-1]["EMA20"]
    )

    # KD
    k, d = calc_kd(df)

    k_value = safe_round(
        k.iloc[-1]
    )

    d_value = safe_round(
        d.iloc[-1]
    )

    # MACD
    macd, signal, hist = calc_macd(df)

    macd_value = safe_round(
        macd.iloc[-1]
    )

    signal_value = safe_round(
        signal.iloc[-1]
    )

    # 量比
    avg_volume_20 = (
        df["Volume"]
        .tail(20)
        .mean()
    )

    volume_ratio = safe_round(
        volume / avg_volume_20
    )

    # 前高
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

    # 籌碼
    stock_id = stock_input

    chip = get_chip_data(stock_id)

    foreign = chip["foreign"]

    trust = chip["trust"]

    dealer = chip["dealer"]

    # AI
    score, reasons = ai_analysis(

        close_price,

        ema20,

        k_value,

        d_value,

        macd_value,

        signal_value,

        foreign,

        trust,

        dealer,

        volume_ratio,

        distance_high
    )

    # =========================
    # 圖表
    # =========================

    fig = make_subplots(

        rows=3,

        cols=1,

        shared_xaxes=True,

        vertical_spacing=0.05,

        row_heights=[0.6, 0.2, 0.2]
    )

    # K線
    fig.add_trace(

        go.Candlestick(

            x=df.index,

            open=df["Open"],

            high=df["High"],

            low=df["Low"],

            close=df["Close"],

            name="K線"
        ),

        row=1,

        col=1
    )

    fig.add_trace(

        go.Scatter(

            x=df.index,

            y=df["EMA20"],

            name="EMA20"
        ),

        row=1,

        col=1
    )

    # KD
    fig.add_trace(

        go.Scatter(

            x=df.index,

            y=k,

            name="K"
        ),

        row=2,

        col=1
    )

    fig.add_trace(

        go.Scatter(

            x=df.index,

            y=d,

            name="D"
        ),

        row=2,

        col=1
    )

    # MACD
    fig.add_trace(

        go.Scatter(

            x=df.index,

            y=macd,

            name="MACD"
        ),

        row=3,

        col=1
    )

    fig.add_trace(

        go.Scatter(

            x=df.index,

            y=signal,

            name="SIGNAL"
        ),

        row=3,

        col=1
    )

    fig.update_layout(

        height=900,

        xaxis_rangeslider_visible=False
    )

    st.plotly_chart(

        fig,

        use_container_width=True
    )

    # =========================
    # 分析
    # =========================

    st.subheader("📊 AI 分析")

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "收盤價",
        close_price
    )

    col2.metric(
        "AI 分數",
        score
    )

    col3.metric(
        "量比",
        volume_ratio
    )

    st.markdown("---")

    st.subheader("🏦 法人籌碼")

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "外資",
        foreign
    )

    c2.metric(
        "投信",
        trust
    )

    c3.metric(
        "自營商",
        dealer
    )

    st.markdown("---")

    st.subheader("⚠️ 隔日沖風險")

    st.warning(
        day_trade_warning(volume_ratio)
    )

    st.markdown("---")

    st.subheader("🧠 AI 判斷")

    for r in reasons:

        st.write(f"✅ {r}")

    st.markdown("---")

    st.subheader("📌 若目前未進場")

    if score >= 12:

        st.success(
            "偏多，可等待回踩 EMA20 或量縮整理後進場"
        )

    elif score >= 8:

        st.info(
            "觀察中，可等突破前高再進場"
        )

    else:

        st.warning(
            "目前結構普通，不建議急著追價"
        )

    st.markdown("---")

    st.subheader("📌 若目前已進場")

    if macd_value > signal_value and k_value > d_value:

        st.success(
            "趨勢仍偏多，可續抱觀察"
        )

    elif k_value < d_value:

        st.warning(
            "KD轉弱，需注意短線拉回"
        )

    else:

        st.info(
            "建議設好停損並觀察量能"
        )
