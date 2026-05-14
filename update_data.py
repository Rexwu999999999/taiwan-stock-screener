import requests
import pandas as pd
from datetime import datetime, timedelta
import time
import os

FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoid2h0IiwiZW1haWwiOiJyZXg5NTQzMEBnbWFpbC5jb20iLCJ0b2tlbl92ZXJzaW9uIjowfQ.vGuPWV1lZl_np1ZA1WuVDP9wEPVIQrzDkQ0GhBj4-KE"

headers = {
    "Authorization": f"Bearer {FINMIND_TOKEN}"
}

url = "https://api.finmindtrade.com/api/v4/data"

watchlist = [
    "2308",
    "2376",
    "2327",
    "3260",
    "2451",
    "1503",
    "8110",
    "4938",
    "2449",
    "2421",
]

theme_map = {

    "2308": "AI",
    "2376": "AI",
    "2327": "AI",

    "1503": "重電",

    "8110": "生技",

    "4938": "散熱",

    "3260": "其他",
    "2451": "其他",
    "2449": "其他",
    "2421": "其他",
}

if not os.path.exists("cache"):
    os.makedirs("cache")


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


all_data = []

for stock_id in watchlist:

    try:

        print(stock_id)

        end_date = get_valid_date(stock_id)

        if end_date is None:
            continue

        start_date = (
            datetime.strptime(end_date, "%Y-%m-%d")
            - timedelta(days=180)
        ).strftime("%Y-%m-%d")

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

        if df.empty:
            continue

        df = df.sort_values("date")

        latest = df.iloc[-1]

        close_price = round(
            latest["close"],
            2
        )

        volume = int(
            latest["Trading_Volume"]
        )

        # =====================
        # MA EMA
        # =====================

        df["MA5"] = (
            df["close"]
            .rolling(5)
            .mean()
        )

        df["EMA20"] = (
            df["close"]
            .ewm(span=20)
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

        # =====================
        # KD
        # =====================

        low9 = df["min"].rolling(9).min()

        high9 = df["max"].rolling(9).max()

        rsv = (
            (
                df["close"] - low9
            )
            /
            (
                high9 - low9
            )
        ) * 100

        df["K"] = (
            rsv
            .ewm(com=2)
            .mean()
        )

        df["D"] = (
            df["K"]
            .ewm(com=2)
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

        # =====================
        # MACD
        # =====================

        ema12 = (
            df["close"]
            .ewm(span=12)
            .mean()
        )

        ema26 = (
            df["close"]
            .ewm(span=26)
            .mean()
        )

        df["MACD"] = ema12 - ema26

        df["SIGNAL"] = (
            df["MACD"]
            .ewm(span=9)
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

        # =====================
        # Volume Ratio
        # =====================

        avg_volume_20 = (
            df["Trading_Volume"]
            .tail(20)
            .mean()
        )

        volume_ratio = round(
            volume / avg_volume_20,
            2
        )

        # =====================
        # Support Resistance
        # =====================

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

        # =====================
        # RR
        # =====================

        reward = resistance - close_price

        risk = close_price - support

        rr = 0

        if risk > 0:

            rr = round(
                reward / risk,
                2
            )

        # =====================
        # Trading Value
        # =====================

        trading_value = round(
            (
                close_price * volume
            ) / 100000000,
            2
        )

        # =====================
        # Institutional
        # =====================

        buy_params = {

            "dataset":
            "TaiwanStockInstitutionalInvestorsBuySell",

            "data_id":
            stock_id,

            "start_date":
            end_date,

            "end_date":
            end_date
        }

        buy_r = requests.get(
            url,
            headers=headers,
            params=buy_params
        )

        buy_df = pd.DataFrame(
            buy_r.json().get("data", [])
        )

        foreign_total = 0

        trust_total = 0

        if not buy_df.empty:

            foreign_df = buy_df[
                buy_df["name"]
                ==
                "Foreign_Investor"
            ]

            trust_df = buy_df[
                buy_df["name"]
                ==
                "Investment_Trust"
            ]

            if not foreign_df.empty:

                foreign_total = int(
                    foreign_df.iloc[0]["buy"]
                    -
                    foreign_df.iloc[0]["sell"]
                )

            if not trust_df.empty:

                trust_total = int(
                    trust_df.iloc[0]["buy"]
                    -
                    trust_df.iloc[0]["sell"]
                )

        # =====================
        # AI Score
        # =====================

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

        if distance_high < 3:
            ai_score -= 3

        elif distance_high > 20:
            ai_score -= 2

        # =====================
        # Quality
        # =====================

        quality = "偏弱"

        if ai_score >= 9:
            quality = "熱門強勢"

        elif ai_score >= 6:
            quality = "可觀察"

        elif ai_score >= 4:
            quality = "普通"

        # =====================
        # Result
        # =====================

        result = {

            "股票":
            stock_id,

            "族群":
            theme_map.get(
                stock_id,
                "其他"
            ),

            "日期":
            end_date,

            "收盤價":
            close_price,

            "MA5":
            ma5,

            "EMA20":
            ema20,

            "KD-K":
            k_value,

            "KD-D":
            d_value,

            "MACD":
            macd_value,

            "SIGNAL":
            signal_value,

            "成交量":
            volume,

            "量比":
            volume_ratio,

            "成交值(億)":
            trading_value,

            "60日高點":
            resistance,

            "20日支撐":
            support,

            "距離前高%":
            distance_high,

            "RR":
            rr,

            "外資":
            foreign_total,

            "投信":
            trust_total,

            "AI分數":
            ai_score,

            "交易品質":
            quality,
        }

        all_data.append(result)

        print(stock_id, "完成")

        time.sleep(0.5)

    except Exception as e:

        print(stock_id, e)

final_df = pd.DataFrame(all_data)

if not final_df.empty:

    final_df = final_df.sort_values(
        "AI分數",
        ascending=False
    )

final_df.to_csv(
    "cache/latest.csv",
    index=False,
    encoding="utf-8-sig"
)

print("完成")
