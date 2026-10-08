import streamlit as st
import pandas as pd
from datetime import date, timedelta
from pathlib import Path
import tempfile

from smart_alarm_app import (
    read_schedule,
    parse_image_schedule,
    read_snooze,
    parse_holiday_file,
    calculate_plan,
    save_report,
    save_json,
    make_ics,
)


# ============================================================
# 1. 页面设置
# ============================================================

st.set_page_config(
    page_title="Smart Alarm Planner",
    page_icon="⏰",
    layout="wide"
)


# ============================================================
# 2. 页面标题
# ============================================================

st.title("⏰ Smart Alarm Planner")

st.write(
    "AI-powered weekly wake-up planner for students"
)

st.info(
    "Upload your timetable and provide last week's snooze data. "
    "The system will calculate your recommended wake-up time for each day."
)


# ============================================================
# 3. 左侧设置
# ============================================================

st.sidebar.header("⚙️ Settings")

transport = st.sidebar.selectbox(
    "Transportation",
    [
        "public",
        "walk",
        "bike"
    ],
    format_func=lambda x: {
        "public": "🚌 Public Transport",
        "walk": "🚶 Walking",
        "bike": "🚲 Cycling"
    }[x]
)

prep_minutes = st.sidebar.number_input(
    "Basic preparation time (minutes)",
    min_value=10,
    max_value=120,
    value=45,
    step=5
)

st.sidebar.write(
    "This includes washing, dressing, breakfast and getting ready."
)


# ============================================================
# 4. 上传课表
# ============================================================

st.header("📅 1. Upload Your Timetable")

schedule_file = st.file_uploader(
    "Upload CSV, TXT or timetable image",
    type=["csv", "txt", "png", "jpg", "jpeg"]
)


# ============================================================
# 5. 贪睡数据
# ============================================================

st.header("😴 2. Last Week Snooze Data")

snooze_file = st.file_uploader(
    "Upload snooze.csv (optional)",
    type=["csv"]
)

if snooze_file is not None:

    snooze_df = pd.read_csv(snooze_file)

    st.write("Your snooze history:")

    st.dataframe(
        snooze_df,
        use_container_width=True
    )

    if "snooze_count" in snooze_df.columns:
        avg_snooze = snooze_df["snooze_count"].mean()

        st.metric(
            "Average Snooze",
            f"{avg_snooze:.2f} times/day"
        )
    else:
        st.warning(
            "The CSV needs a 'snooze_count' column."
        )
        avg_snooze = 0

else:

    avg_snooze = 0

    st.info(
        "No snooze data uploaded. "
        "The system will use 0 snooze as the default."
    )


# ============================================================
# 6. 规划日期
# ============================================================

st.header("📆 3. Planning Week")

default_week = date.today() + timedelta(
    days=(7 - date.today().weekday()) % 7
)

week_start = st.date_input(
    "Select the Monday of the planning week",
    value=default_week
)


# ============================================================
# 7. 生成计划
# ============================================================

st.header("🚀 4. Generate Your Alarm Plan")

generate = st.button(
    "Generate Smart Alarm Plan",
    type="primary",
    use_container_width=True
)


if generate:

    if schedule_file is None:

        st.error(
            "Please upload your timetable first."
        )

        st.stop()

    # --------------------------------------------------------
    # 临时保存上传文件
    # --------------------------------------------------------

    suffix = Path(schedule_file.name).suffix

    with tempfile.NamedTemporaryFile(
        delete=False,
        suffix=suffix
    ) as temp:

        temp.write(
            schedule_file.getbuffer()
        )

        schedule_path = temp.name

    # --------------------------------------------------------
    # 读取课表
    # --------------------------------------------------------

    try:

        if suffix.lower() in [".png", ".jpg", ".jpeg"]:

            schedule = parse_image_schedule(
                schedule_path
            )

        else:

            schedule = read_schedule(
                schedule_path
            )

    except Exception as e:

        st.error(
            f"Could not read timetable: {e}"
        )

        st.stop()

    # --------------------------------------------------------
    # 显示识别到的课程
    # --------------------------------------------------------

    st.subheader("📚 Detected Timetable")

    schedule_table = []

    for item in schedule:

        schedule_table.append(
            {
                "Day": item.day,
                "Start": item.start,
                "Course": item.course
            }
        )

    st.dataframe(
        pd.DataFrame(schedule_table),
        use_container_width=True
    )

    # --------------------------------------------------------
    # 天气位置
    # --------------------------------------------------------

    st.subheader("🌦️ Weather Location")

    col1, col2 = st.columns(2)

    with col1:

        latitude = st.number_input(
            "Latitude",
            value=22.304,
            format="%.4f"
        )

    with col2:

        longitude = st.number_input(
            "Longitude",
            value=114.179,
            format="%.4f"
        )

    st.caption(
        "You can replace these with the latitude and longitude "
        "of your school."
    )

    # --------------------------------------------------------
    # 节假日
    # --------------------------------------------------------

    st.subheader("🏖️ Holidays")

    holiday_text = st.text_area(
        "Enter holidays (one date per line)",
        placeholder="2026-10-13\n2026-10-20"
    )

    holiday_dates = set()

    if holiday_text.strip():

        for line in holiday_text.splitlines():

            line = line.strip()

            if line:
                holiday_dates.add(line)

    # --------------------------------------------------------
    # 修改基础准备时间
    # --------------------------------------------------------

    # 使用用户在侧边栏设置的准备时间
    from smart_alarm_app import DEFAULTS

    DEFAULTS["prep_minutes"] = prep_minutes

    # --------------------------------------------------------
    # 计算
    # --------------------------------------------------------

    plans = calculate_plan(

        week_start=week_start,

        schedule=schedule,

        avg_snooze=avg_snooze,

        transport=transport,

        latitude=latitude,

        longitude=longitude,

        holiday_dates=holiday_dates
    )

    # ========================================================
    # 8. 显示结果
    # ========================================================

    st.success(
        "Your weekly smart alarm plan has been generated!"
    )

    st.subheader("⏰ Weekly Alarm Plan")

    table = []

    for plan in plans:

        table.append(
            {
                "Date": plan.date,

                "Day": plan.weekday,

                "Status": plan.status,

                "First Class": plan.first_class
                if plan.first_class else "-",

                "Base Alarm": plan.base_alarm
                if plan.base_alarm else "-",

                "Weather": (
                    f"-{plan.weather_adjustment} min"
                ),

                "Traffic": (
                    f"-{plan.traffic_adjustment} min"
                ),

                "Snooze": (
                    f"-{plan.snooze_adjustment} min"
                ),

                "FINAL ALARM": (
                    plan.final_alarm
                    if plan.final_alarm else "SKIP"
                )
            }
        )

    result_df = pd.DataFrame(table)

    st.dataframe(
        result_df,
        use_container_width=True
    )

    # ========================================================
    # 9. 每天详细解释
    # ========================================================

    st.subheader("🔍 Daily Calculation Details")

    for plan in plans:

        if plan.status == "ALARM":

            with st.expander(
                f"{plan.date} — {plan.course}"
            ):

                st.write(
                    f"**First class:** {plan.first_class}"
                )

                st.write(
                    f"**Base alarm:** {plan.base_alarm}"
                )

                st.write(
                    f"**Preparation:** -{plan.prep_minutes} minutes"
                )

                st.write(
                    f"**Weather:** "
                    f"{plan.weather_condition} "
                    f"(-{plan.weather_adjustment} minutes)"
                )

                st.write(
                    f"**Traffic:** "
                    f"-{plan.traffic_adjustment} minutes"
                )

                st.write(
                    f"**Snooze adjustment:** "
                    f"-{plan.snooze_adjustment} minutes"
                )

                st.success(
                    f"FINAL ALARM: {plan.final_alarm}"
                )

                if plan.warning:

                    st.warning(
                        plan.warning
                    )

        else:

            st.write(
                f"**{plan.date}** — {plan.warning}"
            )

    # ========================================================
    # 10. 生成下载文件
    # ========================================================

    output_dir = Path("streamlit_output")

    output_dir.mkdir(
        exist_ok=True
    )

    report_file = (
        output_dir /
        "weekly_alarm_plan.txt"
    )

    json_file = (
        output_dir /
        "weekly_alarm_plan.json"
    )

    ics_file = (
        output_dir /
        "weekly_alarms.ics"
    )

    save_report(
        plans,
        str(report_file),
        avg_snooze,
        transport,
        week_start
    )

    save_json(
        plans,
        str(json_file),
        avg_snooze
    )

    make_ics(
        plans,
        str(ics_file)
    )

    # ========================================================
    # 11. 下载按钮
    # ========================================================

    st.subheader(
        "📥 Export Your Weekly Plan"
    )

    col1, col2, col3 = st.columns(3)

    with col1:

        st.download_button(
            "Download TXT",
            data=report_file.read_text(
                encoding="utf-8"
            ),
            file_name="weekly_alarm_plan.txt",
            mime="text/plain"
        )

    with col2:

        st.download_button(
            "Download JSON",
            data=json_file.read_text(
                encoding="utf-8"
            ),
            file_name="weekly_alarm_plan.json",
            mime="application/json"
        )

    with col3:

        st.download_button(
            "Download Calendar (.ics)",
            data=ics_file.read_text(
                encoding="utf-8"
            ),
            file_name="weekly_alarms.ics",
            mime="text/calendar"
        )

    st.divider()

    st.caption(
        "Smart Alarm Planner — Dynamic wake-up planning for students"
    )