# ========================================
# 視覺化 + 外資連續性升級版
# 直接覆蓋 analyze() 裡面對應區塊
# ========================================

# ====================================
# 法人資料
# ====================================

params = {
    "dataset": "TaiwanStockInstitutionalInvestorsBuySell",
    "data_id": stock_id,
    "start_date": start_date,
    "end_date": end_date
}

inst = pd.DataFrame(
    requests.get(
        url,
        headers=headers,
        params=params
    ).json().get("data", [])
)

foreign_week = 0
trust_week = 0

foreign_month = 0
trust_month = 0

foreign_trend = "中立"

if not inst.empty:

    inst = inst.sort_values("date")

    inst["date"] = pd.to_datetime(inst["date"])

    week_inst = inst[
        inst["date"]
        >= (
            pd.to_datetime(end_date)
            - pd.Timedelta(days=7)
        )
    ]

    latest_month = pd.to_datetime(end_date).month
    latest_year = pd.to_datetime(end_date).year

    month_inst = inst[
        (inst["date"].dt.month == latest_month)
        &
        (inst["date"].dt.year == latest_year)
    ]

    foreign_week = net_buy(
        week_inst,
        "Foreign_Investor"
    )

    trust_week = net_buy(
        week_inst,
        "Investment_Trust"
    )

    foreign_month = net_buy(
        month_inst,
        "Foreign_Investor"
    )

    trust_month = net_buy(
        month_inst,
        "Investment_Trust"
    )

    # ====================================
    # 外資連續性
    # ====================================

    foreign_only = inst[
        inst["name"] == "Foreign_Investor"
    ].copy()

    foreign_only["net"] = (
        foreign_only["buy"]
        - foreign_only["sell"]
    )

    foreign_recent = (
        foreign_only["net"]
        .tail(5)
        .tolist()
    )

    positive_days = sum(
        x > 0 for x in foreign_recent
    )

    negative_days = sum(
        x < 0 for x in foreign_recent
    )

    if positive_days >= 4:
        foreign_trend = "連買"

    elif negative_days >= 4:
        foreign_trend = "連賣"

    elif positive_days > negative_days:
        foreign_trend = "偏多"

    elif negative_days > positive_days:
        foreign_trend = "偏空"

# ====================================
# 分數
# ====================================

score = 0

if latest["close"] > latest["EMA20"]:
    score += 2

if latest["EMA20"] > latest["EMA60"]:
    score += 2

if latest["close"] > latest["MA5"]:
    score += 1

if latest["K"] > latest["D"]:
    score += 1

if 35 <= latest["K"] <= 75:
    score += 1

if vol_ratio >= 1.2:
    score += 1

# ====================================
# 外資趨勢評分
# ====================================

if foreign_trend == "連買":
    score += 3

elif foreign_trend == "偏多":
    score += 1

elif foreign_trend == "連賣":
    score -= 3

elif foreign_trend == "偏空":
    score -= 1

# ====================================
# 投信評分
# ====================================

if trust_week > 0:
    score += 2

if trust_month > 0:
    score += 1

if foreign_month > 0:
    score += 1

if week_change > 0:
    score += 1

if bias_ma5 > 8:
    score -= 2

if week_change > 20:
    score -= 2

# ====================================
# 回檔分數
# ====================================

pullback_score = 0

if abs(bias_ema20) <= 3:
    pullback_score += 1

if abs(bias_ma5) <= 5:
    pullback_score += 1

if latest["K"] > latest["D"]:
    pullback_score += 1

if latest["K"] < 75:
    pullback_score += 1

if latest["close"] > latest["EMA20"]:
    pullback_score += 1

# ====================================
# FOMO風險
# ====================================

fomo = 0

if week_change > 15:
    fomo += 1

if bias_ma5 > 8:
    fomo += 1

if latest["K"] > 85:
    fomo += 1

if red_count >= 4:
    fomo += 1

risk = "低"

if fomo == 1:
    risk = "中"

elif fomo >= 2:
    risk = "高"

# ====================================
# 波段階段
# ====================================

stage = "整理"

if (
    latest["close"] > latest["EMA20"]
    and latest["K"] > latest["D"]
    and latest["K"] < 55
):
    stage = "剛轉強"

elif (
    latest["close"] > latest["EMA20"]
    and latest["K"] >= 55
    and latest["K"] < 75
):
    stage = "主升段"

elif (
    latest["K"] >= 75
    or week_change > 15
):
    stage = "過熱"

elif (
    latest["close"] < latest["EMA20"]
    and latest["K"] < latest["D"]
):
    stage = "轉弱"

# ====================================
# 型態分類
# ====================================

setup = "整理"

if pullback_score >= 4:
    setup = "回檔轉強"

elif stage == "剛轉強":
    setup = "突破起漲"

elif stage == "主升段":
    setup = "主升延續"

elif stage == "過熱":
    setup = "末升段"

elif stage == "轉弱":
    setup = "轉弱"

# ====================================
# 訊號判斷
# ====================================

signal = "WAIT"

if (
    latest["close"] > latest["EMA20"]
    and latest["MA5"] > latest["EMA20"]
    and latest["K"] > latest["D"]
    and latest["K"] >= 45
    and latest["K"] <= 65
    and vol_ratio > 1
    and week_change < 8
    and bias_ma5 < 5
    and foreign_trend in ["連買", "偏多"]
):
    signal = "YES"

elif (
    setup == "回檔轉強"
    and foreign_trend in ["連買", "偏多"]
    and risk != "高"
):
    signal = "YES"

elif (
    latest["close"] > latest["EMA20"]
    and latest["K"] > latest["D"]
    and latest["K"] >= 70
    and week_change < 18
    and bias_ma5 < 10
    and foreign_trend != "連賣"
):
    signal = "HOT"

elif (
    latest["close"] > latest["EMA20"]
    and latest["K"] > latest["D"]
    and latest["K"] < 65
    and week_change < 8
    and bias_ma5 < 5
):
    signal = "EARLY"

elif (
    latest["close"] < latest["EMA20"]
    and latest["K"] < latest["D"]
):
    signal = "NO"

# ====================================
# 建議
# ====================================

action = "等待"

if signal == "YES":
    action = "最佳波段區，可觀察進場"

elif signal == "HOT":
    action = "主流強勢但避免追高"

elif signal == "EARLY":
    action = "剛轉強觀察"

elif signal == "NO":
    action = "弱勢避免"

# ====================================
# 入場區間
# ====================================

entry_zone = "等待"

if signal == "YES":

    lower = round(latest["EMA20"] * 0.99, 2)
    upper = round(latest["EMA20"] * 1.02, 2)

    entry_zone = f"{lower} ~ {upper}"

elif signal == "EARLY":

    lower = round(latest["EMA20"] * 0.98, 2)
    upper = round(latest["EMA20"] * 1.01, 2)

    entry_zone = f"{lower} ~ {upper}"

elif signal == "HOT":

    lower = round(latest["MA5"] * 0.97, 2)
    upper = round(latest["EMA20"] * 1.00, 2)

    entry_zone = f"等回檔 {lower} ~ {upper}"

elif signal == "NO":

    entry_zone = "不建議進場"

# ====================================
# 停損價 / 目標價 / RR
# ====================================

stop_loss = round(
    recent_5["min"].min(),
    2
)

target_price = round(
    latest["close"] + (
        latest["close"] - stop_loss
    ) * 2,
    2
)

risk_amt = latest["close"] - stop_loss

reward_amt = (
    target_price
    - latest["close"]
)

rr = 0

if risk_amt > 0:
    rr = round(
        reward_amt / risk_amt,
        2
    )

# ====================================
# 分數條
# ====================================

score_bar = (
    "█" * min(score, 10)
)

score_bar += (
    "░" * (10 - min(score, 10))
)

# ====================================
# 熱度條
# ====================================

heat = 0

heat += min(max(week_change, 0), 10)

heat += min(max(bias_ma5, 0), 10)

heat_score = int(heat)

heat_bar = (
    "🔥" * min(heat_score // 3, 5)
)

# ====================================
# 風險圖示
# ====================================

risk_icon = "🟢"

if risk == "中":
    risk_icon = "🟡"

elif risk == "高":
    risk_icon = "🔴"

# ====================================
# 進場圖示
# ====================================

entry_visual = "⚪"

if signal == "YES":
    entry_visual = "🟢"

elif signal == "HOT":
    entry_visual = "🟠"

elif signal == "NO":
    entry_visual = "🔴"

# ====================================
# 階段燈號
# ====================================

stage_color = "⚪"

if stage == "剛轉強":
    stage_color = "🟢"

elif stage == "主升段":
    stage_color = "🟡"

elif stage == "過熱":
    stage_color = "🔴"

elif stage == "轉弱":
    stage_color = "⚫"

# ====================================
# Return
# ====================================

return {

    "股票": stock_id,

    "收盤價": round(latest["close"], 2),

    "MA5": round(latest["MA5"], 2),

    "MA10": round(latest["MA10"], 2),

    "EMA20": round(latest["EMA20"], 2),

    "EMA60": round(latest["EMA60"], 2),

    "量比": round(vol_ratio, 2),

    "K": round(latest["K"], 1),

    "D": round(latest["D"], 1),

    "本週%": round(week_change, 2),

    "MA5乖離%": round(bias_ma5, 2),

    "EMA20乖離%": round(bias_ema20, 2),

    "紅K數": int(red_count),

    "黑K數": int(black_count),

    "外資週": int(foreign_week),

    "投信週": int(trust_week),

    "外資月": int(foreign_month),

    "投信月": int(trust_month),

    "外資趨勢": foreign_trend,

    "分數": int(score),

    "分數條": f"{score_bar} {score}/10",

    "回檔分數": int(pullback_score),

    "判斷": signal,

    "建議": action,

    "進場": entry_visual,

    "入場區間": entry_zone,

    "停損價": stop_loss,

    "目標價": target_price,

    "RR": rr,

    "型態": setup,

    "波段階段": stage,

    "階段燈號": stage_color,

    "熱度": heat_bar,

    "FOMO風險": int(fomo),

    "風險視覺": risk_icon,

    "風險": risk,

    "資料日期": end_date

}, df
```
