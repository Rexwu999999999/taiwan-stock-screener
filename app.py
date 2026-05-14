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

    st.success("快取資料讀取成功")

    # ===== 篩選器 =====

    col1, col2, col3 = st.columns(3)

    with col1:

        themes = ["全部"] + sorted(
            df["族群"]
            .dropna()
            .unique()
            .tolist()
        )

        selected_theme = st.selectbox(
            "選擇族群",
            themes
        )

    with col2:

        min_ai = st.slider(
            "最低 AI 分數",
            int(df["AI分數"].min()),
            int(df["AI分數"].max()),
            0
        )

    with col3:

        min_value = st.slider(
            "最低成交值(億)",
            0,
            int(df["成交值(億)"].max()),
            0
        )

    # ===== 篩選 =====

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

    # ===== 排序 =====

    filtered_df = filtered_df.sort_values(
        by=[
            "AI分數",
            "成交值(億)",
            "量比"
        ],
        ascending=False
    )

    # ===== 熱門排行榜 =====

    st.subheader("🔥 今日熱門 AI 排行")

    top_df = filtered_df.head(50)

    st.dataframe(
        top_df,
        use_container_width=True,
        height=700
    )

    # ===== 各排行榜 =====

    colA, colB = st.columns(2)

    with colA:

        st.subheader("💰 成交值排行")

        value_rank = filtered_df.sort_values(
            "成交值(億)",
            ascending=False
        ).head(20)

        st.dataframe(
            value_rank[
                [
                    "股票",
                    "族群",
                    "成交值(億)",
                    "AI分數",
                    "交易品質"
                ]
            ],
            use_container_width=True
        )

    with colB:

        st.subheader("⚡ 爆量排行")

        volume_rank = filtered_df.sort_values(
            "量比",
            ascending=False
        ).head(20)

        st.dataframe(
            volume_rank[
                [
                    "股票",
                    "族群",
                    "量比",
                    "AI分數",
                    "交易品質"
                ]
            ],
            use_container_width=True
        )

    # ===== 法人排行 =====

    st.subheader("🧠 法人最強")

    inst_rank = filtered_df.sort_values(
        "外資",
        ascending=False
    ).head(20)

    st.dataframe(
        inst_rank[
            [
                "股票",
                "族群",
                "外資",
                "投信",
                "AI分數",
                "交易品質"
            ]
        ],
        use_container_width=True
    )

except Exception as e:

    st.error(str(e))
