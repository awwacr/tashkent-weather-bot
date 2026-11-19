import os
import sys
import json
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from datetime import datetime
from zoneinfo import ZoneInfo

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHAT_ID = os.getenv("CHAT_ID", "")
WEBAPP_URL = os.getenv("WEBAPP_URL", "")

DATA_PATH = os.path.join("docs", "data.json")

session = requests.Session()
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest"
}
session.headers.update(headers)

retries = Retry(total=4, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
session.mount('https://', HTTPAdapter(max_retries=retries))

WMO_CODES = {
    0: "ясно ☀️", 1: "преимущественно ясно 🌤", 2: "переменная облачность ⛅", 3: "пасмурно ☁️",
    45: "туман 🌫", 48: "густой туман 🌫", 51: "небольшая морось 🌦", 53: "морось 🌧",
    55: "плотная морось 🌧", 61: "небольшой дождь 🌦", 63: "дождь 🌧", 65: "сильный ливень 🌧🌧",
    71: "небольшой снег 🌨", 73: "снег 🌨", 75: "сильный снегопад ❄️", 80: "ливень 🌧",
    81: "сильный ливень 🌧", 82: "шквальный ливень ⛈", 95: "гроза ⛈", 96: "гроза с градом ⛈",
    99: "сильная гроза с градом ⛈",
}

def describe_wmo(code):
    return WMO_CODES.get(code, "облачно ⛅")

def analyze_period(hours_indices, hourly_data):
    temps = [hourly_data["temperature_2m"][i] for i in hours_indices]
    codes = [hourly_data["weather_code"][i] for i in hours_indices]
    precips = [hourly_data.get("precipitation_probability", [0]*24)[i] for i in hours_indices]

    min_t, max_t = round(min(temps)), round(max(temps))
    temp_str = f"+{min_t}°C" if min_t == max_t else f"+{min_t}°...+{max_t}°C"

    rain_codes = [c for c in codes if c in [51, 53, 55, 61, 63, 65, 80, 81, 82, 95, 96, 99]]
    max_precip = max(precips) if precips else 0

    if rain_codes:
        w_desc = describe_wmo(max(rain_codes))
        if max_precip > 20:
            w_desc += f" (вероятность {max_precip}%)"
    else:
        most_common = max(set(codes), key=codes.count)
        w_desc = describe_wmo(most_common)

    return temp_str, w_desc

def get_tashkent_weather():
    url = "https://api.open-meteo.com/v1/forecast?latitude=41.2995&longitude=69.2401&current=temperature_2m,weather_code&hourly=temperature_2m,weather_code,precipitation_probability&daily=temperature_2m_max,temperature_2m_min&timezone=Asia/Tashkent&forecast_days=1"
    try:
        response = session.get(url, timeout=15)
        data = response.json()

        m_t, m_desc = analyze_period(range(6, 12), data["hourly"])
        d_t, d_desc = analyze_period(range(12, 18), data["hourly"])
        e_t, e_desc = analyze_period(range(18, 24), data["hourly"])

        return {
            "current": round(data["current"]["temperature_2m"]),
            "status": describe_wmo(data["current"].get("weather_code", 0)),
            "max": round(data["daily"]["temperature_2m_max"][0]),
            "min": round(data["daily"]["temperature_2m_min"][0]),
            "morning": f"{m_t}, {m_desc}", "day": f"{d_t}, {d_desc}", "evening": f"{e_t}, {e_desc}"
        }
    except:
        return None

def get_air_quality():
    url = "https://air-quality-api.open-meteo.com/v1/air-quality?latitude=41.2995&longitude=69.2401&current=us_aqi&timezone=Asia/Tashkent"
    try:
        response = session.get(url, timeout=15)
        aqi = response.json()["current"]["us_aqi"]
        if aqi <= 50: status = "🟢 Хорошо"
        elif aqi <= 100: status = "🟡 Средне"
        elif aqi <= 150: status = "🟠 Вредно для уязвимых"
        elif aqi <= 200: status = "🔴 Вредно"
        else: status = "🟣 Очень вредно"
        return f"{aqi} AQI ({status})"
    except:
        return "Данные недоступны"

def get_cbu_rates():
    """Берёт официальные курсы ЦБ РУз прямо из официального JSON-шлюза cbu.uz"""
    urls = [
        "https://cbu.uz/ru/arkhiv-kursov-valyut/json/all/",
        "https://cbu.uz/ru/arkhiv-kursov-valyut/json/",
        "https://cbu.uz/uz/arkhiv-kursov-valyut/json/all/"
    ]

    for url in urls:
        try:
            res = session.get(url, timeout=12)
            if res.status_code == 200:
                data = res.json()
                if isinstance(data, list) and len(data) > 0:
                    rates = {}
                    rate_date = ""
                    for item in data:
                        code = item.get("Ccy")
                        if code in ["USD", "EUR", "RUB", "CNY", "KRW"] and code not in rates:
                            rates[code] = {
                                "rate": item.get("Rate"),
                                "diff": item.get("Diff")
                            }
                            if not rate_date:
                                rate_date = item.get("Date", "")

                    if rates:
                        return rates, f"на {rate_date}" if rate_date else "ЦБ РУз"
        except Exception as e:
            print(f"Ошибка запроса к {url}: {e}")
            continue

    return None, ""

def get_random_fact():
    fact_en = ""
    try:
        res = session.get("https://uselessfacts.jsph.pl/api/v2/facts/random", timeout=10)
        fact_en = res.json().get("text", "")
    except:
        pass

    if not fact_en:
        try:
            res = session.get("https://nekos.life/api/v2/fact", timeout=10)
            fact_en = res.json().get("fact", "")
        except:
            return "Космонавты в невесомости не могут плакать привычным образом: слезы собираются в водяные шарики вокруг глаз."

    try:
        translate_url = "https://translate.googleapis.com/translate_a/single"
        params = {"client": "gtx", "sl": "en", "tl": "ru", "dt": "t", "q": fact_en}
        res_tr = session.get(translate_url, params=params, timeout=10)
        data = res_tr.json()
        return "".join([sentence[0] for sentence in data[0]])
    except:
        return fact_en


def fetch_and_save_data():
    tz = ZoneInfo("Asia/Tashkent")
    now = datetime.now(tz)
    months = ["", "января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"]
    weekdays = ["понедельник", "вторник", "среду", "четверг", "пятницу", "субботу", "воскресенье"]
    weekdays_nom = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]

    weather = get_tashkent_weather()
    air = get_air_quality()
    rates, date_info = get_cbu_rates()
    random_fact = get_random_fact()

    payload = {
        "day_str": f"{weekdays[now.weekday()]}, {now.day} {months[now.month]}",
        "day_title": f"{weekdays_nom[now.weekday()]}, {now.day} {months[now.month]}",
        "updated_time": now.strftime("%H:%M"),
        "weather": weather,
        "air": air,
        "rates": rates,
        "rates_date": date_info,
        "fact": random_fact,
    }

    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print("Данные сохранены в", DATA_PATH)
    return payload


def send_daily_report(payload=None):
    if payload is None:
        if os.path.exists(DATA_PATH):
            with open(DATA_PATH, "r", encoding="utf-8") as f:
                payload = json.load(f)
        else:
            payload = fetch_and_save_data()

    weather = payload.get("weather")
    rates = payload.get("rates")
    day_str = payload.get("day_str", "сегодня")

    # Короткое красивое превью в чат + кнопка для открытия Liquid Glass Web App
    preview_lines = [f"✨ <b>Доброе утро! Сводка на {day_str}</b>\n"]
    if weather:
        preview_lines.append(f"🌡 Ташкент: <b>{weather['current']}°C</b> ({weather['status']})")
    if rates and rates.get("USD"):
        usd = rates["USD"]
        preview_lines.append(f"🇺🇸 USD: <b>{usd.get('rate', 'N/A')}</b> сум")
    preview_lines.append("\nНажми кнопку ниже, чтобы открыть подробную сводку 👇")

    body = {
        "chat_id": CHAT_ID,
        "text": "\n".join(preview_lines),
        "parse_mode": "HTML",
    }

    if WEBAPP_URL:
        body["reply_markup"] = {
            "inline_keyboard": [[
                {
                    "text": "✦ Открыть сводку",
                    "web_app": {"url": WEBAPP_URL}
                }
            ]]
        }

    try:
        res = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json=body,
            timeout=15
        )
        print("Telegram status:", res.status_code, res.text)
    except Exception as e:
        print(f"Telegram API Error: {e}")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "--all"
    if mode == "--fetch":
        fetch_and_save_data()
    elif mode == "--send":
        send_daily_report()
    else:
        data = fetch_and_save_data()
        send_daily_report(data)
