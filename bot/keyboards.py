from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from bot.config import MINI_APP_URL


def main_menu_keyboard(game_id: str | None = None) -> InlineKeyboardMarkup:
    """کیبورد اصلی. اگر game_id داده شود، دکمه اول مستقیم به همان بازی داخل Mini App لینک می‌شود."""
    webapp_url = MINI_APP_URL
    if game_id:
        webapp_url = f"{MINI_APP_URL}?game_id={game_id}"

    buttons = [
        [InlineKeyboardButton("🎮 ورود به BEHI PLAY", web_app=WebAppInfo(url=webapp_url))],
        [
            InlineKeyboardButton("🏆 مسابقات", callback_data="menu_competitions"),
            InlineKeyboardButton("👤 پروفایل من", callback_data="menu_profile"),
        ],
        [InlineKeyboardButton("❓ راهنما", callback_data="menu_help")],
    ]
    return InlineKeyboardMarkup(buttons)


def join_game_keyboard(game_id: str) -> InlineKeyboardMarkup:
    url = f"{MINI_APP_URL}?game_id={game_id}"
    buttons = [[InlineKeyboardButton("🎮 ورود به بازی", web_app=WebAppInfo(url=url))]]
    return InlineKeyboardMarkup(buttons)
