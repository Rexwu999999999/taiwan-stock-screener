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


def get_institutional_days(stock_id):

    try:

        end_date = datetime.today().strftime("%Y-%m-%d")

        start_date = (
            datetime.today()
            - timedelta(days=30)
        ).strftime("%Y-%m-%d")

        params = {
            "dataset": "TaiwanStockInstitutionalInvestorsBuySell",
            "data_id": stock_id,
            "start_date": start_date,
            "end_date": end_date
        }

        r = requests.get(
            url,
            headers=headers,
            params=params
        )

        data = r.json().get("data", [])

        if len(data) == 0:
            return 0, 0

        df_ins = pd.DataFrame(data)

        foreign = df_ins[
            df_ins["name"] == "Foreign_Investor"
        ]

        invest = df_ins[
            df_ins["name"] == "Investment_Trust"
        ]

        foreign_days = 0

        for v in reversed(
            foreign["buy_sell"].tolist()
        ):

            if v > 0:
                foreign_days += 1
            else:
                break

        invest_days = 0

        for v in reversed(
            invest["buy_sell"].tolist()
        ):

            if v > 0:
                invest_days += 1
            else:
                break

        return foreign_days, invest_days

    except Exception as e:

        print(stock_id, e)

        return 0, 0


all_data = []

for stock_id in watchlist:

    try:

        print(f"處理 {stock_id}")

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

        ma5 = round(df.iloc[-1]["MA5"], 2)

        ema20 = round(df.iloc[-1]["EMA20"], 2)

        close_price = round(latest["close"], 2)

        foreign_days, invest_days = get_institutional_days(stock_id)

        ai_score = 0

        if close_price > ma5:
            ai_score += 2

        if close_price > ema20:
            ai_score += 3

        if foreign_days >= 3:
            ai_score += 3

        if invest_days >= 3:
            ai_score += 2

        result = {

            "股票": stock_id,

            "日期": end_date,

            "收盤價": close_price,

            "MA5": ma5,

            "EMA20": ema20,

            "成交量":
            int(latest["Trading_Volume"]),

            "外資連買":
            foreign_days,

            "投信連買":
            invest_days,

            "AI分數":
            ai_score,
        }

        all_data.append(result)

        print(f"{stock_id} 完成")

        time.sleep(0.5)

    except Exception as e:

        print(stock_id, e)

final_df = pd.DataFrame(all_data)

print(final_df.columns)

if (
    not final_df.empty
    and "AI分數" in final_df.columns
):

    final_df = final_df.sort_values(
        by="AI分數",
        ascending=False
    )

final_df.to_csv(
    "cache/latest.csv",
    index=False,
    encoding="utf-8-sig"
)

print("完成")
