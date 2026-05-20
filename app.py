import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from streamlit_autorefresh import st_autorefresh

# =====================
# ページ設定
# =====================

st.set_page_config(page_title="勉強優先スケジュール管理")
st.title("勉強優先スケジュール管理アプリ")

# =====================
# 基本設定
# =====================

days = ["月", "火", "水", "木", "金", "土", "日"]

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
# サイドバー設定
# =====================

st.sidebar.header("設定")

user_role = st.sidebar.radio(
    "使っている人",
    ["彼女", "彼氏"]
)

weekday_min = st.sidebar.number_input(
    "平日最低勉強時間",
    min_value=0,
    value=2
)

weekend_min = st.sidebar.number_input(
    "土日最低勉強時間",
    min_value=0,
    value=4
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

# API負荷対策：15秒ごと
if auto_refresh:
    st_autorefresh(
        interval=15000,
        key="auto_refresh"
    )

# =====================
# Google Sheets接続
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
    result["不足数値"] = pd.NA
    result["自動勉強候補"] = ""
    result["勉強候補順"] = pd.NA
    result["自動配置"] = ""
    result["最終行動"] = ""

    # =====================
    # 週全体の不足時間を計算
    # =====================

    weekly_required = weekday_min * 5 + weekend_min * 2

    # 「勉強」だけ現在の勉強予定としてカウント
    # 「勉強できなかった」はカウントしない
    current_study_total = (
        result["彼女"] == "勉強"
    ).sum()

    weekly_shortage = max(
        0,
        weekly_required - current_study_total
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
                result.loc[idx, "判定"] = "振替必要"

            elif girl in [
                "授業",
                "バイト",
                "ご飯",
                "用事",
                "睡眠",
                "移動",
                "その他",
            ]:
                result.loc[idx, "判定"] = "予定優先"

            elif girl == "空き" and boy == "勉強":
                result.loc[idx, "判定"] = "勉強候補"

            elif girl == "空き":
                result.loc[idx, "判定"] = "勉強優先寄り"

            if girl == "空き":
                result.loc[idx, "自動勉強候補"] = ease_label(ease)

                # 勉強優先度を優先
                # 高→中→低、同じなら会いにくい順 ×→△→○→◎
                score = priority_score(priority) * 10 + ease_score(ease)

                all_candidates.append((idx, score))

        last_idx = day_df.index[-1]
        result.loc[last_idx, "不足数値"] = weekly_shortage

    # =====================
    # 振替勉強配置
    # =====================

    all_candidates = sorted(
        all_candidates,
        key=lambda x: x[1]
    )

    for order, (idx, score) in enumerate(
        all_candidates,
        start=1
    ):
        result.loc[idx, "勉強候補順"] = order

        if order <= weekly_shortage:
            result.loc[idx, "自動配置"] = "振替勉強"

    # =====================
    # 最終行動
    # =====================

    for idx in result.index:
        girl = result.loc[idx, "彼女"]
        ease = result.loc[idx, "会いやすさ"]
        auto = result.loc[idx, "自動配置"]

        if auto == "振替勉強":
            result.loc[idx, "最終行動"] = "振替勉強"

        elif girl == "勉強":
            result.loc[idx, "最終行動"] = "勉強"

        elif girl == "勉強できなかった":
            result.loc[idx, "最終行動"] = "勉強できなかった"

        elif girl in [
            "授業",
            "バイト",
            "ご飯",
            "用事",
            "睡眠",
            "移動",
            "その他",
        ]:
            result.loc[idx, "最終行動"] = girl

        elif girl == "空き" and ease == "◎":
            result.loc[idx, "最終行動"] = "会う"

        elif girl == "空き":
            result.loc[idx, "最終行動"] = "会ってもいい"

        else:
            result.loc[idx, "最終行動"] = "自由"

    return result

# =====================
# Google Sheets読み込み
# =====================

try:
    df = load_sheet_cached(
        spreadsheet_url,
        worksheet_name
    )

    worksheet = get_worksheet()

except Exception as e:
    st.error(
        "Google Sheetsの読み込みに失敗しました。URL・シート名・Secrets・共有権限を確認して。"
    )
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

# =====================
# タブ
# =====================

tab_input, tab_result = st.tabs(
    ["入力", "結果"]
)

# =====================
# 入力タブ
# =====================

with tab_input:

    st.subheader("予定を変更する")

    # 曜日選択
    selected_day = st.selectbox(
        "曜日を選ぶ",
        days
    )

    day_df = df[
        df["曜日"] == selected_day
    ].copy()

    # 時間選択
    selected_time = st.selectbox(
        "時間を選ぶ",
        day_df["時間"].astype(str).tolist()
    )

    row_mask = (
        (df["曜日"] == selected_day)
        &
        (df["時間"].astype(str) == str(selected_time))
    )

    row_index = df[
        row_mask
    ].index[0]

    row = df.loc[row_index]

    sheet_row_number = row_index + 2

    target_col = (
        girl_col
        if user_role == "彼女"
        else boy_col
    )

    # 現在状態
    st.markdown(
        f"### {selected_day}曜日 {selected_time}"
    )

    st.info(
        f"現在：彼女={row[girl_col]} / "
        f"彼氏={row[boy_col]} / "
        f"会いやすさ={row['会いやすさ']} / "
        f"勉強優先度={row['勉強優先度']}"
    )

    # 予定変更
    st.write(
        f"### {user_role}予定を変更"
    )

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

                st.success(
                    f"{selected_time} を {plan} に変更しました"
                )

                st.rerun()

    st.divider()

    # 会いやすさ
    st.write("### 会いやすさ")

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

                st.success(
                    f"会いやすさを {ease} に変更しました"
                )

                st.rerun()

    st.divider()

    # 勉強優先度
    st.write("### 勉強優先度")

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

                st.success(
                    f"勉強優先度を {priority} に変更しました"
                )

                st.rerun()

    st.divider()

    # 曜日確認
    with st.expander(
        "この曜日の予定を確認"
    ):
        st.dataframe(
            day_df,
            use_container_width=True,
            hide_index=True
        )

# =====================
# 結果計算
# =====================

result = calculate_result(df)

weekly_required = weekday_min * 5 + weekend_min * 2

current_study_total = int(
    (result["彼女"] == "勉強").sum()
)

weekly_shortage = max(
    0,
    weekly_required - current_study_total
)

summary = []

for day in days:
    d = result[result["曜日"] == day]

    summary.append({
        "曜日": day,
        "彼女合計勉強時間": int(
            (
                (d["最終行動"] == "勉強")
                |
                (d["最終行動"] == "振替勉強")
            ).sum()
        ),
        "彼氏勉強時間": int(
            (d["彼氏"] == "勉強").sum()
        ),
        "勉強できなかった時間": int(
            (d["最終行動"] == "勉強できなかった").sum()
        ),
        "振替勉強時間": int(
            (d["最終行動"] == "振替勉強").sum()
        ),
        "会ってもいい時間": int(
            (d["最終行動"] == "会ってもいい").sum()
        ),
        "勉強時間帯": "、".join(
            d.loc[
                d["最終行動"] == "勉強",
                "時間"
            ].astype(str).tolist()
        ),
        "振替勉強時間帯": "、".join(
            d.loc[
                d["最終行動"] == "振替勉強",
                "時間"
            ].astype(str).tolist()
        ),
        "勉強できなかった時間帯": "、".join(
            d.loc[
                d["最終行動"] == "勉強できなかった",
                "時間"
            ].astype(str).tolist()
        ),
        "会ってもいい時間帯": "、".join(
            d.loc[
                d["最終行動"] == "会ってもいい",
                "時間"
            ].astype(str).tolist()
        ),
    })

summary_df = pd.DataFrame(summary)

# =====================
# 結果タブ
# =====================

with tab_result:

    st.subheader("振替提案")

    missed_plan = result[
        result["最終行動"] == "勉強できなかった"
    ][["曜日", "時間"]]

    replacement_plan = result[
        result["最終行動"] == "振替勉強"
    ][["曜日", "時間"]]

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "週最低勉強時間",
            f"{weekly_required}時間"
        )

    with col2:
        st.metric(
            "現在の勉強予定",
            f"{current_study_total}時間"
        )

    with col3:
        st.metric(
            "不足時間",
            f"{weekly_shortage}時間"
        )

    if not missed_plan.empty:
        st.write("### 勉強できなかった時間")
        st.dataframe(
            missed_plan,
            use_container_width=True,
            hide_index=True
        )

    if not replacement_plan.empty:
        st.write("### 代わりにここで勉強しよう")
        st.dataframe(
            replacement_plan,
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("振替不要です。")

    st.subheader("おすすめ提案")

    study_plan = result[
        (
            result["最終行動"] == "勉強"
        )
        |
        (
            result["最終行動"] == "振替勉強"
        )
    ][["曜日", "時間", "最終行動"]]

    maybe_meet_plan = result[
        result["最終行動"] == "会ってもいい"
    ][["曜日", "時間"]]

    tab_study, tab_maybe = st.tabs(
        ["勉強する時間", "会ってもいい時間"]
    )

    with tab_study:
        if not study_plan.empty:
            st.dataframe(
                study_plan.rename(
                    columns={
                        "最終行動": "種類"
                    }
                ),
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
        d = summary_df[
            summary_df["曜日"] == day
        ].iloc[0]

        with st.expander(
            f"{day}曜日",
            expanded=(day == "月")
        ):
            metric1, metric2, metric3 = st.columns(3)

            with metric1:
                st.metric(
                    "彼女 勉強",
                    f"{d['彼女合計勉強時間']}時間"
                )

            with metric2:
                st.metric(
                    "振替勉強",
                    f"{d['振替勉強時間']}時間"
                )

            with metric3:
                st.metric(
                    "会ってもいい",
                    f"{d['会ってもいい時間']}時間"
                )

            detail_df = pd.DataFrame({
                "項目": [
                    "勉強時間帯",
                    "勉強できなかった",
                    "振替勉強",
                    "会ってもいい",
                ],
                "内容": [
                    d["勉強時間帯"],
                    d["勉強できなかった時間帯"],
                    d["振替勉強時間帯"],
                    d["会ってもいい時間帯"],
                ],
            })

            st.dataframe(
                detail_df,
                use_container_width=True,
                hide_index=True
            )

    st.subheader("週間タイムテーブル")

    time_order_from_data = result[
        "時間"
    ].drop_duplicates().tolist()

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
            result.style.map(
                color_final,
                subset=["最終行動"]
            ),
            use_container_width=True
        )
