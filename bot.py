import os
import requests

# Токены берутся из защищенных настроек GitHub (или запасные значения)
BOT_TOKEN = os.getenv("BOT_TOKEN", "8810079431:AAHe077hsXsje5o4m-adQnvwFnWs4r03hjA")
CHAT_ID = os.getenv("CHAT_ID", "1406906655")


def get_cbu_rates():
    """Получаем официальные курсы валют ЦБ РУз"""
    url = "https://cbu.uz/ru/arkhiv-kursov-valyut/json/"
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        rates = {}
        for item in data:
            code = item.get("Ccy")
            if code in ["USD", "KRW", "RUB"]:
                rates[code] = {
                    "rate": item.get("Rate"),
                    "diff": item.get("Diff"),
                }
        return rates
    except Exception as e:
        print(f"Ошибка при получении курсов валют: {e}")
        return None


def get_tashkent_weather():
    """Получаем погоду в Ташкенте через Open-Meteo"""
    url = "https://api.open-meteo.com/v1/forecast?latitude=41.2995&longitude=69.2401&current_weather=true&daily=temperature_2m_max,temperature_2m_min&timezone=Asia/Tashkent"
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        current_temp = round(data["current_weather"]["temperature"])
        temp_max = round(data["daily"]["temperature_2m_max"][0])
        temp_min = round(data["daily"]["temperature_2m_min"][0])
        return {"current": current_temp, "max": temp_max, "min": temp_min}
    except Exception as e:
        print(f"Ошибка при получении погоды: {e}")
        return None


def send_daily_report():
    rates = get_cbu_rates()
    weather = get_tashkent_weather()

    # Погода
    if weather:
        weather_text = (
            f"☀️ <b>Погода в Ташкенте:</b>\n"
            f"• Сейчас: <b>{weather['current']}°C</b>\n"
            f"• Сегодня: от <b>{weather['min']}°C</b> до <b>{weather['max']}°C</b>\n"
        )
    else:
        weather_text = "☀️ <b>Погода:</b> Не удалось получить данные\n"

    # Курсы валют
    if rates:

        def format_diff(diff):
            if not diff or diff == "0":
                return ""
            return f" ({'+' if not str(diff).startswith('-') else ''}{diff})"

        usd_rate = rates.get("USD", {}).get("rate", "N/A")
        usd_diff = rates.get("USD", {}).get("diff", "0")
        krw_rate = rates.get("KRW", {}).get("rate", "N/A")
        krw_diff = rates.get("KRW", {}).get("diff", "0")
        rub_rate = rates.get("RUB", {}).get("rate", "N/A")
        rub_diff = rates.get("RUB", {}).get("diff", "0")

        rates_text = (
            f"🏦 <b>Курсы валют ЦБ РУз:</b>\n"
            f"🇺🇸 1 USD = <b>{usd_rate}</b> сум{format_diff(usd_diff)}\n"
            f"🇰🇷 1 KRW = <b>{krw_rate}</b> сум{format_diff(krw_diff)}\n"
            f"🇷🇺 1 RUB = <b>{rub_rate}</b> сум{format_diff(rub_diff)}\n"
        )
    else:
        rates_text = "🏦 <b>Курсы валют:</b> Не удалось получить данные\n"

    full_message = f"📊 <b>Ежедневный отчет</b>\n\n{weather_text}\n{rates_text}"

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": full_message, "parse_mode": "HTML"}

    res = requests.post(url, data=payload, timeout=10)
    if res.status_code == 200:
        print("Отчет успешно отправлен в Telegram!")
    else:
        print(f"Ошибка отправки: {res.status_code}, {res.text}")


if __name__ == "__main__":
    send_daily_report()
