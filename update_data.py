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
            - timedelta(days=120)
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

        ai_score = 0

        # 趨勢
        if close_price > ma5:
            ai_score += 2

        if close_price > ema20:
            ai_score += 3

        # 位置
        if distance_high < 3:
            ai_score -= 3

        elif distance_high < 8:
            ai_score += 2

        elif distance_high > 20:
            ai_score -= 2

        # RR
        if rr >= 3:
            ai_score += 3

        elif rr >= 2:
            ai_score += 2

        elif rr < 1:
            ai_score -= 3

        # 品質
        quality = "普通"

        if ai_score >= 7:
            quality = "漂亮"

        elif ai_score >= 4:
            quality = "可觀察"

        else:
            quality = "偏弱"

        result = {

            "股票": stock_id,

            "日期": end_date,

            "收盤價": close_price,

            "MA5": ma5,

            "EMA20": ema20,

            "成交量":
            int(latest["Trading_Volume"]),

            "60日高點":
            resistance,

            "20日低點":
            support,

            "距離前高%":
            distance_high,

            "RR":
            rr,

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
