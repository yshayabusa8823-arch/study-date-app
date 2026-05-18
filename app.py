import streamlit as st
import pandas as pd
from datetime import datetime, time

st.set_page_config(page_title="勉強優先スケジュール管理", layout="wide")
st.title("勉強優先スケジュール管理アプリ")

# =====================
# 設定
# =====================

st.sidebar.header("設定")

weekday_min = st.sidebar.number_input("平日最低勉強時間", min_value=0, value=2)
weekend_min = st.sidebar.number_input("土日最低勉強時間", min_value=0, value=4)

days = ["月", "火", "水", "木", "金", "土", "日"]
time_order = [f"{h}:00" for h in range(8, 24)]

uploaded = st.file_uploader("スケジュール管理表.xlsx をアップロード", type=["xlsx"])

girl_col = "彼女"
boy_col = "彼氏"

# =====================
# 関数
# =====================

def normalize_time(x):
    if pd.isna(x):
        return ""

    # Excel時刻が 0.333333 みたいな数値で来る場合
    if isinstance(x, (int, float)):
        if 0 <= x < 1:
            hour = int(round(x * 24))
            return f"{hour}:00"
        return f"{int(x)}:00"

    # datetime型
    if isinstance(x, datetime):
        return f"{x.hour}:00"

    # time型
    if isinstance(x, time):
        return f"{x.hour}:00"

    # 文字列
    s = str(x).strip()

    if ":" in s:
        hour = int(s.split(":")[0])
        return f"{hour}:00"

    return s


def required_study(day):
    return weekend_min if day in ["土", "日"] else weekday_min


def ease_label(ease):
    return {
        "×": "最優先",
        "△": "高",
        "○": "中",
        "◎": "低",
    }.get(ease, "")


def ease_score(ease):
    return {
        "×": 1,
        "△": 2,
        "○": 3,
        "◎": 4,
    }.get(ease, 9)


def priority_score(priority):
    return {
        "高": 1,
        "中": 2,
        "低": 3,
    }.get(priority, 9)


def color_final(val):
    if val == "勉強":
        return "background-color: #fff2cc"
    if val == "会う":
        return "background-color: #b7e1cd"
    if val == "会ってもいい":
        return "background-color: #d9ead3"
    if val == "授業":
        return "background-color: #f4cccc"
    if val == "バイト":
        return "background-color: #ead1dc"
    if val == "睡眠":
        return "background-color: #cfe2f3"
    if val == "移動":
        return "background-color: #eadcf8"
    return ""

# =====================
# データ読み込み
# =====================

if uploaded:
    df = pd.read_excel(uploaded, sheet_name=0, engine="openpyxl")

    if "しおり" in df.columns:
        girl_col = "しおり"

    if "しゅんさく" in df.columns:
        boy_col = "しゅんさく"

    df = df[["曜日", "時間", girl_col, boy_col, "会いやすさ", "勉強優先度"]]
    df = df[df["曜日"].isin(days)].copy()

    df["時間"] = df["時間"].apply(normalize_time)

else:
    rows = []
    for day in days:
        for t in time_order:
            rows.append({
                "曜日": day,
                "時間": t,
                girl_col: "空き",
                boy_col: "空き",
                "会いやすさ": "○",
                "勉強優先度": "中",
            })

    df = pd.DataFrame(rows)

# =====================
# 入力
# =====================

st.subheader("予定入力・変更")

edited = st.data_editor(
    df,
    use_container_width=True,
    num_rows="dynamic",
    column_config={
        "曜日": st.column_config.SelectboxColumn(options=days),
        girl_col: st.column_config.SelectboxColumn(
            options=["空き", "勉強", "授業", "バイト", "睡眠", "移動", "その他"]
        ),
        boy_col: st.column_config.SelectboxColumn(
            options=["空き", "勉強", "授業", "バイト", "睡眠", "移動", "その他"]
        ),
        "会いやすさ": st.column_config.SelectboxColumn(options=["◎", "○", "△", "×"]),
        "勉強優先度": st.column_config.SelectboxColumn(options=["高", "中", "低"]),
    }
)

st.download_button(
    label="変更内容をCSVでダウンロード",
    data=edited.to_csv(index=False).encode("utf-8-sig"),
    file_name="updated_schedule.csv",
    mime="text/csv",
)

# =====================
# 自動計算
# =====================

result = edited.copy()

result["時間"] = result["時間"].apply(normalize_time)

result["判定"] = ""
result[f"{girl_col}勉強時間"] = 0
result[f"{boy_col}勉強時間"] = 0
result["不足勉強時間"] = ""
result["不足数値"] = pd.NA
result["自動勉強候補"] = ""
result["勉強候補順"] = pd.NA
result["自動配置"] = ""
result["最終行動"] = ""

for day in days:
    mask = result["曜日"] == day
    day_df = result[mask].copy()

    if day_df.empty:
        continue

    result.loc[mask, f"{girl_col}勉強時間"] = (day_df[girl_col] == "勉強").astype(int)
    result.loc[mask, f"{boy_col}勉強時間"] = (day_df[boy_col] == "勉強").astype(int)

    fixed_study = (day_df[girl_col] == "勉強").sum()
    shortage = max(0, required_study(day) - fixed_study)

    candidates = []

    for idx in day_df.index:
        girl = result.loc[idx, girl_col]
        boy = result.loc[idx, boy_col]
        ease = result.loc[idx, "会いやすさ"]
        priority = result.loc[idx, "勉強優先度"]

        if girl == "勉強":
            result.loc[idx, "判定"] = "勉強確定"
        elif girl in ["授業", "バイト", "睡眠", "移動", "その他"]:
            result.loc[idx, "判定"] = "予定優先"
        elif girl == "空き" and boy == "勉強":
            result.loc[idx, "判定"] = "勉強候補"
        elif girl == "空き" and ease == "◎":
            result.loc[idx, "判定"] = "会わない"
        elif girl == "空き":
            result.loc[idx, "判定"] = "勉強優先寄り"

        if girl == "空き":
            result.loc[idx, "自動勉強候補"] = ease_label(ease)

            # 勉強優先度を先に見る：高→中→低
            # 同じ優先度なら会いにくい順：×→△→○→◎
            score = priority_score(priority) * 10 + ease_score(ease)
            candidates.append((idx, score))

    candidates = sorted(candidates, key=lambda x: x[1])

    for order, (idx, score) in enumerate(candidates, start=1):
        result.loc[idx, "勉強候補順"] = order

        if order <= shortage:
            result.loc[idx, "自動配置"] = "勉強確定"

    last_idx = day_df.index[-1]
    result.loc[last_idx, "不足勉強時間"] = "不足勉強時間"
    result.loc[last_idx, "不足数値"] = shortage

# =====================
# 最終行動
# =====================

for idx in result.index:
    girl = result.loc[idx, girl_col]
    ease = result.loc[idx, "会いやすさ"]
    auto = result.loc[idx, "自動配置"]

    if auto == "勉強確定":
        result.loc[idx, "最終行動"] = "勉強"
    elif girl == "勉強":
        result.loc[idx, "最終行動"] = "勉強"
    elif girl in ["授業", "バイト", "睡眠", "移動", "その他"]:
        result.loc[idx, "最終行動"] = girl
    elif girl == "空き" and ease == "◎":
        result.loc[idx, "最終行動"] = "会う"
    elif girl == "空き":
        result.loc[idx, "最終行動"] = "会ってもいい"
    else:
        result.loc[idx, "最終行動"] = "自由"

# =====================
# 自動配置結果
# =====================

st.subheader("自動配置結果")

st.dataframe(
    result.style.map(color_final, subset=["最終行動"]),
    use_container_width=True
)

# =====================
# まとめ
# =====================

summary = []

for day in days:
    d = result[result["曜日"] == day]

    study_hours = int((d["最終行動"] == "勉強").sum())
    meet_hours = int((d["最終行動"] == "会う").sum())
    maybe_hours = int((d["最終行動"] == "会ってもいい").sum())

    study_times = "、".join(
        d.loc[d["最終行動"] == "勉強", "時間"].astype(str).tolist()
    )

    meet_times = "、".join(
        d.loc[d["最終行動"] == "会う", "時間"].astype(str).tolist()
    )

    maybe_times = "、".join(
        d.loc[d["最終行動"] == "会ってもいい", "時間"].astype(str).tolist()
    )

    shortage_values = d["不足数値"].dropna()
    shortage = int(shortage_values.iloc[-1]) if not shortage_values.empty else 0

    summary.append({
        "曜日": day,
        f"{girl_col}合計勉強時間": study_hours,
        f"{boy_col}勉強時間": int((d[boy_col] == "勉強").sum()),
        "不足勉強時間": shortage,
        "会う時間": meet_hours,
        "会ってもいい時間": maybe_hours,
        "勉強時間帯": study_times,
        "会う時間帯": meet_times,
        "会ってもいい時間帯": maybe_times,
    })

summary_df = pd.DataFrame(summary)

# =====================
# カード表示
# =====================

st.subheader("曜日別まとめカード")

cols = st.columns(7)

for i, day in enumerate(days):
    d = summary_df[summary_df["曜日"] == day].iloc[0]

    study_block = (
        f"<p><b>勉強</b><br>{d['勉強時間帯']}</p>"
        if d["勉強時間帯"]
        else ""
    )

    meet_block = (
        f"<p><b>会う</b><br>{d['会う時間帯']}</p>"
        if d["会う時間帯"]
        else ""
    )

    maybe_block = (
        f"<p><b>会ってもいい</b><br>{d['会ってもいい時間帯']}</p>"
        if d["会ってもいい時間帯"]
        else ""
    )

    with cols[i]:
        st.markdown(
            f"""
            <div style="
                padding: 12px;
                border-radius: 12px;
                background-color: #f7f7f7;
                border: 1px solid #ddd;
                min-height: 260px;
            ">
            <h3 style="text-align:center;">{day}</h3>

            <p><b>{girl_col} 勉強</b>：{d[f"{girl_col}合計勉強時間"]}時間</p>
            <p><b>{boy_col} 勉強</b>：{d[f"{boy_col}勉強時間"]}時間</p>
            <p><b>会う</b>：{d["会う時間"]}時間</p>
            <p><b>会ってもいい</b>：{d["会ってもいい時間"]}時間</p>

            <hr>

            {study_block}
            {meet_block}
            {maybe_block}
            </div>
            """,
            unsafe_allow_html=True
        )

# =====================
# 週間タイムテーブル
# =====================

st.subheader("週間タイムテーブル")

calendar_df = result.pivot_table(
    index="時間",
    columns="曜日",
    values="最終行動",
    aggfunc="first"
)

calendar_df = calendar_df.reindex(index=time_order, columns=days)

st.dataframe(
    calendar_df.style.map(color_final),
    use_container_width=True
)