# 常用城市及经纬度（可自行添加更多城市）
CITY_COORDS = {
    "香港 Hong Kong": (22.304, 114.179),
    "北京 Beijing": (39.904, 116.407),
    "上海 Shanghai": (31.230, 121.474),
    "广州 Guangzhou": (23.129, 113.264),
    "深圳 Shenzhen": (22.543, 114.058),
    "台北 Taipei": (25.033, 121.565),
    "澳门 Macau": (22.199, 113.544),
    "新加坡 Singapore": (1.352, 103.820),
    "东京 Tokyo": (35.689, 139.692),
    "纽约 New York": (40.713, -74.006),
    "伦敦 London": (51.507, -0.128),
    "悉尼 Sydney": (-33.869, 151.209),
}
import streamlit as st
import pandas as pd
from datetime import date, timedelta
from pathlib import Path
import tempfile

from smart_alarm_app import (
    read_schedule,
    calculate_plan,
    save_report,
    save_json,
    make_ics,
    DEFAULTS,
)


# ============================================================
# 1. 页面设置
# ============================================================
st.set_page_config(
    page_title="Smart Alarm Planner",
    page_icon="⏰",
    layout="wide",
)


# ============================================================
# 2. 多语言文本
# ============================================================
TEXT = {
    "zh": {
        "lang_label": "语言 / Language",
        "title": "⏰ 智能闹钟规划器",
        "subtitle": "面向学生的 AI 每周起床时间规划工具",
        "intro": "上传你的课表和上一周的贪睡数据，系统会自动计算每天推荐的起床时间。",

        "help_title": "📖 使用说明",
        "help_body": """
**三步就能生成你的闹钟计划：**

1. **上传课表** — 支持 CSV 或 TXT 文件。不确定格式？点下面的「下载课表模板」按钮。
2. **（可选）上传贪睡数据** — 记录上一周每天贪睡的次数，系统会自动帮你提前闹钟。
3. **选择周一日期，点击生成** — 系统会计算每天的推荐起床时间，并给你三种导出格式。

**导出格式说明：**
- **TXT**：人类可读的详细报告
- **JSON**：结构化数据，方便二次开发
- **ICS**：可以导入手机日历（Apple Calendar / Google Calendar / Outlook）

**小提示：** 课表里每一行代表一节课，格式是「星期, 开始时间, 课程名」。
        """,

        "sidebar_settings": "⚙️ 设置",
        "presets_title": "常用预设",
        "preset_early": "早八人",
        "preset_commute": "通勤远",
        "preset_sleeper": "爱赖床",
        "preset_hint": "点击预设按钮，会自动设置下面的准备时间和出行方式。",

        "transport": "出行方式",
        "transport_public": "🚌 公共交通",
        "transport_walk": "🚶 步行",
        "transport_bike": "🚲 骑行",
        "prep_time": "基础准备时间（分钟）",
        "prep_hint": "包括洗漱、穿衣、早餐和出门准备。",

        "step1": "📅 1. 上传课表",
        "step1_upload": "上传 CSV 或 TXT 课表文件",
        "step1_template": "📄 下载课表模板",
        "step2": "😴 2. 上一周贪睡数据（可选）",
        "step2_upload": "上传 snooze.csv（可选）",
        "step2_template": "📄 下载贪睡模板",
        "step2_no_file": "没有上传贪睡数据，系统会默认按 0 次贪睡计算。",
        "step2_history": "你的贪睡记录：",
        "step2_avg": "平均贪睡",
        "step2_times": "次/天",
        "step2_missing_col": "CSV 需要包含 snooze_count、snooze 或 贪睡次数 列。",
        "step3": "📆 3. 规划哪一周",
        "step3_date": "选择规划周的周一日期",
        "step4": "🚀 4. 生成闹钟计划",
        "step4_button": "生成智能闹钟计划",
        "step4_no_schedule": "请先上传你的课表。",

        "detected_title": "📚 识别到的课表",
        "col_day": "星期",
        "col_start": "开始时间",
        "col_course": "课程",

        "weather_location": "🌦️ 天气位置",
        "weather_city": "选择你的城市",
        "weather_city_hint": "系统会自动根据你的选择获取当地天气",
        "weather_hint": "选择你所在的城市，系统会自动获取当地天气",

        "holiday_title": "🏖️ 节假日",
        "holiday_label": "输入节假日（一行一个日期）",
        "holiday_placeholder": "2026-10-13\n2026-10-20",

        "success_msg": "你的每周闹钟计划已生成！",
        "plan_title": "⏰ 每周闹钟计划",
        "first_class": "第一节课",
        "base_alarm": "基准闹钟",
        "weather": "天气",
        "traffic": "交通",
        "snooze": "贪睡",
        "final_alarm": "最终闹钟",
        "skip": "跳过",

        "details_title": "🔍 每日计算明细",
        "detail_prep": "准备时间",
        "detail_weather": "天气",
        "detail_traffic": "交通",
        "detail_snooze": "贪睡调整",
        "detail_minutes": "分钟",

        "export_title": "📥 导出你的每周计划",
        "download_txt": "下载 TXT",
        "download_json": "下载 JSON",
        "download_ics": "下载日历文件 (.ics)",
        "download_note": "TXT 是人类可读报告；JSON 是结构化数据；ICS 可以导入手机日历。",

        "footer": "智能闹钟规划器 — 为学生设计的动态起床时间规划工具",
    },

    "en": {
        "lang_label": "Language / 语言",
        "title": "⏰ Smart Alarm Planner",
        "subtitle": "AI-powered weekly wake-up planner for students",
        "intro": "Upload your timetable and last week's snooze data. The system will calculate your recommended wake-up time for each day.",

        "help_title": "📖 How to use",
        "help_body": """
**Three steps to generate your alarm plan:**

1. **Upload timetable** — CSV or TXT. Not sure about the format? Click "Download Timetable Template".
2. **(Optional) Upload snooze data** — Records how many times you snoozed last week. The system will adjust your alarms.
3. **Pick a Monday, click Generate** — The system calculates your recommended wake-up time and gives you three export formats.

**Export formats:**
- **TXT**: Human-readable report
- **JSON**: Structured data for further development
- **ICS**: Import into Apple Calendar / Google Calendar / Outlook

**Tip:** Each row in the timetable is one class, in the format "weekday, start time, course name".
        """,

        "sidebar_settings": "⚙️ Settings",
        "presets_title": "Presets",
        "preset_early": "Early Bird",
        "preset_commute": "Long Commute",
        "preset_sleeper": "Snooze Lover",
        "preset_hint": "Click a preset to auto-set preparation time and transport.",

        "transport": "Transportation",
        "transport_public": "🚌 Public Transport",
        "transport_walk": "🚶 Walking",
        "transport_bike": "🚲 Cycling",
        "prep_time": "Basic preparation time (minutes)",
        "prep_hint": "Includes washing, dressing, breakfast and getting ready.",

        "step1": "📅 1. Upload Your Timetable",
        "step1_upload": "Upload CSV or TXT timetable",
        "step1_template": "📄 Download Timetable Template",
        "step2": "😴 2. Last Week Snooze Data (optional)",
        "step2_upload": "Upload snooze.csv (optional)",
        "step2_template": "📄 Download Snooze Template",
        "step2_no_file": "No snooze data uploaded. The system will use 0 snooze as the default.",
        "step2_history": "Your snooze history:",
        "step2_avg": "Average Snooze",
        "step2_times": "times/day",
        "step2_missing_col": "The CSV needs a 'snooze_count', 'snooze' or '贪睡次数' column.",
        "step3": "📆 3. Planning Week",
        "step3_date": "Select the Monday of the planning week",
        "step4": "🚀 4. Generate Your Alarm Plan",
        "step4_button": "Generate Smart Alarm Plan",
        "step4_no_schedule": "Please upload your timetable first.",

        "detected_title": "📚 Detected Timetable",
        "col_day": "Day",
        "col_start": "Start",
        "col_course": "Course",

        "weather_location": "🌦️ Weather Location",
        "weather_city": "Select your city",
        "weather_city_hint": "The system will automatically fetch the local weather for you",
        "weather_hint": "Select the city and the system will automatically get the local weather.",

        "holiday_title": "🏖️ Holidays",
        "holiday_label": "Enter holidays (one date per line)",
        "holiday_placeholder": "2026-10-13\n2026-10-20",

        "success_msg": "Your weekly smart alarm plan has been generated!",
        "plan_title": "⏰ Weekly Alarm Plan",
        "first_class": "First Class",
        "base_alarm": "Base Alarm",
        "weather": "Weather",
        "traffic": "Traffic",
        "snooze": "Snooze",
        "final_alarm": "Final Alarm",
        "skip": "SKIP",

        "details_title": "🔍 Daily Calculation Details",
        "detail_prep": "Preparation",
        "detail_weather": "Weather",
        "detail_traffic": "Traffic",
        "detail_snooze": "Snooze adjustment",
        "detail_minutes": "minutes",

        "export_title": "📥 Export Your Weekly Plan",
        "download_txt": "Download TXT",
        "download_json": "Download JSON",
        "download_calendar": "Download Calendar (.ics)",
        "download_ics": "Download Calendar (.ics)",
        "download_note": "TXT is a human-readable report; JSON is structured data; ICS can be imported into your phone calendar.",

        "footer": "Smart Alarm Planner — Dynamic wake-up planning for students",
    },
}


# ============================================================
# 3. 侧边栏：语言 + 预设 + 设置
# ============================================================
lang_label = st.sidebar.radio(
    "Language / 语言",
    ["中文", "English"],
    horizontal=True,
)
lang = "zh" if lang_label == "中文" else "en"
t = TEXT[lang]

st.sidebar.divider()
st.sidebar.header(t["sidebar_settings"])

# -------- 常用预设 --------
st.sidebar.subheader("🎯 " + t["presets_title"])

if "prep_minutes" not in st.session_state:
    st.session_state.prep_minutes = 45
if "transport" not in st.session_state:
    st.session_state.transport = "public"

preset_cols = st.sidebar.columns(3)

if preset_cols[0].button(t["preset_early"], use_container_width=True):
    st.session_state.prep_minutes = 35
    st.session_state.transport = "public"
if preset_cols[1].button(t["preset_commute"], use_container_width=True):
    st.session_state.prep_minutes = 45
    st.session_state.transport = "public"
if preset_cols[2].button(t["preset_sleeper"], use_container_width=True):
    st.session_state.prep_minutes = 50
    st.session_state.transport = "public"

st.sidebar.caption(t["preset_hint"])

# -------- 详细设置 --------
transport = st.sidebar.selectbox(
    t["transport"],
    ["public", "walk", "bike"],
    format_func=lambda x: {
        "public": t["transport_public"],
        "walk": t["transport_walk"],
        "bike": t["transport_bike"],
    }[x],
    key="transport",
)

prep_minutes = st.sidebar.number_input(
    t["prep_time"],
    min_value=10,
    max_value=120,
    step=5,
    key="prep_minutes",
)

st.sidebar.write(t["prep_hint"])


# ============================================================
# 4. 页面标题
# ============================================================
st.title(t["title"])
st.write(t["subtitle"])
st.info(t["intro"])

# -------- 使用说明 --------
with st.expander(t["help_title"], expanded=False):
    st.markdown(t["help_body"])


# ============================================================
# 5. 上传课表 + 模板下载
# ============================================================
st.header(t["step1"])

schedule_file = st.file_uploader(
    t["step1_upload"],
    type=["csv", "txt"],
)

schedule_template = """weekday,start,course
Monday,08:30,Programming
Tuesday,10:00,Mathematics
Wednesday,09:00,English
Thursday,14:00,Physics
Friday,08:00,Computer Science
"""

st.download_button(
    t["step1_template"],
    data=schedule_template,
    file_name="schedule_template.csv",
    mime="text/csv",
)


# ============================================================
# 6. 上传贪睡数据 + 模板下载
# ============================================================
st.header(t["step2"])

snooze_file = st.file_uploader(
    t["step2_upload"],
    type=["csv"],
)

snooze_template = """date,snooze_count
2026-10-01,3
2026-10-02,1
2026-10-03,2
2026-10-04,4
"""

st.download_button(
    t["step2_template"],
    data=snooze_template,
    file_name="snooze_template.csv",
    mime="text/csv",
)

if snooze_file is not None:
    snooze_df = pd.read_csv(snooze_file)
    st.write(t["step2_history"])
    st.dataframe(snooze_df, use_container_width=True)

    possible_cols = ["snooze_count", "snooze", "贪睡次数"]
    snooze_col = next((c for c in possible_cols if c in snooze_df.columns), None)

    if snooze_col is not None:
        avg_snooze = snooze_df[snooze_col].mean()
        st.metric(
            t["step2_avg"],
            f"{avg_snooze:.2f} {t['step2_times']}",
        )
    else:
        st.warning(t["step2_missing_col"])
        avg_snooze = 0
else:
    avg_snooze = 0
    st.info(t["step2_no_file"])


# ============================================================
# 7. 规划日期
# ============================================================
st.header(t["step3"])

today = date.today()
days_until_next_monday = (7 - today.weekday()) % 7
if days_until_next_monday == 0:
    days_until_next_monday = 7
default_week = today + timedelta(days=days_until_next_monday)

week_start = st.date_input(
    t["step3_date"],
    value=default_week,
)


# ============================================================
# 8. 生成按钮
# ============================================================
st.header(t["step4"])

generate = st.button(
    t["step4_button"],
    type="primary",
    use_container_width=True,
)


# ============================================================
# 9. 生成逻辑
# ============================================================
if generate:

    if schedule_file is None:
        st.error(t["step4_no_schedule"])
        st.stop()

    suffix = Path(schedule_file.name).suffix

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp:
        temp.write(schedule_file.getbuffer())
        schedule_path = temp.name

    try:
        schedule = read_schedule(schedule_path)
    except Exception as e:
        st.error(f"Could not read timetable: {e}")
        st.stop()

    # ---------- 识别到的课表 ----------
    st.subheader(t["detected_title"])

    schedule_table = [
        {
            t["col_day"]: item.day,
            t["col_start"]: item.start,
            t["col_course"]: item.course,
        }
        for item in schedule
    ]
    st.dataframe(pd.DataFrame(schedule_table), use_container_width=True)

    # ---------- 天气位置 ----------
    st.subheader(t["weather_location"])
    col1, col2 = st.columns(2)
    with col1:
        latitude = st.number_input(t["latitude"], value=22.304, format="%.4f")
    with col2:
        longitude = st.number_input(t["longitude"], value=114.179, format="%.4f")
    st.caption(t["weather_hint"])

    # ---------- 节假日 ----------
    st.subheader(t["holiday_title"])
    holiday_text = st.text_area(
        t["holiday_label"],
        placeholder=t["holiday_placeholder"],
    )

    holiday_dates = set()
    if holiday_text.strip():
        for line in holiday_text.splitlines():
            line = line.strip()
            if line:
                holiday_dates.add(line)

    # ---------- 应用准备时间 ----------
    DEFAULTS["prep_minutes"] = prep_minutes

    # ---------- 计算 ----------
    plans = calculate_plan(
        week_start=week_start,
        schedule=schedule,
        avg_snooze=avg_snooze,
        transport=transport,
        latitude=latitude,
        longitude=longitude,
        holiday_dates=holiday_dates,
    )

    # ========================================================
    # 10. 结果：卡片显示
    # ========================================================
    st.success(t["success_msg"])
    st.subheader(t["plan_title"])

    for plan in plans:
        with st.container(border=True):
            if plan.status == "ALARM":
                col_left, col_right = st.columns([4, 1])

                with col_left:
                    st.markdown(f"### {plan.date} · {plan.weekday}")
                    st.write(
                        f"**{t['first_class']}:** {plan.first_class} "
                        f"({plan.course or '-'})"
                    )
                    st.write(f"**{t['base_alarm']}:** {plan.base_alarm}")
                    st.caption(
                        f"🌦 {t['weather']}: -{plan.weather_adjustment} min  |  "
                        f"🚌 {t['traffic']}: -{plan.traffic_adjustment} min  |  "
                        f"😴 {t['snooze']}: -{plan.snooze_adjustment} min"
                    )

                with col_right:
                    st.metric(t["final_alarm"], plan.final_alarm)

                if plan.warning:
                    st.warning(plan.warning)

            else:
                col_left, col_right = st.columns([4, 1])
                with col_left:
                    st.markdown(f"### {plan.date} · {plan.weekday}")
                    st.caption(plan.warning)
                with col_right:
                    st.metric(t["final_alarm"], "—")

    # ========================================================
    # 11. 每日明细
    # ========================================================
    st.subheader(t["details_title"])

    for plan in plans:
        if plan.status == "ALARM":
            with st.expander(f"{plan.date} — {plan.course or plan.weekday}"):
                st.write(f"**{t['first_class']}:** {plan.first_class}")
                st.write(f"**{t['base_alarm']}:** {plan.base_alarm}")
                st.write(
                    f"**{t['detail_prep']}:** "
                    f"-{plan.prep_minutes} {t['detail_minutes']}"
                )
                st.write(
                    f"**{t['detail_weather']}** "
                    f"({plan.weather_condition}): "
                    f"-{plan.weather_adjustment} {t['detail_minutes']}"
                )
                st.write(
                    f"**{t['detail_traffic']}:** "
                    f"-{plan.traffic_adjustment} {t['detail_minutes']}"
                )
                st.write(
                    f"**{t['detail_snooze']}:** "
                    f"-{plan.snooze_adjustment} {t['detail_minutes']}"
                )
                st.success(f"{t['final_alarm']}: {plan.final_alarm}")
                if plan.warning:
                    st.warning(plan.warning)
        else:
            st.write(f"**{plan.date}** — {plan.warning}")

    # ========================================================
    # 12. 导出文件
    # ========================================================
    output_dir = Path("streamlit_output")
    output_dir.mkdir(exist_ok=True)

    report_file = output_dir / "weekly_alarm_plan.txt"
    json_file = output_dir / "weekly_alarm_plan.json"
    ics_file = output_dir / "weekly_alarms.ics"

    save_report(plans, str(report_file), avg_snooze, transport, week_start)
    save_json(plans, str(json_file), avg_snooze)
    make_ics(plans, str(ics_file))

    st.subheader(t["export_title"])

    col1, col2, col3 = st.columns(3)
    with col1:
        st.download_button(
            t["download_txt"],
            data=report_file.read_text(encoding="utf-8"),
            file_name="weekly_alarm_plan.txt",
            mime="text/plain",
        )
    with col2:
        st.download_button(
            t["download_json"],
            data=json_file.read_text(encoding="utf-8"),
            file_name="weekly_alarm_plan.json",
            mime="application/json",
        )
    with col3:
        st.download_button(
            t["download_ics"],
            data=ics_file.read_text(encoding="utf-8"),
            file_name="weekly_alarms.ics",
            mime="text/calendar",
        )

    st.caption(t["download_note"])

    st.divider()
    st.caption(t["footer"])
