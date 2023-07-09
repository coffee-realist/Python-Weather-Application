# База данных - БД
# Подключение библиотек для работы с PyQt5 (графическим интерфейсом)
from PyQt5.QtWidgets import QMainWindow, QInputDialog, QSystemTrayIcon, QStyle, QAction, qApp, QMenu
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt
from PyQt5 import uic
from PIL import Image
import sys

# Подключение библиотек для работы с многопоточностью, API запросами к сервису с погодой и БД
import threading
import requests
import sqlite3
from suntime import Sun
from geopy.geocoders import Nominatim

# Подключение библиотек для работы с графиками и временем
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from time import sleep

# Константы для подключения к сервису с погодой
API_ID = 'b4709352c85607f12979db127ef36c97'
CITY_ID_SEARCH_LINK = 'http://api.openweathermap.org/data/2.5/find'
WEATHER_SEARCH_LINK = 'http://api.openweathermap.org/data/2.5/weather'
FIVE_DAY_FORECAST_SEARCH_LINK = 'http://api.openweathermap.org/data/2.5/forecast'

# Константы для подключения к БД и работе с многопоточностью
DATABASE_NAME = 'weather_statistic.sqlite'
DATABASE_CITY = 'Красноярск'
THREAD_EVENT = threading.Event()

# Константа для получения названий месяцев в родительном падеже по их номеру
NUMBER_OF_MONTH_TO_MONTH_NAME_IN_GENITIVE_CASE = {
    1: 'января',
    2: 'февраля',
    3: 'марта',
    4: 'апреля',
    5: 'мая',
    6: 'июня',
    7: 'июля',
    8: 'августа',
    9: 'сентября',
    10: 'октября',
    11: 'ноября',
    12: 'декабря',
}


# Класс, отвечающий за многопоточность
class MyThread(threading.Thread):
    # Изменение init наследуемого класса многопоточности
    def __init__(self, city):
        threading.Thread.__init__(self)
        self.database = 0
        self.city = city

    # Функция подключающая БД и запускающая процесс записи данных в неё
    def run(self):
        self.database = DataBase(self.city)
        self.database.add_info_to_database()


# Класс, отвечающий за работу с погодой (получение текущей погоды и прогноза погоды)
class Weather:
    def __init__(self, city):
        self.city = city
        self.city_id = 0
        # Получение id исследуемого города в API сервисе
        self.get_city_id()

    # Функция, получающая id исследуемого города в API сервисе
    def get_city_id(self):
        # Получение пакета данных о городе в формате JSON на сформированный запрос к API сервису
        cities_query = requests.get(CITY_ID_SEARCH_LINK,
                                    params={'q': self.city,
                                            'type': 'like',
                                            'units': 'metric',
                                            'APPID': API_ID})
        # Разборка пакета JSON на необходимые данные о городе с помощью функции .json()
        cities_data = cities_query.json()
        # Присваивание к city_id данных пакета
        self.city_id = cities_data['list'][0]['id']

    # Функция, возвращающая текущую погоду исследуемого города в API сервисе
    def get_current_weather(self):
        # Получение пакета данных о текущей погоде в формате JSON на сформированный запрос к API сервису
        weather_query = requests.get(WEATHER_SEARCH_LINK,
                                     params={'id': self.city_id,
                                             'units': 'metric',
                                             'lang': 'ru',
                                             'APPID': API_ID})
        # Разборка пакета JSON на необходимые данные о текущей погоде с помощью функции .json()
        weather_data = weather_query.json()
        # Получение температуры, влажности и погодных условий из данных пакета
        temperature = weather_data['main']['temp']
        humidity = weather_data['main']['humidity']
        conditions = weather_data['weather'][0]['description']

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
        return temperature, humidity, conditions, sun_rise.strftime('%H:%M'), sun_dusk.strftime('%H:%M')

    # Функция, возвращающая прогноз погоды на 5 дней исследуемого города в API сервисе
    def get_five_day_weather_forecast(self):
        # Получение пакета данных о прогнозе погоды на 5 дней в формате JSON на сформированный запрос к API сервису
        forecast_query = requests.get(FIVE_DAY_FORECAST_SEARCH_LINK,
                                      params={'id': self.city_id,
                                              'units': 'metric',
                                              'lang': 'ru',
                                              'APPID': API_ID})
        # Разборка пакета JSON на необходимые данные о прогнозе погоды на 5 дней с помощью функции .json()
        forecast_data = forecast_query.json()
        forecast = []
        # Получение прогноза погоды на каждый из 5 последующих дней
        for day in forecast_data['list']:
            forecast.append([f"{'.'.join(day['dt_txt'][5:-3].split('-'))}:",
                             '{0:+3.0f}'.format(day['main']['temp']),
                             day['weather'][0]['description']])
        return forecast


# Класс, отвечающий за работу с БД
class DataBase:
    def __init__(self, main_city):
        # Подключение к БД
        self.db = sqlite3.connect(DATABASE_NAME)
        # Исполнитель запросов к БД
        self.database_executor = self.db.cursor()
        # Исследуемый город
        self.main_city = main_city

    # Функция добавления новой информации о погоде в БД
    def add_info_to_database(self):
        # Глобальное событие для закрытия используемого потока в многопоточности
        global THREAD_EVENT
        # Получение текущего часа
        hour = int(datetime.now().hour)
        # Получение последней даты до наступления нового часа
        last_year, last_month, last_day = map(int, str(datetime.now().date()).split('-'))
        # Подключение к классу, работающему с погодой
        weather = Weather(self.main_city)
        while True:
            # Бездействие 120 секунд, для более эргономичного потребления ресурсов процессора
            sleep(120)
            # Проверка каждые 120 секунд наступил ли новый час
            # Есди да, то делаем новую запись в БД
            if int(datetime.now().hour) != hour:
                # Получение текущей даты и текущего часа
                year, month, day = map(int, str(datetime.now().date()).split('-'))
                hour = int(datetime.now().hour)
                # Получение текущей температуры, влажности, погодных условий
                temperature, humidity, conditions = weather.get_current_weather()[:3]
                # Список, представляющий собой ряд данных, которые добавляются в БД
                row = [year, month, day, hour, int(temperature), int(humidity), conditions]
                self.database_executor.execute("INSERT INTO weather VALUES " + str(tuple(row)))
                # Подтверждение изменений в БД
                self.db.commit()
                # Если наступил новый день, то добавляем среднестатистические данные о прошедшем дне в БД
                if last_day != day:
                    # Получение данных о температуре прошедшего дня
                    temperature_data = self.get_day_temperature(last_year, last_month, last_day)
                    temperatures = [int(hour_temperature[0]) for hour_temperature in temperature_data]
                    min_temperature = min(temperatures)
                    average_temperature = round(sum(temperatures) / len(temperatures))
                    max_temperature = max(temperatures)
                    # Получение данных о влажности прошедшего дня
                    humidity_data = self.get_day_humidity(last_year, last_month, last_day)
                    humidity = [int(hour_humidity[0]) for hour_humidity in humidity_data]
                    min_humidity = min(humidity)
                    average_humidity = round(sum(humidity) / len(humidity))
                    max_humidity = max(humidity)
                    # Список, представляющий собой ряд данных, которые добавляются в БД
                    row = [last_year, last_month, last_day,
                           min_temperature, average_temperature, max_temperature,
                           min_humidity, average_humidity, max_humidity]
                    self.database_executor.execute("INSERT INTO average_month_weather VALUES " + str(tuple(row)))
                    # Подтверждение изменений в БД
                    self.db.commit()
                    # Обновление даты
                    last_year, last_month, last_day = year, month, day
            # Обновление события потока по нажатию соответствующей кнопки, закрытие работы с базой данных
            if THREAD_EVENT.is_set():
                THREAD_EVENT = threading.Event()
                self.close_database()
                break

    # Получение данных из БД о температуре за выбранный месяц
    def get_month_temperature_statistic(self, year, month):
        return self.database_executor.execute("""SELECT day, "minTemperature, °C", "averageTemperature, °C",
                                                    "maxTemperature, °C" FROM average_month_weather
                                                    WHERE year = ? AND month = ?""",
                                              (year, month,)).fetchall()

    # Получение данных из БД о влажности за выбранный месяц
    def get_month_humidity_statistic(self, year, month):
        return self.database_executor.execute("""SELECT day, "minHumidity, %", "averageHumidity, %",
                                                    "maxHumidity, %" FROM average_month_weather
                                                    WHERE year = ? AND month = ?""",
                                              (year, month,)).fetchall()

    # Получение данных из БД о температуре за выбранный день
    def get_day_temperature_statistic(self, year, month, day):
        return self.database_executor.execute("""SELECT w.hour, w."temperature, °C" FROM weather as w
                                        WHERE w.year = ? AND w.month = ? AND w.day = ?""",
                                              (year, month, day,)).fetchall()

    # Получение данных из БД о влажности за выбранный день
    def get_day_humidity_statistic(self, year, month, day):
        return self.database_executor.execute("""SELECT w.hour, w."humidity, %" FROM weather as w
                                        WHERE w.year = ? AND w.month = ? AND w.day = ?""",
                                              (year, month, day,)).fetchall()

    # Получение тепературы из БД за выбранный день
    def get_day_temperature(self, year, month, day):
        return self.database_executor.execute("""SELECT w."temperature, °C" FROM weather as w
                                                    WHERE w.year = ? AND w.month = ? AND w.day = ?""",
                                              (year, month, day,)).fetchall()

    # Получение влажности из БД за выбранный день
    def get_day_humidity(self, year, month, day):
        return self.database_executor.execute("""SELECT w."humidity, %" FROM weather as w
                                                    WHERE w.year = ? AND w.month = ? AND w.day = ?""",
                                              (year, month, day,)).fetchall()

    # Получение годов данных, хранящихся в БД
    def get_years(self):
        return self.database_executor.execute("""SELECT DISTINCT w.year FROM weather AS w""").fetchall()

    # Получение месяцев данных, хранящихся в БД по выбранному году
    def get_months(self, year):
        return self.database_executor.execute("""SELECT DISTINCT w.month FROM weather AS w
                                                    WHERE w.year = ?""",
                                              (year,)).fetchall()

    # Получение дней данных, хранящихся в БД по месяцу
    def get_days(self, year, month):
        return self.database_executor.execute("""SELECT DISTINCT w.day FROM weather as w
                                                    WHERE w.year = ? AND w.month = ?""",
                                              (year, month,)).fetchall()

    # Получение данных из БД о всех погодных условиях за выбранный месяц
    def get_month_conditions(self, year, month):
        return self.database_executor.execute("""SELECT w.conditions FROM weather as w
                                                    WHERE w.year = ? AND w.month = ?""",
                                              (year, month,)).fetchall()

    # Получение данных из БД о всех типах погодных условиях за выбранный месяц
    def get_type_of_month_conditions(self, year, month):
        return self.database_executor.execute("""SELECT DISTINCT w.conditions FROM weather as w
                                                            WHERE w.year = ? AND w.month = ?""",
                                              (year, month,)).fetchall()

    # Получение данных из БД о всех погодных условиях за выбранный день
    def get_day_conditions(self, year, month, day):
        return self.database_executor.execute("""SELECT w.conditions FROM weather as w
                                                    WHERE w.year = ? AND w.month = ? AND w.day = ?""",
                                              (year, month, day)).fetchall()

    # Получение данных из БД о всех типах погодных условиях за выбранный день
    def get_type_of_day_conditions(self, year, month, day):
        return self.database_executor.execute("""SELECT DISTINCT w.conditions FROM weather as w
                                                    WHERE w.year = ? AND w.month = ? AND w.day = ?""",
                                              (year, month, day)).fetchall()

    # Закрытие БД
    def close_database(self):
        self.db.close()


# Класс, отвечающий за работу со статистическими данными и графическим интерфейсом
class Statistic(QMainWindow):
    # Переопределение метода init наследуемого класса, присваивание изначальных значений переменных
    def __init__(self):
        super().__init__()
        uic.loadUi('statistic_ui.ui', self)
        self.tray_icon = QSystemTrayIcon(self)
        self.load_clicks = 0
        self.hide_and_show_clicks = 0
        self.day = 0
        self.month = 0
        self.year = 0
        self.city = ''
        self.graphics_exist = False
        self.month_graphics_exist = False
        self.day_graphics_exist = False
        self.init_ui()

    # Функция, подключающая кнопки графического интерфейса к функциям взаимодействия с графическим интерфейсом
    # и прячущая ненужные на данный момент графические объекты
    def init_ui(self):
        self.setWindowTitle('Метеоприложение')
        self.quit_button.clicked.connect(self.end_process)
        self.load_button.clicked.connect(self.load_data_from_database)
        self.select_city_button.clicked.connect(self.select_city)
        self.current_weather_button.clicked.connect(self.get_current_weather)
        self.forecast_button.clicked.connect(self.get_forecast)
        self.hide_button.clicked.connect(self.hide_show_graphics)
        self.month_statistic_button.clicked.connect(self.get_month_statistic)
        self.day_statistic_button.clicked.connect(self.get_day_statistic)
        self.back_button.clicked.connect(self.back)
        self.forward_button.clicked.connect(self.forward)
        self.background_mod_button.clicked.connect(self.minimize_to_tray)

        self.temperature_graphic_label.hide()
        self.humidity_graphic_label.hide()
        self.back_button.hide()
        self.forward_button.hide()

        # создание меню трэя для работы программы в фоновом режиме
        self.tray_icon.setIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))
        show_action = QAction('Show', self)
        quit_action = QAction('Exit', self)
        hide_action = QAction('Hide', self)
        show_action.triggered.connect(self.show)
        hide_action.triggered.connect(self.hide)
        quit_action.triggered.connect(qApp.quit)
        tray_menu = QMenu()
        tray_menu.addAction(show_action)
        tray_menu.addAction(hide_action)
        tray_menu.addAction(quit_action)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

    # функция, которая при нажатии кнопки "включить фоновой режим", минимизирует программу в трэй
    def minimize_to_tray(self):
        self.hide()
        self.tray_icon.showMessage(
            "Tray Program",
            "Application was minimized to Tray",
            QSystemTrayIcon.Information,
            2000
        )

    # Метод, выходящий из программы
    @staticmethod
    def end_process():
        exit(0)

    # Функция, получающая название выбранного города и очищающая лог ошибок
    def select_city(self):
        self.city = self.investigated_city.text()
        self.errors.clear()

    # Функция, прячущая и показывающая графики изменения погоды и графические объекты, относящиеся к ним
    # Доступна только когда графики построены
    def hide_show_graphics(self):
        # Проверка на существование графиков для взаимодействия с ними и с графическими объектами, относящихся к ним
        if self.graphics_exist:
            self.hide_and_show_clicks += 1
            # Если количество нажатий на кнопку чётно, то показываем графики и графические объекты, относящиеся к ним
            # и меняем название кнопки на противоположное от действия
            if self.hide_and_show_clicks % 2 == 0:
                self.temperature_graphic.show()
                self.humidity_graphic.show()
                self.temperature_graphic_label.show()
                self.humidity_graphic_label.show()
                self.back_button.show()
                self.forward_button.show()
                self.hide_button.setText('Спрятать графики')
            # Если количество нажатий на кнопку нечётно, то прячем графики и графические объекты, относящиеся к ним
            # и меняем название кнопки на противоположное от действия
            else:
                self.temperature_graphic.hide()
                self.humidity_graphic.hide()
                self.temperature_graphic_label.hide()
                self.humidity_graphic_label.hide()
                self.back_button.hide()
                self.forward_button.hide()
                self.hide_button.setText('Показать графики')

    # Начать загрузку данных в БД
    def load_data_from_database(self):
        # Выбрать город
        self.select_city()
        # Проверка на то, является ли город тем, по которому доступна запись в БД
        if self.city == DATABASE_CITY:
            self.load_clicks += 1
            # Меняем название кнопки в зависимости от чётности
            if self.load_clicks % 2 == 0:
                self.load_button.setText('Начать загрузку данных в базу')
                # Устанавливаем значение события для завершения открытого потока и закрытия БД по окночании работы с ней
                THREAD_EVENT.set()
            else:
                self.load_button.setText('Остановить загрузку данных')
                # Создаём экземпляр класса могопоточности и запускаем новый поток для работы с бесконечным циклом
                # отдельно от работы с другими частями программы
                thread1 = MyThread(self.city)
                thread1.start()
        else:
            # Добавление ошибки в лог ошибок
            self.errors.addItem('Извините, на данный момент загрузка')
            self.errors.addItem('в базу данных доступна только по городу')
            self.errors.addItem(DATABASE_CITY)

    # Функция получения текущей погоды
    def get_current_weather(self):
        try:
            # Очистка лога ошибок и выбор города
            self.errors.clear()
            self.select_city()
            # Создание экземпляра класса погоды
            weather = Weather(self.city)
            # Получение температуры, влажности и погодных условий
            temperature, humidity, conditions, sun_rise_time, sun_set_time = weather.get_current_weather()
            # Поднятие первой буквы погодных условий в верхний регистр
            conditions = conditions[0].upper() + conditions[1:]
            # Очистка графического списка от предыдущей погоды, ввод в графический список текущей погоды
            self.current_weather.clear()
            self.current_weather.addItem(conditions)
            self.current_weather.addItem('Температура: ' + str(temperature) + '°C')
            self.current_weather.addItem('Влажность: ' + str(humidity) + '%')
            self.current_weather.addItem('Время восхода: ' + sun_rise_time)
            self.current_weather.addItem('Время заката: ' + sun_set_time)
        except IndexError:
            # Если название города ввели неверно,
            # то будет вызвано исключение IndexError, очищен лог ошибок и добавлена новая ошибка
            self.errors.clear()
            self.errors.addItem('Допущена ошибка при вводе города или ')
            self.errors.addItem('введёный город не найден или ')
            self.errors.addItem('город введён без соответствующих знаков ')
            self.errors.addItem('препинания. Попробуйте ещё раз.')

    # Функция получения прогноза погоды на 5 дней
    def get_forecast(self):
        try:
            # Очистка лога ошибок и выбор города
            self.errors.clear()
            self.select_city()
            # Создание экземпляра класса погоды
            weather = Weather(self.city)
            # Получение погдных условий на 5 последующих дней
            five_day_forecast = weather.get_five_day_weather_forecast()
            # Очистка графического списка от предыдущего прогноза погоды,
            # ввод в графический список текущего прогноза погоды
            self.forecast.clear()
            for current in five_day_forecast:
                self.forecast.addItem(' '.join(current))
        except IndexError:
            # Если название города ввели неверно,
            # то будет вызвано исключение IndexError, очищен лог ошибок и добавлена новая ошибка
            self.errors.clear()
            self.errors.addItem('Допущена ошибка при вводе города или ')
            self.errors.addItem('введёный город не найден или ')
            self.errors.addItem('город введён без соответствующих знаков ')
            self.errors.addItem('препинания. Попробуйте ещё раз.')

    # Функция, рисующая и сохраняющая в файл графики температуры и влажности за выбранный месяц
    def draw_and_save_month_graphics(self, database, year, month):
        # Выбор города
        self.select_city()
        # Получение среднестатистических данных о погодных условиях за месяц
        conditions_data = database.get_month_conditions(year, month)
        conditions_types_data = database.get_type_of_month_conditions(year, month)
        conditions = [condition[0] for condition in conditions_data]
        conditions_types = [condition_type[0] for condition_type in conditions_types_data]
        # Получение наиболее часто встречающегося погодного условия за месяц
        max_frequency = 0
        max_frequency_condition = ''
        for condition in conditions_types:
            current_frequency = conditions.count(condition)
            if current_frequency > max_frequency:
                max_frequency = current_frequency
                max_frequency_condition = condition

        # Получение данных о температуре за выбранный месяц
        data = database.get_month_temperature_statistic(year, month)
        days = [str(current_day[0]) for current_day in data]
        min_temperature = [current_day[1] for current_day in data]
        average_temperature = [current_day[2] for current_day in data]
        max_temperature = [current_day[3] for current_day in data]
        # Построение графика изменения тмператур с помощью модуля matplotlib.pyplot (plt)
        plt.style.use('dark_background')
        temperature_graphic, temperature_plot = plt.subplots(nrows=1, ncols=1)
        temperature_plot.plot(days, max_temperature, '.-', color='red')
        temperature_plot.plot(days, average_temperature, '.-', color='green')
        temperature_plot.plot(days, min_temperature, '.-', color='blue')
        # Легенда данных графика изменения температур
        temperature_plot.legend(['Максимальная температура',
                                 'Среднестатистическая температура',
                                 'Минимальная температура'])
        # Подписи осей графика изменения температур
        temperature_plot.set_xlabel('День ' + NUMBER_OF_MONTH_TO_MONTH_NAME_IN_GENITIVE_CASE[int(month)])
        temperature_plot.set_ylabel('Температура, °C')
        # Заголовок графика изменения температур
        title = 'Погодные условия ' + NUMBER_OF_MONTH_TO_MONTH_NAME_IN_GENITIVE_CASE[int(month)]
        title += ' ' + str(year) + ' года:\n' + 'преимущественно ' + str(max_frequency_condition)
        plt.title(title)
        # Сохранение графика изменения температур и закрытие работы с ним
        temperature_graphic.savefig('temperature_graphic.png')
        plt.close(temperature_graphic)

        # Получение данных о влажности за выбранный месяц
        data = database.get_month_humidity_statistic(year, month)
        days = [str(current_day[0]) for current_day in data]
        min_humidity = [current_day[1] for current_day in data]
        average_humidity = [current_day[2] for current_day in data]
        max_humidity = [current_day[3] for current_day in data]
        # Построение графика изменения влажности с помощью модуля matplotlib.pyplot (plt)
        humidity_graphic, humidity_plot = plt.subplots(nrows=1, ncols=1)
        humidity_plot.plot(days, max_humidity, '.-', color='red')
        humidity_plot.plot(days, average_humidity, '.-', color='green')
        humidity_plot.plot(days, min_humidity, '.-', color='blue')
        # Легенда данных графика изменения влажности
        humidity_plot.legend(['Максимальная влажность',
                              'Среднестатистическая влажность',
                              'Минимальная влажность'])
        # Подписи осей графика изменения влажности
        humidity_plot.set_xlabel('День ' + NUMBER_OF_MONTH_TO_MONTH_NAME_IN_GENITIVE_CASE[month])
        humidity_plot.set_ylabel('Влажность, %')
        # Заголовок графика изменения влажности
        title = 'Погодные условия ' + NUMBER_OF_MONTH_TO_MONTH_NAME_IN_GENITIVE_CASE[int(month)]
        title += ' ' + str(year) + ' года:\n' + 'преимущественно ' + str(max_frequency_condition)
        plt.title(title)
        # Сохранение графика изменения влажности и закрытие работы с ним
        humidity_graphic.savefig('humidity_graphic.png')
        plt.close(humidity_graphic)

    # Функция, рисующая и сохраняющая в файл графики температуры и влажности за выбранный день
    def draw_and_save_day_graphics(self, database, year, month, day):
        # Выбор города
        self.select_city()
        # Получение среднестатистических данных о погодных условиях за день
        conditions_data = database.get_day_conditions(year, month, day)
        conditions_types_data = database.get_type_of_day_conditions(year, month, day)
        conditions = [condition[0] for condition in conditions_data]
        conditions_types = [condition_type[0] for condition_type in conditions_types_data]
        # Получение наиболее часто встречающегося погодного условия за день
        max_frequency = 0
        max_frequency_condition = ''
        for condition in conditions_types:
            current_frequency = conditions.count(condition)
            if current_frequency > max_frequency:
                max_frequency = current_frequency
                max_frequency_condition = condition

        # Получение данных о температуре за выбранный день
        data = database.get_day_temperature_statistic(year, month, day)
        hours = [str(current_day[0]) + ':00' for current_day in data]
        temperature = [current_day[1] for current_day in data]
        # Построение графика изменения тмператур с помощью модуля matplotlib.pyplot (plt)
        plt.style.use('dark_background')
        temperature_graphic, temperature_plot = plt.subplots(nrows=1, ncols=1)
        temperature_plot.plot(hours, temperature, '.-')
        # Подписи осей графика изменения температур
        temperature_plot.set_xlabel('Время')
        temperature_plot.set_ylabel('Температура, °C')
        # Заголовок графика изменения температур
        title = 'Погодные условия ' + str(day) + ' ' + NUMBER_OF_MONTH_TO_MONTH_NAME_IN_GENITIVE_CASE[int(month)]
        title += ' ' + str(year) + ' года:\n' + 'преимущественно ' + str(max_frequency_condition)
        plt.title(title)
        # поворот делений оси X на 45 градусов для портативного вмещения времени
        temperature_plot.tick_params(axis='x', labelrotation=45)
        # Сохранение графика изменения температур и закрытие работы с ним
        temperature_graphic.savefig('temperature_graphic.png')
        plt.close(temperature_graphic)

        # Получение данных о влажности за выбранный день
        data = database.get_day_humidity_statistic(year, month, day)
        hours = [str(current_day[0]) + ':00' for current_day in data]
        humidity = [current_day[1] for current_day in data]
        # Построение графика изменения влажности с помощью модуля matplotlib.pyplot (plt)
        humidity_graphic, humidity_plot = plt.subplots(nrows=1, ncols=1)
        humidity_plot.plot(hours, humidity, '.-')
        # Подписи осей графика изменения влажности
        humidity_plot.set_xlabel('Время')
        humidity_plot.set_ylabel('Влажность, %')
        # Заголовок графика изменения влажности
        title = 'Погодные условия ' + str(day) + ' ' + NUMBER_OF_MONTH_TO_MONTH_NAME_IN_GENITIVE_CASE[int(month)]
        title += ' ' + str(year) + ' года:\n' + 'преимущественно ' + str(max_frequency_condition)
        plt.title(title)
        # поворот делений оси X на 45 градусов для портативного вмещения времени
        humidity_plot.tick_params(axis='x', labelrotation=45)
        # Сохранение графика изменения влажности и закрытие работы с ним
        humidity_graphic.savefig('humidity_graphic.png')
        plt.close(humidity_graphic)

    # Функция запрашивающая данные необходимые для графиков изменения температуры и влажности за месяц,
    # если они не переданы, показывающая графики изменения температуры и влажности за месяц
    # и подгоняющая размер изображений под соответствующие графические объекты
    def get_month_statistic(self, year=0, month=0, move=''):
        # Выбор города
        self.select_city()
        # Проверка на то, является ли город тем, по которому доступна запись в БД
        if self.city != DATABASE_CITY:
            # Очистка лога ошибок и добавление новой ошибки
            self.errors.clear()
            self.errors.addItem('Извините, на данный момент статистика')
            self.errors.addItem('за период доступна только по городу ' + DATABASE_CITY)
            return
        # Создание экземпляра базы данных для получения всех годов и месяцев
        database = DataBase(self.city)
        # Если параметр year не назначен необходимо произвести выбор даты
        if year == 0:
            # Выбор года
            years = [str(year[0]) for year in database.get_years()]
            selected_year, ok_pressed = QInputDialog.getItem(self,
                                                             'Получение данных об исследуемом периоде',
                                                             'Выберите год', years)
            if ok_pressed and selected_year not in years:
                self.errors.addItem('Извините, данные по выбранному периоду')
                self.errors.addItem('времени отсутствуют в базе данных')
                return
            if ok_pressed:
                year = int(selected_year)
                # Выбор месяца
                months = [str(month[0]) for month in database.get_months(year)]
                selected_month, ok_pressed = QInputDialog.getItem(self,
                                                                  'Получения данных об исследуемом периоде',
                                                                  'Выберите месяц', months)
                if ok_pressed and selected_month not in months:
                    self.errors.addItem('Извините, данные по выбранному периоду')
                    self.errors.addItem('времени отсутствуют в базе данных')
                    return
                if ok_pressed:
                    month = int(selected_month)
        # Если месяц выбран
        if month != 0:
            # Получение списков годов и месяцев для проверки на корректность запроса к БД
            years = [year[0] for year in database.get_years()]
            months = [month[0] for month in database.get_months(year)]
            # Если год и месяц корректно выбраны
            if year in years and month in months:
                # Построение и сохранение графиков в файлы
                self.draw_and_save_month_graphics(database, year, month)
                self.graphics_exist = True
                # Изменение размера изображений
                temperature_image = Image.open('temperature_graphic.png')
                new_temperature_image = temperature_image.resize((550, 429))
                new_temperature_image.save('temperature_graphic.png')

                humidity_image = Image.open('humidity_graphic.png')
                new_humidity_image = humidity_image.resize((550, 429))
                new_humidity_image.save('humidity_graphic.png')

                # присвоение изображений к соответствующим графичсеким объектам
                temperature_pix_map = QPixmap('temperature_graphic.png')
                humidity_pix_map = QPixmap('humidity_graphic.png')
                self.temperature_graphic.setPixmap(temperature_pix_map)
                self.humidity_graphic.setPixmap(humidity_pix_map)
                self.temperature_graphic_label.show()
                self.humidity_graphic_label.show()
                self.temperature_graphic.show()
                self.humidity_graphic.show()
                self.back_button.show()
                self.forward_button.show()

                # Установка новых заголовков кнопок в соответствии с исследуемым периодои времени
                self.back_button.setText('Предыдущий месяц')
                self.forward_button.setText('Следующий месяц')
                # Сохранение года и месяца
                self.year = year
                self.month = month
                # Указание существующего типа графиков
                self.month_graphics_exist = True
                self.day_graphics_exist = False
            else:
                # Иначе, если выбранная дата не корректна, то откатываем значение кнопок,
                # переключающих месяцы, на шаг назад/вперед
                if move == 'back':
                    if self.month == 12:
                        self.month = 1
                        self.year += 1
                    else:
                        self.month += 1
                else:
                    if self.month == 1:
                        self.month = 12
                        self.year -= 1
                    else:
                        self.month -= 1
                # Очистка лога ошибок и добавление новой ошибки о некорректном запросе к БД
                self.errors.clear()
                self.errors.addItem('Переключение на выбранный месяц')
                self.errors.addItem('не доступно, т. к. он отсутствует в')
                self.errors.addItem('базе данных')
        # Закрытие базы данных
        database.close_database()

    # Функция запрашивающая данные необходимые для графиков изменения температуры и влажности за день,
    # если они не переданы, показывающая графики изменения температуры и влажности за день
    # и подгоняющая размер изображений под соответствующие графические объекты
    def get_day_statistic(self, year=0, month=0, day=0, move=''):
        # Выбор города
        self.select_city()
        # Проверка на то, является ли город тем, по которому доступна запись в БД
        if self.city != DATABASE_CITY:
            # Очистка лога ошибок и добавление новой ошибки
            self.errors.clear()
            self.errors.addItem('Извините, на данный момент статистика')
            self.errors.addItem('за период доступна только по городу ' + DATABASE_CITY)
            return
        # Создание экземпляра базы данных для получения всех годов, месяцев и дней
        database = DataBase(self.city)
        # Если параметр year не назначен необходимо произвести выбор даты
        if year == 0:
            # Выбор года
            years = [str(year[0]) for year in database.get_years()]
            selected_year, ok_pressed = QInputDialog.getItem(self,
                                                             'Получение данных об исследуемом периоде',
                                                             'Выберите год', years)
            if ok_pressed and selected_year not in years:
                self.errors.addItem('Извините, данные по выбранному периоду')
                self.errors.addItem('времени отсутствуют в базе данных')
                return
            if ok_pressed:
                year = int(selected_year)
                # Выбор месяца
                months = [str(month[0]) for month in database.get_months(year)]
                selected_month, ok_pressed = QInputDialog.getItem(self,
                                                                  'Получения данных об исследуемом периоде',
                                                                  'Выберите месяц', months)
                if ok_pressed and selected_month not in months:
                    self.errors.addItem('Извините, данные по выбранному периоду')
                    self.errors.addItem('времени отсутствуют в базе данных')
                    return
                if ok_pressed:
                    month = int(selected_month)
                    # Выбор дня
                    days = [str(day[0]) for day in database.get_days(year, month)]
                    selected_day, ok_pressed = QInputDialog.getItem(self,
                                                                    'Получения данных об исследуемом периоде',
                                                                    'Выберите день', days)
                    if ok_pressed and selected_day not in days:
                        self.errors.addItem('Извините, данные по выбранному периоду')
                        self.errors.addItem('времени отсутствуют в базе данных')
                        return
                    if ok_pressed:
                        day = int(selected_day)

        # Если день выбран
        if day != 0:
            # Получение списков годов, месяцев и дней для проверки на корректность запроса к БД
            years = [year[0] for year in database.get_years()]
            months = [month[0] for month in database.get_months(year)]
            days = [day[0] for day in database.get_days(year, month)]
            # Если год, месяц и день корректно выбраны
            if year in years and month in months and day in days:
                # Построение и сохранение графиков в файлы
                self.draw_and_save_day_graphics(database, year, month, day)
                self.graphics_exist = True
                # Изменение размера изображений
                temperature_image = Image.open('temperature_graphic.png')
                new_temperature_image = temperature_image.resize((550, 429))
                new_temperature_image.save('temperature_graphic.png')

                humidity_image = Image.open('humidity_graphic.png')
                new_humidity_image = humidity_image.resize((550, 429))
                new_humidity_image.save('humidity_graphic.png')

                # присвоение изображений к соответствующим графичсеким объектам
                temperature_pix_map = QPixmap('temperature_graphic.png')
                humidity_pix_map = QPixmap('humidity_graphic.png')
                self.temperature_graphic.setPixmap(temperature_pix_map)
                self.humidity_graphic.setPixmap(humidity_pix_map)
                self.temperature_graphic_label.show()
                self.humidity_graphic_label.show()
                self.temperature_graphic.show()
                self.humidity_graphic.show()
                self.back_button.show()
                self.forward_button.show()

                # Установка новых заголовков кнопок в соответствии с исследуемым периодои времени
                self.back_button.setText('Предыдущий день')
                self.forward_button.setText('Следующий день')
                # Сохранение года и месяца
                self.year = year
                self.month = month
                self.day = day
                # Указание существующего типа графиков
                self.day_graphics_exist = True
                self.month_graphics_exist = False
            else:
                # Иначе, если выбранная дата не корректна, то откатываем значение кнопок,
                # переключающих месяцы, на шаг назад/вперед
                if move == 'back':
                    graphic_date = datetime(self.year, self.month, self.day) + timedelta(days=1)
                else:
                    graphic_date = datetime(self.year, self.month, self.day) - timedelta(days=1)
                self.year = int(graphic_date.year)
                self.month = int(graphic_date.month)
                self.day = int(graphic_date.day)
                # Очистка лога ошибок и добавление новой ошибки о некорректном запросе к БД
                self.errors.clear()
                self.errors.addItem('Переключение на выбранный день')
                self.errors.addItem('не доступно, т. к. он отсутствует в')
                self.errors.addItem('базе данных')
        # Закрытие базы данных
        database.close_database()

    def back(self):
        # Если графики изменения температуры и влажности за выбранный месяц построены
        if self.month_graphics_exist:
            # Отнимаем от даты 1 месяц
            if self.month == 1:
                self.month = 12
                self.year -= 1
            else:
                self.month -= 1
            # Построение новых графиков изменения температуры и влажности за выбранный месяц
            self.get_month_statistic(year=self.year, month=self.month, move='back')
        # Если же графики изменения температуры и влажности за выбранный день построены
        elif self.day_graphics_exist:
            # Создаем новую дату, которая является предыдущей датой, но на день ранее
            graphic_date = datetime(self.year, self.month, self.day) - timedelta(days=1)
            self.year = int(graphic_date.year)
            self.month = int(graphic_date.month)
            self.day = int(graphic_date.day)
            # Построение новых графиков изменения температуры и влажности за выбранный день
            self.get_day_statistic(year=self.year, month=self.month, day=self.day, move='back')

    def forward(self):
        # Если графики изменения температуры и влажности за выбранный месяц построены
        if self.month_graphics_exist:
            # Прибавляем к дате 1 месяц
            if self.month == 12:
                self.month = 1
                self.year += 1
            else:
                self.month += 1
            # Построение новых графиков изменения температуры и влажности за выбранный месяц
            self.get_month_statistic(year=self.year, month=self.month, move='forward')
        elif self.day_graphics_exist:
            # Создаем новую дату, которая является предыдущей датой, но на день позже
            graphic_date = datetime(self.year, self.month, self.day) + timedelta(days=1)
            self.year = int(graphic_date.year)
            self.month = int(graphic_date.month)
            self.day = int(graphic_date.day)
            # Построение новых графиков изменения температуры и влажности за выбранный день
            self.get_day_statistic(year=self.year, month=self.month, day=self.day, move='forward')


# установка темной темы интерфейса
def set_dark_theme():
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(53, 53, 53))
    palette.setColor(QPalette.WindowText, Qt.white)
    palette.setColor(QPalette.Base, QColor(25, 25, 25))
    palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
    palette.setColor(QPalette.ToolTipBase, Qt.black)
    palette.setColor(QPalette.ToolTipText, Qt.white)
    palette.setColor(QPalette.Text, Qt.white)
    palette.setColor(QPalette.Button, QColor(53, 53, 53))
    palette.setColor(QPalette.ButtonText, Qt.white)
    palette.setColor(QPalette.BrightText, Qt.red)
    palette.setColor(QPalette.Link, QColor(42, 130, 218))
    palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.HighlightedText, Qt.black)
    app.setPalette(palette)


# Создание экземпляра класса интерфейса и запуск приложения
if __name__ == '__main__':
    app = QApplication(sys.argv)
    set_dark_theme()
    statistic = Statistic()
    statistic.show()
    sys.exit(app.exec_())
