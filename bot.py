import io
import os
import json
import base64
import threading
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
import pandas as pd
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# --- API KEYS SETUP ---
TELEGRAM_BOT_TOKEN = "8806559022:AAG33EUsuXzHsrVrOPeVNvbE-C08ePW6CZQ"
GEMINI_API_KEY = "AQ.Ab8RN6KKLgE7oJ8FHJ-FS4dG8mzcviJPQtLnXxUJjKnXfQOBTw"

# Web port server Render free tier ko live rakhne ke liye
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"OK")
    def log_message(self, format, *args):
        pass

def start_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    server.serve_forever()

threading.Thread(target=start_server, daemon=True).start()

user_mode = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_mode[chat_id] = "packet"
    welcome_text = (
        "Namaste! 🙏\n"
        "Photo bhejkar Excel data banane wala bot ready hai.\n\n"
        "Mode chunane ke liye:\n"
        "• /packet - ART_NO | COLOR | PACKET_QTY | QTY_BOX | RATE\n"
        "• /dabba  - ART_NO | COLOR | PACKET_QTY | RATE\n\n"
        "Abhi Packet Sheet mode set hai. Kripya photo bhejein!"
    )
    await update.message.reply_text(welcome_text)

async def set_packet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_mode[update.effective_chat.id] = "packet"
    await update.message.reply_text("✅ Packet Sheet Mode set ho gaya!\nColumns: ART_NO | COLOR | PACKET_QTY | QTY_BOX | RATE")

async def set_dabba(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_mode[update.effective_chat.id] = "dabba"
    await update.message.reply_text("✅ Dabba Sheet Mode set ho gaya!\nColumns: ART_NO | COLOR | PACKET_QTY | RATE")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    mode = user_mode.get(chat_id, "packet")

    status_msg = await update.message.reply_text("⏳ Photo scan ho rahi hai, kripya thoda intezar karein...")

    try:
        photo_file = await update.message.photo[-1].get_file()
        image_bytes = await photo_file.download_as_bytearray()
        img_b64 = base64.b64encode(image_bytes).decode("utf-8")

        if mode == "packet":
            cols = ["ART_NO", "COLOR", "PACKET_QTY", "QTY_BOX", "RATE"]
            rules = (
                "Extract rows with exact columns: ART_NO, COLOR, PACKET_QTY, QTY_BOX, RATE.\n"
                "- If quantity is written like '2 x 144' or '2 * 144', PACKET_QTY is 2 and QTY_BOX is 144.\n"
                "- If single qty like '144' is given, put 1 in PACKET_QTY and 144 in QTY_BOX.\n"
                "- If color is not specified, write '-'."
            )
        else:
            cols = ["ART_NO", "COLOR", "PACKET_QTY", "RATE"]
            rules = (
                "Extract rows with exact columns: ART_NO, COLOR, PACKET_QTY, RATE.\n"
                "- If quantity is written like '2 x 144', PACKET_QTY is 2.\n"
                "- If color is not specified, write '-'."
            )

        prompt = f"""
        Extract tabular invoice data from this image:
        {rules}
        Format output strictly as Tab Separated Values (TSV).
        Header line must be: {'\t'.join(cols)}
        Do NOT enclose in markdown or code blocks.
        If any row has blur or unclear numbers/rates, mark as 'UNCLEAR' and append a line starting with 'DOUBT: details'.
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

        res = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=60)
        res_data = res.json()

        if "error" in res_data:
            err_msg = res_data["error"].get("message", "Unknown error")
            await status_msg.edit_text(f"❌ API Error: {err_msg}")
            return

        out_text = res_data["candidates"][0]["content"]["parts"][0]["text"].strip()
        
        lines = [l.strip() for l in out_text.splitlines() if l.strip()]
        doubts = []
        tsv_rows = []

        for line in lines:
            if line.startswith("DOUBT:"):
                doubts.append(line.replace("DOUBT:", "").strip())
            else:
                tsv_rows.append(line)

        clean_tsv = "\n".join(tsv_rows)
        df = pd.read_csv(io.StringIO(clean_tsv), sep='\t')

        excel_buf = io.BytesIO()
        with pd.ExcelWriter(excel_buf, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name=f"{mode.capitalize()}")
        excel_buf.seek(0)

        await status_msg.delete()

        # Copy-Paste Text bhejein
        await update.message.reply_text(f"📋 **Excel Copy-Paste Text ({mode.upper()}):**\n\n```\n{clean_tsv}\n```", parse_mode="Markdown")

        # Excel File bhejein
        await update.message.reply_document(
            document=excel_buf,
            filename=f"SunilRakhi_{mode.capitalize()}.xlsx",
            caption=f"📊 {mode.capitalize()} Excel Sheet Ready!"
        )

        if doubts:
            doubt_text = "⚠️ **Handwriting Doubt:**\n" + "\n".join([f"• {d}" for d in doubts])
            await update.message.reply_text(doubt_text, parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"❌ Error aayi: {str(e)}")

def main():
    app = (
        ApplicationBuilder()
        .token(TELEGRAM_BOT_TOKEN)
        .connect_timeout(30.0)
        .read_timeout(30.0)
        .write_timeout(30.0)
        .pool_timeout(30.0)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("packet", set_packet))
    app.add_handler(CommandHandler("dabba", set_dabba))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    print("Bot polling started...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
