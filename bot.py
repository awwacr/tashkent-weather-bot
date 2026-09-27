from datetime import datetime
import os
import requests
import random
from zoneinfo import ZoneInfo
from deep_translator import GoogleTranslator

BOT_TOKEN = os.getenv("BOT_TOKEN", "8810079431:AAHe077hsXsje5o4m-adQnvwFnWs4r03hjA")
CHAT_ID = os.getenv("CHAT_ID", "1406906655")

WMO_CODES = {
    0: "ясно ☀️",
    1: "преимущественно ясно 🌤",
    2: "переменная облачность ⛅",
    3: "пасмурно ☁️",
    45: "туман 🌫",
    48: "густой туман 🌫",
    51: "небольшая морось 🌦",
    53: "морось 🌧",
    55: "плотная морось 🌧",
    61: "небольшой дождь 🌦",
    63: "дождь 🌧",
    65: "сильный ливень 🌧🌧",
    71: "небольшой снег 🌨",
    73: "снег 🌨",
    75: "сильный снегопад ❄️",
    80: "ливневый дождь 🌧",
    81: "сильный ливень 🌧",
    82: "шквальный ливень ⛈",
    95: "гроза ⛈",
    96: "гроза с градом ⛈",
    99: "сильная гроза с градом ⛈",
}

def describe_wmo(code):
    return WMO_CODES.get(code, "облачно ⛅")

def analyze_period(hours_indices, hourly_data):
    temps = [hourly_data["temperature_2m"][i] for i in hours_indices]
    codes = [hourly_data["weather_code"][i] for i in hours_indices]
    precips = [
        hourly_data.get("precipitation_probability", [0] * 24)[i]
        for i in hours_indices
    ]

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
    url = (
        "https://api.open-meteo.com/v1/forecast?"
        "latitude=41.2995&longitude=69.2401&"
        "current=temperature_2m,weather_code&"
        "hourly=temperature_2m,weather_code,precipitation_probability&"
        "daily=temperature_2m_max,temperature_2m_min&"
        "timezone=Asia/Tashkent&forecast_days=1"
    )
    try:
        response = requests.get(url, timeout=12)
        data = response.json()

        current_temp = round(data["current"]["temperature_2m"])
        current_code = data["current"].get("weather_code", 0)
        current_status = describe_wmo(current_code)

        temp_max = round(data["daily"]["temperature_2m_max"][0])
        temp_min = round(data["daily"]["temperature_2m_min"][0])

        hourly = data["hourly"]
        morning_t, morning_desc = analyze_period(range(6, 12), hourly)
        day_t, day_desc = analyze_period(range(12, 18), hourly)
        evening_t, evening_desc = analyze_period(range(18, 24), hourly)

        return {
            "current": current_temp,
            "status": current_status,
            "max": temp_max,
            "min": temp_min,
            "morning": f"{morning_t}, {morning_desc}",
            "day": f"{day_t}, {day_desc}",
            "evening": f"{evening_t}, {evening_desc}",
        }
    except Exception as e:
        print(f"Ошибка погоды: {e}")
        return None

def get_air_quality():
    url = "https://air-quality-api.open-meteo.com/v1/air-quality?latitude=41.2995&longitude=69.2401&current=us_aqi&timezone=Asia/Tashkent"
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        aqi = data["current"]["us_aqi"]
        
        if aqi <= 50:
            status = "🟢 Хорошо"
        elif aqi <= 100:
            status = "🟡 Средне"
        elif aqi <= 150:
            status = "🟠 Вредно для уязвимых"
        elif aqi <= 200:
            status = "🔴 Вредно"
        elif aqi <= 300:
            status = "🟣 Очень вредно"
        else:
            status = "🟤 Опасно"
            
        return f"{aqi} AQI ({status})"
    except Exception as e:
        print(f"Ошибка AQI: {e}")
        return "Данные недоступны"

def get_cbu_rates():
    url = "https://cbu.uz/ru/arkhiv-kursov-valyut/json/"
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        rates = {}
        rate_date = ""

        for item in data:
            code = item.get("Ccy")
            if code in ["USD", "KRW", "RUB", "CNY"] and code not in rates:
                rates[code] = {
                    "rate": item.get("Rate"),
                    "diff": item.get("Diff"),
                }
                if not rate_date:
                    rate_date = item.get("Date", "")

        return rates, rate_date
    except Exception as e:
        print(f"Ошибка валют: {e}")
        return None, ""

def get_random_fact():
    """Маскируемся под браузер и пробуем 2 разных API"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    }
    
    # Попытка №1: Основное API
    try:
        res = requests.get("https://uselessfacts.jsph.pl/api/v2/facts/random?language=en", headers=headers, timeout=8)
        if res.status_code == 200:
            fact_en = res.json().get("text", "")
            return GoogleTranslator(source='en', target='ru').translate(fact_en)
    except Exception as e:
        print(f"API 1 упал: {e}")
        
    # Попытка №2: Запасное API (Popcat)
    try:
        res2 = requests.get("https://api.popcat.xyz/fact", headers=headers, timeout=8)
        if res2.status_code == 200:
            fact_en2 = res2.json().get("fact", "")
            return GoogleTranslator(source='en', target='ru').translate(fact_en2)
    except Exception as e:
        print(f"API 2 упал: {e}")

    # Попытка №3: Случайный факт из базы (если интернет отрубило полностью)
    backup_facts = [
        "Космонавты не могут плакать в космосе: из-за невесомости слезы собираются в шарики вокруг глаз.",
        "Ленивцы могут задерживать дыхание под водой до 40 минут — это дольше, чем дельфины!",
        "В космосе два чистых куска металла мгновенно прилипают друг к другу намертво (холодная сварка).",
        "Мед — единственный продукт на планете, который никогда не портится.",
        "У осьминога три сердца, синяя кровь и девять мозговых центров.",
        "Роговица глаза — единственная ткань человека, получающая кислород прямо из воздуха."
    ]
    return random.choice(backup_facts)

def send_daily_report():
    tashkent_tz = ZoneInfo("Asia/Tashkent")
    now = datetime.now(tashkent_tz)

    months = ["", "января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"]
    weekdays = ["понедельник", "вторник", "среду", "четверг", "пятницу", "субботу", "воскресенье"]

    day_str = f"{weekdays[now.weekday()]}, {now.day} {months[now.month]}"
    current_time_str = now.strftime("%H:%M")

    weather = get_tashkent_weather()
    air_quality = get_air_quality()
    rates, rate_date = get_cbu_rates()
    random_fact = get_random_fact()

    if weather:
        weather_text = (
            f"☀️ <b>Погода в Ташкенте:</b>\n"
            f"• Сейчас ({current_time_str}): <b>{weather['current']}°C</b> ({weather['status']})\n"
            f"• За сутки: от <b>{weather['min']}°C</b> до <b>+{weather['max']}°C</b>\n\n"
            f"🌫 <b>Качество воздуха:</b> {air_quality}\n\n"
            f"🕒 <b>Прогноз по часам на сегодня:</b>\n"
            f"🌅 <b>Утро (до 11:00):</b> {weather['morning']}\n"
            f"☀️ <b>День (12:00–17:00):</b> {weather['day']}\n"
            f"🌙 <b>Вечер (после 18:00):</b> {weather['evening']}\n"
        )
    else:
        weather_text = "☀️ <b>Погода:</b> Данные временно недоступны\n"

    if rates:
        def format_diff(diff):
            if not diff or diff == "0":
                return ""
            return f" ({'+' if not str(diff).startswith('-') else ''}{diff})"

        usd = rates.get("USD", {})
        cny = rates.get("CNY", {})
        krw = rates.get("KRW", {})
        rub = rates.get("RUB", {})

        date_note = f" (на {rate_date})" if rate_date else ""
        rates_text = (
            f"🏦 <b>Курсы валют ЦБ РУз{date_note}:</b>\n"
            f"🇺🇸 1 USD = <b>{usd.get('rate', 'N/A')}</b> сум{format_diff(usd.get('diff', '0'))}\n"
            f"🇨🇳 1 CNY = <b>{cny.get('rate', 'N/A')}</b> сум{format_diff(cny.get('diff', '0'))}\n"
            f"🇰🇷 1 KRW = <b>{krw.get('rate', 'N/A')}</b> сум{format_diff(krw.get('diff', '0'))}\n"
            f"🇷🇺 1 RUB = <b>{rub.get('rate', 'N/A')}</b> сум{format_diff(rub.get('diff', '0'))}\n"
        )
    else:
        rates_text = "🏦 <b>Курсы валют:</b> Данные временно недоступны\n"

    full_message = (
        f"📊 <b>Сводка на {day_str}</b>\n\n"
        f"{weather_text}\n"
        f"{rates_text}\n"
        f"💡 <b>Интересный факт:</b>\n<i>{random_fact}</i>"
    )

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": full_message, "parse_mode": "HTML"}

    try:
        res = requests.post(url, data=payload, timeout=12)
        if res.status_code == 200:
            print("Отчет успешно отправлен в Telegram!")
        else:
            print(f"Ошибка отправки: {res.status_code}, {res.text}")
    except Exception as e:
        print(f"Ошибка сети: {e}")

if __name__ == "__main__":
    send_daily_report()
