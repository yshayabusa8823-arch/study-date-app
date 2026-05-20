import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from streamlit_autorefresh import st_autorefresh
from datetime import datetime
from zoneinfo import ZoneInfo

# =====================
# ページ設定
# =====================

st.set_page_config(
    page_title="Study Date",
    page_icon="📚",
    layout="centered"
)

# =====================
# CSS
# =====================

st.markdown("""
<style>
.block-container {
    padding-top: 1.2rem;
    padding-bottom: 5rem;
}

h1, h2, h3 {
    letter-spacing: -0.03em;
}

.card {
    padding: 18px;
    border-radius: 22px;
    background: #ffffff;
    border: 1px solid #eeeeee;
    box-shadow: 0 4px 14px rgba(0,0,0,0.05);
    margin-bottom: 16px;
}

.metric-big {
    font-size: 42px;
    font-weight: 800;
    line-height: 1.1;
}

.muted {
    color: #777;
    font-size: 14px;
}

.tag {
    display: inline-block;
    padding: 7px 11px;
    border-radius: 999px;
    background: #f4f4f5;
    margin: 3px;
    font-size: 14px;
}

.study {
    background: #fff2cc;
}

.meet {
    background: #d9ead3;
}

.warn {
    background: #fce5cd;
}

.bad {
    background: #f4cccc;
}

.ok {
    background: #d9ead3;
}

div.stButton > button {
    border-radius: 16px;
    min-height: 44px;
    font-size: 15px;
    width: 100%;
}

[data-testid="stMetric"] {
    background: #ffffff;
    padding: 14px;
    border-radius: 18px;
    border: 1px solid #eeeeee;
    box-shadow: 0 2px 8px rgba(0,0,0,0.04);
}

.stTabs [data-baseweb="tab-list"] {
    gap: 6px;
}

.stTabs [data-baseweb="tab"] {
    border-radius: 999px;
    padding: 8px 14px;
    background-color: #f5f5f5;
}
</style>
""", unsafe_allow_html=True)

# =====================
# 基本設定
# =====================

st.title("📚 Study Date")

days = ["月", "火", "水", "木", "金", "土", "日"]

weekday_map = {
    0: "月",
    1: "火",
    2: "水",
    3: "木",
    4: "金",
    5: "土",
    6: "日",
}

today_day = weekday_map[
    datetime.now(ZoneInfo("Asia/Tokyo")).weekday()
]

remaining_days = days[days.index(today_day):]

plans = [
    "空き",
    "勉強",
    "勉強できなかった",
    "授業",
    "バイト",
    "ご飯",
    "用事",
    "睡眠",
    "移動",
    "その他",
]

ease_options = ["◎", "○", "△", "×"]
priority_options = ["高", "中", "低"]

girl_col = "彼女"
boy_col = "彼氏"

# =====================
# サイドバー
# =====================

st.sidebar.header("設定")

user_role = st.sidebar.radio(
    "使っている人",
    ["彼女", "彼氏"]
)

weekday_min = st.sidebar.number_input(
    "平日最低勉強時間",
    min_value=0,
    value=5
)

weekend_min = st.sidebar.number_input(
    "土日最低勉強時間",
    min_value=0,
    value=7
)

spreadsheet_url = st.sidebar.text_input(
    "Google Sheets URL",
    value="https://docs.google.com/spreadsheets/d/1-IXnv2wGZR6S4kXTTS0eB5EpuE7fepEQMtM72lZm-eQ/edit?gid=0#gid=0"
)

worksheet_name = st.sidebar.text_input(
    "シート名",
    value="予定入力"
)

auto_refresh = st.sidebar.checkbox(
    "自動更新する",
    value=True
)

if auto_refresh:
    st_autorefresh(
        interval=15000,
        key="auto_refresh"
    )

# =====================
# Google Sheets 接続
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


@st.cache_data(ttl=10)
def load_sheet_cached(url, sheet_name):
    client = connect_gsheet()
    sheet = client.open_by_url(url)
    worksheet = sheet.worksheet(sheet_name)
    data = worksheet.get_all_records()
    return pd.DataFrame(data)


def get_worksheet():
    client = connect_gsheet()
    sheet = client.open_by_url(spreadsheet_url)
    return sheet.worksheet(worksheet_name)


def update_one_row(worksheet, row_number, row_values):
    worksheet.update(
        f"A{row_number}:F{row_number}",
        [row_values]
    )

# =====================
# ロジック関数
# =====================

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
    if val == "振替勉強":
        return "background-color: #fce5cd"
    if val == "勉強できなかった":
        return "background-color: #f4cccc"
    if val == "会う":
        return "background-color: #b7e1cd"
    if val == "会ってもいい":
        return "background-color: #d9ead3"
    if val == "彼氏予定あり":
        return "background-color: #eeeeee"
    if val == "授業":
        return "background-color: #f4cccc"
    if val == "バイト":
        return "background-color: #ead1dc"
    if val == "ご飯":
        return "background-color: #ffe599"
    if val == "用事":
        return "background-color: #d0e0e3"
    if val == "睡眠":
        return "background-color: #cfe2f3"
    if val == "移動":
        return "background-color: #eadcf8"
    return ""


def calculate_result(df):
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
        weekly_required - actual_study_total
    )

    all_candidates = []

    for day in days:
        mask = result["曜日"] == day
        day_df = result[mask].copy()

        if day_df.empty:
            continue

        result.loc[mask, "彼女勉強時間"] = (
            day_df["彼女"] == "勉強"
        ).astype(int)

        result.loc[mask, "彼氏勉強時間"] = (
            day_df["彼氏"] == "勉強"
        ).astype(int)

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

    all_candidates = sorted(
        all_candidates,
        key=lambda x: x[1]
    )

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
            "彼女合計勉強時間": int(
                ((d["最終行動"] == "勉強") | (d["最終行動"] == "振替勉強")).sum()
            ),
            "彼氏勉強時間": int((d["彼氏"] == "勉強").sum()),
            "勉強できなかった時間": int((d["最終行動"] == "勉強できなかった").sum()),
            "振替勉強時間": int((d["最終行動"] == "振替勉強").sum()),
            "会ってもいい時間": int((d["最終行動"] == "会ってもいい").sum()),
            "彼氏予定あり時間": int((d["最終行動"] == "彼氏予定あり").sum()),
            "勉強時間帯": "、".join(
                d.loc[d["最終行動"] == "勉強", "時間"].astype(str).tolist()
            ),
            "振替勉強時間帯": "、".join(
                d.loc[d["最終行動"] == "振替勉強", "時間"].astype(str).tolist()
            ),
            "勉強できなかった時間帯": "、".join(
                d.loc[d["最終行動"] == "勉強できなかった", "時間"].astype(str).tolist()
            ),
            "会ってもいい時間帯": "、".join(
                d.loc[d["最終行動"] == "会ってもいい", "時間"].astype(str).tolist()
            ),
            "彼氏予定あり時間帯": "、".join(
                d.loc[d["最終行動"] == "彼氏予定あり", "時間"].astype(str).tolist()
            ),
        })

    return pd.DataFrame(summary)

# =====================
# データ読み込み
# =====================

try:
    df = load_sheet_cached(spreadsheet_url, worksheet_name)
    worksheet = get_worksheet()

except Exception as e:
    st.error("Google Sheetsの読み込みに失敗しました。URL・シート名・Secrets・共有権限を確認して。")
    st.exception(e)
    st.stop()

required_cols = [
    "曜日",
    "時間",
    "彼女",
    "彼氏",
    "会いやすさ",
    "勉強優先度",
]

missing_cols = [
    c for c in required_cols
    if c not in df.columns
]

if missing_cols:
    st.error(
        f"Google Sheetsに必要な列が足りません：{missing_cols}"
    )
    st.stop()

df = df[required_cols].copy()
df = df[df["曜日"].isin(days)].copy()

result, stats = calculate_result(df)
summary_df = make_summary(result)

# =====================
# 便利データ
# =====================

today_df = result[result["曜日"] == today_day].copy()

today_study = today_df[
    (today_df["最終行動"] == "勉強")
    | (today_df["最終行動"] == "振替勉強")
][["時間", "最終行動"]]

today_maybe = today_df[
    today_df["最終行動"] == "会ってもいい"
][["時間"]]

today_missed = today_df[
    today_df["最終行動"] == "勉強できなかった"
][["時間"]]

replacement_plan = result[
    result["最終行動"] == "振替勉強"
][["曜日", "時間"]]

maybe_meet_plan = result[
    result["最終行動"] == "会ってもいい"
][["曜日", "時間"]]

study_plan = result[
    (result["最終行動"] == "勉強")
    | (result["最終行動"] == "振替勉強")
][["曜日", "時間", "最終行動"]]

# =====================
# タブ構成
# =====================

tab_home, tab_input, tab_week, tab_analysis = st.tabs(
    ["🏠 今日", "✏️ 入力", "📅 週間", "📊 分析"]
)

# =====================
# ホーム
# =====================

with tab_home:
    today_study_times = today_study["時間"].astype(str).tolist()
    today_meet_times = today_maybe["時間"].astype(str).tolist()

    if stats["shortage_after_missed"] > 0 and today_study_times:
        hero_title = "📚 今日は勉強優先"
        hero_message = (
            f"最低勉強時間まであと{stats['shortage_after_missed']}時間。"
            f"今日は {'、'.join(today_study_times[:3])} あたりで勉強しよう。"
        )
        hero_color = "#fff7e6"

    elif stats["shortage_after_missed"] > 0:
        hero_title = "⚠️ 今週の勉強時間が不足中"
        hero_message = (
            f"最低勉強時間まであと{stats['shortage_after_missed']}時間。"
            f"今日入れられる勉強時間は少なそうだから、週間ページで振替候補を確認しよう。"
        )
        hero_color = "#fff1f0"

    elif today_meet_times:
        hero_title = "❤️ 今日は会いやすい日"
        hero_message = (
            f"最低勉強時間は達成ペース。"
            f"今日は {'、'.join(today_meet_times[:3])} が会ってもいい時間です。"
        )
        hero_color = "#f6ffed"

    else:
        hero_title = "🌙 今日は予定確認だけでOK"
        hero_message = (
            "最低勉強時間は達成ペース。"
            "今日は無理に予定を増やさなくても大丈夫そうです。"
        )
        hero_color = "#f5f7ff"

    st.markdown(f"""
    <div style="
        padding: 24px;
        border-radius: 28px;
        background: {hero_color};
        border: 1px solid #eeeeee;
        margin-bottom: 20px;
        box-shadow: 0 4px 14px rgba(0,0,0,0.05);
    ">
        <div style="color:#666; font-size:14px; margin-bottom:8px;">
            今日の提案
        </div>
        <div style="font-size:34px; font-weight:800; line-height:1.2; margin-bottom:10px;">
            {hero_title}
        </div>
        <div style="font-size:17px; line-height:1.7; color:#444;">
            {hero_message}
        </div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.metric(
            "最低との差",
            f"{stats['actual_study_total'] - stats['weekly_required']}時間"
        )

    with col2:
        st.metric(
            "来週繰り越し",
            f"{stats['next_carryover']}時間"
        )

    if stats["shortage_after_missed"] > 0:
        st.error(
            f"最低勉強時間を {stats['shortage_after_missed']}時間 下回っています。"
        )
    else:
        st.success("最低勉強時間は満たせています。")

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("📚 今日の勉強")

    if not today_study.empty:
        for _, r in today_study.iterrows():
            tag_class = "warn" if r["最終行動"] == "振替勉強" else "study"
            st.markdown(
                f'<span class="tag {tag_class}">{r["時間"]} {r["最終行動"]}</span>',
                unsafe_allow_html=True
            )
    else:
        st.caption("今日の勉強予定はありません。")

    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("🤝 今日会ってもいい時間")

    if not today_maybe.empty:
        for _, r in today_maybe.iterrows():
            st.markdown(
                f'<span class="tag meet">{r["時間"]}</span>',
                unsafe_allow_html=True
            )
    else:
        st.caption("今日の会ってもいい時間はありません。")

    st.markdown('</div>', unsafe_allow_html=True)

    if not replacement_plan.empty:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("🔁 振替提案")
        st.dataframe(
            replacement_plan,
            use_container_width=True,
            hide_index=True
        )
        st.markdown('</div>', unsafe_allow_html=True)

# =====================
# 入力
# =====================

with tab_input:
    st.subheader("予定を変更する")

    selected_day = st.selectbox("曜日を選ぶ", days)
    day_df = df[df["曜日"] == selected_day].copy()

    selected_time = st.selectbox(
        "時間を選ぶ",
        day_df["時間"].astype(str).tolist()
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
        <h2>{selected_day}曜日 {selected_time}</h2>
        <p>彼女：<b>{row[girl_col]}</b> / 彼氏：<b>{row[boy_col]}</b></p>
        <p>会いやすさ：<b>{row["会いやすさ"]}</b> / 勉強優先度：<b>{row["勉強優先度"]}</b></p>
    </div>
    """, unsafe_allow_html=True)

    st.write(f"### {user_role}予定を変更")

    cols = st.columns(3)

    for i, plan in enumerate(plans):
        with cols[i % 3]:
            if st.button(
                plan,
                key=f"{selected_day}_{selected_time}_{target_col}_{plan}"
            ):
                new_girl = row[girl_col]
                new_boy = row[boy_col]

                if user_role == "彼女":
                    new_girl = plan
                else:
                    new_boy = plan

                update_one_row(
                    worksheet,
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

                load_sheet_cached.clear()
                st.success(f"{selected_time} を {plan} に変更しました")
                st.rerun()

    with st.expander("会いやすさ・勉強優先度を変更"):
        st.write("会いやすさ")

        ease_cols = st.columns(4)

        for i, ease in enumerate(ease_options):
            with ease_cols[i]:
                if st.button(
                    ease,
                    key=f"{selected_day}_{selected_time}_ease_{ease}"
                ):
                    update_one_row(
                        worksheet,
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

                    load_sheet_cached.clear()
                    st.success(f"会いやすさを {ease} に変更しました")
                    st.rerun()

        st.write("勉強優先度")

        pri_cols = st.columns(3)

        for i, priority in enumerate(priority_options):
            with pri_cols[i]:
                if st.button(
                    priority,
                    key=f"{selected_day}_{selected_time}_priority_{priority}"
                ):
                    update_one_row(
                        worksheet,
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

                    load_sheet_cached.clear()
                    st.success(f"勉強優先度を {priority} に変更しました")
                    st.rerun()

    with st.expander("この曜日の予定を確認"):
        st.dataframe(
            day_df,
            use_container_width=True,
            hide_index=True
        )

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

    calendar_df = calendar_df.reindex(
        index=time_order_from_data,
        columns=days
    )

    st.dataframe(
        calendar_df.style.map(color_final),
        use_container_width=True
    )

    st.subheader("会ってもいい時間")

    if not maybe_meet_plan.empty:
        st.dataframe(
            maybe_meet_plan,
            use_container_width=True,
            hide_index=True
        )
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
        st.metric("現在の勉強予定", f"{stats['actual_study_total']}時間")

    with col3:
        st.metric(
            "最低との差",
            f"{stats['actual_study_total'] - stats['weekly_required']}時間"
        )

    col4, col5, col6 = st.columns(3)

    with col4:
        st.metric("勉強できなかった", f"{stats['missed_total']}時間")

    with col5:
        st.metric("今週に入れる振替", f"{stats['auto_place_count']}時間")

    with col6:
        st.metric("来週繰り越し", f"{stats['next_carryover']}時間")

    if stats["shortage_after_missed"] > 0:
        st.warning(
            f"最低勉強時間を {stats['shortage_after_missed']}時間 下回っています。"
        )
    else:
        st.success("最低勉強時間は満たせています。")

    st.subheader("おすすめ提案")

    tab_study, tab_maybe = st.tabs(["勉強する時間", "会ってもいい時間"])

    with tab_study:
        if not study_plan.empty:
            st.dataframe(
                study_plan.rename(columns={"最終行動": "種類"}),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("勉強予定はありません。")

    with tab_maybe:
        if not maybe_meet_plan.empty:
            st.dataframe(
                maybe_meet_plan,
                use_container_width=True,
                hide_index=True
            )
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
                "項目": [
                    "勉強時間帯",
                    "勉強できなかった",
                    "振替勉強",
                    "会ってもいい",
                    "彼氏予定あり",
                ],
                "内容": [
                    d["勉強時間帯"],
                    d["勉強できなかった時間帯"],
                    d["振替勉強時間帯"],
                    d["会ってもいい時間帯"],
                    d["彼氏予定あり時間帯"],
                ],
            })

            st.dataframe(
                detail_df,
                use_container_width=True,
                hide_index=True
            )

    with st.expander("詳細データを見る"):
        st.dataframe(
            result.style.map(color_final, subset=["最終行動"]),
            use_container_width=True
        )
