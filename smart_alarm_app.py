#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Smart Alarm Planner
一个面向学生的 AI 智能作息与动态闹钟规划终端 App。

功能：
1. 读取 CSV / TXT 课表
2. 可选读取截图：需要本机安装 Tesseract + pytesseract
3. 根据第一节课时间计算起床时间
4. 天气补偿：雨/雪/恶劣天气自动增加安全余量
5. 根据上一周平均贪睡次数自适应调整
6. 无课日 / 法定节假日自动跳过
7. 05:30 前响铃时给出睡眠预警
8. 生成：
   - weekly_alarm_plan.txt：人类可读的计算明细
   - weekly_alarm_plan.json：结构化数据
   - weekly_alarms.ics：可导入 Apple Calendar / Google Calendar / Outlook
9. 数据缺失时使用默认值平滑兜底

安装：
    pip install requests

可选：
    pip install holidays pillow pytesseract

运行：
    python smart_alarm_app.py --schedule schedule.csv --snooze snooze.csv

截图课表：
    python smart_alarm_app.py --schedule timetable.png --snooze snooze.csv

如果不提供天气 API 数据，程序会使用默认天气安全余量。
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import sys
from dataclasses import dataclass, asdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

DEFAULTS = {
    "prep_minutes": 45,              # 洗漱 + 穿衣 + 早餐 + 出门准备
    "weather_buffer_minutes": 5,     # 无天气数据时的默认余量
    "traffic_buffer_minutes": 5,     # 无交通数据时的默认余量
    "snooze_penalty_minutes": 5,     # 每天超过阈值后的统一提前量
    "snooze_threshold": 2,           # 平均贪睡 > 2 次才触发
    "minimum_alarm": "05:30",
}

WEATHER_RULES = {
    "clear": 0,
    "partly cloudy": 0,
    "cloudy": 0,
    "rain": 10,
    "heavy rain": 15,
    "snow": 15,
    "heavy snow": 20,
    "thunderstorm": 20,
    "storm": 20,
}

WEEKDAYS = {
    "monday": 0, "mon": 0, "周一": 0, "星期一": 0,
    "tuesday": 1, "tue": 1, "周二": 1, "星期二": 1,
    "wednesday": 2, "wed": 2, "周三": 2, "星期三": 2,
    "thursday": 3, "thu": 3, "周四": 3, "星期四": 3,
    "friday": 4, "fri": 4, "周五": 4, "星期五": 4,
    "saturday": 5, "sat": 5, "周六": 5, "星期六": 5,
    "sunday": 6, "sun": 6, "周日": 6, "星期日": 6,
}


@dataclass
class ClassItem:
    day: int
    start: str
    course: str = ""


@dataclass
class DayPlan:
    date: str
    weekday: str
    status: str
    first_class: Optional[str]
    course: str
    base_alarm: Optional[str]
    prep_minutes: int
    weather_condition: str
    weather_adjustment: int
    traffic_adjustment: int
    snooze_adjustment: int
    final_alarm: Optional[str]
    warning: str
    explanation: str


def parse_time(value: str) -> tuple[int, int]:
    """支持 8:00 / 08:00 / 8：00 / 8.00 等常见写法。"""
    value = value.strip().replace("：", ":").replace(".", ":")
    m = re.match(r"^(\d{1,2}):(\d{1,2})$", value)
    if not m:
        raise ValueError(f"无法识别时间：{value}")
    h, minute = int(m.group(1)), int(m.group(2))
    if not (0 <= h <= 23 and 0 <= minute <= 59):
        raise ValueError(f"时间超出范围：{value}")
    return h, minute


def time_to_minutes(value: str) -> int:
    h, m = parse_time(value)
    return h * 60 + m


def minutes_to_time(total: int) -> str:
    total %= 24 * 60
    return f"{total // 60:02d}:{total % 60:02d}"


def normalize_weekday(value: str) -> int:
    key = value.strip().lower()
    if key in WEEKDAYS:
        return WEEKDAYS[key]
    if key.isdigit() and 0 <= int(key) <= 6:
        return int(key)
    raise ValueError(f"无法识别星期：{value}")


def read_schedule(path: str) -> list[ClassItem]:
    """
    CSV 推荐格式：
    weekday,start,course
    Monday,08:30,Programming
    Tuesday,10:00,Mathematics

    TXT 也支持：
    Monday 08:30 Programming
    周一 08:30 编程
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"找不到课表文件：{path}")

    if p.suffix.lower() == ".csv":
        items = []
        with p.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            fields = {x.lower().strip(): x for x in (reader.fieldnames or [])}

            # 尝试找到星期 / 时间 / 课程列
            day_col = next((fields[k] for k in fields if k in
                            {"weekday", "day", "星期", "星期几"}), None)
            time_col = next((fields[k] for k in fields if k in
                             {"start", "start_time", "time", "开始时间"}), None)
            course_col = next((fields[k] for k in fields if k in
                               {"course", "课程", "name"}), None)

            if not day_col or not time_col:
                raise ValueError(
                    "CSV 至少需要 weekday/day/星期 和 start/start_time/time/开始时间 两列。"
                )

            for row in reader:
                if not row.get(day_col) or not row.get(time_col):
                    continue
                items.append(
                    ClassItem(
                        day=normalize_weekday(row[day_col]),
                        start=row[time_col].strip(),
                        course=(row.get(course_col, "") if course_col else "").strip()
                    )
                )
        return items

    # TXT / 普通文本
    text = p.read_text(encoding="utf-8")
    return parse_schedule_text(text)


def parse_schedule_text(text: str) -> list[ClassItem]:
    items = []

    # 匹配：
    # Monday 08:30 Programming
    # 周一 08:30 编程
    pattern = re.compile(
        r"(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|"
        r"Mon|Tue|Wed|Thu|Fri|Sat|Sun|周一|周二|周三|周四|周五|周六|周日|"
        r"星期一|星期二|星期三|星期四|星期五|星期六|星期日)"
        r"\s+(\d{1,2}[:：.]\d{2})\s*(.*)",
        re.IGNORECASE
    )

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = pattern.search(line)
        if m:
            items.append(
                ClassItem(
                    day=normalize_weekday(m.group(1)),
                    start=m.group(2),
                    course=m.group(3).strip(" ,，-\t")
                )
            )

    if not items:
        raise ValueError(
            "没有从文本中识别到课表。请使用类似：\n"
            "Monday 08:30 Programming\n"
            "Tuesday 10:00 Mathematics"
        )
    return items


def parse_image_schedule(path: str) -> list[ClassItem]:
    """
    可选 OCR。
    需要：
        pip install pillow pytesseract

    同时需要系统安装 Tesseract OCR。
    """
    try:
        from PIL import Image
        import pytesseract
    except ImportError:
        raise RuntimeError(
            "图片课表需要额外安装：pip install pillow pytesseract"
        )

    text = pytesseract.image_to_string(Image.open(path))
    if not text.strip():
        raise RuntimeError("OCR 没有识别出文字，请使用 CSV/TXT 或提高截图清晰度。")
    print("\n[OCR 识别结果]")
    print(text)
    print("[/OCR 识别结果]\n")
    return parse_schedule_text(text)


def read_snooze(path: Optional[str]) -> float:
    """
    snooze.csv 推荐：
    date,snooze_count
    2026-10-01,3
    2026-10-02,1
    """
    if not path:
        print("[兜底] 未提供贪睡数据，默认平均每天 0 次。")
        return 0.0

    p = Path(path)
    if not p.exists():
        print("[兜底] 找不到贪睡文件，默认平均每天 0 次。")
        return 0.0

    values = []
    with p.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw = row.get("snooze_count") or row.get("snooze") or row.get("贪睡次数")
            if raw is None:
                continue
            try:
                values.append(float(raw))
            except ValueError:
                pass

    if not values:
        print("[兜底] 贪睡数据为空，默认平均每天 0 次。")
        return 0.0

    return sum(values) / len(values)


def get_weather_forecast(
    target_date: date,
    latitude: Optional[float],
    longitude: Optional[float]
) -> tuple[str, int]:
    """
    使用 Open-Meteo 获取当天白天的天气风险。
    如果没有经纬度 / 网络 / API 失败，则返回默认余量。

    注意：
    这里不会自动获取精确地理位置，以保护隐私。
    用户可以手动输入学校附近的经纬度。
    """
    if latitude is None or longitude is None:
        return "unknown", DEFAULTS["weather_buffer_minutes"]

    try:
        import requests
    except ImportError:
        return "unknown", DEFAULTS["weather_buffer_minutes"]

    try:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "daily": "weather_code,precipitation_probability_max,snowfall_sum",
            "timezone": "auto",
            "start_date": target_date.isoformat(),
            "end_date": target_date.isoformat(),
        }
        response = requests.get(url, params=params, timeout=8)
        response.raise_for_status()
        data = response.json()

        code = data["daily"]["weather_code"][0]
        rain_prob = data["daily"]["precipitation_probability_max"][0] or 0
        snowfall = data["daily"]["snowfall_sum"][0] or 0

        # WMO weather codes
        if snowfall >= 5:
            condition = "snow"
            adjustment = 15 if snowfall < 15 else 20
        elif code in {95, 96, 99}:
            condition = "thunderstorm"
            adjustment = 20
        elif code in {61, 63, 65, 80, 81, 82}:
            condition = "heavy rain" if rain_prob >= 70 else "rain"
            adjustment = 15 if rain_prob >= 70 else 10
        elif code in {1, 2, 3, 45, 48}:
            condition = "cloudy"
            adjustment = 0
        else:
            condition = "clear"
            adjustment = 0

        return condition, adjustment

    except Exception:
        return "unknown", DEFAULTS["weather_buffer_minutes"]


def get_traffic_adjustment(
    transport: str,
    weather_adjustment: int
) -> int:
    """
    简化的交通安全模型。
    实际项目可进一步接 Google Maps / 高德 / 百度等 API。

    步行：天气影响较明显
    骑行：天气影响更明显
    公交：默认增加少量缓冲
    """
    transport = transport.lower().strip()

    if transport in {"walk", "walking", "步行"}:
        return 5 if weather_adjustment >= 10 else 0

    if transport in {"bike", "bicycle", "cycling", "骑行"}:
        return 10 if weather_adjustment >= 10 else 3

    if transport in {"bus", "metro", "public", "public transport", "公交", "地铁", "公共交通"}:
        return 5 if weather_adjustment >= 10 else 3

    return DEFAULTS["traffic_buffer_minutes"]


def next_monday(start: date) -> date:
    return start + timedelta(days=(7 - start.weekday()) % 7)


def parse_holiday_file(path: Optional[str]) -> set[str]:
    """
    holiday.txt：
    一行一个 YYYY-MM-DD
    """
    if not path:
        return set()

    p = Path(path)
    if not p.exists():
        return set()

    holidays = set()
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if re.match(r"^\d{4}-\d{2}-\d{2}$", line):
            holidays.add(line)
    return holidays


def try_get_holidays(year: int) -> set[str]:
    """
    如果安装 holidays，则自动识别法定节假日。
    香港 / 中国大陆等地区的具体假期安排差异较大，
    因此默认不强行猜测，建议使用 holiday.txt 精确指定。
    """
    try:
        import holidays
        # 不自动假定地区，避免把美国/香港/大陆规则混在一起。
        return set()
    except ImportError:
        return set()


def calculate_plan(
    week_start: date,
    schedule: list[ClassItem],
    avg_snooze: float,
    transport: str,
    latitude: Optional[float],
    longitude: Optional[float],
    holiday_dates: set[str],
) -> list[DayPlan]:

    # 上周平均贪睡超过 2 次：统一提前。
    if avg_snooze > DEFAULTS["snooze_threshold"]:
        snooze_adjustment = math.ceil(avg_snooze - DEFAULTS["snooze_threshold"]) \
                            * DEFAULTS["snooze_penalty_minutes"]
    else:
        snooze_adjustment = 0

    # 每天第一节课
    first_classes = {}
    for item in schedule:
        try:
            start_min = time_to_minutes(item.start)
        except ValueError:
            continue

        if item.day not in first_classes or start_min < time_to_minutes(first_classes[item.day].start):
            first_classes[item.day] = item

    plans = []

    for i in range(7):
        d = week_start + timedelta(days=i)
        weekday_name = d.strftime("%A")
        date_str = d.isoformat()

        if date_str in holiday_dates:
            plans.append(
                DayPlan(
                    date=date_str,
                    weekday=weekday_name,
                    status="HOLIDAY_SKIP",
                    first_class=None,
                    course="",
                    base_alarm=None,
                    prep_minutes=DEFAULTS["prep_minutes"],
                    weather_condition="holiday",
                    weather_adjustment=0,
                    traffic_adjustment=0,
                    snooze_adjustment=0,
                    final_alarm=None,
                    warning="法定节假日：跳过闹钟",
                    explanation="当天属于 holiday.txt 中设置的假期，因此不配置起床闹钟。"
                )
            )
            continue

        item = first_classes.get(i)

        if not item:
            plans.append(
                DayPlan(
                    date=date_str,
                    weekday=weekday_name,
                    status="NO_CLASS_SKIP",
                    first_class=None,
                    course="",
                    base_alarm=None,
                    prep_minutes=DEFAULTS["prep_minutes"],
                    weather_condition="no class",
                    weather_adjustment=0,
                    traffic_adjustment=0,
                    snooze_adjustment=0,
                    final_alarm=None,
                    warning="无课日：跳过闹钟",
                    explanation="当天没有识别到课程，因此开启跳过闹钟模式。"
                )
            )
            continue

        class_minutes = time_to_minutes(item.start)
        base_alarm_minutes = class_minutes - DEFAULTS["prep_minutes"]
        base_alarm = minutes_to_time(base_alarm_minutes)

        weather_condition, weather_adjustment = get_weather_forecast(
            d, latitude, longitude
        )

        traffic_adjustment = get_traffic_adjustment(
            transport, weather_adjustment
        )

        # “调整”意味着进一步提前，所以从基准时间中减去。
        final_minutes = (
            base_alarm_minutes
            - weather_adjustment
            - traffic_adjustment
            - snooze_adjustment
        )
        final_alarm = minutes_to_time(final_minutes)

        warning = ""
        if time_to_minutes(final_alarm) < time_to_minutes(DEFAULTS["minimum_alarm"]):
            warning = (
                "健康睡眠预警：计算出的响铃时间早于 05:30，"
                "建议检查前一晚入睡时间，并避免长期睡眠不足。"
            )

        explanation = (
            f"第一节课 {item.start} → "
            f"基础扣除 {DEFAULTS['prep_minutes']} 分钟 → {base_alarm}；"
            f"天气补偿 -{weather_adjustment} 分钟；"
            f"交通补偿 -{traffic_adjustment} 分钟；"
            f"贪睡调整 -{snooze_adjustment} 分钟；"
            f"最终 {final_alarm}"
        )

        plans.append(
            DayPlan(
                date=date_str,
                weekday=weekday_name,
                status="ALARM",
                first_class=item.start,
                course=item.course,
                base_alarm=base_alarm,
                prep_minutes=DEFAULTS["prep_minutes"],
                weather_condition=weather_condition,
                weather_adjustment=weather_adjustment,
                traffic_adjustment=traffic_adjustment,
                snooze_adjustment=snooze_adjustment,
                final_alarm=final_alarm,
                warning=warning,
                explanation=explanation,
            )
        )

    return plans


def make_ics(plans: list[DayPlan], output: str):
    """
    生成标准 ICS 日历文件。
    每个闹钟作为一个全天可导入的“起床提醒事件”。

    不同系统对 ALARM 的支持程度不同，因此这里同时设置：
    - DTSTART
    - VALARM
    """
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Smart Alarm Planner//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]

    for plan in plans:
        if plan.status != "ALARM" or not plan.final_alarm:
            continue

        dt = datetime.strptime(
            f"{plan.date} {plan.final_alarm}",
            "%Y-%m-%d %H:%M"
        )
        dtstamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        dtstart = dt.strftime("%Y%m%dT%H%M%S")

        uid = f"smart-alarm-{plan.date}@smart-alarm-app"

        title = f"⏰ 起床：{plan.course or '上课'}"

        lines.extend([
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{dtstamp}",
            f"DTSTART:{dtstart}",
            f"SUMMARY:{title}",
            f"DESCRIPTION:{plan.explanation}",
            "BEGIN:VALARM",
            "TRIGGER:PT0M",
            "ACTION:DISPLAY",
            f"DESCRIPTION:{title}",
            "END:VALARM",
            "END:VEVENT",
        ])

    lines.append("END:VCALENDAR")

    Path(output).write_text("\r\n".join(lines), encoding="utf-8")


def save_json(plans: list[DayPlan], output: str, avg_snooze: float):
    data = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "average_snooze_last_week": round(avg_snooze, 2),
        "default_settings": DEFAULTS,
        "plans": [asdict(x) for x in plans],
    }
    Path(output).write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def save_report(
    plans: list[DayPlan],
    output: str,
    avg_snooze: float,
    transport: str,
    week_start: date,
):
    lines = [
        "SMART ALARM PLANNER — WEEKLY REPORT",
        "=" * 70,
        f"规划周：{week_start.isoformat()} 至 {(week_start + timedelta(days=6)).isoformat()}",
        f"上一周平均贪睡次数：{avg_snooze:.2f} 次/天",
        f"出行方式：{transport}",
        f"基础准备时间：{DEFAULTS['prep_minutes']} 分钟",
        "",
    ]

    for p in plans:
        lines.append(f"[{p.date} {p.weekday}]")
        lines.append(f"状态：{p.status}")

        if p.status == "ALARM":
            lines.append(f"第一节课：{p.first_class}  | 课程：{p.course or '未填写'}")
            lines.append(f"基准闹钟：{p.base_alarm}")
            lines.append(f"天气：{p.weather_condition}，提前 {p.weather_adjustment} 分钟")
            lines.append(f"交通：提前 {p.traffic_adjustment} 分钟")
            lines.append(f"贪睡：提前 {p.snooze_adjustment} 分钟")
            lines.append(f"最终响铃：{p.final_alarm}")
            if p.warning:
                lines.append(f"⚠ {p.warning}")
            lines.append(f"计算：{p.explanation}")
        else:
            lines.append(f"最终响铃：跳过")
            lines.append(f"说明：{p.warning}")

        lines.append("-" * 70)

    Path(output).write_text("\n".join(lines), encoding="utf-8")


def print_summary(plans: list[DayPlan], avg_snooze: float):
    print("\n" + "=" * 70)
    print("SMART ALARM PLANNER")
    print("=" * 70)
    print(f"上一周平均贪睡：{avg_snooze:.2f} 次/天")
    print()

    for p in plans:
        if p.status == "ALARM":
            print(
                f"{p.date} {p.weekday:<9} | "
                f"第一节 {p.first_class:<5} | "
                f"基准 {p.base_alarm} | "
                f"天气 -{p.weather_adjustment:02d} | "
                f"交通 -{p.traffic_adjustment:02d} | "
                f"贪睡 -{p.snooze_adjustment:02d} | "
                f"最终 {p.final_alarm}"
            )
            if p.warning:
                print("  ⚠ " + p.warning)
        else:
            print(f"{p.date} {p.weekday:<9} | {p.warning}")

    print("=" * 70)
    print("已生成：")
    print("  weekly_alarm_plan.txt")
    print("  weekly_alarm_plan.json")
    print("  weekly_alarms.ics")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="学生 AI 智能作息与动态闹钟规划终端 App"
    )

    parser.add_argument(
        "--schedule", required=True,
        help="课表文件：CSV / TXT / PNG / JPG"
    )
    parser.add_argument(
        "--snooze",
        help="上一周贪睡数据 CSV"
    )
    parser.add_argument(
        "--week",
        help="规划周的周一日期，例如 2026-10-12；不填则自动取下一个周一"
    )
    parser.add_argument(
        "--transport",
        default="public",
        choices=["walk", "bike", "public"],
        help="出行方式：walk / bike / public"
    )
    parser.add_argument(
        "--latitude", type=float,
        help="学校附近纬度，例如 22.304"
    )
    parser.add_argument(
        "--longitude", type=float,
        help="学校附近经度，例如 114.179"
    )
    parser.add_argument(
        "--holidays",
        help="holiday.txt，一行一个 YYYY-MM-DD"
    )
    parser.add_argument(
        "--output-dir",
        default="smart_alarm_output",
        help="输出文件夹"
    )

    args = parser.parse_args()

    # 1. 确定下周周一
    if args.week:
        week_start = datetime.strptime(args.week, "%Y-%m-%d").date()
    else:
        week_start = next_monday(date.today())

    # 2. 读取课表
    schedule_path = Path(args.schedule)
    if schedule_path.suffix.lower() in {".png", ".jpg", ".jpeg"}:
        schedule = parse_image_schedule(str(schedule_path))
    else:
        schedule = read_schedule(str(schedule_path))

    # 3. 读取贪睡数据
    avg_snooze = read_snooze(args.snooze)

    # 4. 读取节假日
    holiday_dates = parse_holiday_file(args.holidays)

    # 5. 计算
    plans = calculate_plan(
        week_start=week_start,
        schedule=schedule,
        avg_snooze=avg_snooze,
        transport=args.transport,
        latitude=args.latitude,
        longitude=args.longitude,
        holiday_dates=holiday_dates,
    )

    # 6. 输出
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    report_file = output_dir / "weekly_alarm_plan.txt"
    json_file = output_dir / "weekly_alarm_plan.json"
    ics_file = output_dir / "weekly_alarms.ics"

    save_report(plans, str(report_file), avg_snooze, args.transport, week_start)
    save_json(plans, str(json_file), avg_snooze)
    make_ics(plans, str(ics_file))

    print_summary(plans, avg_snooze)

    print(f"报告：{report_file}")
    print(f"JSON：{json_file}")
    print(f"日历：{ics_file}")


if __name__ == "__main__":
    main()
