import os
import io
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from PIL import Image
import google.generativeai as genai

# =========================================================
# 1. RENDER PORT BINDING (DUMMY WEB SERVER)
# =========================================================
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is alive and healthy!")

    def log_message(self, format, *args):
        return  # Server access logs band rakhne ke liye

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

# Server ko background thread me start karein
threading.Thread(target=run_web_server, daemon=True).start()

# =========================================================
# 2. API KEYS CONFIGURATION
# =========================================================
# Render Environment Variables se keys lega, agar waha nahi hai to direct quote me daal sakte hain
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "YAHAN_APNA_TELEGRAM_BOT_TOKEN_DAALEIN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "YAHAN_APNA_GEMINI_API_KEY_DAALEIN")

# Bot aur Gemini setup
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel("gemini-1.5-flash")

# =========================================================
# 3. TELEGRAM BOT HANDLERS
# =========================================================
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = (
        "Namaste!\n\n"
        "Ye bot Sunil Rakhi Excel automation ke liye active hai.\n"
        "Aap mujhe koi bhi product ya details ki photo bhej sakte hain."
    )
    bot.reply_to(message, welcome_text)

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    try:
        bot.reply_to(message, "Photo mil gayi hai! Gemini AI se data analyze ho raha hai, kripya thoda intezar karein...")

        # Photo download karein
        file_id = message.photo[-1].file_id
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        # Image ko memory me open karein
        image = Image.open(io.BytesIO(downloaded_file))

        # Gemini Prompt
        prompt = (
            "Analyze this product label/rakhi image carefully. "
            "Extract all relevant details like Art Number, Quantity (Packet/Box), Rate, and Color. "
            "Present the extracted data clearly in structured text or table format."
        )

        # Gemini response generate karein
        response = gemini_model.generate_content([prompt, image])
        
        if response.text:
            bot.reply_to(message, response.text)
        else:
            bot.reply_to(message, "Gemini koi data extract nahi kar paya. Kripya clear photo bhejein.")

    except Exception as e:
        bot.reply_to(message, f"Error aayi: {str(e)}")

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    try:
        # Normal text message ke liye Gemini reply
        response = gemini_model.generate_content(message.text)
        bot.reply_to(message, response.text)
    except Exception as e:
        bot.reply_to(message, f"Error: {str(e)}")

# =========================================================
# 4. BOT POLLING (SABSE AAKHRI LINE)
# =========================================================
if __name__ == "__main__":
    print("Bot polling started...")
    bot.infinity_polling(timeout=60, long_polling_timeout=30)
