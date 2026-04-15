import io
import os
import random
import string
from PIL import Image
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    CallbackQueryHandler,
    filters,
)

TOKEN = "8624511949:AAFFlUJOZIWQ-Z7Nzv1LCkXjVbkVMz4x1h0"
ALLOWED_USER_IDS = {1610000020,514590673}

MAX_SIZE = 1600
JPEG_QUALITY = 78

RATIOS = {
    "1:1": 1 / 1,
    "3:4": 3 / 4,
    "9:16": 9 / 16,
}


def random_filename(length: int = 32) -> str:
    chars = string.ascii_lowercase + string.digits
    name = "".join(random.choice(chars) for _ in range(length))
    return f"{name}.jpg"


def crop_and_compress(image_bytes: bytes, ratio: str) -> io.BytesIO:
    with Image.open(io.BytesIO(image_bytes)) as img:
        img = img.convert("RGB")

        target_ratio = RATIOS.get(ratio, 1 / 1)

        w, h = img.size
        current_ratio = w / h

        if current_ratio > target_ratio:
            new_w = int(h * target_ratio)
            left = (w - new_w) // 2
            img = img.crop((left, 0, left + new_w, h))
        else:
            new_h = int(w / target_ratio)
            top = (h - new_h) // 2
            img = img.crop((0, top, w, top + new_h))

        w, h = img.size
        scale = min(MAX_SIZE / max(w, h), 1.0)
        new_size = (int(w * scale), int(h * scale))

        if new_size != (w, h):
            img = img.resize(new_size, Image.Resampling.LANCZOS)

        output = io.BytesIO()
        img.save(output, format="JPEG", quality=JPEG_QUALITY, optimize=True)
        output.seek(0)
        return output


def compress_image_bytes(image_bytes: bytes) -> io.BytesIO:
    with Image.open(io.BytesIO(image_bytes)) as img:
        img = img.convert("RGB")

        w, h = img.size
        scale = min(MAX_SIZE / max(w, h), 1.0)
        new_size = (int(w * scale), int(h * scale))

        if new_size != (w, h):
            img = img.resize(new_size, Image.Resampling.LANCZOS)

        output = io.BytesIO()
        img.save(output, format="JPEG", quality=JPEG_QUALITY, optimize=True)
        output.seek(0)
        return output


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.from_user:
        return

    keyboard = [
        [InlineKeyboardButton("Узнать мой ID", callback_data="my_id")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Отправь фото. Я предложу формат обрезки. Если пришлёшь изображение файлом, я просто сожму его и верну обратно.",
        reply_markup=reply_markup
    )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.photo or not update.message.from_user:
        return

    if update.message.from_user.id not in ALLOWED_USER_IDS:
        await update.message.reply_text("У тебя нет доступа к этому боту.")
        return

    photo = update.message.photo[-1]
    file = await photo.get_file()
    image_bytes = await file.download_as_bytearray()

    context.user_data["temp_image"] = bytes(image_bytes)

    keyboard = [
        [InlineKeyboardButton("1:1 (Квадрат)", callback_data="1:1")],
        [InlineKeyboardButton("3:4 (Портрет)", callback_data="3:4")],
        [InlineKeyboardButton("9:16 (Stories)", callback_data="9:16")],
        [InlineKeyboardButton("Без обрезки", callback_data="compress_only")],
        [InlineKeyboardButton("Узнать мой ID", callback_data="my_id")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Выбери вариант обработки:",
        reply_markup=reply_markup
    )


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.from_user:
        return

    if query.data == "my_id":
        await query.answer()
        await query.message.reply_text(f"Твой Telegram ID: {query.from_user.id}")
        return

    if query.from_user.id not in ALLOWED_USER_IDS:
        await query.answer("Нет доступа.", show_alert=True)
        return

    await query.answer()

    image_bytes = context.user_data.get("temp_image")
    if not image_bytes:
        await query.message.reply_text("Ошибка: фото не найдено. Отправь его ещё раз.")
        return

    try:
        if query.data == "compress_only":
            processed_file = compress_image_bytes(image_bytes)
        else:
            processed_file = crop_and_compress(image_bytes, query.data)

        await query.message.reply_document(
            document=processed_file,
            filename=random_filename()
        )
    except Exception:
        await query.message.reply_text("Не удалось обработать изображение.")


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.document or not update.message.from_user:
        return

    if update.message.from_user.id not in ALLOWED_USER_IDS:
        await update.message.reply_text("У тебя нет доступа к этому боту.")
        return

    document = update.message.document

    if not document.mime_type or not document.mime_type.startswith("image/"):
        await update.message.reply_text("Пришли именно изображение.")
        return

    file = await document.get_file()
    image_bytes = await file.download_as_bytearray()

    try:
        compressed = compress_image_bytes(bytes(image_bytes))
        await update.message.reply_document(
            document=compressed,
            filename=random_filename()
        )
    except Exception:
        await update.message.reply_text("Не удалось обработать файл.")


def main() -> None:
    if not TOKEN:
        raise ValueError("Не найден BOT_TOKEN в переменных окружения.")

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.IMAGE, handle_document))
    app.add_handler(CallbackQueryHandler(button_callback))

    app.run_polling()


if __name__ == "__main__":
    main()