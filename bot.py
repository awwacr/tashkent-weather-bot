import os
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from datetime import datetime
from zoneinfo import ZoneInfo

BOT_TOKEN = os.getenv("BOT_TOKEN", "8810079431:AAHe077hsXsje5o4m-adQnvwFnWs4r03hjA")
CHAT_ID = os.getenv("CHAT_ID", "1406906655")
APINEX_API_KEY = os.getenv("APINEX_API_KEY", "")

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
    except:
        return None, ""

def get_ai_message(weather_status, aqi_status):
    if not APINEX_API_KEY:
        return "🧠 Подключите API-ключ нейросети (APINEX_API_KEY), чтобы увидеть здесь уникальный текст!"
    
    api_url = "https://api.apinex.bond/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {APINEX_API_KEY}",
        "Content-Type": "application/json"
    }
    
    prompt = (
        f"Сегодня в Ташкенте погода: {weather_status}, качество воздуха: {aqi_status}. "
        "Напиши один очень интересный, малоизвестный факт (из науки, истории, природы или космоса) "
        "и добавь одно короткое пожелание на день, учитывая текущую погоду и воздух. "
        "Текст должен быть коротким, легким для чтения, с 1-2 эмодзи. "
        "Не используй приветствия вроде 'Привет' или 'Вот факт'."
    )
    
    payload = {
        "model": "free/glm-5.3",
        "messages": [
            {"role": "system", "content": "Ты крутой ассистент, который пишет утренние сводки."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 250,
        "temperature": 0.7
    }
    
    try:
        res = session.post(api_url, headers=headers, json=payload, timeout=25)
        if res.status_code == 200:
            return res.json()["choices"][0]["message"]["content"].strip()
        else:
            print(f"Ошибка нейросети: {res.text}")
            return "Сегодня нейросеть отдыхает, но завтра обязательно расскажет что-то интересное! ✨"
    except Exception as e:
        print(f"Сбой соединения с AI: {e}")
        return "Нейросеть сейчас недоступна 🤖"

def send_daily_report():
    tz = ZoneInfo("Asia/Tashkent")
    now = datetime.now(tz)
    months = ["", "января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"]
    weekdays = ["понедельник", "вторник", "среду", "четверг", "пятницу", "субботу", "воскресенье"]

    day_str = f"{weekdays[now.weekday()]}, {now.day} {months[now.month]}"
    
    weather = get_tashkent_weather()
    air = get_air_quality()
    rates, r_date = get_cbu_rates()

    weather_info = f"{weather['current']}°C, {weather['status']}" if weather else "неизвестно"
    
    # Запрос к нейросети GLM-5.3
    ai_text = get_ai_message(weather_info, air)

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

    full_message = f"📊 <b>Сводка на {day_str}</b>\n\n{w_text}\n{r_text}\n💡 <b>От нейросети:</b>\n<i>{ai_text}</i>"

    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", 
                      data={"chat_id": CHAT_ID, "text": full_message, "parse_mode": "HTML"}, timeout=15)
    except Exception as e:
        print(f"Telegram API Error: {e}")

if __name__ == "__main__":
    send_daily_report()
