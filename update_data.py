import requests
import pandas as pd
from datetime import datetime, timedelta
import time
import os

FINMIND_TOKEN = "你的token"

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

        result = {

            "股票": stock_id,

            "日期": end_date,

            "收盤價":
            round(latest["close"], 2),

            "MA5":
            round(df.iloc[-1]["MA5"], 2),

            "EMA20":
            round(df.iloc[-1]["EMA20"], 2),

            "成交量":
            int(latest["Trading_Volume"]),
        }

        all_data.append(result)

        print(f"{stock_id} 完成")

        time.sleep(0.5)

    except Exception as e:

        print(stock_id, e)

final_df = pd.DataFrame(all_data)

final_df.to_csv(
    "cache/latest.csv",
    index=False,
    encoding="utf-8-sig"
)

print("完成")
