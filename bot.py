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
        return  # Server console logs clean rakhne ke liye

def start_http_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleHealthHandler)
    server.serve_forever()

# Render ke port scan timeout ko bypass karne ke liye daemon thread me start karein
threading.Thread(target=start_http_server, daemon=True).start()

# ==============================================================================
# 2. API KEYS CONFIGURATION
# ==============================================================================
# Yahan apni dono keys double quotes ke andar paste karein:
TELEGRAM_BOT_TOKEN = "PASTE_YOUR_TELEGRAM_BOT_TOKEN_HERE"
GEMINI_API_KEY = "PASTE_YOUR_GEMINI_API_KEY_HERE"

# Bot Initialise
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

# Gemini AI Initialise (Safe block taaki initialization par crash na ho)
gemini_model = None
try:
    import google.generativeai as genai
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel("gemini-1.5-flash")
    print("Gemini API successfully configured.")
except Exception as error:
    print(f"Gemini Init Notice: {error}")

# ==============================================================================
# 3. TELEGRAM BOT HANDLERS
# ==============================================================================
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = (
        "Namaste!\n\n"
        "Sunil Rakhi automation bot successfully active ho gaya hai.\n"
        "Aap mujhe kisi bhi product, packet ya box label ki photo bhej sakte hain."
    )
    bot.reply_to(message, welcome_text)

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    if not gemini_model:
        bot.reply_to(message, "Gemini API key configure nahi hui hai. Kripya key verify karein.")
        return

    try:
        bot.reply_to(message, "Photo mil gayi hai! Gemini AI se analyze ho raha hai, kripya wait karein...")

        # Highest resolution photo download karein
        file_id = message.photo[-1].file_id
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        # Image load karein
        image = Image.open(io.BytesIO(downloaded_file))

        prompt = (
            "Analyze this product/rakhi packaging image carefully. "
            "Extract: Art No, Packet Quantity, Box Quantity, Rate, and Color. "
            "Format the output cleanly line by line."
        )

        response = gemini_model.generate_content([prompt, image])
        bot.reply_to(message, response.text if response.text else "Koi readable details detect nahi hui.")

    except Exception as e:
        bot.reply_to(message, f"Photo process karne me error aayi: {str(e)}")

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    if not gemini_model:
        bot.reply_to(message, f"Message received: {message.text}")
        return

    try:
        response = gemini_model.generate_content(message.text)
        bot.reply_to(message, response.text)
    except Exception as e:
        bot.reply_to(message, f"Error: {str(e)}")

# ==============================================================================
# 4. BOT POLLING (SABSE LAST)
# ==============================================================================
if __name__ == "__main__":
    print("Bot polling started successfully...")
    bot.infinity_polling(timeout=60, long_polling_timeout=30)
