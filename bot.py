import io
import os
import asyncio
import base64
import requests
import pandas as pd
from aiohttp import web
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# --- CREDENTIALS ---
TELEGRAM_BOT_TOKEN = "8806559022:AAG33EUsuXzHsrVrOPeVNvbE-C08ePW6CZQ"
GEMINI_API_KEY = "AQ.Ab8RN6KKLgE7oJ8FHJ-FS4dG8mzcviJPQtLnXxUJjKnXfQOBTw"

user_mode = {}

# Render Port Health Check
async def handle_ping(request):
    return web.Response(text="Bot is running!")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_mode[chat_id] = "packet"
    msg = (
        "Namaste! 🙏\n"
        "Photo bhejkar Excel data banane wala bot ready hai.\n\n"
        "Mode:\n"
        "• /packet - ART_NO | COLOR | PACKET_QTY | QTY_BOX | RATE\n"
        "• /dabba  - ART_NO | COLOR | PACKET_QTY | RATE\n\n"
        "Abhi Packet Mode set hai. Photo bhejiye!"
    )
    await update.message.reply_text(msg)

async def set_packet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_mode[update.effective_chat.id] = "packet"
    await update.message.reply_text("✅ Packet Sheet Mode set ho gaya!\nColumns: ART_NO | COLOR | PACKET_QTY | QTY_BOX | RATE")

async def set_dabba(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_mode[update.effective_chat.id] = "dabba"
    await update.message.reply_text("✅ Dabba Sheet Mode set ho gaya!\nColumns: ART_NO | COLOR | PACKET_QTY | RATE")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    mode = user_mode.get(chat_id, "packet")
    status_msg = await update.message.reply_text("⏳ Photo scan ho rahi hai, kripya intezar karein...")

    try:
        photo_file = await update.message.photo[-1].get_file()
        img_bytes = await photo_file.download_as_bytearray()
        img_b64 = base64.b64encode(img_bytes).decode("utf-8")

        if mode == "packet":
            cols = ["ART_NO", "COLOR", "PACKET_QTY", "QTY_BOX", "RATE"]
            rules = (
                "Extract rows with exact columns: ART_NO, COLOR, PACKET_QTY, QTY_BOX, RATE.\n"
                "- If qty is written like '2 x 144' or '2 * 144', PACKET_QTY is 2 and QTY_BOX is 144.\n"
                "- If single qty like '144' is given, put 1 in PACKET_QTY and 144 in QTY_BOX.\n"
                "- If color is missing, put '-'."
            )
        else:
            cols = ["ART_NO", "COLOR", "PACKET_QTY", "RATE"]
            rules = (
                "Extract rows with exact columns: ART_NO, COLOR, PACKET_QTY, RATE.\n"
                "- If qty is written like '2 x 144', take packet count (2) as PACKET_QTY.\n"
                "- If color is missing, put '-'."
            )

        prompt = f"""
        Extract tabular invoice data from this image:
        {rules}
        Output format: strictly TSV (Tab Separated Values) text only.
        First line headers: {'\t'.join(cols)}
        No markdown code fences. Just clean rows.
        If handwriting is unclear/blur, put 'UNCLEAR' in that column and append a line starting with 'DOUBT: details'.
        """

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
        payload = {
            "contents": [{
                "parts": [
                    {"text": prompt},
                    {"inlineData": {"mimeType": "image/jpeg", "data": img_b64}}
                ]
            }]
        }

        loop = asyncio.get_running_loop()
        res = await loop.run_in_executor(None, lambda: requests.post(url, json=payload, timeout=60))
        res_data = res.json()

        if "error" in res_data:
            err = res_data["error"].get("message", "API Error")
            await status_msg.edit_text(f"❌ Error: {err}")
            return

        out_text = res_data["candidates"][0]["content"]["parts"][0]["text"].strip()
        lines = [l.strip() for l in out_text.splitlines() if l.strip()]
        
        doubts = []
        tsv_rows = []
        for l in lines:
            if l.startswith("DOUBT:"):
                doubts.append(l.replace("DOUBT:", "").strip())
            else:
                tsv_rows.append(l)

        clean_tsv = "\n".join(tsv_rows)
        df = pd.read_csv(io.StringIO(clean_tsv), sep='\t')

        excel_buf = io.BytesIO()
        with pd.ExcelWriter(excel_buf, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name=f"{mode.capitalize()}")
        excel_buf.seek(0)

        await status_msg.delete()

        # Copy-Paste text
        await update.message.reply_text(f"📋 **Copy-Paste Text ({mode.upper()}):**\n\n```\n{clean_tsv}\n```", parse_mode="Markdown")

        # Excel file
        await update.message.reply_document(
            document=excel_buf,
            filename=f"Data_{mode.capitalize()}.xlsx",
            caption=f"📊 {mode.capitalize()} Excel Ready!"
        )

        if doubts:
            doubt_text = "⚠️ **Handwriting Doubt:**\n" + "\n".join([f"• {d}" for d in doubts])
            await update.message.reply_text(doubt_text, parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"❌ Error aayi: {str(e)}")

async def main():
    port = int(os.environ.get("PORT", 8080))
    app_web = web.Application()
    app_web.router.add_get('/', handle_ping)
    runner = web.AppRunner(app_web)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

    tg_app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    tg_app.add_handler(CommandHandler("start", start))
    tg_app.add_handler(CommandHandler("packet", set_packet))
    tg_app.add_handler(CommandHandler("dabba", set_dabba))
    tg_app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    await tg_app.initialize()
    await tg_app.start()
    await tg_app.updater.start_polling(drop_pending_updates=True)

    # Keep alive
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
