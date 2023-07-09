import sqlite3
from transliterate import translit
from geopy import Nominatim
from suntime import Sun
import requests
from datetime import datetime
import schedule
import telebot
from threading import Thread
from time import sleep
from functools import cache

ACCUWEATHER_API_KEY = "qsgs86Lya91hSOnHHfmwHr8VLUvg3M1W"
NOTIFICATION_HOUR = 22
SAFETY_VISIBILITY = 1.5
API_ID = "b4709352c85607f12979db127ef36c97"
CITY_ID_SEARCH_LINK = "http://api.openweathermap.org/data/2.5/find"
WEATHER_SEARCH_LINK = "http://api.openweathermap.org/data/2.5/weather"
FIVE_DAY_FORECAST_SEARCH_LINK = "http://api.openweathermap.org/data/2.5/forecast"
bot = telebot.TeleBot("5271653231:AAEkzk5kIs3E3Sm2UcQSQAfZ36GCRDVk7Z4")
MAIN_CITY = "Красноярск"
DATABASE_NAME = 'weather_telebot.sqlite'


# Класс, отвечающий за работу со статистическими данными и графическим интерфейсом
class Weather:
    def __init__(self, city):
        self.city = city
        self.city_id = 0
        # Получение id исследуемого города в API сервисе
        self.get_city_id()

    @staticmethod
    def is_city_exist(city):
        cities_query = requests.get(CITY_ID_SEARCH_LINK,
                                    params={"q": city,
                                            "type": "like",
                                            "units": "metric",
                                            "APPID": API_ID})
        # Разборка пакета JSON на необходимые данные о городе с помощью функции .json()
        cities_data = cities_query.json()
        return len(cities_data['list'])

    # Функция, получающая id исследуемого города в API сервисе
    def get_city_id(self):
        # Получение пакета данных о городе в формате JSON на сформированный запрос к API сервису
        cities_query = requests.get(CITY_ID_SEARCH_LINK,
                                    params={"q": self.city,
                                            "type": "like",
                                            "units": "metric",
                                            "APPID": API_ID})
        # Разборка пакета JSON на необходимые данные о городе с помощью функции .json()
        cities_data = cities_query.json()
        # Присваивание к city_id данных пакета
        self.city_id = cities_data["list"][0]["id"]

    # Функция, возвращающая текущую погоду исследуемого города в API сервисе
    def get_current_weather(self):
        # Получение пакета данных о текущей погоде в формате JSON на сформированный запрос к API сервису
        weather_query = requests.get(WEATHER_SEARCH_LINK,
                                     params={"id": self.city_id,
                                             "units": "metric",
                                             "lang": "ru",
                                             "APPID": API_ID})
        # Разборка пакета JSON на необходимые данные о текущей погоде с помощью функции .json()
        weather_data = weather_query.json()
        # Получение температуры, влажности и погодных условий из данных пакета
        temperature = weather_data["main"]["temp"]
        humidity = weather_data["main"]["humidity"]
        conditions = weather_data["weather"][0]["description"]

        # Получение координат в исследуемом городе
        location = Nominatim(user_agent="weather_statistics").geocode(self.city)
        latitude = location.latitude
        longitude = location.longitude
        # Установка позиции Солнца и временной зоны, в которой находится пользователь
        sun = Sun(latitude, longitude)
        time_zone = datetime.now()
        # Получение времени рассвета/заката в выбранном городе
        sun_rise = sun.get_local_sunrise_time(time_zone)
        sun_dusk = sun.get_local_sunset_time(time_zone)
        return temperature, humidity, conditions, sun_rise.strftime("%H:%M"), sun_dusk.strftime("%H:%M")

    # Функция, возвращающая прогноз погоды на 5 дней исследуемого города в API сервисе
    def get_five_day_weather_forecast(self):
        # Получение пакета данных о прогнозе погоды на 5 дней в формате JSON на сформированный запрос к API сервису
        forecast_query = requests.get(FIVE_DAY_FORECAST_SEARCH_LINK,
                                      params={"id": self.city_id,
                                              "units": "metric",
                                              "lang": "ru",
                                              "APPID": API_ID})
        # Разборка пакета JSON на необходимые данные о прогнозе погоды на 5 дней с помощью функции .json()
        forecast_data = forecast_query.json()
        forecast = []
        # Получение прогноза погоды на каждый из 5 последующих дней
        for day in forecast_data["list"]:
            forecast.append([f"{'.'.join(day['dt_txt'][5:-3].split('-'))}:",
                             "{0:+3.0f}".format(day["main"]["temp"]),
                             day["weather"][0]["description"]])
        return forecast


# Класс, отвечающий за работу с БД
class DataBase:
    def __init__(self):
        self.db = sqlite3.connect(DATABASE_NAME)
        self.database_executor = self.db.cursor()

    def add_user(self, user_id, city):
        row = [user_id, city, False]
        self.database_executor.execute("INSERT INTO cities VALUES " + str(tuple(row)))
        self.db.commit()

    def is_user_exist(self, user_id):
        return len(self.database_executor.execute("""SELECT c.city FROM cities as c
                                                            WHERE c.user_id = ?""",
                                                  (user_id,)).fetchall())

    def edit_notification(self, user_id, notify):
        self.database_executor.execute("""UPDATE cities SET notification = ? WHERE user_id = ?""", (notify, user_id,))
        self.db.commit()

    def edit_city(self, user_id, city):
        self.database_executor.execute("""UPDATE cities SET city = ? WHERE user_id = ?""", (city, user_id,))
        self.db.commit()

    def get_city_of_user(self, user_id):
        return self.database_executor.execute("""SELECT c.city FROM cities as c WHERE c.user_id = ?""",
                                              (user_id,)).fetchall()

    def get_notified_users(self):
        return self.database_executor.execute("""SELECT c.user_id, c.city FROM cities as c 
                                                        WHERE c.notification = 1""").fetchall()


def get_current_weather(message):
    weather = Weather(MAIN_CITY)
    if weather.is_city_exist(message.text):
        weather = Weather(message.text)
        temperature, humidity, conditions, sun_rise_time, sun_set_time = weather.get_current_weather()
        conditions = conditions[0].upper() + conditions[1:]
        current_weather = ""
        current_weather += conditions + "\n"
        current_weather += 'Температура: ' + str(temperature) + '°C' + "\n"
        current_weather += 'Влажность: ' + str(humidity) + '%' + "\n"
        current_weather += 'Время восхода: ' + sun_rise_time + "\n"
        current_weather += 'Время заката: ' + sun_set_time + "\n"
        markup = telebot.types.InlineKeyboardMarkup(row_width=2)
        my_weather_button = telebot.types.InlineKeyboardButton("По моему городу",
                                                               callback_data="my_current_weather")
        other_weather_button = telebot.types.InlineKeyboardButton("По другому городу",
                                                                  callback_data="other_current_weather")
        back_button = telebot.types.InlineKeyboardButton("Назад", callback_data="back")
        markup.add(my_weather_button, other_weather_button, back_button)
        bot.send_message(message.from_user.id, text=current_weather, reply_markup=markup)
    else:
        alert_message = bot.send_message(message.from_user.id,
                                         text="Проверьте правильность написания города и введите его еще раз")
        bot.register_next_step_handler(alert_message, get_current_weather)


def get_weather_forecast(message):
    weather = Weather(MAIN_CITY)
    if weather.is_city_exist(message.text):
        weather = Weather(message.text)
        weather_forecast = "\n".join(" ".join(i) for i in weather.get_five_day_weather_forecast())
        markup = telebot.types.InlineKeyboardMarkup(row_width=2)
        my_weather_button = telebot.types.InlineKeyboardButton("По моему городу",
                                                               callback_data="my_weather_forecast")
        other_weather_button = telebot.types.InlineKeyboardButton("По другому городу",
                                                                  callback_data="other_weather_forecast")
        back_button = telebot.types.InlineKeyboardButton("Назад", callback_data="back")
        markup.add(my_weather_button, other_weather_button, back_button)
        bot.send_message(message.from_user.id, text=weather_forecast, reply_markup=markup)
    else:
        alert_message = bot.send_message(message.from_user.id,
                                         text="Проверьте правильность написания города и введите его еще раз")
        bot.register_next_step_handler(alert_message, get_weather_forecast)


def set_city(message):
    test_weather = Weather(MAIN_CITY)
    database = DataBase()
    if test_weather.is_city_exist(message.text):
        database.add_user(message.from_user.id, message.text.lower())
        markup = telebot.types.InlineKeyboardMarkup(row_width=2)
        current_weather_button = telebot.types.InlineKeyboardButton("Текущая погода",
                                                                    callback_data="current_weather")
        weather_forecast_button = telebot.types.InlineKeyboardButton("Прогноз погоды",
                                                                     callback_data="weather_forecast")
        database = DataBase()
        if database.is_user_exist(message.from_user.id):
            city_edit_button = telebot.types.InlineKeyboardButton("Изменить мой город",
                                                                  callback_data="change_city")
        else:
            city_edit_button = telebot.types.InlineKeyboardButton("Указать мой город",
                                                                  callback_data="set_city")
        notification_edit_button = telebot.types.InlineKeyboardButton("Уведомления",
                                                                      callback_data="notifications")
        instruction_button = telebot.types.InlineKeyboardButton("Инструкция",
                                                                callback_data="instruction")
        markup.add(current_weather_button, weather_forecast_button, city_edit_button,
                   notification_edit_button, instruction_button)
        bot.send_message(message.from_user.id, "Ваш населённый пункт установлен", reply_markup=markup)
    else:
        alert_message = bot.send_message(message.from_user.id,
                                         text="Проверьте правильность написания города и введите его еще раз")
        bot.register_next_step_handler(alert_message, set_city)


def edit_city(message):
    test_weather = Weather(MAIN_CITY)
    database = DataBase()
    if test_weather.is_city_exist(message.text):
        database.edit_city(message.from_user.id, message.text)
        markup = telebot.types.InlineKeyboardMarkup(row_width=2)
        current_weather_button = telebot.types.InlineKeyboardButton("Текущая погода",
                                                                    callback_data="current_weather")
        weather_forecast_button = telebot.types.InlineKeyboardButton("Прогноз погоды",
                                                                     callback_data="weather_forecast")
        database = DataBase()
        if database.is_user_exist(message.from_user.id):
            city_edit_button = telebot.types.InlineKeyboardButton("Изменить мой город",
                                                                  callback_data="change_city")
        else:
            city_edit_button = telebot.types.InlineKeyboardButton("Указать мой город",
                                                                  callback_data="set_city")
        notification_edit_button = telebot.types.InlineKeyboardButton("Уведомления",
                                                                      callback_data="notifications")
        instruction_button = telebot.types.InlineKeyboardButton("Инструкция",
                                                                callback_data="instruction")
        markup.add(current_weather_button, weather_forecast_button, city_edit_button,
                   notification_edit_button, instruction_button)
        bot.send_message(message.from_user.id, "Ваш населённый пункт изменён", reply_markup=markup)
    else:
        alert_message = bot.send_message(message.from_user.id,
                                         text="Проверьте правильность написания города и введите его еще раз")
        bot.register_next_step_handler(alert_message, edit_city)


@cache
def get_notification_message(city, time):
    city = translit(city, language_code='ru', reversed=True)
    url = f"http://dataservice.accuweather.com//locations/v1/cities/search?apikey={ACCUWEATHER_API_KEY}&q={city}"
    query = requests.get(url).json()
    try:
        location_id = query[0]["Key"]
    except KeyError:
        location_id = query["Key"]
    url_page = "http://dataservice.accuweather.com/forecasts/v1/hourly/12hour/" + str(
        location_id) + "?apikey=" + ACCUWEATHER_API_KEY + "&details=true&metric=true"
    json_page = requests.get(url_page)
    json_data = json_page.json()[0]
    temperature = json_data['Temperature']['Value']
    # weather = json_data['IconPhrase']
    rain_chance = json_data['RainProbability']
    snow_chance = json_data['SnowProbability']
    ice_chance = json_data['IceProbability']
    thunderstorm_chance = json_data['ThunderstormProbability']
    visibility = json_data['Visibility']['Value']
    visibility_message = ""
    rain_message = ""
    snow_message = ""
    ice_message = ""
    thunderstorm_message = ""
    temperature_message = f"\nтемпература {temperature}°C"
    if visibility < SAFETY_VISIBILITY:
        visibility_message = f"\nопасная видимость {visibility * 1000}м"
    if rain_chance:
        rain_message = f"\nдождь с шансом {rain_chance}%"
    if snow_chance:
        snow_message = f"\nснег с шансом {snow_chance}%"
    if ice_chance:
        ice_message = f"\nгололёд с шансом {ice_chance}%"
    if thunderstorm_chance:
        thunderstorm_message = f"\nгроза с шансом {thunderstorm_chance}%"
    alert_message = f"{time} ожидается:{temperature_message}{visibility_message}{rain_message}" \
                    f"{snow_message}{ice_message}{thunderstorm_message}"
    return alert_message


def morning_notify_all_users():
    database = DataBase()
    users = database.get_notified_users()
    for user_id, city in users:
        bot.send_message(user_id, text=get_notification_message(city, 'Сегодня'))


def evening_notify_all_users():
    database = DataBase()
    users = database.get_notified_users()
    for user_id, city in users:
        bot.send_message(user_id, text=get_notification_message(city, 'Завтра'))


def schedule_checker():
    while True:
        schedule.run_pending()
        sleep(10)


@bot.message_handler(['text'])
def start(message):
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    current_weather_button = telebot.types.InlineKeyboardButton("Текущая погода",
                                                                callback_data="current_weather")
    weather_forecast_button = telebot.types.InlineKeyboardButton("Прогноз погоды",
                                                                 callback_data="weather_forecast")
    database = DataBase()
    if database.is_user_exist(message.from_user.id):
        city_edit_button = telebot.types.InlineKeyboardButton("Изменить мой город",
                                                              callback_data="change_city")
    else:
        city_edit_button = telebot.types.InlineKeyboardButton("Указать мой город",
                                                              callback_data="set_city")
    notification_edit_button = telebot.types.InlineKeyboardButton("Уведомления",
                                                                  callback_data="notifications")
    instruction_button = telebot.types.InlineKeyboardButton("Инструкция",
                                                            callback_data="instruction")
    markup.add(current_weather_button, weather_forecast_button, city_edit_button,
               notification_edit_button, instruction_button)
    bot.send_message(message.from_user.id, "Добро пожаловать в главное меню", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: True)
def get_callbacks(call):
    if call.data == "current_weather":
        bot.answer_callback_query(call.id)
        markup = telebot.types.InlineKeyboardMarkup(row_width=2)
        my_weather_button = telebot.types.InlineKeyboardButton("По моему городу",
                                                               callback_data="my_current_weather")
        other_weather_button = telebot.types.InlineKeyboardButton("По другому городу",
                                                                  callback_data="other_current_weather")
        back_button = telebot.types.InlineKeyboardButton("Назад", callback_data="back")
        markup.add(my_weather_button, other_weather_button, back_button)
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=markup)
    elif call.data == "weather_forecast":
        bot.answer_callback_query(call.id)
        markup = telebot.types.InlineKeyboardMarkup(row_width=2)
        my_weather_button = telebot.types.InlineKeyboardButton("По моему городу",
                                                               callback_data="my_weather_forecast")
        other_weather_button = telebot.types.InlineKeyboardButton("По другому городу",
                                                                  callback_data="other_weather_forecast")
        back_button = telebot.types.InlineKeyboardButton("Назад", callback_data="back")
        markup.add(my_weather_button, other_weather_button, back_button)
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=markup)
    elif call.data == "my_current_weather":
        bot.answer_callback_query(call.id)
        database = DataBase()
        markup = telebot.types.InlineKeyboardMarkup(row_width=2)
        my_weather_button = telebot.types.InlineKeyboardButton("По моему городу",
                                                               callback_data="my_current_weather")
        other_weather_button = telebot.types.InlineKeyboardButton("По другому городу",
                                                                  callback_data="other_current_weather")
        back_button = telebot.types.InlineKeyboardButton("Назад", callback_data="back")
        markup.add(my_weather_button, other_weather_button, back_button)
        if database.is_user_exist(call.from_user.id):
            weather = Weather(database.get_city_of_user(call.from_user.id))
            temperature, humidity, conditions, sun_rise_time, sun_set_time = weather.get_current_weather()
            conditions = conditions[0].upper() + conditions[1:]
            current_weather = ""
            current_weather += conditions + "\n"
            current_weather += 'Температура: ' + str(temperature) + '°C' + "\n"
            current_weather += 'Влажность: ' + str(humidity) + '%' + "\n"
            current_weather += 'Время восхода: ' + sun_rise_time + "\n"
            current_weather += 'Время заката: ' + sun_set_time + "\n"
            bot.send_message(call.from_user.id, text=current_weather, reply_markup=markup)
        else:
            bot.send_message(call.from_user.id,
                             text="Для получения погодных данных о своём городе, "
                                  "необходимо вернуться в главное меню и указать его", reply_markup=markup)
    elif call.data == "other_current_weather":
        bot.answer_callback_query(call.id)
        message = bot.send_message(call.from_user.id, "Введите название города")
        bot.register_next_step_handler(message, get_current_weather)
    elif call.data == "my_weather_forecast":
        bot.answer_callback_query(call.id)
        database = DataBase()
        markup = telebot.types.InlineKeyboardMarkup(row_width=2)
        my_weather_button = telebot.types.InlineKeyboardButton("По моему городу",
                                                               callback_data="my_weather_forecast")
        other_weather_button = telebot.types.InlineKeyboardButton("По другому городу",
                                                                  callback_data="other_weather_forecast")
        back_button = telebot.types.InlineKeyboardButton("Назад", callback_data="back")
        markup.add(my_weather_button, other_weather_button, back_button)
        if database.is_user_exist(call.from_user.id):
            weather = Weather(database.get_city_of_user(call.from_user.id))
            weather_forecast = "\n".join(" ".join(i) for i in weather.get_five_day_weather_forecast())
            bot.send_message(call.from_user.id, text=weather_forecast, reply_markup=markup)
        else:
            bot.send_message(call.from_user.id,
                             text="Для получения погодных данных о своём городе, "
                                  "необходимо вернуться в главное меню и указать его", reply_markup=markup)
    elif call.data == "other_weather_forecast":
        bot.answer_callback_query(call.id)
        message = bot.send_message(call.from_user.id, "Введите название города")
        bot.register_next_step_handler(message, get_weather_forecast)
    elif call.data == "instruction":
        bot.answer_callback_query(call.id)
        markup = telebot.types.InlineKeyboardMarkup(row_width=2)
        current_weather_button = telebot.types.InlineKeyboardButton("Текущая погода",
                                                                    callback_data="current_weather")
        weather_forecast_button = telebot.types.InlineKeyboardButton("Прогноз погоды",
                                                                     callback_data="weather_forecast")
        database = DataBase()
        if database.is_user_exist(call.from_user.id):
            city_edit_button = telebot.types.InlineKeyboardButton("Изменить мой город",
                                                                  callback_data="change_city")
        else:
            city_edit_button = telebot.types.InlineKeyboardButton("Указать мой город",
                                                                  callback_data="set_city")
        notification_edit_button = telebot.types.InlineKeyboardButton("Уведомления",
                                                                      callback_data="notifications")
        instruction_button = telebot.types.InlineKeyboardButton("Инструкция",
                                                                callback_data="instruction")
        markup.add(current_weather_button, weather_forecast_button, city_edit_button,
                   notification_edit_button, instruction_button)
        bot.send_message(call.from_user.id,
                         "Этот бот создан для получения текущей погоды и прогноза погоды по любому городу, "
                         "а также для получения уведомлений о последующих погодных условиях.\n"
                         "Для получения уведомлений вам необходимо указать свой город.\n", reply_markup=markup)
    elif call.data == "set_city":
        bot.answer_callback_query(call.id)
        message = bot.send_message(call.from_user.id, "Введите название города")
        bot.register_next_step_handler(message, set_city)
    elif call.data == "change_city":
        bot.answer_callback_query(call.id)
        message = bot.send_message(call.from_user.id, "Введите название города")
        bot.register_next_step_handler(message, edit_city)
    elif call.data == "back":
        bot.answer_callback_query(call.id)
        markup = telebot.types.InlineKeyboardMarkup(row_width=2)
        current_weather_button = telebot.types.InlineKeyboardButton("Текущая погода",
                                                                    callback_data="current_weather")
        weather_forecast_button = telebot.types.InlineKeyboardButton("Прогноз погоды",
                                                                     callback_data="weather_forecast")
        database = DataBase()
        if database.is_user_exist(call.from_user.id):
            city_edit_button = telebot.types.InlineKeyboardButton("Изменить мой город",
                                                                  callback_data="change_city")
        else:
            city_edit_button = telebot.types.InlineKeyboardButton("Указать мой город",
                                                                  callback_data="set_city")
        notification_edit_button = telebot.types.InlineKeyboardButton("Уведомления",
                                                                      callback_data="notifications")
        instruction_button = telebot.types.InlineKeyboardButton("Инструкция",
                                                                callback_data="instruction")
        markup.add(current_weather_button, weather_forecast_button, city_edit_button,
                   notification_edit_button, instruction_button)
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=markup)
    elif call.data == "notifications":
        bot.answer_callback_query(call.id)
        database = DataBase()
        if database.is_user_exist(call.from_user.id):
            markup = telebot.types.InlineKeyboardMarkup(row_width=2)
            on_notifications_button = telebot.types.InlineKeyboardButton("Включить уведомления",
                                                                         callback_data="on_notifications")
            off_notifications_button = telebot.types.InlineKeyboardButton("Выключить уведомления",
                                                                          callback_data="off_notifications")
            back_button = telebot.types.InlineKeyboardButton("Назад", callback_data="back")
            markup.add(on_notifications_button, off_notifications_button, back_button)
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=markup)
        else:
            markup = telebot.types.InlineKeyboardMarkup(row_width=2)
            current_weather_button = telebot.types.InlineKeyboardButton("Текущая погода",
                                                                        callback_data="current_weather")
            weather_forecast_button = telebot.types.InlineKeyboardButton("Прогноз погоды",
                                                                         callback_data="weather_forecast")
            database = DataBase()
            if database.is_user_exist(call.from_user.id):
                city_edit_button = telebot.types.InlineKeyboardButton("Изменить мой город",
                                                                      callback_data="change_city")
            else:
                city_edit_button = telebot.types.InlineKeyboardButton("Указать мой город",
                                                                      callback_data="set_city")
            notification_edit_button = telebot.types.InlineKeyboardButton("Уведомления",
                                                                          callback_data="notifications")
            instruction_button = telebot.types.InlineKeyboardButton("Инструкция",
                                                                    callback_data="instruction")
            markup.add(current_weather_button, weather_forecast_button, city_edit_button,
                       notification_edit_button, instruction_button)
            bot.send_message(call.from_user.id, "Для получения уведомлений пожалуйста укажите свой город",
                             reply_markup=markup)
    elif call.data == "on_notifications":
        bot.answer_callback_query(call.id)
        database = DataBase()
        database.edit_notification(call.from_user.id, True)
        markup = telebot.types.InlineKeyboardMarkup(row_width=2)
        on_notifications_button = telebot.types.InlineKeyboardButton("Включить уведомления",
                                                                     callback_data="on_notifications")
        off_notifications_button = telebot.types.InlineKeyboardButton("Выключить уведомления",
                                                                      callback_data="off_notifications")
        back_button = telebot.types.InlineKeyboardButton("Назад", callback_data="back")
        markup.add(on_notifications_button, off_notifications_button, back_button)
        bot.send_message(call.from_user.id, "Теперь уведомления включены", reply_markup=markup)
    elif call.data == "off_notifications":
        bot.answer_callback_query(call.id)
        database = DataBase()
        database.edit_notification(call.from_user.id, False)
        markup = telebot.types.InlineKeyboardMarkup(row_width=2)
        on_notifications_button = telebot.types.InlineKeyboardButton("Включить уведомления",
                                                                     callback_data="on_notifications")
        off_notifications_button = telebot.types.InlineKeyboardButton("Выключить уведомления",
                                                                      callback_data="off_notifications")
        back_button = telebot.types.InlineKeyboardButton("Назад", callback_data="back")
        markup.add(on_notifications_button, off_notifications_button, back_button)
        bot.send_message(call.from_user.id, "Теперь уведомления выключены", reply_markup=markup)
    else:
        bot.send_message(call.from_user.id, "Данная операция не доступна, пожалуйста "
                                            "вернитесь в главное меню, написав /start или нажав кнопку 'Назад'")


if __name__ == "__main__":
    schedule.every().day.at("07:00").do(morning_notify_all_users)
    schedule.every().day.at("22:00").do(evening_notify_all_users)
    Thread(target=schedule_checker).start()
    bot.polling(none_stop=True)
