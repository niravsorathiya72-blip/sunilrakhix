import os
import io
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from PIL import Image

# ==============================================================================
# 1. RENDER PORT BINDING (HTTP HEALTH CHECK SERVER)
# ==============================================================================
class SimpleHealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Bot service is healthy and active!")

    def log_message(self, format, *args):
        return

def start_http_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleHealthHandler)
    server.serve_forever()

threading.Thread(target=start_http_server, daemon=True).start()

# ==============================================================================
# 2. BOT & GEMINI API CONFIGURATION
# ==============================================================================
TELEGRAM_BOT_TOKEN = "8806559022:AAG33EUsuXzHsrVrOPevNvbE-C08ePw6CZQ"
GEMINI_API_KEY = "AQ.Ab8RN6KXlej5SMT9p1NyeeyAbtAC-Sf33hwNG9y9TdiDdHpadg"

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

gemini_model = None
try:
    import google.generativeai as genai
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel("gemini-1.5-flash")
    print("Gemini API successfully configured.")
except Exception as error:
    print(f"Gemini Init Warning: {error}")

# ==============================================================================
# 3. TELEGRAM BOT HANDLERS (GUJARATI + HINDI + ENGLISH)
# ==============================================================================
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = (
        "🙏 **Namaste / નમસ્તે!**\n\n"
        "**SUNILRAKHIEXCEL Bot** is ready.\n\n"
        "🔹 **English:** Please send a clear photo of the product, label, or packet.\n"
        "🔹 **ગુજરાતી:** કૃપા કરીને પ્રોડક્ટ, પેકેટ અથવા બોક્સ લેબલનો સ્પષ્ટ ફોટો મોકલો.\n"
        "🔹 **हिंदी:** कृपया प्रोडक्ट, पैकेट या बॉक्स लेबल का साफ़ फोटो भेजें."
    )
    bot.reply_to(message, welcome_text, parse_mode="Markdown")

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    wait_msg = (
        "⏳ **Processing...**\n"
        "• Photo received! Analyzing details...\n"
        "• ફોટો મળી ગયો છે! વિગતો ચકાસાઈ રહી છે...\n"
        "• फोटो मिल गया है! डिटेल्स चेक हो रही हैं..."
    )
    bot.reply_to(message, wait_msg, parse_mode="Markdown")

    if not gemini_model:
        bot.reply_to(message, "⚠️ API Configuration error. Please check Gemini API Key.")
        return

    try:
        file_id = message.photo[-1].file_id
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        image = Image.open(io.BytesIO(downloaded_file))

        prompt = (
            "Analyze this product/rakhi packaging image carefully. "
            "Extract the following details accurately:\n"
            "- Art No / Code\n"
            "- Packet Quantity\n"
            "- Box Quantity\n"
            "- Rate / Price\n"
            "- Color / Design\n\n"
            "Provide the extracted output in clean text with Gujarati, Hindi, and English labels so it is very easy to read."
        )

        response = gemini_model.generate_content([prompt, image])
        bot.reply_to(message, response.text if response.text else "Details detect kavaledu / વિગતો મળી નથી.")

    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    if not gemini_model:
        bot.reply_to(message, f"Received: {message.text}")
        return

    try:
        response = gemini_model.generate_content(message.text)
        bot.reply_to(message, response.text)
    except Exception as e:
        bot.reply_to(message, f"Error: {str(e)}")

# ==============================================================================
# 4. BOT POLLING
# ==============================================================================
if __name__ == "__main__":
    print("Bot polling started...")
    bot.infinity_polling(timeout=60, long_polling_timeout=30)
