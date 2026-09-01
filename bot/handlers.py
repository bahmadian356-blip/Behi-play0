import logging
from telegram import Update
from telegram.ext import ContextTypes

from bot.keyboards import main_menu_keyboard, join_game_keyboard
from bot.supabase_client import (
    get_or_create_profile,
    get_profile_by_telegram_id,
    get_user_rank,
    get_game_by_id,
)

logger = logging.getLogger(__name__)

WELCOME_TEXT = (
    "🎮 *به BEHI PLAY خوش اومدی!*\n\n"
    "اینجا می‌تونی بازی بسازی، دوستاتو دعوت کنی، مسابقه بدی و "
    "با کسب XP سطح خودتو بالا ببری.\n\n"
    "برای شروع، دکمه *ورود به BEHI PLAY* رو بزن 👇"
)

HELP_TEXT = (
    "❓ *راهنمای BEHI PLAY*\n\n"
    "/start – شروع و نمایش منوی اصلی\n"
    "/play – ورود مستقیم به Mini App\n"
    "/profile – نمایش خلاصه پروفایل تو\n"
    "/rank – نمایش رتبه‌ی تو در رتبه‌بندی\n"
    "/help – همین راهنما\n\n"
    "برای دعوت دوستان، داخل Mini App یک اتاق بساز و لینک اختصاصی رو براشون بفرست."
)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    profile = get_or_create_profile(user)

    # پردازش Deep Link مثل: /start game_GAME_ID
    args = context.args
    if args and args[0].startswith("game_"):
        game_id = args[0].replace("game_", "", 1)
        game = get_game_by_id(game_id)
        if game:
            await update.message.reply_text(
                f"🎉 شما به بازی *{game.get('name', 'بدون نام')}* دعوت شدید!\n"
                "برای ورود به اتاق دکمه زیر رو بزن:",
                parse_mode="Markdown",
                reply_markup=join_game_keyboard(game_id),
            )
            return
        else:
            await update.message.reply_text(
                "⚠️ این بازی پیدا نشد یا منقضی شده. از منوی اصلی یک بازی جدید بساز."
            )

    await update.message.reply_text(
        WELCOME_TEXT, parse_mode="Markdown", reply_markup=main_menu_keyboard()
    )


async def play_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "برای بازی کردن، وارد Mini App شو 👇", reply_markup=main_menu_keyboard()
    )


async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    profile = get_profile_by_telegram_id(user.id) or get_or_create_profile(user)

    text = (
        f"👤 *پروفایل {profile.get('first_name') or user.first_name}*\n\n"
        f"🏷 یوزرنیم: @{profile.get('username') or 'ندارد'}\n"
        f"⭐ Level: {profile.get('level', 1)}\n"
        f"✨ XP: {profile.get('xp', 0)}\n"
        f"🎮 بازی‌ها: {profile.get('games_played', 0)}\n"
        f"🏆 برد: {profile.get('wins', 0)}\n"
        f"❌ باخت: {profile.get('losses', 0)}\n"
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_menu_keyboard())


async def rank_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    rank = get_user_rank(user.id)
    if rank is None:
        get_or_create_profile(user)
        rank = get_user_rank(user.id)

    await update.message.reply_text(f"📊 رتبه‌ی فعلی تو: *#{rank}*", parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT, parse_mode="Markdown")


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "menu_profile":
        await profile_command_from_callback(update, context)
    elif query.data == "menu_help":
        await query.message.reply_text(HELP_TEXT, parse_mode="Markdown")
    elif query.data == "menu_competitions":
        await query.message.reply_text(
            "برای ساخت یا پیوستن به یک مسابقه، وارد Mini App شو و بخش «مسابقه با دوستان» رو باز کن.",
            reply_markup=main_menu_keyboard(),
        )


async def profile_command_from_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    profile = get_profile_by_telegram_id(user.id) or get_or_create_profile(user)
    text = (
        f"👤 *پروفایل {profile.get('first_name') or user.first_name}*\n\n"
        f"⭐ Level: {profile.get('level', 1)}\n"
        f"✨ XP: {profile.get('xp', 0)}\n"
        f"🎮 بازی‌ها: {profile.get('games_played', 0)}\n"
    )
    await update.callback_query.message.reply_text(text, parse_mode="Markdown")
