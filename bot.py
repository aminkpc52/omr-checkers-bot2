"""
bot.py
--------
Bot Telegram untuk semakan OMR automatik, dengan sistem KELAS (butang):

  /kelas
    -> senarai kelas sedia ada (butang) + "Tambah Kelas Baru"
    -> pilih kelas -> menu: Masukkan Skema Baru / Semak Jawapan / Jana Analisis Penuh

Setiap kali gambar disemak untuk sesuatu kelas, jawapan yang dikesan (A/B/C/D/
Kosong/Berganda) direkodkan bagi kelas itu (lihat class_manager.py). "Jana
Analisis Penuh" memaparkan jumlah A/B/C/D bagi SETIAP soalan, dikumpul
daripada SEMUA gambar yang telah disemak untuk kelas tersebut.

Cara jalankan (dalam Visual Studio / VS Code):
    1. python -m venv venv
    2. venv\\Scripts\\activate          (Windows)   atau   source venv/bin/activate   (Mac/Linux)
    3. pip install -r requirements.txt
    4. Tetapkan token bot anda (environment variable TELEGRAM_BOT_TOKEN, atau gantikan BOT_TOKEN di bawah)
    5. python bot.py

Rujuk README.md untuk arahan penuh & cara dapatkan token daripada BotFather.
"""

import asyncio
import logging
import os

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TimedOut, NetworkError
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from telegram.request import HTTPXRequest

import omr_generator
import omr_scanner
import class_manager

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8941910574:AAEERN3OggHXzjXINvkVsXXP7iYa0SV7IVY")


# ---------------------------------------------------------------------------
# Bina papan kekunci (keyboard)
# ---------------------------------------------------------------------------

def _class_list_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    classes = class_manager.list_classes(chat_id)
    rows = []
    row = []
    for class_id, name in classes:
        row.append(InlineKeyboardButton(name, callback_data=f"cls_sel|{class_id}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("➕ Tambah Kelas Baru", callback_data="cls_new")])
    if classes:
        rows.append([InlineKeyboardButton("🗑️ Reset Semua (Padam Segalanya)", callback_data="cls_reset_all")])
    return InlineKeyboardMarkup(rows)


def _reset_all_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Ya, Padam Semua", callback_data="cls_reset_all_confirm")],
        [InlineKeyboardButton("❌ Batal", callback_data="cls_back")],
    ])


def _class_menu_keyboard(class_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 Masukkan Skema Baru", callback_data=f"cls_setskema|{class_id}")],
        [InlineKeyboardButton("📷 Semak Jawapan (Upload Gambar)", callback_data=f"cls_check|{class_id}")],
        [InlineKeyboardButton("📊 Jana Analisis Penuh", callback_data=f"cls_analysis|{class_id}")],
        [InlineKeyboardButton("🔙 Kembali ke Senarai Kelas", callback_data="cls_back")],
    ])


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.chat_data.clear()
    await update.message.reply_text(
        "Selamat datang ke Bot Semakan OMR!\n\n"
        "/kelas - Urus kelas (skema jawapan, semak jawapan, analisis)\n"
        "/generate - Jana borang OMR kosong (20 soalan)\n"
        "/reset - Reset semula perbualan/sesi bot"
    )


async def generate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Menjana borang OMR anda...")
    image_bytes = omr_generator.generate_omr_sheet()
    await update.message.reply_photo(
        photo=image_bytes,
        filename="borang_omr.png",
        caption=(
            "Ini borang OMR anda (20 soalan). Cetak & isi, atau isi terus di skrin.\n"
            "Pastikan ke-4 penanda hitam di penjuru kelihatan jelas semasa mengambil gambar nanti."
        ),
    )


async def kelas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.chat_data.pop("awaiting_new_class_name", None)
    context.chat_data.pop("awaiting_scheme_for_class", None)
    context.chat_data.pop("awaiting_check_for_class", None)

    chat_id = update.effective_chat.id
    classes = class_manager.list_classes(chat_id)
    text = "Senarai kelas anda:" if classes else "Belum ada kelas lagi. Tekan butang di bawah untuk tambah kelas."
    await update.message.reply_text(text, reply_markup=_class_list_keyboard(chat_id))


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.chat_data.clear()
    await update.message.reply_text(
        "Sesi/perbualan telah direset. (Kelas & skema jawapan yang telah disimpan masih dikekalkan - "
        "guna /kelas untuk teruskan.)"
    )


# ---------------------------------------------------------------------------
# Callback query handler - semua butang inline diproses di sini
# ---------------------------------------------------------------------------

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    data = query.data

    # ---- Reset Semua - minta pengesahan dahulu ----
    if data == "cls_reset_all":
        await query.edit_message_text(
            "⚠️ Adakah anda PASTI?\n\n"
            "Ini akan memadam SEMUA kelas, skema jawapan, dan analisis yang tersimpan "
            "bagi perbualan ini. Tindakan ini TIDAK BOLEH DIUNDUR.",
            reply_markup=_reset_all_confirm_keyboard(),
        )
        return

    # ---- Reset Semua - disahkan, laksanakan ----
    if data == "cls_reset_all_confirm":
        class_manager.delete_all_classes(chat_id)
        context.chat_data.clear()
        await query.edit_message_text(
            "🗑️ Semua kelas, skema, dan analisis telah dipadam. Mula semula dari sini.",
            reply_markup=_class_list_keyboard(chat_id),
        )
        return

    # ---- Kembali ke senarai kelas ----
    if data == "cls_back":
        context.chat_data.pop("awaiting_new_class_name", None)
        context.chat_data.pop("awaiting_scheme_for_class", None)
        context.chat_data.pop("awaiting_check_for_class", None)
        classes = class_manager.list_classes(chat_id)
        text = "Senarai kelas anda:" if classes else "Belum ada kelas lagi. Tekan butang di bawah untuk tambah kelas."
        await query.edit_message_text(text, reply_markup=_class_list_keyboard(chat_id))
        return

    # ---- Tambah kelas baharu ----
    if data == "cls_new":
        context.chat_data["awaiting_new_class_name"] = True
        await query.edit_message_text("Taip nama kelas baharu anda (contoh: 5 Bestari) dan hantar sebagai mesej.")
        return

    # ---- Pilih kelas sedia ada -> papar menu kelas ----
    if data.startswith("cls_sel|"):
        class_id = data.split("|", 1)[1]
        name = class_manager.get_class_name(chat_id, class_id)
        if not name:
            await query.edit_message_text("Kelas tidak dijumpai (mungkin telah dipadam).",
                                           reply_markup=_class_list_keyboard(chat_id))
            return
        scheme = class_manager.get_scheme(chat_id, class_id)
        status = "✅ Skema telah ditetapkan" if scheme else "⚠️ Skema belum ditetapkan"
        await query.edit_message_text(
            f"Kelas: {name}\n{status}\n\nSila pilih tindakan:",
            reply_markup=_class_menu_keyboard(class_id),
        )
        return

    # ---- Minta skema baharu untuk kelas ----
    if data.startswith("cls_setskema|"):
        class_id = data.split("|", 1)[1]
        name = class_manager.get_class_name(chat_id, class_id)
        if not name:
            await query.edit_message_text("Kelas tidak dijumpai.", reply_markup=_class_list_keyboard(chat_id))
            return
        context.chat_data["awaiting_scheme_for_class"] = class_id
        await query.edit_message_text(
            f"Kelas: {name}\n\nTaip skema jawapan (20 huruf, cth: ABCDABCDABCDABCDABCD) dan hantar sebagai mesej."
        )
        return

    # ---- Mula semakan (minta gambar) ----
    if data.startswith("cls_check|"):
        class_id = data.split("|", 1)[1]
        name = class_manager.get_class_name(chat_id, class_id)
        if not name:
            await query.edit_message_text("Kelas tidak dijumpai.", reply_markup=_class_list_keyboard(chat_id))
            return
        scheme = class_manager.get_scheme(chat_id, class_id)
        if not scheme:
            await query.edit_message_text(
                f"Kelas: {name}\n\nSkema jawapan belum ditetapkan. Sila 'Masukkan Skema Baru' dahulu.",
                reply_markup=_class_menu_keyboard(class_id),
            )
            return
        context.chat_data["awaiting_check_for_class"] = class_id
        await query.edit_message_text(
            f"Kelas: {name}\n\nSedia untuk semakan! Sila hantar/upload gambar borang OMR yang telah diisi sekarang.\n"
            "Bot akan terus menganalisis sebaik sahaja gambar diterima."
        )
        return

    # ---- Jana analisis penuh ----
    if data.startswith("cls_analysis|"):
        class_id = data.split("|", 1)[1]
        name = class_manager.get_class_name(chat_id, class_id)
        if not name:
            await query.edit_message_text("Kelas tidak dijumpai.", reply_markup=_class_list_keyboard(chat_id))
            return
        analysis = class_manager.get_analysis(chat_id, class_id)
        report = class_manager.format_analysis(name, analysis)
        await query.edit_message_text(report, reply_markup=_class_menu_keyboard(class_id))
        return


# ---------------------------------------------------------------------------
# Text handler - untuk input nama kelas baharu & skema (bukan arahan /)
# ---------------------------------------------------------------------------

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text or ""

    # ---- Sedang menunggu nama kelas baharu ----
    if context.chat_data.get("awaiting_new_class_name"):
        context.chat_data["awaiting_new_class_name"] = False
        try:
            class_id = class_manager.add_class(chat_id, text)
        except ValueError as e:
            context.chat_data["awaiting_new_class_name"] = True
            await update.message.reply_text(f"Ralat: {e}\nSila taip semula nama kelas.")
            return

        name = class_manager.get_class_name(chat_id, class_id)
        await update.message.reply_text(
            f"Kelas '{name}' berjaya ditambah!\n\nSila pilih tindakan:",
            reply_markup=_class_menu_keyboard(class_id),
        )
        return

    # ---- Sedang menunggu skema jawapan bagi satu kelas ----
    class_id = context.chat_data.get("awaiting_scheme_for_class")
    if class_id:
        context.chat_data["awaiting_scheme_for_class"] = None
        name = class_manager.get_class_name(chat_id, class_id) or "?"
        try:
            scheme = class_manager.set_scheme_from_string(chat_id, class_id, text)
        except ValueError as e:
            context.chat_data["awaiting_scheme_for_class"] = class_id
            await update.message.reply_text(f"Ralat: {e}\nSila taip semula skema.")
            return

        await update.message.reply_text(
            f"Skema jawapan kelas '{name}' berjaya disimpan:\n\n" + class_manager.format_scheme(scheme),
            reply_markup=_class_menu_keyboard(class_id),
        )
        return

    # ---- Tiada apa yang dijangka - beri panduan ----
    await update.message.reply_text("Guna /kelas untuk mula, atau /generate untuk jana borang OMR kosong.")


# ---------------------------------------------------------------------------
# Photo handler - inilah bahagian yang memproses imej SEPENUHNYA DALAM MEMORI
# ---------------------------------------------------------------------------

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    class_id = context.chat_data.get("awaiting_check_for_class")

    if not class_id:
        await update.message.reply_text("Guna /kelas -> pilih kelas -> 'Semak Jawapan' dahulu sebelum menghantar gambar.")
        return

    name = class_manager.get_class_name(chat_id, class_id)
    scheme = class_manager.get_scheme(chat_id, class_id)
    if not name or not scheme:
        await update.message.reply_text("Kelas atau skema tidak dijumpai. Guna /kelas untuk semak semula.")
        context.chat_data["awaiting_check_for_class"] = None
        return

    await update.message.reply_text(f"Menganalisis gambar bagi kelas '{name}'...")

    # Muat turun gambar terus ke memori (bytearray) - TIDAK ditulis ke cakera.
    # Cuba beberapa kali jika sambungan rangkaian terputus/timeout.
    photo = update.message.photo[-1]  # resolusi tertinggi yang tersedia
    tg_file = await photo.get_file()

    image_bytes = None
    last_error = None
    for attempt in range(3):
        try:
            image_bytes = bytes(await tg_file.download_as_bytearray())
            break
        except (TimedOut, NetworkError) as e:
            last_error = e
            logger.warning("Muat turun gambar gagal (percubaan %s/3): %s", attempt + 1, e)
            await asyncio.sleep(2)

    if image_bytes is None:
        await update.message.reply_text(
            "Gagal memuat turun gambar disebabkan masalah sambungan rangkaian selepas beberapa "
            "percubaan. Sila periksa sambungan internet anda dan cuba semula."
        )
        logger.error("Muat turun gambar gagal selepas 3 percubaan: %s", last_error)
        return

    # Gambar boleh dihantar berulang kali untuk kelas yang sama (tidak reset flag),
    # supaya guru boleh terus upload gambar seterusnya tanpa tekan butang semula.

    try:
        result, annotated_png = omr_scanner.scan_score_and_annotate(image_bytes, scheme)
    except omr_scanner.OMRScanError as e:
        await update.message.reply_text(
            f"Tidak dapat menganalisis gambar: {e}\n\nSila hantar semula gambar yang lebih jelas."
        )
        return
    finally:
        # Pastikan rujukan bait imej asal dilepaskan serta-merta.
        del image_bytes

    # Rekod jawapan yang dikesan untuk analisis A/B/C/D terkumpul bagi kelas ini.
    total_checked = class_manager.add_submission(chat_id, class_id, result["answers"])

    lines = [
        f"Kelas: {name}",
        f"Keputusan: {result['total']} / {result['max_score']}",
        "",
        "🟩 Hijau = Betul   🟥 Merah = Salah   🟨 Kuning = Kosong/Tidak Jelas",
    ]
    if result["wrong"]:
        lines.append(f"Salah (soalan): {', '.join(map(str, result['wrong']))}")
    if result["blank"]:
        lines.append(f"Tidak dijawab (soalan): {', '.join(map(str, result['blank']))}")
    if result["multiple"]:
        lines.append(f"Jawapan berganda/tidak jelas (soalan): {', '.join(map(str, result['multiple']))}")
    lines.append(f"\nJumlah gambar disemak untuk kelas ini setakat ini: {total_checked}")
    lines.append("Hantar gambar seterusnya untuk terus semak, atau guna /kelas untuk 'Jana Analisis Penuh'.")

    # Gambar bertanda dihantar terus daripada memori (annotated_png ialah bait PNG,
    # bukan fail pada cakera) kemudian rujukannya dilupuskan.
    await update.message.reply_photo(photo=annotated_png, filename="omr_ditanda.png")
    del annotated_png

    await update.message.reply_text("\n".join(lines))


# ---------------------------------------------------------------------------

def main():
    if BOT_TOKEN == "PUT_YOUR_TOKEN_HERE":
        raise SystemExit(
            "Sila tetapkan token bot Telegram anda dahulu.\n"
            "Cara 1: set environment variable TELEGRAM_BOT_TOKEN\n"
            "Cara 2: gantikan terus nilai BOT_TOKEN dalam bot.py\n"
            "Dapatkan token daripada @BotFather di Telegram."
        )

    # Had masa rangkaian dinaikkan daripada nilai lalai (biasanya 5s) supaya bot
    # tidak mudah 'TimedOut' semasa memuat turun/muat naik gambar pada sambungan
    # yang perlahan.
    request = HTTPXRequest(
        connect_timeout=20.0,
        read_timeout=60.0,
        write_timeout=60.0,
        pool_timeout=20.0,
    )
    get_updates_request = HTTPXRequest(
        connect_timeout=20.0,
        read_timeout=40.0,
        pool_timeout=20.0,
    )
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .request(request)
        .get_updates_request(get_updates_request)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("generate", generate))
    app.add_handler(CommandHandler("kelas", kelas))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("Bot sedang berjalan...")
    app.run_polling()


if __name__ == "__main__":
    main()