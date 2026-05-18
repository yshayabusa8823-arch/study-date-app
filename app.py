import streamlit as st
import pandas as pd
from datetime import datetime, time

st.set_page_config(page_title="勉強優先スケジュール管理")

st.title("勉強優先スケジュール管理アプリ")

# =====================
# 設定
# =====================

st.sidebar.header("設定")

weekday_min = st.sidebar.number_input("平日最低勉強時間", min_value=0, value=2)
weekend_min = st.sidebar.number_input("土日最低勉強時間", min_value=0, value=4)

days = ["月", "火", "水", "木", "金", "土", "日"]

uploaded = st.file_uploader("スケジュール管理表.xlsx をアップロード", type=["xlsx"])

girl_col = "彼女"
boy_col = "彼氏"

# =====================
# 関数
# =====================

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

else:
    rows = []
    for day in days:
        for h in range(8, 24):
            rows.append({
                "曜日": day,
                "時間": f"{h}:00",
                girl_col: "空き",
                boy_col: "空き",
                "会いやすさ": "○",
                "勉強優先度": "中",
            })

    df = pd.DataFrame(rows)


# =====================
# タブ
# =====================

tab_input, tab_result = st.tabs(["入力", "結果"])

# =====================
# 入力タブ
# =====================

with tab_input:
    st.subheader("予定入力・変更")

    selected_day = st.selectbox("編集する曜日", days)

    day_df = df[df["曜日"] == selected_day].copy()

    edited_day = st.data_editor(
        day_df,
        use_container_width=True,
        num_rows="dynamic",
        hide_index=True,
        column_config={
            "曜日": st.column_config.SelectboxColumn(options=days),
            girl_col: st.column_config.SelectboxColumn(
                options=["空き", "勉強", "授業", "バイト", "睡眠", "移動", "その他"]
            ),
            boy_col: st.column_config.SelectboxColumn(
                options=["空き", "勉強", "授業", "バイト", "睡眠", "移動", "その他"]
            ),
            "会いやすさ": st.column_config.SelectboxColumn(
                options=["◎", "○", "△", "×"]
            ),
            "勉強優先度": st.column_config.SelectboxColumn(
                options=["高", "中", "低"]
            ),
        }
    )

    other_df = df[df["曜日"] != selected_day].copy()
    edited = pd.concat([other_df, edited_day], ignore_index=True)

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

    result.loc[mask, f"{girl_col}勉強時間"] = (
        day_df[girl_col] == "勉強"
    ).astype(int)

    result.loc[mask, f"{boy_col}勉強時間"] = (
        day_df[boy_col] == "勉強"
    ).astype(int)

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
# まとめ作成
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
# 結果タブ
# =====================

with tab_result:
    st.subheader("曜日別まとめ")

    for day in days:
        d = summary_df[summary_df["曜日"] == day].iloc[0]

        with st.expander(f"{day}曜日", expanded=(day == "月")):
            st.write(f"**{girl_col} 勉強**：{d[f'{girl_col}合計勉強時間']}時間")
            st.write(f"**{boy_col} 勉強**：{d[f'{boy_col}勉強時間']}時間")
            st.write(f"**会う**：{d['会う時間']}時間")
            st.write(f"**会ってもいい**：{d['会ってもいい時間']}時間")

            if d["勉強時間帯"]:
                st.write(f"**勉強時間帯**：{d['勉強時間帯']}")

            if d["会う時間帯"]:
                st.write(f"**会う時間帯**：{d['会う時間帯']}")

            if d["会ってもいい時間帯"]:
                st.write(f"**会ってもいい時間帯**：{d['会ってもいい時間帯']}")

    st.subheader("週間タイムテーブル")

    time_order_from_data = result["時間"].drop_duplicates().tolist()

    calendar_df = result.pivot_table(
        index="時間",
        columns="曜日",
        values="最終行動",
        aggfunc="first"
    )

    calendar_df = calendar_df.reindex(
        index=time_order_from_data,
        columns=days
    )

    st.dataframe(
        calendar_df.style.map(color_final),
        use_container_width=True
    )

    with st.expander("詳細データを見る"):
        st.dataframe(
            result.style.map(color_final, subset=["最終行動"]),
            use_container_width=True
        )
