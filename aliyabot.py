import logging
import os
import json
from os.path import exists
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler, CallbackQueryHandler
)

BOT_TOKEN = os.environ["BOT_TOKEN"]

logging.basicConfig(level=logging.INFO)

CHOOSING, TYPING_DESC, ASK_PHOTO, SENDING_PHOTO = range(4)

DATA_FILE = "data.json"


if exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        data = json.load(f)
else:
    data = {
        "users": {},
        "items": [],
        "button_stats": {}
    }

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    username = update.message.from_user.username or "anon"

    if user_id not in data["users"]:
        data["users"][user_id] = username
        save_data()

    user_number = list(data["users"]).index(user_id) + 1

    keyboard = [["🟢 Нашёл", "🔴 Потерял"],
                ["🟢 Найдено", "🔴 Потеряно"],
                ["🗂 Мои посты"]]

    await update.message.reply_text(
        f"Привет! Ты {user_number}-й пользователь по счёту.\nВыберите действие:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return CHOOSING


async def send_template(update: Update, context: ContextTypes.DEFAULT_TYPE, mode: str = ""):
    if mode == "found":
        template = (
            "❗️*Шаблон для сообщения, если вы нашли вещь:*\n\n"
            "*1. Что вы нашли:*\n"
            "_Кратко опишите предмет — например: студенческий, браслет, бутылка и т.п._\n\n"
            "*2. Где нашли:*\n"
            "_Укажите место: аудитория, корпус, коридор, столовая и т.п._\n\n"
            "*3. Когда нашли:*\n"
            "_Дата и время, если знаете_\n\n"
            "*4. Контакт или где забрать:*"
        )
    elif mode == "lost":
        template = (
            "❗️*Шаблон для сообщения, если вы ищите вещь:*\n\n"
            "*1. Что вы потеряли:*\n"
            "_Кратко и понятно опишите предмет — например: зонт, ключи, студенческий билет и т.д._\n\n"
            "*2. Где примерно потеряли:*\n"
            "_Укажите корпус, аудиторию, зону (библиотека, столовая и т.д.)_\n\n"
            "*3. Когда потеряли:*\n"
            "_Дата и примерное время_\n\n"
            "*4. Фото (если есть)*"
        )
    else:
        template = (
            "❗️*Общий шаблон:*\n\n"
            "1. Что потеряно/найдено\n"
            "2. Где\n"
            "3. Когда\n"
            "4. Фото (если есть)\n"
            "5. Контакт: @username\n"
            "#поиск #находка"
        )
    await update.message.reply_text(template, parse_mode="Markdown")
    return CHOOSING


async def choose_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text
    if msg == "🟢 Нашёл":
        context.user_data["type"] = "found"
        await send_template(update, context, "found")
        await update.message.reply_text("✏️ Введите описание:")
        return TYPING_DESC
    elif msg == "🔴 Потерял":
        context.user_data["type"] = "lost"
        await send_template(update, context, "lost")
        await update.message.reply_text("✏️ Введите описание:")
        return TYPING_DESC
    elif msg == "🟢 Найдено":
        return await show_found_items(update, context)
    elif msg == "🔴 Потеряно":
        return await show_lost_items(update, context)
    elif msg == "🗂 Мои посты":
        return await show_my_posts(update, context)
    else:
        await update.message.reply_text("Выберите действие с клавиатуры.")
        return CHOOSING


async def get_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    control_buttons = ["🟢 Нашёл", "🔴 Потерял", "🟢 Найдено", "🔴 Потеряно", "🗂 Мои посты"]

    if text in control_buttons:
        return await choose_action(update, context)

    context.user_data["description"] = text
    keyboard = [["✅ Да", "❌ Нет"]]
    await update.message.reply_text("У вас есть фото этой вещи?", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    return ASK_PHOTO

async def ask_for_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    answer = update.message.text
    if answer == "✅ Да":
        await update.message.reply_text("📸 Пожалуйста, отправьте фото:")
        return SENDING_PHOTO
    elif answer == "❌ Нет":
        return await save_item_without_photo(update, context)
    else:
        await update.message.reply_text("Пожалуйста, выберите ✅ Да или ❌ Нет.")
        return ASK_PHOTO


async def save_item_without_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global data
    item = {
        "user_id": update.message.from_user.id,
        "username": update.message.from_user.username or "anon",
        "type": context.user_data["type"],
        "description": context.user_data["description"],
        "photo_file_id": None
    }
    data["items"].append(item)
    save_data()
    await update.message.reply_text("✅ Объявление без фото добавлено!")
    return await start(update, context)



async def get_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global data
    photo_file_id = update.message.photo[-1].file_id
    item = {
        "user_id": update.message.from_user.id,
        "username": update.message.from_user.username or "anon",
        "type": context.user_data["type"],
        "description": context.user_data["description"],
        "photo_file_id": photo_file_id
    }
    data["items"].append(item)
    save_data()
    await update.message.reply_text("✅ Объявление с фото добавлено!")
    return await start(update, context)



async def show_found_items(update: Update, context: ContextTypes.DEFAULT_TYPE):
    found_items = [item for item in data["items"] if item["type"] == "found"]
    if not found_items:
        await update.message.reply_text("❌ Найденных вещей пока нет.")
        return CHOOSING
    for item in found_items[:5]:
        caption = f"🟢 *Найдено*\n\n*Описание:* {item['description']}\n*Контакт:* @{item['username']}"
        if item["photo_file_id"]:
            await update.message.reply_photo(item["photo_file_id"], caption=caption, parse_mode="Markdown")
        else:
            await update.message.reply_text(caption + "\n\n📌 *Фото не было отправлено*", parse_mode="Markdown")
    return CHOOSING


async def show_lost_items(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lost_items = [item for item in data["items"] if item["type"] == "lost"]
    if not lost_items:
        await update.message.reply_text("❌ Потерянных вещей пока нет.")
        return CHOOSING
    for item in lost_items[:5]:
        caption = f"🔴 *Потеряно*\n\n*Описание:* {item['description']}\n*Контакт:* @{item['username']}"
        if item["photo_file_id"]:
            await update.message.reply_photo(item["photo_file_id"], caption=caption, parse_mode="Markdown")
        else:
            await update.message.reply_text(caption + "\n\n📌 *Фото не было отправлено*", parse_mode="Markdown")
    return CHOOSING


async def show_my_posts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_posts = [item for item in data["items"] if item["user_id"] == user_id]
    if not user_posts:
        await update.message.reply_text("❌ У вас пока нет добавленных постов.")
        return CHOOSING
    for item in user_posts[:10]:
        label = "🟢 Найдено" if item["type"] == "found" else "🔴 Потеряно"
        caption = f"{label}\n\n*Описание:* {item['description']}\n*Вы добавили этот пост.*"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🗑 Удалить", callback_data=f"delete:{item['user_id']}"),
             InlineKeyboardButton("✅ Оставить", callback_data="ignore")]
        ])
        if item["photo_file_id"]:
            await update.message.reply_photo(item["photo_file_id"], caption=caption, parse_mode="Markdown", reply_markup=keyboard)
        else:
            await update.message.reply_text(caption, reply_markup=keyboard, parse_mode="Markdown")
    return CHOOSING


async def delete_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global data
    query = update.callback_query
    await query.answer()

    action, user_id = query.data.split(":")
    user_id = int(user_id)

    user_posts = [item for item in data["items"] if item["user_id"] == user_id]
    if user_posts:
        data["items"].remove(user_posts[0])
        save_data()

        try:
            await query.message.delete()
        except Exception as e:
            logging.warning(f"Не удалось удалить сообщение: {e}")
    else:
        await query.answer("❌ Пост не найден")

    return ConversationHandler.END


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING: [MessageHandler(filters.TEXT, choose_action)],
            TYPING_DESC: [MessageHandler(filters.TEXT, get_description)],
            ASK_PHOTO: [MessageHandler(filters.TEXT, ask_for_photo)],
            SENDING_PHOTO: [MessageHandler(filters.PHOTO, get_photo)],
        },
        fallbacks=[],
    )

    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(delete_post, pattern="delete:"))

    app.run_polling()

if __name__ == "__main__":
    main()
