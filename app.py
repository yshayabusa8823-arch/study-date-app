import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from streamlit_autorefresh import st_autorefresh
from datetime import datetime, date
from zoneinfo import ZoneInfo

# =====================
# 基本設定
# =====================

st.set_page_config(page_title="Study Date", page_icon="📚", layout="centered")

CURRENT_SHEET = "current"
MASTER_SHEET = "master"
CARRYOVER_SHEET = "carryover"

days = ["月", "火", "水", "木", "金", "土", "日"]
weekday_map = {0: "月", 1: "火", 2: "水", 3: "木", 4: "金", 5: "土", 6: "日"}

now_jst = datetime.now(ZoneInfo("Asia/Tokyo"))
today_day = weekday_map[now_jst.weekday()]
tomorrow_day = days[(days.index(today_day) + 1) % 7]
remaining_days = days[days.index(today_day):]

plans = ["空き", "勉強", "勉強できなかった", "授業", "バイト", "ご飯", "用事", "睡眠", "移動", "その他"]
ease_options = ["◎", "○", "△", "×"]
priority_options = ["高", "中", "低"]

girl_col = "彼女"
boy_col = "彼氏"

exam_dates = {
    "中央": date(2026, 8, 22),
    "早稲田": date(2026, 8, 29),
    "慶應": date(2026, 9, 5),
}
countdowns = {k: (v - date.today()).days for k, v in exam_dates.items()}

# =====================
# CSS
# =====================

st.markdown("""
<style>
.block-container { padding-top: 1.2rem; padding-bottom: 5rem; }
h1, h2, h3 { letter-spacing: -0.03em; }
.card {
    padding: 18px; border-radius: 22px; background: #ffffff;
    border: 1px solid #eeeeee; box-shadow: 0 4px 14px rgba(0,0,0,0.05);
    margin-bottom: 16px;
}
.tag {
    display: inline-block; padding: 7px 11px; border-radius: 999px;
    margin: 3px; font-size: 14px;
}
.study { background: #fff2cc; }
.meet { background: #d9ead3; }
.warn { background: #fce5cd; }
.bad { background: #f4cccc; }
div.stButton > button {
    border-radius: 16px; min-height: 44px; font-size: 14px; width: 100%;
}
[data-testid="stMetric"] {
    background: #ffffff; padding: 14px; border-radius: 18px;
    border: 1px solid #eeeeee; box-shadow: 0 2px 8px rgba(0,0,0,0.04);
}
.stTabs [data-baseweb="tab-list"] { gap: 6px; }
.stTabs [data-baseweb="tab"] {
    border-radius: 999px; padding: 8px 14px; background-color: #f5f5f5;
}
</style>
""", unsafe_allow_html=True)

st.title("📚 Study Date")

# =====================
# サイドバー
# =====================

st.sidebar.header("設定")

user_role = st.sidebar.radio("使っている人", ["彼女", "彼氏"])
weekday_min = st.sidebar.number_input("平日最低勉強時間", min_value=0, value=5)
weekend_min = st.sidebar.number_input("土日最低勉強時間", min_value=0, value=7)

spreadsheet_url = st.sidebar.text_input(
    "Google Sheets URL",
    value="https://docs.google.com/spreadsheets/d/1-IXnv2wGZR6S4kXTTS0eB5EpuE7fepEQMtM72lZm-eQ/edit?gid=0#gid=0"
)

auto_refresh = st.sidebar.checkbox("自動更新する", value=True)

if auto_refresh:
    st_autorefresh(interval=60000, key="auto_refresh")

if st.sidebar.button("手動更新"):
    st.cache_data.clear()
    st.rerun()

# =====================
# Google Sheets
# =====================

@st.cache_resource
def connect_gsheet():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    credentials = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=scopes,
    )
    return gspread.authorize(credentials)


@st.cache_resource
def open_spreadsheet(url):
    client = connect_gsheet()
    return client.open_by_url(url)


def get_ws(sheet, name):
    return sheet.worksheet(name)


@st.cache_data(ttl=60)
def load_current_sheet(url):
    sheet = open_spreadsheet(url)
    ws = sheet.worksheet(CURRENT_SHEET)
    data = ws.get_all_records()
    return pd.DataFrame(data)


def read_carryover(sheet):
    try:
        ws = get_ws(sheet, CARRYOVER_SHEET)
        records = ws.get_all_records()
        for r in records:
            if str(r.get("key")) == "next_carryover":
                return int(r.get("value", 0))
    except Exception:
        pass
    return 0


def write_carryover(sheet, value):
    ws = get_ws(sheet, CARRYOVER_SHEET)
    ws.update("A1:B2", [["key", "value"], ["next_carryover", int(value)]])


def format_time_range(time_str):
    try:
        s = str(time_str).strip()
        start_hour = int(s.split(":")[0])
        end_hour = start_hour + 1
        return f"{start_hour:02d}:00-{end_hour:02d}:00"
    except Exception:
        return str(time_str)


def format_df_time_range(df, time_col="時間"):
    copied = df.copy()
    if time_col in copied.columns:
        copied[time_col] = copied[time_col].apply(format_time_range)
    return copied


def batch_update_rows(worksheet, updates):
    if updates:
        worksheet.batch_update(updates, value_input_option="USER_ENTERED")
    return len(updates)


def reset_current_from_master(sheet):
    master_ws = get_ws(sheet, MASTER_SHEET)
    current_ws = get_ws(sheet, CURRENT_SHEET)

    master_data = master_ws.get_all_values()
    current_ws.clear()

    if master_data:
        current_ws.update(f"A1:F{len(master_data)}", master_data)


def apply_carryover_to_current(sheet, carryover_hours):
    if carryover_hours <= 0:
        return 0

    current_ws = get_ws(sheet, CURRENT_SHEET)
    df = pd.DataFrame(current_ws.get_all_records())

    if df.empty:
        return 0

    candidates = []

    for idx, row in df.iterrows():
        if row.get("彼女") == "空き":
            priority = row.get("勉強優先度", "低")
            ease = row.get("会いやすさ", "○")
            score = priority_score(priority) * 10 + ease_score(ease)
            candidates.append((idx, score))

    candidates = sorted(candidates, key=lambda x: x[1])
    selected = candidates[:carryover_hours]

    updates = []

    for idx, _ in selected:
        row = df.loc[idx]
        sheet_row_number = idx + 2
        updates.append({
            "range": f"A{sheet_row_number}:F{sheet_row_number}",
            "values": [[
                row["曜日"],
                row["時間"],
                "勉強",
                row["彼氏"],
                row["会いやすさ"],
                row["勉強優先度"],
            ]]
        })

    return batch_update_rows(current_ws, updates)


def weekly_reset_if_needed(sheet):
    now = datetime.now(ZoneInfo("Asia/Tokyo"))
    today_str = now.strftime("%Y-%m-%d")

    # 月曜0時以降、まだ今週リセットしていなければ実行
    # Streamlitは常時起動ではないため、誰かが開いたタイミングで実行される
    if now.weekday() != 0:
        return

    last_reset = st.session_state.get("last_reset_date")

    if last_reset == today_str:
        return

    carryover_hours = read_carryover(sheet)

    reset_current_from_master(sheet)

    applied = apply_carryover_to_current(sheet, carryover_hours)

    write_carryover(sheet, max(0, carryover_hours - applied))

    st.session_state["last_reset_date"] = today_str
    st.cache_data.clear()


def update_one_row(worksheet, row_number, row_values):
    worksheet.update(f"A{row_number}:F{row_number}", [row_values])


# =====================
# ロジック
# =====================

def ease_label(ease):
    return {"×": "最優先", "△": "高", "○": "中", "◎": "低"}.get(ease, "")


def ease_score(ease):
    return {"×": 1, "△": 2, "○": 3, "◎": 4}.get(ease, 9)


def priority_score(priority):
    return {"高": 1, "中": 2, "低": 3}.get(priority, 9)


def color_final(val):
    colors = {
        "勉強": "background-color: #fff2cc",
        "振替勉強": "background-color: #fce5cd",
        "勉強できなかった": "background-color: #f4cccc",
        "会う": "background-color: #b7e1cd",
        "会ってもいい": "background-color: #d9ead3",
        "彼氏予定あり": "background-color: #eeeeee",
        "授業": "background-color: #f4cccc",
        "バイト": "background-color: #ead1dc",
        "ご飯": "background-color: #ffe599",
        "用事": "background-color: #d0e0e3",
        "睡眠": "background-color: #cfe2f3",
        "移動": "background-color: #eadcf8",
    }
    return colors.get(val, "")


def calculate_result(df, previous_carryover):
    result = df.copy()

    result["判定"] = ""
    result["彼女勉強時間"] = 0
    result["彼氏勉強時間"] = 0
    result["自動勉強候補"] = ""
    result["勉強候補順"] = pd.NA
    result["自動配置"] = ""
    result["最終行動"] = ""

    weekly_required = weekday_min * 5 + weekend_min * 2
    actual_study_total = (result["彼女"] == "勉強").sum()
    missed_total = (result["彼女"] == "勉強できなかった").sum()

    shortage_after_missed = max(
        0,
        weekly_required + previous_carryover - actual_study_total
    )

    all_candidates = []

    for day in days:
        mask = result["曜日"] == day
        day_df = result[mask].copy()

        if day_df.empty:
            continue

        result.loc[mask, "彼女勉強時間"] = (day_df["彼女"] == "勉強").astype(int)
        result.loc[mask, "彼氏勉強時間"] = (day_df["彼氏"] == "勉強").astype(int)

        for idx in day_df.index:
            girl = result.loc[idx, "彼女"]
            boy = result.loc[idx, "彼氏"]
            ease = result.loc[idx, "会いやすさ"]
            priority = result.loc[idx, "勉強優先度"]

            if girl == "勉強":
                result.loc[idx, "判定"] = "勉強確定"
            elif girl == "勉強できなかった":
                result.loc[idx, "判定"] = "最低割れなら振替必要"
            elif girl in ["授業", "バイト", "ご飯", "用事", "睡眠", "移動", "その他"]:
                result.loc[idx, "判定"] = "予定優先"
            elif girl == "空き" and boy == "勉強":
                result.loc[idx, "判定"] = "勉強候補"
            elif girl == "空き" and boy != "空き":
                result.loc[idx, "判定"] = "彼氏予定あり"
            elif girl == "空き":
                result.loc[idx, "判定"] = "勉強優先寄り"

            if girl == "空き" and day in remaining_days:
                result.loc[idx, "自動勉強候補"] = ease_label(ease)
                score = priority_score(priority) * 10 + ease_score(ease)
                all_candidates.append((idx, score))

    all_candidates = sorted(all_candidates, key=lambda x: x[1])

    available_candidate_count = len(all_candidates)
    auto_place_count = min(shortage_after_missed, available_candidate_count)
    next_carryover = max(0, shortage_after_missed - available_candidate_count)

    for order, (idx, score) in enumerate(all_candidates, start=1):
        result.loc[idx, "勉強候補順"] = order
        if order <= auto_place_count:
            result.loc[idx, "自動配置"] = "振替勉強"

    for idx in result.index:
        girl = result.loc[idx, "彼女"]
        boy = result.loc[idx, "彼氏"]
        ease = result.loc[idx, "会いやすさ"]
        auto = result.loc[idx, "自動配置"]

        if auto == "振替勉強":
            result.loc[idx, "最終行動"] = "振替勉強"
        elif girl == "勉強":
            result.loc[idx, "最終行動"] = "勉強"
        elif girl == "勉強できなかった":
            result.loc[idx, "最終行動"] = "勉強できなかった"
        elif girl in ["授業", "バイト", "ご飯", "用事", "睡眠", "移動", "その他"]:
            result.loc[idx, "最終行動"] = girl
        elif girl == "空き" and boy == "空き" and ease == "◎":
            result.loc[idx, "最終行動"] = "会う"
        elif girl == "空き" and boy == "空き":
            result.loc[idx, "最終行動"] = "会ってもいい"
        elif girl == "空き" and boy != "空き":
            result.loc[idx, "最終行動"] = "彼氏予定あり"
        else:
            result.loc[idx, "最終行動"] = "自由"

    stats = {
        "weekly_required": int(weekly_required),
        "previous_carryover": int(previous_carryover),
        "actual_study_total": int(actual_study_total),
        "missed_total": int(missed_total),
        "shortage_after_missed": int(shortage_after_missed),
        "available_candidate_count": int(available_candidate_count),
        "auto_place_count": int(auto_place_count),
        "next_carryover": int(next_carryover),
    }

    return result, stats


def make_summary(result):
    summary = []

    for day in days:
        d = result[result["曜日"] == day]

        summary.append({
            "曜日": day,
            "彼女合計勉強時間": int(((d["最終行動"] == "勉強") | (d["最終行動"] == "振替勉強")).sum()),
            "彼氏勉強時間": int((d["彼氏"] == "勉強").sum()),
            "勉強できなかった時間": int((d["最終行動"] == "勉強できなかった").sum()),
            "振替勉強時間": int((d["最終行動"] == "振替勉強").sum()),
            "会ってもいい時間": int((d["最終行動"] == "会ってもいい").sum()),
            "彼氏予定あり時間": int((d["最終行動"] == "彼氏予定あり").sum()),
            "勉強時間帯": "、".join(format_time_range(t) for t in d.loc[d["最終行動"] == "勉強", "時間"].astype(str).tolist()),
            "振替勉強時間帯": "、".join(format_time_range(t) for t in d.loc[d["最終行動"] == "振替勉強", "時間"].astype(str).tolist()),
            "勉強できなかった時間帯": "、".join(format_time_range(t) for t in d.loc[d["最終行動"] == "勉強できなかった", "時間"].astype(str).tolist()),
            "会ってもいい時間帯": "、".join(format_time_range(t) for t in d.loc[d["最終行動"] == "会ってもいい", "時間"].astype(str).tolist()),
            "彼氏予定あり時間帯": "、".join(format_time_range(t) for t in d.loc[d["最終行動"] == "彼氏予定あり", "時間"].astype(str).tolist()),
        })

    return pd.DataFrame(summary)


def extract_day_data(result, target_day):
    day_df = result[result["曜日"] == target_day].copy()

    study = day_df[
        (day_df["最終行動"] == "勉強")
        | (day_df["最終行動"] == "振替勉強")
    ][["時間", "最終行動"]]

    maybe = day_df[day_df["最終行動"] == "会ってもいい"][["時間"]]
    missed = day_df[day_df["最終行動"] == "勉強できなかった"][["時間"]]

    return study, maybe, missed


def apply_replacements_selected_to_sheet(worksheet, result_df, selected_indexes):
    updates = []

    for idx in selected_indexes:
        row = result_df.loc[idx]
        sheet_row_number = idx + 2

        updates.append({
            "range": f"A{sheet_row_number}:F{sheet_row_number}",
            "values": [[
                row["曜日"],
                row["時間"],
                "勉強",
                row["彼氏"],
                row["会いやすさ"],
                row["勉強優先度"],
            ]]
        })

    return batch_update_rows(worksheet, updates)


def apply_status_selected_to_sheet(worksheet, df, selected_indexes, new_status):
    updates = []

    for idx in selected_indexes:
        row = df.loc[idx]
        sheet_row_number = idx + 2

        updates.append({
            "range": f"A{sheet_row_number}:F{sheet_row_number}",
            "values": [[
                row["曜日"],
                row["時間"],
                new_status,
                row["彼氏"],
                row["会いやすさ"],
                row["勉強優先度"],
            ]]
        })

    return batch_update_rows(worksheet, updates)


# =====================
# データ読み込み
# =====================

try:
    sheet = open_spreadsheet(spreadsheet_url)
    weekly_reset_if_needed(sheet)

    current_ws = get_ws(sheet, CURRENT_SHEET)
    previous_carryover = read_carryover(sheet)

    df = load_current_sheet(spreadsheet_url)

except Exception as e:
    st.error("Google Sheetsの読み込みに失敗しました。API上限の可能性もあります。少し時間を置いてから、左の「手動更新」を押してください。")
    st.exception(e)
    st.stop()

required_cols = ["曜日", "時間", "彼女", "彼氏", "会いやすさ", "勉強優先度"]
missing_cols = [c for c in required_cols if c not in df.columns]

if missing_cols:
    st.error(f"Google Sheetsに必要な列が足りません：{missing_cols}")
    st.stop()

df = df[required_cols].copy()
df = df[df["曜日"].isin(days)].copy()

result, stats = calculate_result(df, previous_carryover)
summary_df = make_summary(result)

replacement_plan = result[result["最終行動"] == "振替勉強"][["曜日", "時間"]]
maybe_meet_plan = result[result["最終行動"] == "会ってもいい"][["曜日", "時間"]]

study_plan = result[
    (result["最終行動"] == "勉強")
    | (result["最終行動"] == "振替勉強")
][["曜日", "時間", "最終行動"]]

# =====================
# タブ
# =====================

tab_home, tab_input, tab_week, tab_analysis = st.tabs(
    ["🏠 今日", "✏️ 入力", "📅 週間", "📊 分析"]
)

# =====================
# ホーム
# =====================

with tab_home:
    view_day_label = st.radio("表示する日", ["今日", "明日"], horizontal=True)

    target_day = today_day if view_day_label == "今日" else tomorrow_day
    target_study, target_maybe, target_missed = extract_day_data(result, target_day)

    target_study_times = target_study["時間"].astype(str).tolist()
    label_prefix = "今日" if view_day_label == "今日" else "明日"

    if stats["shortage_after_missed"] > 0 and target_study_times:
        suggested_times = [format_time_range(t) for t in target_study_times[:3]]
        suggested_hours = len(target_study_times)
        hero_title = f"📚 {label_prefix}は勉強優先"
        hero_message = f"最低勉強時間まであと{stats['shortage_after_missed']}時間。{label_prefix}は {'、'.join(suggested_times)} あたりを中心に、合計{suggested_hours}時間勉強しよう！"
        hero_color = "#fff7e6"
    elif stats["shortage_after_missed"] > 0:
        hero_title = "⚠️ 今週の勉強時間が不足中"
        hero_message = f"最低勉強時間まであと{stats['shortage_after_missed']}時間。週間ページで振替候補を確認しよう。"
        hero_color = "#fff1f0"
    elif target_study_times:
        suggested_times = [format_time_range(t) for t in target_study_times[:3]]
        suggested_hours = len(target_study_times)
        hero_title = f"📚 {label_prefix}の勉強ペースは順調"
        hero_message = f"{label_prefix}は {'、'.join(suggested_times)} あたりを中心に、合計{suggested_hours}時間勉強しよう！"
        hero_color = "#f6ffed"
    else:
        hero_title = f"📘 {label_prefix}の勉強ペースは余裕あり"
        hero_message = f"{label_prefix}は追加の振替勉強は必要なさそうです。"
        hero_color = "#f5f7ff"

    st.markdown(f"""
    <div style="padding:24px;border-radius:28px;background:{hero_color};border:1px solid #eeeeee;margin-bottom:20px;box-shadow:0 4px 14px rgba(0,0,0,0.05);">
        <div style="color:#666;font-size:14px;margin-bottom:8px;">{label_prefix}の提案：{target_day}曜日</div>
        <div style="font-size:34px;font-weight:800;line-height:1.2;margin-bottom:10px;">{hero_title}</div>
        <div style="font-size:17px;line-height:1.7;color:#444;">{hero_message}</div>
    </div>
    """, unsafe_allow_html=True)

    st.subheader("📅 ロースクール試験まで")
    cols = st.columns(3)

    for i, school_name in enumerate(["中央", "早稲田", "慶應"]):
        days_left = countdowns[school_name]

        with cols[i]:
            if days_left <= 100:
                card_color = "linear-gradient(135deg,#ffeded,#ffe3e3)"
                border = "#ff9e9e"
                title_color = "#d32f2f"
                num_color = "#b71c1c"
                icon = "🔥"
                note = "100日切り"
            else:
                card_color = "#ffffff"
                border = "#eeeeee"
                title_color = "#555"
                num_color = "#222"
                icon = "🎓"
                note = "試験までカウントダウン中"

            st.markdown(f"""
            <div style="padding:18px;border-radius:24px;background:{card_color};border:1px solid {border};box-shadow:0 4px 14px rgba(0,0,0,0.05);min-height:150px;">
                <div style="font-size:15px;color:{title_color};font-weight:700;margin-bottom:10px;">{icon} {school_name}ロー</div>
                <div style="font-size:34px;font-weight:800;color:{num_color};line-height:1.1;">あと{days_left}日</div>
                <div style="margin-top:14px;font-size:14px;color:{title_color};font-weight:600;">{note}</div>
            </div>
            """, unsafe_allow_html=True)

    st.metric("前週繰り越し", f"{stats['previous_carryover']}時間")
    st.metric("週合計目標との差", f"{stats['actual_study_total'] - stats['weekly_required']}時間")
    st.metric("来週繰り越し", f"{stats['next_carryover']}時間")

    if stats["shortage_after_missed"] > 0:
        st.error(f"最低勉強時間を {stats['shortage_after_missed']}時間 下回っています。")
    else:
        st.success("最低勉強時間は満たせています。")

    st.subheader(f"📚 {label_prefix}の勉強")
    if not target_study.empty:
        for _, r in target_study.iterrows():
            tag_class = "warn" if r["最終行動"] == "振替勉強" else "study"
            st.markdown(
                f'<span class="tag {tag_class}">{format_time_range(r["時間"])} {r["最終行動"]}</span>',
                unsafe_allow_html=True
            )
    else:
        st.caption(f"{label_prefix}の勉強予定はありません。")

    st.subheader(f"🤝 {label_prefix}会ってもいい時間")
    if not target_maybe.empty:
        for _, r in target_maybe.iterrows():
            st.markdown(
                f'<span class="tag meet">{format_time_range(r["時間"])}</span>',
                unsafe_allow_html=True
            )
    else:
        st.caption(f"{label_prefix}の会ってもいい時間はありません。")

    if not target_missed.empty:
        st.subheader(f"⚠️ {label_prefix}の勉強できなかった時間")
        for _, r in target_missed.iterrows():
            st.markdown(
                f'<span class="tag bad">{format_time_range(r["時間"])}</span>',
                unsafe_allow_html=True
            )

    st.subheader("🔁 今週の振替提案")

    if not replacement_plan.empty:
        selected_replacements = []

        for idx, row in result[result["最終行動"] == "振替勉強"].iterrows():
            label = f'{row["曜日"]} {format_time_range(row["時間"])}'
            use_it = st.checkbox(
                f"{label} をスケジュールに反映する",
                key=f"replace_{idx}"
            )
            if use_it:
                selected_replacements.append(idx)

        if st.button("選択した振替提案だけ反映する"):
            try:
                updated_count = apply_replacements_selected_to_sheet(
                    current_ws,
                    result,
                    selected_replacements
                )
                write_carryover(sheet, stats["next_carryover"])
                st.cache_data.clear()
                st.success(f"{updated_count}件の振替提案を反映しました。")
                st.rerun()
            except Exception as e:
                st.error("振替提案の反映に失敗しました。少し時間を置いて再試行して。")
                st.exception(e)
    else:
        st.info("今週の振替提案はありません。")

# =====================
# 入力
# =====================

with tab_input:
    st.subheader("予定を変更する")

    selected_day = st.selectbox("曜日を選ぶ", days)
    day_df = df[df["曜日"] == selected_day].copy()

    selected_time = st.selectbox(
        "時間を選ぶ",
        day_df["時間"].astype(str).tolist(),
        format_func=format_time_range
    )

    row_mask = (
        (df["曜日"] == selected_day)
        & (df["時間"].astype(str) == str(selected_time))
    )

    row_index = df[row_mask].index[0]
    row = df.loc[row_index]
    sheet_row_number = row_index + 2

    target_col = girl_col if user_role == "彼女" else boy_col

    st.markdown(f"""
    <div class="card">
        <div class="muted">選択中</div>
        <h2>{selected_day}曜日 {format_time_range(selected_time)}</h2>
        <p>彼女：<b>{row[girl_col]}</b> / 彼氏：<b>{row[boy_col]}</b></p>
        <p>会いやすさ：<b>{row["会いやすさ"]}</b> / 勉強優先度：<b>{row["勉強優先度"]}</b></p>
    </div>
    """, unsafe_allow_html=True)

    st.write(f"### {user_role}予定を変更")

    cols = st.columns(3)

    for i, plan in enumerate(plans):
        with cols[i % 3]:
            if st.button(plan, key=f"{selected_day}_{selected_time}_{target_col}_{plan}"):
                new_girl = row[girl_col]
                new_boy = row[boy_col]

                if user_role == "彼女":
                    new_girl = plan
                else:
                    new_boy = plan

                update_one_row(
                    current_ws,
                    sheet_row_number,
                    [
                        row["曜日"],
                        row["時間"],
                        new_girl,
                        new_boy,
                        row["会いやすさ"],
                        row["勉強優先度"],
                    ],
                )

                st.cache_data.clear()
                st.success(f"{format_time_range(selected_time)} を {plan} に変更しました")
                st.rerun()

    with st.expander("時間割から一括変更する", expanded=True):
        st.write("### 変更したい曜日を選ぶ")

        bulk_day = st.radio(
            "曜日",
            days,
            horizontal=True,
            key="bulk_day_selector"
        )

        new_status = st.radio(
            "選択した時間を何に変更する？",
            ["勉強", "勉強できなかった"],
            horizontal=True,
            key="bulk_status_selector"
        )

        st.caption("変更したい時間をタップして選んでから、下の反映ボタンを押す。")

        bulk_day_df = df[df["曜日"] == bulk_day].copy()
        selected_indexes = []

        for idx, row in bulk_day_df.iterrows():
            current_status = row["彼女"]
            time_label = format_time_range(row["時間"])

            badge = {
                "勉強": "📚",
                "勉強できなかった": "⚠️",
                "空き": "○",
                "授業": "🏫",
                "バイト": "💼",
                "ご飯": "🍚",
                "用事": "📝",
                "睡眠": "😴",
                "移動": "🚃",
            }.get(current_status, "・")

            checked = st.checkbox(
                f"{badge} {time_label}　現在：{current_status}",
                key=f"bulk_select_{bulk_day}_{row['時間']}_{idx}"
            )

            if checked:
                selected_indexes.append(idx)

        st.write(f"選択中：{len(selected_indexes)}件")

        if st.button(f"選択した時間を「{new_status}」に変更する"):
            try:
                updated_count = apply_status_selected_to_sheet(
                    current_ws,
                    df,
                    selected_indexes,
                    new_status
                )
                st.cache_data.clear()
                st.success(f"{updated_count}件を「{new_status}」に変更しました。")
                st.rerun()
            except Exception as e:
                st.error("一括変更に失敗しました。少し時間を置いて再試行して。")
                st.exception(e)

    with st.expander("会いやすさ・勉強優先度を変更"):
        st.write("会いやすさ")
        ease_cols = st.columns(4)

        for i, ease in enumerate(ease_options):
            with ease_cols[i]:
                if st.button(ease, key=f"{selected_day}_{selected_time}_ease_{ease}"):
                    update_one_row(
                        current_ws,
                        sheet_row_number,
                        [
                            row["曜日"],
                            row["時間"],
                            row[girl_col],
                            row[boy_col],
                            ease,
                            row["勉強優先度"],
                        ],
                    )

                    st.cache_data.clear()
                    st.success(f"会いやすさを {ease} に変更しました")
                    st.rerun()

        st.write("勉強優先度")
        pri_cols = st.columns(3)

        for i, priority in enumerate(priority_options):
            with pri_cols[i]:
                if st.button(priority, key=f"{selected_day}_{selected_time}_priority_{priority}"):
                    update_one_row(
                        current_ws,
                        sheet_row_number,
                        [
                            row["曜日"],
                            row["時間"],
                            row[girl_col],
                            row[boy_col],
                            row["会いやすさ"],
                            priority,
                        ],
                    )

                    st.cache_data.clear()
                    st.success(f"勉強優先度を {priority} に変更しました")
                    st.rerun()

    with st.expander("この曜日の予定を確認"):
        st.dataframe(format_df_time_range(day_df), use_container_width=True, hide_index=True)

# =====================
# 週間
# =====================

with tab_week:
    st.subheader("📅 週間タイムテーブル")
    st.caption(f"今日：{today_day}曜日 / 今週の残り対象：{''.join(remaining_days)}")

    time_order_from_data = result["時間"].drop_duplicates().tolist()

    calendar_df = result.pivot_table(
        index="時間",
        columns="曜日",
        values="最終行動",
        aggfunc="first"
    )

    calendar_df = calendar_df.reindex(index=time_order_from_data, columns=days)
    calendar_df.index = [format_time_range(t) for t in calendar_df.index]

    st.dataframe(calendar_df.style.map(color_final), use_container_width=True)

    st.subheader("会ってもいい時間")

    if not maybe_meet_plan.empty:
        st.dataframe(format_df_time_range(maybe_meet_plan), use_container_width=True, hide_index=True)
    else:
        st.info("会ってもいい時間はありません。")

# =====================
# 分析
# =====================

with tab_analysis:
    st.subheader("📊 今週の勉強調整")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("週最低勉強時間", f"{stats['weekly_required']}時間")

    with col2:
        st.metric("前週繰り越し", f"{stats['previous_carryover']}時間")

    with col3:
        st.metric("現在の勉強予定", f"{stats['actual_study_total']}時間")

    col4, col5, col6 = st.columns(3)

    with col4:
        st.metric("週合計目標との差", f"{stats['actual_study_total'] - stats['weekly_required']}時間")

    with col5:
        st.metric("今週に入れる振替", f"{stats['auto_place_count']}時間")

    with col6:
        st.metric("来週繰り越し", f"{stats['next_carryover']}時間")

    if stats["shortage_after_missed"] > 0:
        st.warning(f"最低勉強時間を {stats['shortage_after_missed']}時間 下回っています。")
    else:
        st.success("最低勉強時間は満たせています。")

    if st.button("現在の来週繰り越し時間をcarryoverに保存する"):
        write_carryover(sheet, stats["next_carryover"])
        st.success(f"来週繰り越し時間 {stats['next_carryover']}時間 を保存しました。")

    st.subheader("おすすめ提案")

    tab_study, tab_maybe = st.tabs(["勉強する時間", "会ってもいい時間"])

    with tab_study:
        if not study_plan.empty:
            st.dataframe(
                format_df_time_range(study_plan.rename(columns={"最終行動": "種類"})),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("勉強予定はありません。")

    with tab_maybe:
        if not maybe_meet_plan.empty:
            st.dataframe(format_df_time_range(maybe_meet_plan), use_container_width=True, hide_index=True)
        else:
            st.info("会ってもいい時間はありません。")

    st.subheader("曜日別まとめ")

    for day in days:
        d = summary_df[summary_df["曜日"] == day].iloc[0]

        with st.expander(f"{day}曜日", expanded=(day == today_day)):
            metric1, metric2, metric3 = st.columns(3)

            with metric1:
                st.metric("彼女 勉強", f"{d['彼女合計勉強時間']}時間")

            with metric2:
                st.metric("振替勉強", f"{d['振替勉強時間']}時間")

            with metric3:
                st.metric("会ってもいい", f"{d['会ってもいい時間']}時間")

            detail_df = pd.DataFrame({
                "項目": ["勉強時間帯", "勉強できなかった", "振替勉強", "会ってもいい", "彼氏予定あり"],
                "内容": [
                    d["勉強時間帯"],
                    d["勉強できなかった時間帯"],
                    d["振替勉強時間帯"],
                    d["会ってもいい時間帯"],
                    d["彼氏予定あり時間帯"],
                ],
            })

            st.dataframe(detail_df, use_container_width=True, hide_index=True)

    with st.expander("詳細データを見る"):
        detail_result = result.copy()
        detail_result["時間"] = detail_result["時間"].apply(format_time_range)

        st.dataframe(
            detail_result.style.map(color_final, subset=["最終行動"]),
            use_container_width=True
        )
