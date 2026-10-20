import streamlit as st
import pandas as pd
from datetime import date, timedelta
from pathlib import Path
import tempfile
import io

# 引入 OCR 和 PDF 处理库
from PIL import Image
import pytesseract
import fitz  # PyMuPDF

from smart_alarm_app import (
    read_schedule,
    parse_schedule_text, # 复用后端的文本解析函数
    calculate_plan,
    save_report,
    save_json,
    make_ics,
    DEFAULTS,
)

# ============================================================
# 地理数据（精简版，保留上一版的数据结构）
# ============================================================
GEO_DATA = {
    "CN": {"zh": "中国", "en": "China", "regions": {
        "BJ": ("北京市", "Beijing", [("北京", "Beijing", 39.9042, 116.4074)]),
        "SH": ("上海市", "Shanghai", [("上海", "Shanghai", 31.2304, 121.4737)]),
        "GD": ("广东省", "Guangdong", [("广州", "Guangzhou", 23.1291, 113.2644), ("深圳", "Shenzhen", 22.5431, 114.0579), ("珠海", "Zhuhai", 22.2707, 113.5767)]),
        "ZJ": ("浙江省", "Zhejiang", [("杭州", "Hangzhou", 30.2741, 120.1551), ("宁波", "Ningbo", 29.8683, 121.5440)]),
        "SC": ("四川省", "Sichuan", [("成都", "Chengdu", 30.5728, 104.0668)]),
        "HK": ("香港特别行政区", "Hong Kong SAR", [("香港", "Hong Kong", 22.3193, 114.1694)]),
        "MO": ("澳门特别行政区", "Macau SAR", [("澳门", "Macau", 22.1987, 113.5439)]),
        "TW": ("台湾省", "Taiwan", [("台北", "Taipei", 25.0330, 121.5654)]),
    }},
    "US": {"zh": "美国", "en": "United States", "regions": {
        "CA": ("加利福尼亚州", "California", [("洛杉矶", "Los Angeles", 34.0522, -118.2437), ("旧金山", "San Francisco", 37.7749, -122.4194)]),
        "NY": ("纽约州", "New York", [("纽约", "New York", 40.7128, -74.0060)]),
    }},
    "GB": {"zh": "英国", "en": "United Kingdom", "regions": {
        "ENG": ("英格兰", "England", [("伦敦", "London", 51.5074, -0.1278), ("曼彻斯特", "Manchester", 53.4808, -2.2426)]),
    }},
    "JP": {"zh": "日本", "en": "Japan", "regions": {
        "KANTO": ("关东地方", "Kanto", [("东京", "Tokyo", 35.6762, 139.6503)]),
        "KANSAI": ("关西地方", "Kansai", [("大阪", "Osaka", 34.6937, 135.5023)]),
    }},
    "SG": {"zh": "新加坡", "en": "Singapore", "regions": {
        "SG": ("新加坡", "Singapore", [("新加坡", "Singapore", 1.3521, 103.8198)]),
    }},
}

# ============================================================
# 页面设置与多语言
# ============================================================
st.set_page_config(page_title="Smart Alarm Planner", page_icon="⏰", layout="wide")

TEXT = {
    "zh": {
        "title": "⏰ 智能闹钟规划器",
        "subtitle": "面向学生的 AI 每周起床时间规划工具",
        "intro": "上传或输入你的课表和上一周的贪睡数据，系统会自动计算每天推荐的起床时间。",
        "help_title": "📖 使用说明",
        "help_body": """
**三步就能生成你的闹钟计划：**
1. **输入课表** — 支持直接打字（如 `Monday 08:30`）、上传 CSV 或 **图片/PDF 截图识别**。
2. **上传贪睡数据** — 记录上一周每天贪睡的次数，系统会自动帮你提前闹钟。
3. **点击生成** — 系统计算推荐起床时间。

**小提示：** 识别截图后，如果你发现识别有误，可以直接在弹出的文本框里修改！
        """,
        "sidebar_settings": "⚙️ 设置",
        "presets_title": "常用预设",
        "preset_early": "早八人", "preset_commute": "通勤远", "preset_sleeper": "爱赖床",
        "preset_hint": "点击预设按钮，会自动设置准备时间和出行方式。",
        "transport": "出行方式",
        "transport_public": "🚌 公共交通", "transport_walk": "🚶 步行", "transport_bike": "🚲 骑行",
        "prep_time": "基础准备时间（分钟）", "prep_hint": "包括洗漱、穿衣、早餐和出门准备。",
        
        "step1": "📅 1. 填写你的课表",
        "tab_csv": "📁 上传文件 (CSV/TXT)",
        "tab_text": "⌨️ 手动输入",
        "tab_ocr": "📸 图片/PDF 识别",
        "csv_upload": "上传 CSV 或 TXT 文件",
        "template_btn": "📄 下载课表模板",
        "text_input_label": "输入每天的第一节课（每行一个）",
        "text_placeholder": "Monday 08:30\n周二 10:00\n周三 14:00",
        "ocr_upload": "上传课表截图或 PDF",
        "ocr_hint": "支持白底黑字截图、PDF 文件。识别后请检查下方文字是否有误。",
        "ocr_result": "识别结果（可直接修改）",
        
        "step2": "😴 2. 上一周贪睡数据（可选）",
        "step2_upload": "上传 snooze.csv",
        "step2_no_file": "没有上传贪睡数据，默认按 0 次计算。",
        "step3": "📆 3. 规划哪一周",
        "step3_date": "选择周一日期",
        "step_weather": "🌦️ 4. 选择你的位置",
        "weather_country": "选择国家/地区", "weather_region": "选择省/州", "weather_city": "选择城市",
        "step_holiday": "🏖️ 5. 节假日（可选）",
        "holiday_label": "输入节假日（一行一个日期）",
        "step4": "🚀 6. 生成闹钟计划",
        "step4_button": "生成智能闹钟计划",
        "no_schedule": "请先提供课表数据。",
        "success_msg": "你的每周闹钟计划已生成！",
        "plan_title": "⏰ 每周闹钟计划",
        "first_class": "第一节课", "base_alarm": "基准闹钟", "final_alarm": "最终闹钟",
        "details_title": "🔍 每日计算明细",
        "export_title": "📥 导出你的每周计划",
        "download_txt": "下载 TXT", "download_json": "下载 JSON", "download_calendar": "下载 .ics 日历",
        "footer": "智能闹钟规划器 — 为学生设计的动态起床时间规划工具"
    },
    "en": {
        "title": "⏰ Smart Alarm Planner",
        "subtitle": "AI-powered weekly wake-up planner",
        "intro": "Provide your timetable and snooze data to generate your plan.",
        "help_title": "📖 How to use",
        "help_body": "1. Enter timetable (Text, CSV, or OCR). 2. Enter snooze. 3. Generate.",
        "sidebar_settings": "⚙️ Settings",
        "presets_title": "Presets",
        "preset_early": "Early Bird", "preset_commute": "Long Commute", "preset_sleeper": "Snooze Lover",
        "preset_hint": "Click to auto-set preparation time and transport.",
        "transport": "Transportation",
        "transport_public": "🚌 Public Transport", "transport_walk": "🚶 Walking", "transport_bike": "🚲 Cycling",
        "prep_time": "Preparation time (minutes)", "prep_hint": "Time to get ready.",
        
        "step1": "📅 1. Your Timetable",
        "tab_csv": "📁 Upload File (CSV/TXT)",
        "tab_text": "⌨️ Manual Input",
        "tab_ocr": "📸 OCR from Image/PDF",
        "csv_upload": "Upload CSV or TXT",
        "template_btn": "📄 Download Template",
        "text_input_label": "Enter first class for each day (one per line)",
        "text_placeholder": "Monday 08:30\nTuesday 10:00\nWednesday 14:00",
        "ocr_upload": "Upload Screenshot or PDF",
        "ocr_hint": "Supports clear text images and PDFs. Please check and edit the extracted text below.",
        "ocr_result": "Extracted Text (Editable)",
        
        "step2": "😴 2. Snooze Data (optional)",
        "step2_upload": "Upload snooze.csv",
        "step2_no_file": "No snooze data. Default to 0.",
        "step3": "📆 3. Planning Week",
        "step3_date": "Select Monday",
        "step_weather": "🌦️ 4. Location",
        "weather_country": "Country", "weather_region": "State/Province", "weather_city": "City",
        "step_holiday": "🏖️ 5. Holidays (optional)",
        "holiday_label": "Holidays (YYYY-MM-DD, one per line)",
        "step4": "🚀 6. Generate Plan",
        "step4_button": "Generate Smart Alarm Plan",
        "no_schedule": "Please provide timetable data.",
        "success_msg": "Plan generated successfully!",
        "plan_title": "⏰ Weekly Alarm Plan",
        "first_class": "First Class", "base_alarm": "Base Alarm", "final_alarm": "Final Alarm",
        "details_title": "🔍 Details",
        "export_title": "📥 Export",
        "download_txt": "Download TXT", "download_json": "Download JSON", "download_calendar": "Download .ics",
        "footer": "Smart Alarm Planner"
    }
}

lang_label = st.sidebar.radio("Language / 语言", ["中文", "English"], horizontal=True)
lang = "zh" if lang_label == "中文" else "en"
t = TEXT[lang]

# ============================================================
# 侧边栏设置
# ============================================================
st.sidebar.divider()
st.sidebar.header(t["sidebar_settings"])
if "prep_minutes" not in st.session_state: st.session_state.prep_minutes = 45
if "transport" not in st.session_state: st.session_state.transport = "public"

preset_cols = st.sidebar.columns(3)
if preset_cols[0].button(t["preset_early"], use_container_width=True):
    st.session_state.prep_minutes = 35; st.session_state.transport = "public"
if preset_cols[1].button(t["preset_commute"], use_container_width=True):
    st.session_state.prep_minutes = 45; st.session_state.transport = "public"
if preset_cols[2].button(t["preset_sleeper"], use_container_width=True):
    st.session_state.prep_minutes = 50; st.session_state.transport = "public"

transport = st.sidebar.selectbox(t["transport"], ["public", "walk", "bike"], 
    format_func=lambda x: {"public": t["transport_public"], "walk": t["transport_walk"], "bike": t["transport_bike"]}[x], key="transport")
prep_minutes = st.sidebar.number_input(t["prep_time"], min_value=10, max_value=120, step=5, key="prep_minutes")

# ============================================================
# 页面标题
# ============================================================
st.title(t["title"])
st.write(t["subtitle"])
st.info(t["intro"])
with st.expander(t["help_title"]): st.markdown(t["help_body"])

# ============================================================
# 1. 课表输入（核心改造区）
# ============================================================
st.header(t["step1"])

# 提供三种输入方式的 Tab
tab_csv, tab_text, tab_ocr = st.tabs([t["tab_csv"], t["tab_text"], t["tab_ocr"]])

final_schedule_text = "" # 最终交给系统解析的文本
uploaded_file_for_csv = None

# --- Tab 1: CSV 上传 ---
with tab_csv:
    uploaded_file_for_csv = st.file_uploader(t["csv_upload"], type=["csv", "txt"])
    schedule_template = "weekday,start,course\nMonday,08:30,Programming\nTuesday,10:00,Mathematics\n"
    st.download_button(t["template_btn"], data=schedule_template, file_name="schedule_template.csv", mime="text/csv")

# --- Tab 2: 手动输入 ---
with tab_text:
    manual_text = st.text_area(t["text_input_label"], placeholder=t["text_placeholder"], height=150)
    if manual_text.strip():
        final_schedule_text = manual_text

# --- Tab 3: OCR 识别 ---
with tab_ocr:
    st.caption(t["ocr_hint"])
    ocr_file = st.file_uploader(t["ocr_upload"], type=["png", "jpg", "jpeg", "pdf"])
    
    if ocr_file is not None:
        with st.spinner("正在识别文字，请稍候..."):
            extracted_text = ""
            try:
                # 如果是图片
                if ocr_file.type in ["image/png", "image/jpeg", "image/jpg"]:
                    img = Image.open(ocr_file)
                    extracted_text = pytesseract.image_to_string(img, lang="eng+chi_sim")
                # 如果是 PDF
                elif ocr_file.type == "application/pdf":
                    pdf_bytes = ocr_file.read()
                    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                    for page in doc:
                        # 先尝试直接提取 PDF 里的文本（速度快、准确率高）
                        page_text = page.get_text()
                        if page_text.strip():
                            extracted_text += page_text + "\n"
                        else:
                            # 如果是扫描版 PDF，转成图片再 OCR
                            pix = page.get_pixmap()
                            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                            extracted_text += pytesseract.image_to_string(img, lang="eng+chi_sim") + "\n"
                
                # 把识别结果放进文本框让用户确认和修改
                final_schedule_text = st.text_area(t["ocr_result"], value=extracted_text, height=200)
            except Exception as e:
                st.error(f"识别失败: {e}")

# ============================================================
# 2. 贪睡数据
# ============================================================
st.header(t["step2"])
snooze_file = st.file_uploader(t["step2_upload"], type=["csv"])
avg_snooze = 0
if snooze_file is not None:
    snooze_df = pd.read_csv(snooze_file)
    snooze_col = next((c for c in ["snooze_count", "snooze", "贪睡次数"] if c in snooze_df.columns), None)
    if snooze_col:
        avg_snooze = snooze_df[snooze_col].mean()
        st.metric(t["step2_avg"], f"{avg_snooze:.2f}")
else:
    st.info(t["step2_no_file"])

# ============================================================
# 3. 日期
# ============================================================
st.header(t["step3"])
today = date.today()
days_until_next_monday = (7 - today.weekday()) % 7
if days_until_next_monday == 0: days_until_next_monday = 7
default_week = today + timedelta(days=days_until_next_monday)
week_start = st.date_input(t["step3_date"], value=default_week)

# ============================================================
# 4. 国家/省/市
# ============================================================
st.header(t["step_weather"])
country_codes = list(GEO_DATA.keys())
country_names = [GEO_DATA[c]["zh" if lang=="zh" else "en"] for c in country_codes]
def_country_idx = country_codes.index("CN") if "CN" in country_codes else 0

col1, col2, col3 = st.columns(3)
with col1:
    sel_country_name = st.selectbox(t["weather_country"], country_names, index=def_country_idx)
sel_country_code = country_codes[country_names.index(sel_country_name)]
country_data = GEO_DATA[sel_country_code]

region_codes = list(country_data["regions"].keys())
region_names = [country_data["regions"][r][0 if lang=="zh" else 1] for r in region_codes]
with col2:
    sel_region_name = st.selectbox(t["weather_region"], region_names)
sel_region_code = region_codes[region_names.index(sel_region_name)]
region_data = country_data["regions"][sel_region_code]

cities = region_data[2]
city_names = [c[0] if lang=="zh" else c[1] for c in cities]
with col3:
    sel_city_name = st.selectbox(t["weather_city"], city_names)
sel_city = cities[city_names.index(sel_city_name)]
latitude, longitude = sel_city[2], sel_city[3]

# ============================================================
# 5. 节假日
# ============================================================
st.header(t["step_holiday"])
holiday_text = st.text_area(t["holiday_label"], placeholder="2026-10-13\n2026-10-20")
holiday_dates = set([l.strip() for l in holiday_text.splitlines() if l.strip()])

# ============================================================
# 6. 生成按钮
# ============================================================
st.header(t["step4"])
generate = st.button(t["step4_button"], type="primary", use_container_width=True)

if generate:
    # 统一获取课表数据
    schedule = []
    
    if uploaded_file_for_csv is not None:
        # 处理 CSV
        suffix = Path(uploaded_file_for_csv.name).suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp:
            temp.write(uploaded_file_for_csv.getbuffer())
            temp_path = temp.name
        try:
            schedule = read_schedule(temp_path)
        except Exception as e:
            st.error(f"CSV 读取失败: {e}")
            st.stop()
            
    elif final_schedule_text.strip():
        # 处理 文本/OCR
        try:
            schedule = parse_schedule_text(final_schedule_text)
        except Exception as e:
            st.error(f"文本解析失败，请检查格式。报错：{e}")
            st.stop()
            
    if not schedule:
        st.error(t["no_schedule"])
        st.stop()

    # 计算计划
    DEFAULTS["prep_minutes"] = prep_minutes
    plans = calculate_plan(week_start, schedule, avg_snooze, transport, latitude, longitude, holiday_dates)

    # 结果展示
    st.success(t["success_msg"])
    st.subheader(t["plan_title"])
    for plan in plans:
        with st.container(border=True):
            if plan.status == "ALARM":
                c1, c2 = st.columns([4, 1])
                with c1:
                    st.markdown(f"### {plan.date} · {plan.weekday}")
                    st.write(f"**{t['first_class']}:** {plan.first_class} ({plan.course or '-'})")
                    st.write(f"**{t['base_alarm']}:** {plan.base_alarm}")
                    st.caption(f"🌦 天气: -{plan.weather_adjustment} min | 🚌 交通: -{plan.traffic_adjustment} min | 😴 贪睡: -{plan.snooze_adjustment} min")
                with c2:
                    st.metric(t["final_alarm"], plan.final_alarm)
                if plan.warning: st.warning(plan.warning)
            else:
                st.markdown(f"### {plan.date} · {plan.weekday}")
                st.caption(plan.warning)

    # 导出
    output_dir = Path("streamlit_output"); output_dir.mkdir(exist_ok=True)
    report_file = output_dir / "plan.txt"
    json_file = output_dir / "plan.json"
    ics_file = output_dir / "alarms.ics"
    
    save_report(plans, str(report_file), avg_snooze, transport, week_start)
    save_json(plans, str(json_file), avg_snooze)
    make_ics(plans, str(ics_file))

    st.subheader(t["export_title"])
    c1, c2, c3 = st.columns(3)
    with c1: st.download_button(t["download_txt"], report_file.read_text("utf-8"), "plan.txt")
    with c2: st.download_button(t["download_json"], json_file.read_text("utf-8"), "plan.json")
    with c3: st.download_button(t["download_calendar"], ics_file.read_text("utf-8"), "alarms.ics")

    st.divider()
    st.caption(t["footer"])
