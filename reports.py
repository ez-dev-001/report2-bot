import telebot
import config
import json
import re
import threading
import time
from datetime import datetime, timedelta
from telebot import types

bot = telebot.TeleBot(config.TOKEN)

YOUR_ADMIN_ID = [1409326380,740112531]  # Ваш админ ID

# Функция загрузки данных из JSON-файла
def load_config():
    with open('config.json', 'r') as f:
        return json.load(f)

# Функция сохранения данных в JSON-файл
def save_config(data):
    with open('config.json', 'w') as f:
        json.dump(data, f, indent=4)

# Инициализация данных
config_data = load_config()
ALLOWED_CHAT_ID = config_data['ALLOWED_CHAT_ID']
chat_to_person_map = config_data['chat_to_person_map']

# Регулярное выражение для проверки формата "*."
pattern = r"^(\d{1,2})\."

message_data = {chat_id: {} for chat_id in ALLOWED_CHAT_ID}
duplicate_messages = {}
places = {chat_id: [] for chat_id in ALLOWED_CHAT_ID}
awaiting_responses = {}

# Временной диапазон отправки (по GMT+1)
start_hour = 7
end_hour = 23
minute_of_hour = 10
final_minute = 55

# Функция отправки сообщений с учетом привязки
def send_scheduled_messages():
    while True:
        current_time = datetime.utcnow() + timedelta(hours=1)
        current_hour = current_time.hour
        current_minute = current_time.minute

        if current_hour == 23 and current_minute == 59:
            print("Время 23:59 по GMT+1. Остановка бота.")
            bot.stop_polling()
            return

        if (start_hour <= current_hour <= end_hour and current_minute == minute_of_hour) or (current_hour == end_hour and current_minute == final_minute):
            for chat_id in ALLOWED_CHAT_ID:
                chat_info = bot.get_chat(chat_id)
                chat_title = chat_info.title if chat_info else f"Chat ID: {chat_id}"

                # Инициализация отчетов
                report = f"Отчет чата '{chat_title}':\n"
                report2 = f"Aдреса чата '{chat_title}':\n"
                
                # Флаг наличия данных для report
                report_has_data = False
                report2_has_data = False

                # Сбор сообщений в report, если они есть
                if message_data.get(chat_id):
                    report += "\n".join(f"{message_data[chat_id][number]}" for number in sorted(message_data[chat_id].keys()))
                    message_data[chat_id].clear()
                    report_has_data = True
                    print(f"Сообщения отправлены для чата '{chat_title}' и словарь очищен.")
                else:
                    print(f"Нет новых сообщений для отправки в чате '{chat_title}'.")

                # Если это последний отчет дня, собираем места в report2
                if current_hour == end_hour and current_minute == final_minute:
                    if places.get(chat_id):
                        places_list = "\n".join(f"{place}" for place in places[chat_id])
                        report2 += f"Список мест:\n{places_list}"
                        places[chat_id].clear()
                        report2_has_data = True
                        print(f"Добавлен итоговый список мест для чата '{chat_title}'.")
                
                # Отправка report, если есть данные
                if report_has_data and report.strip() != f"Отчет чата '{chat_title}':\n":
                    bot.send_message(chat_id, report)
                    person_chat_id = chat_to_person_map.get(str(chat_id))
                    if person_chat_id:
                        print(f"Отправка отчета в личный чат с ID {person_chat_id}...")
                        bot.send_message(person_chat_id, report)
                    else:
                        print(f"Ошибка: Для чата {chat_id} не найден привязанный ID пользователя.")
                # Отправка report2, если есть данные (только для итогового отчета)
                if report2_has_data and report2.strip() != f"Aдреса чата '{chat_title}':\n":
                    person_chat_id = chat_to_person_map.get(str(chat_id))
                    if person_chat_id:
                        print(f"Отправка итогового отчета в личный чат с ID {person_chat_id}...")
                        bot.send_message(person_chat_id, report2)
                    else:
                        print(f"Ошибка: Для чата {chat_id} не найден привязанный ID пользователя.")

            # Пауза на 60 секунд для проверки расписания
            time.sleep(60)
        else:
            # Пауза на 10 секунд
            time.sleep(10)
# Команда добавления нового чата
@bot.message_handler(commands=['add_chat'])
def add_chat(message):
    if message.from_user.id not in YOUR_ADMIN_ID:
        bot.reply_to(message, "У вас нет прав для выполнения этой команды.")
        return

    try:
        command_parts = message.text.split()
        chat_id = int(command_parts[1])

        if chat_id not in ALLOWED_CHAT_ID:
            ALLOWED_CHAT_ID.append(chat_id)
            bot.reply_to(message, f"Чат с ID {chat_id} добавлен.")

            if str(chat_id) not in chat_to_person_map:
                awaiting_responses[chat_id] = "awaiting_person_chat_id"
                bot.reply_to(message, f"Чат {chat_id} требует привязки к пользователю. Укажите ID пользователя.")
            save_config({"ALLOWED_CHAT_ID": ALLOWED_CHAT_ID, "chat_to_person_map": chat_to_person_map})
        else:
            bot.reply_to(message, f"Чат с ID {chat_id} уже добавлен.")
    except (IndexError, ValueError):
        bot.reply_to(message, "Укажите корректный ID чата.")

@bot.message_handler(func=lambda message: message.chat.id in YOUR_ADMIN_ID)
def handle_user_input(message):
    if message.text.isdigit() or message.text.startswith("-"):
        user_id = int(message.text)
        chat_id = next((c_id for c_id, status in awaiting_responses.items() if status == "awaiting_person_chat_id"), None)

        if chat_id:
            chat_to_person_map[str(chat_id)] = user_id
            awaiting_responses.pop(chat_id)
            save_config({"ALLOWED_CHAT_ID": ALLOWED_CHAT_ID, "chat_to_person_map": chat_to_person_map})
            bot.reply_to(message, f"Чат {chat_id} привязан к пользователю {user_id}.")
        else:
            bot.reply_to(message, "Нет чатов, ожидающих привязки.")
    else:
        bot.reply_to(message, "Введите ID пользователя.")

@bot.message_handler(func=lambda message: message.chat.id in ALLOWED_CHAT_ID and not message.text.startswith('/'))
def check_message(message):
    chat_id = message.chat.id

    # Убедимся, что chat_id существует в словаре message_data
    if chat_id not in message_data:
        message_data[chat_id] = {}  # Инициализируем пустой словарь для этого chat_id

    # Убедимся, что chat_id существует в словаре places
    if chat_id not in places:
        places[chat_id] = []  # Инициализируем пустой список для этого chat_id

    # Обработка сообщений, начинающихся с #
    if message.text.startswith("#"):
        place_name = message.text.strip("#").strip()
        if place_name:
            current_time2 = (datetime.utcnow() + timedelta(hours=1)).strftime("%H:%M")
            places[chat_id].append(f"{current_time2} - {place_name}")
            print(f"Место '{place_name}' добавлено в список.")
            return
        else:
            bot.reply_to(message, "Пожалуйста, укажите название места после '#'.")
    # Проверка формата "*."
    match = re.match(pattern, message.text)
    if match:
        number = int(match.group(1))

        if number in message_data[chat_id]:
            duplicate_messages[number] = message.text
            markup = types.InlineKeyboardMarkup()
            overwrite_button = types.InlineKeyboardButton("✅", callback_data=f"overwrite_{number}")
            keep_button = types.InlineKeyboardButton("❌", callback_data=f"keep_{number}")
            markup.add(overwrite_button, keep_button)

            bot.send_message(chat_id, f"Сообщение с номером {number} уже существует. Хотите перезаписать?", reply_markup=markup)
            print(f"Сообщение с номером {number} уже существует. Отправлена кнопка выбора.")
        else:
            message_data[chat_id][number] = message.text
            print(f"Сообщение '{message.text}' добавлено под номером {number} для чата {chat_id}.")
    else:
        print("-")

# Обработчики callback для подтверждения перезаписи сообщений
@bot.callback_query_handler(func=lambda call: call.data.startswith('overwrite_'))
def handle_overwrite_callback(call):
    chat_id = call.message.chat.id
    number = int(call.data.split('_')[1])

    if number in duplicate_messages:
        message_data[chat_id][number] = duplicate_messages[number]
        bot.send_message(chat_id, f"✅ㅤ")
        duplicate_messages.pop(number, None)
        print(f"Перезаписано сообщение с номером {number} для чата {chat_id}")
    else:
        bot.send_message(chat_id, f"Нет дубликата для номера {number}.")
    
    bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)

@bot.callback_query_handler(func=lambda call: call.data.startswith('keep_'))
def handle_keep_callback(call):
    chat_id = call.message.chat.id
    number = int(call.data.split('_')[1])
    duplicate_messages.pop(number, None)
    bot.send_message(chat_id, f"Перезапись отменена.")
    print(f"Сообщение под номером {number} оставлено без изменений в чате {chat_id}.")
    bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)

# Запуск потока для периодической отправки сообщений по расписанию
schedule_thread = threading.Thread(target=send_scheduled_messages, daemon=True)
schedule_thread.start()

# Запуск бота
bot.polling(none_stop=True)
