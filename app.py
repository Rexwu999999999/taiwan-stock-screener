import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="台股快取選股系統",
    layout="wide"
)

st.title("🔥 台股快取選股系統")

try:

    df = pd.read_csv(
        "cache/latest.csv"
    )

except:

    st.error("找不到資料")

    st.stop()

st.success("快取資料讀取成功")


# =========================
# 篩選器
# =========================

col1, col2, col3 = st.columns(3)

themes = ["全部"] + sorted(
    df["族群"].dropna().unique().tolist()
)

selected_theme = col1.selectbox(
    "選擇族群",
    themes
)

min_ai = col2.slider(
    "最低 AI 分數",
    0,
    int(df["AI分數"].max()),
    0
)

min_value = col3.slider(
    "最低成交值(億)",
    0,
    int(df["成交值(億)"].max()),
    0
)


filtered_df = df.copy()

if selected_theme != "全部":

    filtered_df = filtered_df[
        filtered_df["族群"] == selected_theme
    ]

filtered_df = filtered_df[
    filtered_df["AI分數"] >= min_ai
]

filtered_df = filtered_df[
    filtered_df["成交值(億)"] >= min_value
]


# =========================
# 熱門 AI 排行
# =========================

st.subheader("🔥 今日熱門 AI 排行")

show_columns = [

    "熱門排行",

    "股票",

    "名稱",

    "市場",

    "族群",

    "日期",

    "收盤價",

    "漲幅%",

    "MA5",

    "EMA20",

    "KD-K",

    "KD-D",

    "MACD",

    "SIGNAL",

    "成交量",

    "量比",

    "成交值(億)",

    "60日高點",

    "20日支撐",

    "距離前高%",

    "RR",

    "外資今日",

    "外資3日",

    "AI分數",

    "交易品質",
]

show_columns = [
    c for c in show_columns
    if c in filtered_df.columns
]

st.dataframe(

    filtered_df[show_columns],

    use_container_width=True,

    height=700
)


# =========================
# 成交值排行
# =========================

st.subheader("💰 成交值排行")

value_df = (

    filtered_df
    .sort_values(
        "成交值(億)",
        ascending=False
    )
    .head(20)
)

st.dataframe(

    value_df[show_columns],

    use_container_width=True,

    height=500
)


# =========================
# 爆量排行
# =========================

st.subheader("⚡ 爆量排行")

volume_df = (

    filtered_df
    .sort_values(
        "量比",
        ascending=False
    )
    .head(20)
)

st.dataframe(

    volume_df[show_columns],

    use_container_width=True,

    height=500
)


# =========================
# 外資排行
# =========================

st.subheader("🏦 外資排行")

foreign_df = (

    filtered_df
    .sort_values(
        "外資3日",
        ascending=False
    )
    .head(20)
)

st.dataframe(

    foreign_df[show_columns],

    use_container_width=True,

    height=500
)