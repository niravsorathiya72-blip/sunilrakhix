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
TELEGRAM_BOT_TOKEN = "8934435754:AAHxFWaP4d4cUAlN4DviFpHMrka1hJo5V4w"
GEMINI_API_KEY = "AQ.Ab8RN6KXlej5SMT9p1NyeeyAbtAC-Sf33hwNG9y9TdiDdHpadg"

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

gemini_model = None
try:
    import google.generativeai as genai
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel("gemini-1.5-flash")
    print("Gemini API configured successfully.")
except Exception as error:
    print(f"Gemini Init Warning: {error}")

# ==============================================================================
# 3. TELEGRAM BOT HANDLERS
# ==============================================================================
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = (
        "Namaste!\n\n"
        "SUNILRAKHIEXCEL Bot khaddam db b-najah.\n"
        "Sift lia ay soura dyal product ola label bach t-t-analyse b Gemini."
    )
    bot.reply_to(message, welcome_text)

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    if not gemini_model:
        bot.reply_to(message, "Gemini API key ma khaddamax mezian. Khellik m3ana.")
        return

    try:
        bot.reply_to(message, "Waslat l-photo! Gemini kay-analyse l-ma3loumat db, sber chwya...")

        file_id = message.photo[-1].file_id
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        image = Image.open(io.BytesIO(downloaded_file))

        prompt = (
            "Analyze this product/rakhi packaging image carefully. "
            "Extract: Art No, Packet Quantity, Box Quantity, Rate, and Color. "
            "Format the output cleanly line by line."
        )

        response = gemini_model.generate_content([prompt, image])
        bot.reply_to(message, response.text if response.text else "Ma lqina hta chi ma3loumat f l-photo.")

    except Exception as e:
        bot.reply_to(message, f"Mochkil f l-processing: {str(e)}")

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    if not gemini_model:
        bot.reply_to(message, f"Wselli l-message: {message.text}")
        return

    try:
        response = gemini_model.generate_content(message.text)
        bot.reply_to(message, response.text)
    except Exception as e:
        bot.reply_to(message, f"Mochkil: {str(e)}")

# ==============================================================================
# 4. BOT POLLING
# ==============================================================================
if __name__ == "__main__":
    print("Bot polling started...")
    bot.infinity_polling(timeout=60, long_polling_timeout=30)
