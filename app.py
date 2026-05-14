import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="台股潛力股 AI 系統",
    layout="wide"
)

st.title("🚀 台股潛力股 AI 系統")

# =========================
# 讀取資料
# =========================

try:

    df = pd.read_csv(
        "cache/latest.csv"
    )

except:

    st.error("讀取資料失敗")

    st.stop()

st.success("資料載入成功")


# =========================
# 側邊欄
# =========================

st.sidebar.header("篩選器")

themes = ["全部"] + sorted(
    df["族群"]
    .dropna()
    .unique()
    .tolist()
)

selected_theme = st.sidebar.selectbox(
    "族群",
    themes
)

min_ai = st.sidebar.slider(
    "最低 AI 分數",
    int(df["AI分數"].min()),
    int(df["AI分數"].max()),
    20
)

min_value = st.sidebar.slider(
    "最低成交值(億)",
    0,
    int(df["成交值(億)"].max()),
    3
)

min_volume_ratio = st.sidebar.slider(
    "最低量比",
    0.0,
    float(df["量比"].max()),
    1.0
)

quality_options = [

    "全部",

    "提前發動",

    "潛力強勢",

    "可觀察",

    "普通"
]

selected_quality = st.sidebar.selectbox(
    "交易品質",
    quality_options
)


# =========================
# 篩選
# =========================

filtered_df = df.copy()

if selected_theme != "全部":

    filtered_df = filtered_df[
        filtered_df["族群"] == selected_theme
    ]

if selected_quality != "全部":

    filtered_df = filtered_df[
        filtered_df["交易品質"] == selected_quality
    ]

filtered_df = filtered_df[
    filtered_df["AI分數"] >= min_ai
]

filtered_df = filtered_df[
    filtered_df["成交值(億)"] >= min_value
]

filtered_df = filtered_df[
    filtered_df["量比"] >= min_volume_ratio
]


# =========================
# 排序
# =========================

filtered_df = filtered_df.sort_values(

    by=[
        "AI分數",
        "量比",
        "外資3日",
        "投信3日",
        "成交值(億)"
    ],

    ascending=False
)


# =========================
# 顯示欄位
# =========================

show_columns = [

    "熱門排行",

    "股票",

    "名稱",

    "市場",

    "族群",

    "交易品質",

    "AI分數",

    "收盤價",

    "漲幅%",

    "量比",

    "成交值(億)",

    "外資今日",

    "外資3日",

    "投信今日",

    "投信3日",

    "KD-K",

    "KD-D",

    "MACD",

    "SIGNAL",

    "MA5",

    "EMA20",

    "距離前高%",

    "RR",

    "日期",
]

show_columns = [
    c for c in show_columns
    if c in filtered_df.columns
]


# =========================
# 統計
# =========================

st.subheader("📊 市場統計")

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "篩選後股票數",
    len(filtered_df)
)

col2.metric(
    "平均 AI 分數",
    round(filtered_df["AI分數"].mean(), 2)
)

col3.metric(
    "平均量比",
    round(filtered_df["量比"].mean(), 2)
)

col4.metric(
    "平均漲幅%",
    round(filtered_df["漲幅%"].mean(), 2)
)


# =========================
# 提前發動
# =========================

st.subheader("🚀 提前發動")

starter_df = filtered_df[
    filtered_df["交易品質"] == "提前發動"
]

st.dataframe(

    starter_df[show_columns],

    use_container_width=True,

    height=500
)


# =========================
# 潛力強勢
# =========================

st.subheader("🔥 潛力強勢")

strong_df = filtered_df[
    filtered_df["交易品質"] == "潛力強勢"
]

st.dataframe(

    strong_df[show_columns],

    use_container_width=True,

    height=500
)


# =========================
# 全部排行
# =========================

st.subheader("📈 AI 潛力股排行")

st.dataframe(

    filtered_df[show_columns],

    use_container_width=True,

    height=800
)


# =========================
# 爆量排行
# =========================

st.subheader("⚡ 爆量排行")

volume_df = filtered_df.sort_values(
    "量比",
    ascending=False
).head(30)

st.dataframe(

    volume_df[show_columns],

    use_container_width=True,

    height=500
)


# =========================
# 外資排行
# =========================

st.subheader("🏦 外資排行")

foreign_df = filtered_df.sort_values(
    "外資3日",
    ascending=False
).head(30)

st.dataframe(

    foreign_df[show_columns],

    use_container_width=True,

    height=500
)


# =========================
# 投信排行
# =========================

st.subheader("🏛 投信排行")

trust_df = filtered_df.sort_values(
    "投信3日",
    ascending=False
).head(30)

st.dataframe(

    trust_df[show_columns],

    use_container_width=True,

    height=500
)