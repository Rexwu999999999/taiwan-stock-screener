import os
import time
import requests
import pandas as pd
from datetime import datetime, timedelta

FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoid2h0IiwiZW1haWwiOiJyZXg5NTQzMEBnbWFpbC5jb20iLCJ0b2tlbl92ZXJzaW9uIjowfQ.vGuPWV1lZl_np1ZA1WuVDP9wEPVIQrzDkQ0GhBj4-KE"

headers = {
    "Authorization": f"Bearer {FINMIND_TOKEN}"
}

url = "https://api.finmindtrade.com/api/v4/data"

os.makedirs("cache", exist_ok=True)


def api_get(params):

    r = requests.get(
        url,
        headers=headers,
        params=params,
        timeout=60
    )

    data = r.json().get("data", [])

    return pd.DataFrame(data)


def get_valid_end_date():

    test_stock = "2330"

    for i in range(10):

        d = (
            datetime.today()
            - timedelta(days=i)
        ).strftime("%Y-%m-%d")

        df = api_get({
            "dataset": "TaiwanStockPrice",
            "data_id": test_stock,
            "start_date": d,
            "end_date": d
        })

        if not df.empty:
            return d

    return datetime.today().strftime("%Y-%m-%d")


def get_stock_list():

    df = api_get({
        "dataset": "TaiwanStockInfo"
    })

    if df.empty:

        return pd.DataFrame(
            columns=[
                "stock_id",
                "stock_name",
                "industry_category"
            ]
        )
df["stock_id"] = (
    df["stock_id"]
    .astype(str)
    .str.replace(".0", "", regex=False)
)

df = df[
    df["stock_id"].str.len() == 4
].copy()

df = df[
    df["stock_id"].str.isnumeric()
].copy()
    if "stock_name" not in df.columns:
        df["stock_name"] = ""

    if "industry_category" not in df.columns:
        df["industry_category"] = "其他"

    exclude_keywords = [
        "ETF",
        "ETN",
        "指數",
        "期貨",
        "債",
        "受益",
        "基金"
    ]

    for kw in exclude_keywords:

        df = df[
            ~df["stock_name"]
            .astype(str)
            .str.contains(
                kw,
                na=False
            )
        ]

    df = df.drop_duplicates(
        subset=["stock_id"]
    )

    return df[
        [
            "stock_id",
            "stock_name",
            "industry_category"
        ]
    ]


def get_institutional_data(end_date):

    df = api_get({
        "dataset": "TaiwanStockInstitutionalInvestorsBuySell",
        "start_date": end_date,
        "end_date": end_date
    })

    if df.empty:
        return pd.DataFrame()

    df["stock_id"] = df["stock_id"].astype(str)

    return df


def calc_institutional(stock_id, inst_df):

    foreign_total = 0
    trust_total = 0

    if inst_df.empty:
        return foreign_total, trust_total

    one = inst_df[
        inst_df["stock_id"] == stock_id
    ]

    if one.empty:
        return foreign_total, trust_total

    foreign = one[
        one["name"] == "Foreign_Investor"
    ]

    trust = one[
        one["name"] == "Investment_Trust"
    ]

    if not foreign.empty:

        foreign_total = int(
            foreign["buy"].sum()
            - foreign["sell"].sum()
        )

    if not trust.empty:

        trust_total = int(
            trust["buy"].sum()
            - trust["sell"].sum()
        )

    return foreign_total, trust_total


def get_theme(stock_id, industry):

    theme_map = {

        "2308": "AI",
        "2376": "AI",
        "2327": "AI",
        "2382": "AI",
        "3017": "AI",
        "3231": "AI",
        "6669": "AI",

        "1503": "重電",
        "1504": "重電",
        "1519": "重電",

        "4938": "散熱",
        "3014": "散熱",

        "8110": "生技",

        "2330": "半導體",
        "2454": "半導體",
        "2303": "半導體",

        "3324": "CPO",
        "4908": "CPO",
    }

    return theme_map.get(
        stock_id,
        industry if industry else "其他"
    )


def analyze_stock(
    stock_id,
    stock_name,
    industry,
    df,
    inst_df,
    end_date
):

    if df.empty:
        return None

    df = df.sort_values("date").copy()

    if len(df) < 60:
        return None

    for col in [
        "open",
        "max",
        "min",
        "close",
        "Trading_Volume"
    ]:

        df[col] = pd.to_numeric(
            df[col],
            errors="coerce"
        )

    df = df.dropna(
        subset=[
            "close",
            "Trading_Volume"
        ]
    )

    if len(df) < 60:
        return None

    latest = df.iloc[-1]

    close_price = round(
        latest["close"],
        2
    )

    volume = int(
        latest["Trading_Volume"]
    )

    df["MA5"] = (
        df["close"]
        .rolling(5)
        .mean()
    )

    df["EMA20"] = (
        df["close"]
        .ewm(
            span=20,
            adjust=False
        )
        .mean()
    )

    ma5 = round(
        df.iloc[-1]["MA5"],
        2
    )

    ema20 = round(
        df.iloc[-1]["EMA20"],
        2
    )

    avg_volume_20 = (
        df["Trading_Volume"]
        .tail(20)
        .mean()
    )

    volume_ratio = 0

    if avg_volume_20 > 0:

        volume_ratio = round(
            volume / avg_volume_20,
            2
        )

    high_60 = df["close"].tail(60).max()

    low_20 = df["close"].tail(20).min()

    resistance = round(
        high_60,
        2
    )

    support = round(
        low_20,
        2
    )

    distance_high = round(
        (
            (high_60 - close_price)
            / high_60
        ) * 100,
        2
    )

    reward = resistance - close_price

    risk = close_price - support

    rr = 0

    if risk > 0:

        rr = round(
            reward / risk,
            2
        )

    trading_value = round(
        close_price
        * volume
        / 100000000,
        2
    )

    low9 = df["min"].rolling(9).min()

    high9 = df["max"].rolling(9).max()

    rsv = (
        (df["close"] - low9)
        /
        (high9 - low9)
    ) * 100

    df["K"] = (
        rsv
        .ewm(
            com=2,
            adjust=False
        )
        .mean()
    )

    df["D"] = (
        df["K"]
        .ewm(
            com=2,
            adjust=False
        )
        .mean()
    )

    k_value = round(
        df.iloc[-1]["K"],
        2
    )

    d_value = round(
        df.iloc[-1]["D"],
        2
    )

    ema12 = (
        df["close"]
        .ewm(
            span=12,
            adjust=False
        )
        .mean()
    )

    ema26 = (
        df["close"]
        .ewm(
            span=26,
            adjust=False
        )
        .mean()
    )

    df["MACD"] = ema12 - ema26

    df["SIGNAL"] = (
        df["MACD"]
        .ewm(
            span=9,
            adjust=False
        )
        .mean()
    )

    macd_value = round(
        df.iloc[-1]["MACD"],
        2
    )

    signal_value = round(
        df.iloc[-1]["SIGNAL"],
        2
    )

    foreign_total, trust_total = calc_institutional(
        stock_id,
        inst_df
    )

    ai_score = 0

    if close_price > ma5:
        ai_score += 2

    if close_price > ema20:
        ai_score += 2

    if volume_ratio > 1.5:
        ai_score += 2

    if macd_value > signal_value:
        ai_score += 2

    if k_value > d_value:
        ai_score += 1

    if foreign_total > 0:
        ai_score += 2

    if trust_total > 0:
        ai_score += 1

    if rr >= 2:
        ai_score += 2

    elif rr < 0.5:
        ai_score -= 1

    if distance_high < 2:
        ai_score -= 1

    quality = "偏弱"

    if ai_score >= 10:

        quality = "熱門強勢"

    elif ai_score >= 7:

        quality = "可觀察"

    elif ai_score >= 4:

        quality = "普通"

    theme = get_theme(
        stock_id,
        industry
    )

    return {

        "股票": stock_id,

        "名稱": stock_name,

        "族群": theme,

        "日期": end_date,

        "收盤價": close_price,

        "MA5": ma5,

        "EMA20": ema20,

        "KD-K": k_value,

        "KD-D": d_value,

        "MACD": macd_value,

        "SIGNAL": signal_value,

        "成交量": volume,

        "量比": volume_ratio,

        "成交值(億)": trading_value,

        "60日高點": resistance,

        "20日支撐": support,

        "距離前高%": distance_high,

        "RR": rr,

        "外資": foreign_total,

        "投信": trust_total,

        "AI分數": ai_score,

        "交易品質": quality,
    }


def main():

    end_date = get_valid_end_date()

    start_date = (
        datetime.strptime(
            end_date,
            "%Y-%m-%d"
        )
        - timedelta(days=180)
    ).strftime("%Y-%m-%d")

    print("DATA_DATE", end_date)

    stock_info = get_stock_list()

    print("STOCK_COUNT", len(stock_info))

    inst_df = get_institutional_data(
        end_date
    )

    all_data = []

    for idx, row in stock_info.iterrows():

        stock_id = row["stock_id"]

        stock_name = row["stock_name"]

        industry = row["industry_category"]

        try:

            df_stock = api_get({

                "dataset": "TaiwanStockPrice",

                "data_id": stock_id,

                "start_date": start_date,

                "end_date": end_date
            })

            result = analyze_stock(

                stock_id=stock_id,

                stock_name=stock_name,

                industry=industry,

                df=df_stock,

                inst_df=inst_df,

                end_date=end_date
            )

            if result is not None:
                all_data.append(result)

            if idx % 50 == 0:
                print("PROGRESS", idx)

            time.sleep(0.05)

        except:
            pass

    final_df = pd.DataFrame(all_data)

    if final_df.empty:

        print("NO_RESULT")

        return

    final_df = final_df.sort_values(

        by=[
            "AI分數",
            "成交值(億)",
            "量比"
        ],

        ascending=False
    )

    final_df["熱門排行"] = range(
        1,
        len(final_df) + 1
    )

    final_df.to_csv(

        "cache/latest.csv",

        index=False,

        encoding="utf-8-sig"
    )

    print("DONE")

    print(
        "RESULT_COUNT",
        len(final_df)
    )


if __name__ == "__main__":
    main()
