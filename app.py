import streamlit as st
import pandas as pd

# ====================================
# 頁面
# ====================================

st.set_page_config(
    page_title="台股快取選股系統",
    layout="wide"
)

st.title("🔥 台股快取選股系統")

# ====================================
# 讀取快取
# ====================================

try:

    df = pd.read_csv(
        "cache/latest.csv"
    )

    st.success("快取資料讀取成功")

    st.dataframe(
        df,
        use_container_width=True
    )

except Exception as e:

    st.error(e)
