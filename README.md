Суть данного проекта заключается в реализации метео-приложения, строящего графики
зависимости температуры и влажности от времени, способного определить текущую погоду
и прогноз погоды на ближайшие 5 дней

Проект использует базу данных для построения графиков.
Если нажать кнопку "Начать загрузку данных в базу", то пока программа включена,
она будет каждый час записывать текущую погоду и по окончанию дня записывать
среднестатистические данные в базу данных для того, чтобы в дальнейшем 
использовать эти данные для построения статистических графиков.
На данный момент в базе уже есть данные погоды с 5 по 10 Ноября

humidity_graphic.png - файл, в который сохраняется изображение графика зависимости
влажности от времени
temperature_graphic.png - файл, в который сохраняется изображение графика зависимости
температуры от времени
README.TXT - пояснительная записка
statistic_ui.ui - ui файл с графическим интерфейсом
weather_statistic.pptx - презентация проекта
weather_statistic.sqlite - база данных
weather_statistic.py - код проекта

Примечание:
Вводимые названия городов должны быть на английском языке.
Для работы программы необходимо установить библиотеки: matplotlib, PyQt5, pillow (PIL), sqlite3, suntime, geopy.
