git add bot.py
git commit -m "Add dummy port server for render"
git push origin main
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# Render માટે ડમી વેબ સર્વર
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

    def log_message(self, format, *args):
        return  # બિનજરૂરી લોગ બંધ રાખવા માટે

def run_web_server():
    # Render આપોઆપ PORT એન્વાયર્નમેન્ટ વેરીએબલ આપે છે
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

# બોટ ચાલુ થાય એ પહેલાં બેકગ્રાઉન્ડ થ્રેડમાં સર્વર સ્ટાર્ટ થશે
threading.Thread(target=run_web_server, daemon=True).start()
import io
import json
import base64
import requests
import pandas as pd
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

TELEGRAM_BOT_TOKEN = "8806559022:AAG33EUsuXzHsrVrOPeVNvbE-C08ePW6CZQ"
GEMINI_API_KEY = "AQ.Ab8RN6KKLgE7oJ8FHJ-FS4dG8mzcviJPQtLnXxUJjKnXfQOBTw"

user_mode = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_mode[update.effective_chat.id] = "packet"
    await update.message.reply_text(
        "Namaste! 🙏\n"
        "Photo bhejkar Excel data banane wala bot ready hai.\n\n"
        "Commands:\n"
        "• /packet - ART_NO | COLOR | PACKET_QTY | QTY_BOX | RATE\n"
        "• /dabba  - ART_NO | COLOR | PACKET_QTY | RATE\n\n"
        "Abhi Packet Sheet mode set hai. Parchi ki photo bhejein!"
    )

async def set_packet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_mode[update.effective_chat.id] = "packet"
    await update.message.reply_text("✅ Packet Mode set ho gaya!\nColumns: ART_NO | COLOR | PACKET_QTY | QTY_BOX | RATE")

async def set_dabba(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_mode[update.effective_chat.id] = "dabba"
    await update.message.reply_text("✅ Dabba Mode set ho gaya!\nColumns: ART_NO | COLOR | PACKET_QTY | RATE")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mode = user_mode.get(update.effective_chat.id, "packet")
    status_msg = await update.message.reply_text("⏳ Photo scan ho rahi hai, kripya intezar karein...")

    try:
        photo_file = await update.message.photo[-1].get_file()
        img_bytes = await photo_file.download_as_bytearray()
        img_b64 = base64.b64encode(img_bytes).decode("utf-8")

        if mode == "packet":
            cols = ["ART_NO", "COLOR", "PACKET_QTY", "QTY_BOX", "RATE"]
            rules = (
                "Extract rows with exact columns: ART_NO, COLOR, PACKET_QTY, QTY_BOX, RATE.\n"
                "- If quantity is written like '2 x 144' or '2 * 144', PACKET_QTY is 2 and QTY_BOX is 144.\n"
                "- If single qty like '144' is given, put 1 in PACKET_QTY and 144 in QTY_BOX.\n"
                "- If color is missing, put '-'."
            )
        else:
            cols = ["ART_NO", "COLOR", "PACKET_QTY", "RATE"]
            rules = (
                "Extract rows with exact columns: ART_NO, COLOR, PACKET_QTY, RATE.\n"
                "- If quantity is written like '2 x 144', take packet count (2) as PACKET_QTY.\n"
                "- If color is missing, put '-'."
            )

        prompt = f"""
        Extract tabular invoice data from this image:
        {rules}
        Output format: strictly TSV (Tab Separated Values) text only.
        First line headers: {'\t'.join(cols)}
        Do NOT enclose in markdown backticks or explanations. Just pure TSV rows.
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

        res = requests.post(url, json=payload, timeout=60)
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

        await update.message.reply_text(f"📋 **Copy-Paste Text ({mode.upper()}):**\n\n```\n{clean_tsv}\n```", parse_mode="Markdown")

        await update.message.reply_document(
            document=excel_buf,
            filename=f"SunilRakhi_{mode.capitalize()}.xlsx",
            caption=f"📊 {mode.capitalize()} Excel Sheet Ready!"
        )

        if doubts:
            doubt_text = "⚠️ **Handwriting Doubt:**\n" + "\n".join([f"• {d}" for d in doubts])
            await update.message.reply_text(doubt_text, parse_mode="Markdown")

    except Exception as e:
        await status_msg.edit_text(f"❌ Error: {str(e)}")

def main():
    app = (
        ApplicationBuilder()
        .token(TELEGRAM_BOT_TOKEN)
        .connect_timeout(60.0)
        .read_timeout(60.0)
        .write_timeout(60.0)
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
