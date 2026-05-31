import asyncio
import json
import os
from datetime import datetime

import gspread
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    WebAppInfo,
)

BOT_TOKEN = "8924834761:AAGIvnb-TQVIL9uND8YMrXoZWt57lXzfxvc"
ADMIN_ID = 124435947
WEB_APP_URL = "https://gdd48fjfrg-cmyk.github.io/courier-bot/"
GOOGLE_SHEET_ID = "1DiM4Ba_cOONBxoWwl4Gna3-zsYLkJLZKKYkK3MDM0RE"

REGISTER_LINK = "https://reg.eda.yandex.ru/?advertisement_campaign=forms_for_agents&user_invite_code=67dd9abed6de4f799486a0435d56f4c7&utm_content=blank"
APPLICATIONS_FILE = "applications.json"
GOOGLE_CREDENTIALS_FILE = "service_account.json"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# ---------- GOOGLE SHEETS ----------

def get_sheet():
    try:
        gc = gspread.service_account(filename=GOOGLE_CREDENTIALS_FILE)
        spreadsheet = gc.open_by_key(GOOGLE_SHEET_ID)
        sheet = spreadsheet.sheet1
        return sheet
    except Exception as e:
        print("Google Sheets connection error:", e)
        return None


sheet = get_sheet()


def append_to_google_sheets(application):
    global sheet

    if sheet is None:
        sheet = get_sheet()

    if sheet is None:
        print("Google Sheets is not connected")
        return False

    try:
        sheet.append_row([
            application.get("date", ""),
            application.get("name", ""),
            application.get("phone", ""),
            application.get("city", "Красноярск"),
            application.get("district", ""),
            normalize_transport(application.get("transport", "")),
            "Да" if application.get("friendBonus") else "Нет",
            application.get("source", ""),
            application.get("user_id", ""),
            application.get("username", ""),
        ])
        return True
    except Exception as e:
        print("Google Sheets append error:", e)
        return False


# ---------- STATES ----------

class Form(StatesGroup):
    waiting_for_district = State()
    waiting_for_phone = State()
    waiting_for_name = State()


DISTRICTS = [
    "Центральный", "Советский", "Октябрьский", "Железнодорожный",
    "Свердловский", "Кировский", "Ленинский", "Покровка",
    "Взлётка", "Северный", "Солнечный", "Зелёная Роща",
    "Черёмушки", "Студгородок",
]


# ---------- KEYBOARDS ----------

main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🚀 Открыть Web App", web_app=WebAppInfo(url=WEB_APP_URL))],
        [KeyboardButton(text="🚴 Стать курьером")],
        [KeyboardButton(text="💰 Доход"), KeyboardButton(text="❓ Частые вопросы")],
        [KeyboardButton(text="🔗 Регистрация"), KeyboardButton(text="ℹ️ Условия")],
    ],
    resize_keyboard=True,
)

districts_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Центральный"), KeyboardButton(text="Советский")],
        [KeyboardButton(text="Октябрьский"), KeyboardButton(text="Железнодорожный")],
        [KeyboardButton(text="Свердловский"), KeyboardButton(text="Кировский")],
        [KeyboardButton(text="Ленинский"), KeyboardButton(text="Покровка")],
        [KeyboardButton(text="Взлётка"), KeyboardButton(text="Северный")],
        [KeyboardButton(text="Солнечный"), KeyboardButton(text="Зелёная Роща")],
        [KeyboardButton(text="Черёмушки"), KeyboardButton(text="Студгородок")],
        [KeyboardButton(text="⬅️ Назад")],
    ],
    resize_keyboard=True,
)

phone_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📱 Отправить номер телефона", request_contact=True)],
        [KeyboardButton(text="⬅️ Назад")],
    ],
    resize_keyboard=True,
    one_time_keyboard=True,
)

register_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Зарегистрироваться", url=REGISTER_LINK)]
    ]
)

admin_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="📋 Заявки", callback_data="admin_applications")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="🧹 Очистить заявки", callback_data="admin_clear")],
    ]
)


# ---------- HELPERS ----------

def load_applications():
    if not os.path.exists(APPLICATIONS_FILE):
        return []

    with open(APPLICATIONS_FILE, "r", encoding="utf-8") as file:
        try:
            return json.load(file)
        except json.JSONDecodeError:
            return []


def save_applications(applications):
    with open(APPLICATIONS_FILE, "w", encoding="utf-8") as file:
        json.dump(applications, file, ensure_ascii=False, indent=4)


def user_already_applied(user_id):
    applications = load_applications()
    return any(app.get("user_id") == user_id for app in applications)


def normalize_transport(transport):
    names = {
        "foot": "Пеший",
        "bike": "Вело",
        "car": "Авто",
    }
    return names.get(transport, transport or "Не указан")


def save_application(application):
    applications = load_applications()

    if any(app.get("user_id") == application.get("user_id") for app in applications):
        return False

    applications.append(application)
    save_applications(applications)
    append_to_google_sheets(application)

    return True


async def notify_admin(application):
    username = application.get("username")
    username_text = f"@{username}" if username else "Не указан"

    text = (
        "🔥 Новая заявка!\n\n"
        f"👤 Имя: {application.get('name')}\n"
        f"📱 Телефон: {application.get('phone')}\n"
        f"🏙 Город: Красноярск\n"
        f"📍 Район: {application.get('district')}\n"
        f"🚴 Транспорт: {normalize_transport(application.get('transport'))}\n"
        f"👥 Друг: {'Да' if application.get('friendBonus') else 'Нет'}\n"
        f"📦 Источник: {application.get('source')}\n"
        f"🆔 ID: {application.get('user_id')}\n"
        f"🔗 Username: {username_text}\n"
        f"📅 Дата: {application.get('date')}"
    )

    try:
        await bot.send_message(ADMIN_ID, text)
    except Exception:
        pass


# ---------- COMMANDS ----------

@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "👋 Привет!\n\n"
        "Это бот для подключения курьеров Яндекс Еды в Красноярске.\n\n"
        "🚴 Работа пешком, на велосипеде или авто\n"
        "💰 Свободный график\n"
        "📍 Районы по Красноярску\n"
        "⚡ Быстрое подключение\n\n"
        "Выбери действие ниже 👇",
        reply_markup=main_keyboard,
    )


@dp.message(Command("id"))
async def get_id(message: Message):
    await message.answer(f"Твой Telegram ID: {message.from_user.id}")


@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Нет доступа.")
        return

    await message.answer("👑 Админ-панель", reply_markup=admin_keyboard)


# ---------- MENU ----------

@dp.message(F.text == "⬅️ Назад")
async def back(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Главное меню 👇", reply_markup=main_keyboard)


@dp.message(F.text == "💰 Доход")
async def income_info(message: Message):
    await message.answer(
        "💰 Доход зависит от количества заказов, района и времени выхода.\n\n"
        "✅ Пеший: примерно 400 ₽/час\n"
        "✅ Вело: примерно 450 ₽/час\n"
        "✅ Авто: примерно 510 ₽/час\n\n"
        "Точный доход зависит от спроса, района, чаевых и бонусов."
    )


@dp.message(F.text == "❓ Частые вопросы")
async def faq(message: Message):
    await message.answer(
        "❓ Частые вопросы\n\n"
        "1️⃣ Можно без опыта?\n"
        "Да, опыт не нужен.\n\n"
        "2️⃣ Можно пешком?\n"
        "Да, можно пешком, на велосипеде или авто.\n\n"
        "3️⃣ Какой график?\n"
        "Свободный.\n\n"
        "4️⃣ Где работа?\n"
        "Красноярск и районы города.\n\n"
        "5️⃣ Как начать?\n"
        "Оставь заявку или нажми регистрацию 👇",
        reply_markup=register_keyboard,
    )


@dp.message(F.text == "ℹ️ Условия")
async def work_info(message: Message):
    await message.answer(
        "ℹ️ Условия работы\n\n"
        "📍 Красноярск\n"
        "🎂 От 18 лет\n"
        "🚶 Пешком / 🚲 Велосипед / 🚗 Авто\n"
        "🕒 Свободный график\n"
        "⚡ Быстрое подключение",
        reply_markup=register_keyboard,
    )


@dp.message(F.text == "🔗 Регистрация")
async def registration(message: Message):
    await message.answer(
        "Нажми кнопку ниже для регистрации 👇",
        reply_markup=register_keyboard,
    )


# ---------- BOT APPLICATION ----------

@dp.message(F.text == "🚴 Стать курьером")
async def become_courier(message: Message, state: FSMContext):
    if user_already_applied(message.from_user.id):
        await state.clear()
        await message.answer(
            "✅ Ты уже оставлял заявку.\n\n"
            "Повторную заявку с этого Telegram-аккаунта отправить нельзя.",
            reply_markup=main_keyboard,
        )
        return

    await state.set_state(Form.waiting_for_district)
    await message.answer("📍 Выбери район Красноярска 👇", reply_markup=districts_keyboard)


@dp.message(Form.waiting_for_district)
async def get_district(message: Message, state: FSMContext):
    district = message.text.strip()

    if district not in DISTRICTS:
        await message.answer("Выбери район кнопкой 👇")
        return

    await state.update_data(district=district)
    await state.set_state(Form.waiting_for_phone)
    await message.answer("📱 Отправь номер телефона кнопкой ниже 👇", reply_markup=phone_keyboard)


@dp.message(Form.waiting_for_phone, F.contact)
async def get_phone(message: Message, state: FSMContext):
    if message.contact.user_id != message.from_user.id:
        await message.answer("Отправь именно свой номер через кнопку 👇", reply_markup=phone_keyboard)
        return

    await state.update_data(phone=message.contact.phone_number)
    await state.set_state(Form.waiting_for_name)
    await message.answer("Теперь напиши своё имя:", reply_markup=ReplyKeyboardRemove())


@dp.message(Form.waiting_for_phone)
async def wrong_phone(message: Message):
    await message.answer("Используй кнопку отправки номера 👇", reply_markup=phone_keyboard)


@dp.message(Form.waiting_for_name)
async def get_name(message: Message, state: FSMContext):
    if user_already_applied(message.from_user.id):
        await state.clear()
        await message.answer(
            "✅ Ты уже оставлял заявку.\n\n"
            "Повторную заявку с этого Telegram-аккаунта отправить нельзя.",
            reply_markup=main_keyboard,
        )
        return

    name = message.text.strip()

    if len(name) < 2 or len(name) > 30:
        await message.answer("Напиши нормальное имя от 2 до 30 символов.")
        return

    data = await state.get_data()

    application = {
        "user_id": message.from_user.id,
        "username": message.from_user.username,
        "name": name,
        "phone": data["phone"],
        "city": "Красноярск",
        "district": data["district"],
        "transport": "Не указан",
        "friendBonus": False,
        "source": "Бот",
        "date": datetime.now().strftime("%d.%m.%Y %H:%M"),
    }

    saved = save_application(application)
    await state.clear()

    if not saved:
        await message.answer(
            "✅ Ты уже оставлял заявку.\n\n"
            "Повторную заявку с этого Telegram-аккаунта отправить нельзя.",
            reply_markup=main_keyboard,
        )
        return

    await message.answer(
        "✅ Заявка отправлена!\n\n"
        "Теперь зарегистрируйся по кнопке ниже 👇",
        reply_markup=register_keyboard,
    )
    await message.answer("Главное меню 👇", reply_markup=main_keyboard)

    await notify_admin(application)


# ---------- WEB APP APPLICATION ----------

@dp.message(F.web_app_data)
async def web_app_handler(message: Message):
    user_id = message.from_user.id

    if user_already_applied(user_id):
        await message.answer(
            "✅ Ты уже оставлял заявку.\n\n"
            "Повторную заявку с этого Telegram-аккаунта отправить нельзя.",
            reply_markup=main_keyboard,
        )
        return

    try:
        data = json.loads(message.web_app_data.data)
    except Exception:
        await message.answer("❌ Ошибка получения заявки из Web App.")
        return

    name = str(data.get("name", "")).strip()
    phone = str(data.get("phone", "")).strip()
    district = str(data.get("district", "")).strip()
    transport = str(data.get("transport", "Не указан")).strip()
    friend_bonus = bool(data.get("friendBonus", False))

    if len(name) < 2 or len(name) > 30:
        await message.answer("❌ Некорректное имя.")
        return

    if len(phone) < 10 or len(phone) > 20:
        await message.answer("❌ Некорректный телефон.")
        return

    if district not in DISTRICTS:
        await message.answer("❌ Некорректный район.")
        return

    application = {
        "user_id": user_id,
        "username": message.from_user.username,
        "name": name,
        "phone": phone,
        "city": "Красноярск",
        "district": district,
        "transport": transport,
        "friendBonus": friend_bonus,
        "source": "Web App",
        "date": datetime.now().strftime("%d.%m.%Y %H:%M"),
    }

    saved = save_application(application)

    if not saved:
        await message.answer(
            "✅ Ты уже оставлял заявку.\n\n"
            "Повторную заявку с этого Telegram-аккаунта отправить нельзя.",
            reply_markup=main_keyboard,
        )
        return

    await message.answer(
        "✅ Заявка из Web App принята!\n\n"
        "Теперь зарегистрируйся по кнопке ниже 👇",
        reply_markup=register_keyboard,
    )
    await message.answer("Главное меню 👇", reply_markup=main_keyboard)

    await notify_admin(application)


# ---------- ADMIN CALLBACKS ----------

@dp.callback_query(F.data == "admin_applications")
async def show_applications(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Нет доступа", show_alert=True)
        return

    applications = load_applications()

    if not applications:
        await callback.message.answer("Заявок пока нет.")
        return

    text = "📋 Последние заявки:\n\n"

    for app in applications[-10:]:
        username = app.get("username")
        username_text = f"@{username}" if username else "Не указан"

        text += (
            f"👤 Имя: {app.get('name', 'Не указано')}\n"
            f"📱 Телефон: {app.get('phone', 'Не указан')}\n"
            f"🏙 Город: {app.get('city', 'Красноярск')}\n"
            f"📍 Район: {app.get('district', 'Не указан')}\n"
            f"🚴 Транспорт: {normalize_transport(app.get('transport'))}\n"
            f"👥 Друг: {'Да' if app.get('friendBonus') else 'Нет'}\n"
            f"📦 Источник: {app.get('source', 'Не указан')}\n"
            f"🆔 ID: {app.get('user_id', 'Не указан')}\n"
            f"🔗 Username: {username_text}\n"
            f"📅 Дата: {app.get('date', 'Не указана')}\n"
            "──────────────\n"
        )

    await callback.message.answer(text)


@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Нет доступа", show_alert=True)
        return

    applications = load_applications()

    districts = {}
    sources = {}
    transports = {}

    for app in applications:
        district = app.get("district", "Не указан")
        source = app.get("source", "Не указан")
        transport = normalize_transport(app.get("transport"))

        districts[district] = districts.get(district, 0) + 1
        sources[source] = sources.get(source, 0) + 1
        transports[transport] = transports.get(transport, 0) + 1

    text = f"📊 Статистика\n\nВсего заявок: {len(applications)}\n\n"

    if districts:
        text += "📍 По районам:\n"
        for district, count in districts.items():
            text += f"— {district}: {count}\n"

    if transports:
        text += "\n🚴 По транспорту:\n"
        for transport, count in transports.items():
            text += f"— {transport}: {count}\n"

    if sources:
        text += "\n📦 По источникам:\n"
        for source, count in sources.items():
            text += f"— {source}: {count}\n"

    await callback.message.answer(text)


@dp.callback_query(F.data == "admin_clear")
async def clear_applications(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Нет доступа", show_alert=True)
        return

    save_applications([])
    await callback.message.answer("🧹 Заявки очищены.")


@dp.message()
async def unknown_message(message: Message):
    await message.answer("Выбери действие ниже 👇", reply_markup=main_keyboard)


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())