import logging
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler

from bot.config import TELEGRAM_BOT_TOKEN
from bot import handlers
from bot.keepalive import start_keepalive_server

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)


def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", handlers.start_command))
    app.add_handler(CommandHandler("play", handlers.play_command))
    app.add_handler(CommandHandler("profile", handlers.profile_command))
    app.add_handler(CommandHandler("rank", handlers.rank_command))
    app.add_handler(CommandHandler("help", handlers.help_command))
    app.add_handler(CallbackQueryHandler(handlers.button_callback))

    logging.info("BEHI PLAY bot is starting (polling mode)...")
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    mainstart_keepalive_server()
