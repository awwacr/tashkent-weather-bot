import os
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from datetime import datetime
from zoneinfo import ZoneInfo

BOT_TOKEN = os.getenv("BOT_TOKEN", "8810079431:AAHe077hsXsje5o4m-adQnvwFnWs4r03hjA")
CHAT_ID = os.getenv("CHAT_ID", "1406906655")

# Настраиваем авто-повторы (если сайты ЦБ или погоды временно зависли)
session = requests.Session()
retries = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
session.mount('https://', HTTPAdapter(max_retries=retries))

WMO_CODES = {
    0: "ясно ☀️", 1: "преимущественно ясно 🌤", 2: "переменная облачность ⛅", 3: "пасмурно ☁️",
    45: "туман 🌫", 48: "густой туман 🌫", 51: "небольшая морось 🌦", 53: "морось 🌧",
    55: "плотная морось 🌧", 61: "небольшой дождь 🌦", 63: "дождь 🌧", 65: "сильный ливень 🌧🌧",
    71: "небольшой снег 🌨", 73: "снег 🌨", 75: "сильный снегопад ❄️", 80: "ливневый дождь 🌧",
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
        current_temp = round(data["current"]["temperature_2m"])
        current_code = data["current"].get("weather_code", 0)
        temp_max = round(data["daily"]["temperature_2m_max"][0])
        temp_min = round(data["daily"]["temperature_2m_min"][0])
        hourly = data["hourly"]
        
        m_t, m_desc = analyze_period(range(6, 12), hourly)
        d_t, d_desc = analyze_period(range(12, 18), hourly)
        e_t, e_desc = analyze_period(range(18, 24), hourly)

        return {
            "current": current_temp, "status": describe_wmo(current_code),
            "max": temp_max, "min": temp_min,
            "morning": f"{m_t}, {m_desc}", "day": f"{d_t}, {d_desc}", "evening": f"{e_t}, {e_desc}"
        }
    except Exception as e:
        print(f"Ошибка погоды: {e}")
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
        elif aqi <= 300: status = "🟣 Очень вредно"
        else: status = "🟤 Опасно"
        return f"{aqi} AQI ({status})"
    except:
        return "Данные недоступны"

def get_cbu_rates():
    url = "https://cbu.uz/ru/arkhiv-kursov-valyut/json/"
    try:
        response = session.get(url, timeout=20)
        data = response.json()
        rates, rate_date = {}, ""
        for item in data:
            code = item.get("Ccy")
            if code in ["USD", "KRW", "RUB", "CNY"] and code not in rates:
                rates[code] = {"rate": item.get("Rate"), "diff": item.get("Diff")}
                if not rate_date: rate_date = item.get("Date", "")
        return rates, rate_date
    except Exception as e:
        print(f"Ошибка валют: {e}")
        return None, ""

def get_random_fact():
    """Берет случайный факт из интернета и переводит его через Google API"""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    fact_en = ""
    
    # Попытка 1: UselessFacts API
    try:
        res = session.get("https://uselessfacts.jsph.pl/api/v2/facts/random", headers=headers, timeout=10)
        fact_en = res.json().get("text", "")
    except:
        pass

    # Попытка 2 (если первый сайт упал): Nekos API
    if not fact_en:
        try:
            res = session.get("https://nekos.life/api/v2/fact", headers=headers, timeout=10)
            fact_en = res.json().get("fact", "")
        except:
            return "Сегодня факты взяли выходной, но завтра обязательно вернутся! 🧠"

    # Перевод текста на русский язык через скрытый API Google Translate
    try:
        translate_url = "https://translate.googleapis.com/translate_a/single"
        params = {
            "client": "gtx",
            "sl": "en",
            "tl": "ru",
            "dt": "t",
            "q": fact_en
        }
        res_tr = session.get(translate_url, params=params, timeout=10)
        data = res_tr.json()
        # Собираем переведенные предложения
        fact_ru = "".join([sentence[0] for sentence in data[0]])
        return fact_ru
    except Exception as e:
        print(f"Ошибка перевода: {e}")
        return fact_en # Если гугл отвалился, отправим на английском

def send_daily_report():
    tz = ZoneInfo("Asia/Tashkent")
    now = datetime.now(tz)
    months = ["", "января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"]
    weekdays = ["понедельник", "вторник", "среду", "четверг", "пятницу", "субботу", "воскресенье"]

    day_str = f"{weekdays[now.weekday()]}, {now.day} {months[now.month]}"
    
    weather = get_tashkent_weather()
    air = get_air_quality()
    rates, r_date = get_cbu_rates()
    random_fact = get_random_fact()

    if weather:
        w_text = (f"☀️ <b>Погода в Ташкенте:</b>\n• Сейчас ({now.strftime('%H:%M')}): <b>{weather['current']}°C</b> ({weather['status']})\n"
                  f"• За сутки: от <b>{weather['min']}°C</b> до <b>+{weather['max']}°C</b>\n\n"
                  f"🌫 <b>Качество воздуха:</b> {air}\n\n"
                  f"🕒 <b>Прогноз по часам на сегодня:</b>\n"
                  f"🌅 <b>Утро (до 11:00):</b> {weather['morning']}\n"
                  f"☀️ <b>День (12:00–17:00):</b> {weather['day']}\n"
                  f"🌙 <b>Вечер (после 18:00):</b> {weather['evening']}\n")
    else:
        w_text = "☀️ <b>Погода:</b> Данные временно недоступны\n"

    if rates:
        def fmt(d): return f" ({'+' if not str(d).startswith('-') else ''}{d})" if d and d != "0" else ""
        usd, cny, krw, rub = rates.get("USD",{}), rates.get("CNY",{}), rates.get("KRW",{}), rates.get("RUB",{})
        r_text = (f"🏦 <b>Курсы валют ЦБ РУз (на {r_date}):</b>\n"
                  f"🇺🇸 1 USD = <b>{usd.get('rate','N/A')}</b> сум{fmt(usd.get('diff'))}\n"
                  f"🇨🇳 1 CNY = <b>{cny.get('rate','N/A')}</b> сум{fmt(cny.get('diff'))}\n"
                  f"🇰🇷 1 KRW = <b>{krw.get('rate','N/A')}</b> сум{fmt(krw.get('diff'))}\n"
                  f"🇷🇺 1 RUB = <b>{rub.get('rate','N/A')}</b> сум{fmt(rub.get('diff'))}\n")
    else:
        r_text = "🏦 <b>Курсы валют:</b> Данные временно недоступны\n"

    full_message = f"📊 <b>Сводка на {day_str}</b>\n\n{w_text}\n{r_text}\n💡 <b>Интересный факт:</b>\n<i>{random_fact}</i>"

    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", 
                      data={"chat_id": CHAT_ID, "text": full_message, "parse_mode": "HTML"}, timeout=15)
    except Exception as e:
        print(f"Telegram API Error: {e}")

if __name__ == "__main__":
    send_daily_report()
