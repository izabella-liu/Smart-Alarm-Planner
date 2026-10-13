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
# 全球地理数据（三级：国家/地区 → 省/州 → 城市）
# 每条记录格式：(中文名, 英文名, 纬度, 经度)
# ============================================================
GEO_DATA = {
    "CN": {
        "zh": "中国", "en": "China",
        "regions": {
            "BJ": ("北京市", "Beijing", [("北京", "Beijing", 39.9042, 116.4074)]),
            "TJ": ("天津市", "Tianjin", [("天津", "Tianjin", 39.3434, 117.3616)]),
            "SH": ("上海市", "Shanghai", [("上海", "Shanghai", 31.2304, 121.4737)]),
            "CQ": ("重庆市", "Chongqing", [("重庆", "Chongqing", 29.5630, 106.5516)]),
            "HE": ("河北省", "Hebei", [("石家庄", "Shijiazhuang", 38.0428, 114.5149), ("唐山", "Tangshan", 39.6304, 118.1804), ("保定", "Baoding", 38.8740, 115.4646)]),
            "SX": ("山西省", "Shanxi", [("太原", "Taiyuan", 37.8706, 112.5489), ("大同", "Datong", 40.0768, 113.3001)]),
            "LN": ("辽宁省", "Liaoning", [("沈阳", "Shenyang", 41.8057, 123.4315), ("大连", "Dalian", 38.9140, 121.6147)]),
            "JL": ("吉林省", "Jilin", [("长春", "Changchun", 43.8171, 125.3235), ("吉林", "Jilin City", 43.8378, 126.5495)]),
            "HL": ("黑龙江省", "Heilongjiang", [("哈尔滨", "Harbin", 45.8038, 126.5350), ("齐齐哈尔", "Qiqihar", 47.3543, 123.9181)]),
            "JS": ("江苏省", "Jiangsu", [("南京", "Nanjing", 32.0603, 118.7969), ("苏州", "Suzhou", 31.2989, 120.5853), ("无锡", "Wuxi", 31.4912, 120.3119), ("徐州", "Xuzhou", 34.2058, 117.2848)]),
            "ZJ": ("浙江省", "Zhejiang", [("杭州", "Hangzhou", 30.2741, 120.1551), ("宁波", "Ningbo", 29.8683, 121.5440), ("温州", "Wenzhou", 27.9938, 120.6994)]),
            "AH": ("安徽省", "Anhui", [("合肥", "Hefei", 31.8206, 117.2272), ("芜湖", "Wuhu", 31.3526, 118.4331)]),
            "FJ": ("福建省", "Fujian", [("福州", "Fuzhou", 26.0745, 119.2965), ("厦门", "Xiamen", 24.4798, 118.0894), ("泉州", "Quanzhou", 24.8741, 118.6757)]),
            "JX": ("江西省", "Jiangxi", [("南昌", "Nanchang", 28.6820, 115.8579), ("赣州", "Ganzhou", 25.8309, 114.9350)]),
            "SD": ("山东省", "Shandong", [("济南", "Jinan", 36.6512, 117.1201), ("青岛", "Qingdao", 36.0671, 120.3826), ("烟台", "Yantai", 37.4638, 121.4479)]),
            "HA": ("河南省", "Henan", [("郑州", "Zhengzhou", 34.7466, 113.6254), ("洛阳", "Luoyang", 34.6197, 112.4540)]),
            "HB": ("湖北省", "Hubei", [("武汉", "Wuhan", 30.5928, 114.3055), ("宜昌", "Yichang", 30.6919, 111.2864)]),
            "HN": ("湖南省", "Hunan", [("长沙", "Changsha", 28.2282, 112.9388), ("株洲", "Zhuzhou", 27.8274, 113.1340)]),
            "GD": ("广东省", "Guangdong", [("广州", "Guangzhou", 23.1291, 113.2644), ("深圳", "Shenzhen", 22.5431, 114.0579), ("东莞", "Dongguan", 23.0207, 113.7518), ("佛山", "Foshan", 23.0218, 113.1219), ("珠海", "Zhuhai", 22.2707, 113.5767)]),
            "HI": ("海南省", "Hainan", [("海口", "Haikou", 20.0444, 110.1999), ("三亚", "Sanya", 18.2528, 109.5119)]),
            "SC": ("四川省", "Sichuan", [("成都", "Chengdu", 30.5728, 104.0668), ("绵阳", "Mianyang", 31.4675, 104.6796)]),
            "GZ": ("贵州省", "Guizhou", [("贵阳", "Guiyang", 26.6470, 106.6302), ("遵义", "Zunyi", 27.7256, 106.9273)]),
            "YN": ("云南省", "Yunnan", [("昆明", "Kunming", 24.8801, 102.8329), ("大理", "Dali", 25.6065, 100.2676)]),
            "SN": ("陕西省", "Shaanxi", [("西安", "Xi'an", 34.3416, 108.9398), ("宝鸡", "Baoji", 34.3617, 107.2374)]),
            "GS": ("甘肃省", "Gansu", [("兰州", "Lanzhou", 36.0611, 103.8343), ("天水", "Tianshui", 34.5809, 105.7249)]),
            "QH": ("青海省", "Qinghai", [("西宁", "Xining", 36.6171, 101.7782)]),
            "TW": ("台湾省", "Taiwan", [("台北", "Taipei", 25.0330, 121.5654), ("高雄", "Kaohsiung", 22.6273, 120.3014), ("台中", "Taichung", 24.1477, 120.6736), ("台南", "Tainan", 22.9998, 120.2269)]),
            "NM": ("内蒙古自治区", "Inner Mongolia", [("呼和浩特", "Hohhot", 40.8414, 111.7519), ("包头", "Baotou", 40.6574, 109.8403)]),
            "GX": ("广西壮族自治区", "Guangxi", [("南宁", "Nanning", 22.8170, 108.3665), ("桂林", "Guilin", 25.2736, 110.2900)]),
            "XZ": ("西藏自治区", "Tibet", [("拉萨", "Lhasa", 29.6500, 91.1000)]),
            "NX": ("宁夏回族自治区", "Ningxia", [("银川", "Yinchuan", 38.4872, 106.2309)]),
            "XJ": ("新疆维吾尔自治区", "Xinjiang", [("乌鲁木齐", "Urumqi", 43.8256, 87.6168), ("喀什", "Kashgar", 39.4677, 75.9938)]),
            "HK": ("香港特别行政区", "Hong Kong SAR", [("香港", "Hong Kong", 22.3193, 114.1694)]),
            "MO": ("澳门特别行政区", "Macau SAR", [("澳门", "Macau", 22.1987, 113.5439)]),
        },
    },
    "US": {
        "zh": "美国", "en": "United States",
        "regions": {
            "CA": ("加利福尼亚州", "California", [("洛杉矶", "Los Angeles", 34.0522, -118.2437), ("旧金山", "San Francisco", 37.7749, -122.4194), ("圣地亚哥", "San Diego", 32.7157, -117.1611)]),
            "NY": ("纽约州", "New York", [("纽约", "New York", 40.7128, -74.0060), ("水牛城", "Buffalo", 42.8864, -78.8784)]),
            "TX": ("德克萨斯州", "Texas", [("休斯顿", "Houston", 29.7604, -95.3698), ("达拉斯", "Dallas", 32.7767, -96.7970), ("奥斯汀", "Austin", 30.2672, -97.7431)]),
            "WA": ("华盛顿州", "Washington", [("西雅图", "Seattle", 47.6062, -122.3321)]),
            "IL": ("伊利诺伊州", "Illinois", [("芝加哥", "Chicago", 41.8781, -87.6298)]),
            "FL": ("佛罗里达州", "Florida", [("迈阿密", "Miami", 25.7617, -80.1918), ("奥兰多", "Orlando", 28.5383, -81.3792)]),
            "MA": ("马萨诸塞州", "Massachusetts", [("波士顿", "Boston", 42.3601, -71.0589)]),
            "PA": ("宾夕法尼亚州", "Pennsylvania", [("费城", "Philadelphia", 39.9526, -75.1652), ("匹兹堡", "Pittsburgh", 40.4406, -79.9959)]),
            "GA": ("佐治亚州", "Georgia", [("亚特兰大", "Atlanta", 33.7490, -84.3880)]),
            "NV": ("内华达州", "Nevada", [("拉斯维加斯", "Las Vegas", 36.1699, -115.1398)]),
        },
    },
    "GB": {
        "zh": "英国", "en": "United Kingdom",
        "regions": {
            "ENG": ("英格兰", "England", [("伦敦", "London", 51.5074, -0.1278), ("曼彻斯特", "Manchester", 53.4808, -2.2426), ("伯明翰", "Birmingham", 52.4862, -1.8904), ("利物浦", "Liverpool", 53.4084, -2.9916)]),
            "SCT": ("苏格兰", "Scotland", [("爱丁堡", "Edinburgh", 55.9533, -3.1883), ("格拉斯哥", "Glasgow", 55.8642, -4.2518)]),
            "WLS": ("威尔士", "Wales", [("卡迪夫", "Cardiff", 51.4816, -3.1791)]),
            "NIR": ("北爱尔兰", "Northern Ireland", [("贝尔法斯特", "Belfast", 54.5973, -5.9301)]),
        },
    },
    "JP": {
        "zh": "日本", "en": "Japan",
        "regions": {
            "KANTO": ("关东地方", "Kanto", [("东京", "Tokyo", 35.6762, 139.6503), ("横滨", "Yokohama", 35.4437, 139.6380)]),
            "KANSAI": ("关西地方", "Kansai", [("大阪", "Osaka", 34.6937, 135.5023), ("京都", "Kyoto", 35.0116, 135.7681), ("神户", "Kobe", 34.6901, 135.1955)]),
            "CHUBU": ("中部地方", "Chubu", [("名古屋", "Nagoya", 35.1815, 136.9066)]),
            "HOKKAIDO": ("北海道", "Hokkaido", [("札幌", "Sapporo", 43.0618, 141.3545)]),
            "KYUSHU": ("九州", "Kyushu", [("福冈", "Fukuoka", 33.5904, 130.4017)]),
        },
    },
    "KR": {
        "zh": "韩国", "en": "South Korea",
        "regions": {
            "SEL": ("首尔特别市", "Seoul", [("首尔", "Seoul", 37.5665, 126.9780)]),
            "BUS": ("釜山广域市", "Busan", [("釜山", "Busan", 35.1796, 129.0756)]),
            "INC": ("仁川广域市", "Incheon", [("仁川", "Incheon", 37.4563, 126.7052)]),
        },
    },
    "SG": {
        "zh": "新加坡", "en": "Singapore",
        "regions": {
            "SG": ("新加坡", "Singapore", [("新加坡", "Singapore", 1.3521, 103.8198)]),
        },
    },
    "AU": {
        "zh": "澳大利亚", "en": "Australia",
        "regions": {
            "NSW": ("新南威尔士州", "New South Wales", [("悉尼", "Sydney", -33.8688, 151.2093)]),
            "VIC": ("维多利亚州", "Victoria", [("墨尔本", "Melbourne", -37.8136, 144.9631)]),
            "QLD": ("昆士兰州", "Queensland", [("布里斯班", "Brisbane", -27.4698, 153.0251)]),
            "WA": ("西澳大利亚州", "Western Australia", [("珀斯", "Perth", -31.9505, 115.8605)]),
        },
    },
    "CA": {
        "zh": "加拿大", "en": "Canada",
        "regions": {
            "ON": ("安大略省", "Ontario", [("多伦多", "Toronto", 43.6532, -79.3832), ("渥太华", "Ottawa", 45.4215, -75.6972)]),
            "BC": ("不列颠哥伦比亚省", "British Columbia", [("温哥华", "Vancouver", 49.2827, -123.1207)]),
            "QC": ("魁北克省", "Quebec", [("蒙特利尔", "Montreal", 45.5017, -73.5673)]),
        },
    },
    "FR": {
        "zh": "法国", "en": "France",
        "regions": {
            "IDF": ("法兰西岛", "Île-de-France", [("巴黎", "Paris", 48.8566, 2.3522)]),
            "PAC": ("普罗旺斯", "Provence", [("马赛", "Marseille", 43.2965, 5.3698)]),
        },
    },
    "DE": {
        "zh": "德国", "en": "Germany",
        "regions": {
            "BE": ("柏林州", "Berlin", [("柏林", "Berlin", 52.5200, 13.4050)]),
            "BY": ("巴伐利亚州", "Bavaria", [("慕尼黑", "Munich", 48.1351, 11.5820)]),
            "HH": ("汉堡州", "Hamburg", [("汉堡", "Hamburg", 53.5511, 9.9937)]),
        },
    },
    "IN": {
        "zh": "印度", "en": "India",
        "regions": {
            "MH": ("马哈拉施特拉邦", "Maharashtra", [("孟买", "Mumbai", 19.0760, 72.8777), ("浦那", "Pune", 18.5204, 73.8567)]),
            "DL": ("德里", "Delhi", [("新德里", "New Delhi", 28.6139, 77.2090)]),
            "KA": ("卡纳塔克邦", "Karnataka", [("班加罗尔", "Bangalore", 12.9716, 77.5946)]),
        },
    },
}


# ============================================================
# 页面设置
# ============================================================
st.set_page_config(
    page_title="Smart Alarm Planner",
    page_icon="⏰",
    layout="wide",
)


# ============================================================
# 多语言文本
# ============================================================
TEXT = {
    "zh": {
        "title": "⏰ 智能闹钟规划器",
        "subtitle": "面向学生的 AI 每周起床时间规划工具",
        "intro": "上传你的课表和上一周的贪睡数据，系统会自动计算每天推荐的起床时间。",

        "help_title": "📖 使用说明",
        "help_body": """
**三步就能生成你的闹钟计划：**

1. **上传课表** — 支持 CSV 或 TXT 文件。不确定格式？点下面的「下载课表模板」按钮。
2. **（可选）上传贪睡数据** — 记录上一周每天贪睡的次数，系统会自动帮你提前闹钟。
3. **选择日期、国家 / 省 / 城市，点击生成** — 系统会计算每天的推荐起床时间。

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
        "step_weather": "🌦️ 4. 选择你的位置",
        "weather_country": "选择国家或地区",
        "weather_region": "选择省 / 州",
        "weather_city": "选择城市",
        "weather_hint": "系统会自动根据你选择的城市获取当地天气。",
        "step_holiday": "🏖️ 5. 节假日（可选）",
        "step4": "🚀 6. 生成闹钟计划",
        "step4_button": "生成智能闹钟计划",
        "step4_no_schedule": "请先上传你的课表。",

        "detected_title": "📚 识别到的课表",
        "col_day": "星期",
        "col_start": "开始时间",
        "col_course": "课程",

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
        "download_calendar": "下载日历文件 (.ics)",
        "download_note": "TXT 是人类可读报告；JSON 是结构化数据；ICS 可以导入手机日历。",

        "footer": "智能闹钟规划器 — 为学生设计的动态起床时间规划工具",
    },

    "en": {
        "title": "⏰ Smart Alarm Planner",
        "subtitle": "AI-powered weekly wake-up planner for students",
        "intro": "Upload your timetable and last week's snooze data. The system will calculate your recommended wake-up time for each day.",

        "help_title": "📖 How to use",
        "help_body": """
**Three steps to generate your alarm plan:**

1. **Upload timetable** — CSV or TXT. Not sure about the format? Click "Download Timetable Template".
2. **(Optional) Upload snooze data** — Records how many times you snoozed last week. The system will adjust your alarms.
3. **Pick a date, country/province/city, click Generate** — The system calculates your recommended wake-up time.

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
        "step_weather": "🌦️ 4. Select Your Location",
        "weather_country": "Select country or region",
        "weather_region": "Select province / state",
        "weather_city": "Select city",
        "weather_hint": "The system will fetch the local weather automatically for the selected city.",
        "step_holiday": "🏖️ 5. Holidays (optional)",
        "step4": "🚀 6. Generate Your Alarm Plan",
        "step4_button": "Generate Smart Alarm Plan",
        "step4_no_schedule": "Please upload your timetable first.",

        "detected_title": "📚 Detected Timetable",
        "col_day": "Day",
        "col_start": "Start",
        "col_course": "Course",

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
        "download_note": "TXT is a human-readable report; JSON is structured data; ICS can be imported into your phone calendar.",

        "footer": "Smart Alarm Planner — Dynamic wake-up planning for students",
    },
}


# ============================================================
# 侧边栏：语言 + 预设 + 设置
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
# 页面标题
# ============================================================
st.title(t["title"])
st.write(t["subtitle"])
st.info(t["intro"])

with st.expander(t["help_title"], expanded=False):
    st.markdown(t["help_body"])


# ============================================================
# 1. 上传课表 + 模板下载
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
# 2. 上传贪睡数据 + 模板下载
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
# 3. 规划日期
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
# 4. 三级联动：国家 → 省 / 州 → 城市
# ============================================================
st.header(t["step_weather"])

# -------- 第一级：国家 / 地区 --------
country_codes = list(GEO_DATA.keys())
country_names_display = [
    GEO_DATA[code]["zh"] if lang == "zh" else GEO_DATA[code]["en"]
    for code in country_codes
]

# 默认选择中国
try:
    default_country_idx = country_codes.index("CN")
except ValueError:
    default_country_idx = 0

selected_country_display = st.selectbox(
    t["weather_country"],
    country_names_display,
    index=default_country_idx,
)
selected_country_code = country_codes[
    country_names_display.index(selected_country_display)
]
country_data = GEO_DATA[selected_country_code]

# -------- 第二级：省 / 州 --------
region_codes = list(country_data["regions"].keys())
region_names_display = [
    country_data["regions"][rc][0 if lang == "zh" else 1]
    for rc in region_codes
]

col_region, col_city = st.columns(2)

with col_region:
    selected_region_display = st.selectbox(
        t["weather_region"],
        region_names_display,
    )

selected_region_code = region_codes[
    region_names_display.index(selected_region_display)
]
region_data = country_data["regions"][selected_region_code]

# -------- 第三级：城市 --------
cities = region_data[2]
city_names_display = [
    c[0] if lang == "zh" else c[1]
    for c in cities
]

with col_city:
    selected_city_display = st.selectbox(
        t["weather_city"],
        city_names_display,
    )

selected_city = cities[
    city_names_display.index(selected_city_display)
]
latitude = selected_city[2]
longitude = selected_city[3]

st.caption(t["weather_hint"])


# ============================================================
# 5. 节假日
# ============================================================
st.header(t["step_holiday"])

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


# ============================================================
# 6. 生成按钮
# ============================================================
st.header(t["step4"])

generate = st.button(
    t["step4_button"],
    type="primary",
    use_container_width=True,
)


# ============================================================
# 生成逻辑
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
    # 结果：卡片显示
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
    # 每日明细
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
    # 导出文件
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
            t["download_calendar"],
            data=ics_file.read_text(encoding="utf-8"),
            file_name="weekly_alarms.ics",
            mime="text/calendar",
        )

    st.caption(t["download_note"])

    st.divider()
    st.caption(t["footer"])
