import io
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import pandas as pd
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from google import genai
from google.genai import types

# --- API KEYS SETUP ---
TELEGRAM_BOT_TOKEN = "8806559022:AAG33EUsuXzHsrVrOPeVNvbE-CO8ePW6CZQ"
GEMINI_API_KEY = "AQ.Ab8RN6ICDLbODPXFTjhbP6EfgEM6ELLCpnsjyRAZ1KmcAAWWcw"

# Dummy Web Server (Render free web service ko 24 ghante Live rakhne ke liye)
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b"Bot is Running Perfectly!")

def run_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), SimpleHandler)
    server.serve_forever()

# Client initialize
ai_client = genai.Client(api_key=GEMINI_API_KEY)
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

async def set_packet_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_mode[update.effective_chat.id] = "packet"
    await update.message.reply_text("✅ Packet Sheet Mode set ho gaya hai!\nColumns: ART_NO | COLOR | PACKET_QTY | QTY_BOX | RATE")

async def set_dabba_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_mode[update.effective_chat.id] = "dabba"
    await update.message.reply_text("✅ Dabba Sheet Mode set ho gaya hai!\nColumns: ART_NO | COLOR | PACKET_QTY | RATE")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    mode = user_mode.get(chat_id, "packet")
    
    await update.message.reply_text("⏳ Photo scan ho rahi hai, kripya intezar karein...")

    try:
        photo_file = await update.message.photo[-1].get_file()
        image_bytes = await photo_file.download_as_bytearray()

        if mode == "packet":
            cols = ["ART_NO", "COLOR", "PACKET_QTY", "QTY_BOX", "RATE"]
            rule_desc = (
                "Extract rows with exact columns: ART_NO, COLOR, PACKET_QTY, QTY_BOX, RATE.\n"
                "- If quantity is written like '2 x 144' or '2 * 144', PACKET_QTY is 2 and QTY_BOX is 144.\n"
                "- If only single qty is given (e.g. 144), put it in QTY_BOX and put 1 in PACKET_QTY.\n"
                "- If color is not specified, leave COLOR as '-'.\n"
            )
        else:
            cols = ["ART_NO", "COLOR", "PACKET_QTY", "RATE"]
            rule_desc = (
                "Extract rows with exact columns: ART_NO, COLOR, PACKET_QTY, RATE.\n"
                "- If quantity is written like '2 x 144', take packet count (2) as PACKET_QTY.\n"
                "- If color is not specified, leave COLOR as '-'.\n"
            )

        prompt = f"""
        You are an expert at reading handwritten bills and printed invoices.
        Extract all items from this image following these instructions:
        {rule_desc}

        CRITICAL RULES:
        1. If any handwritten number, art number, or rate is blur or unclear, mark that specific field as 'UNCLEAR'.
        2. Output format must strictly be TSV (Tab Separated Values) text only.
        3. The first line must be headers: {'\t'.join(cols)}
        4. Do not enclose the output in code blocks or add markdown intros. Just raw TSV lines.
        5. If there are unclear entries, add a line starting with 'DOUBT:' at the bottom explaining which line has doubt.
        """

        response = ai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[
                types.Part.from_bytes(data=bytes(image_bytes), mime_type="image/jpeg"),
                prompt
            ]
        )
        
        result_text = response.text.strip()
        doubts = []
        tsv_lines = []
        for line in result_text.splitlines():
            if line.startswith("DOUBT:"):
                doubts.append(line.replace("DOUBT:", "").strip())
            elif "UNCLEAR" in line or "?" in line:
                tsv_lines.append(line)
                doubts.append(f"Unclear entry detect hui: {line}")
            else:
                tsv_lines.append(line)

        clean_tsv = "\n".join(tsv_lines)
        df = pd.read_csv(io.StringIO(clean_tsv), sep='\t')

        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name=f"{mode.capitalize()}_Sheet")
        excel_buffer.seek(0)

        # Copy-Paste Text
        copy_text = f"📋 Excel Copy-Paste Text ({mode.upper()}):\n\n```\n{clean_tsv}\n```"
        await update.message.reply_text(copy_text, parse_mode="Markdown")

        # Excel File
        await update.message.reply_document(
            document=excel_buffer,
            filename=f"Order_{mode.capitalize()}_Data.xlsx",
            caption=f"📊 Aapki {mode.capitalize()} Sheet ready hai!"
        )

        if doubts:
            doubt_msg = "⚠️ Dhyan dein! Kuch data me doubt hai, kripya check karein:\n"
            for d in doubts:
                doubt_msg += f"• {d}\n"
            await update.message.reply_text(doubt_msg)

    except Exception as e:
        await update.message.reply_text(f"❌ Error aayi: {str(e)}\nKripya saaf photo dobara bhejein.")

def main():
    threading.Thread(target=run_server, daemon=True).start()
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("packet", set_packet_mode))
    app.add_handler(CommandHandler("dabba", set_dabba_mode))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.run_polling()

if __name__ == "__main__":
    main()
