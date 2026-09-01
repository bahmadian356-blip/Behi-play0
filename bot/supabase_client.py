"""
اتصال به Supabase با استفاده از Service Role Key.
این کلاینت فقط سمت Backend (بات) استفاده می‌شود و هرگز نباید به فرانت‌اند ارسال شود.
"""
from supabase import create_client, Client
from bot.config import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def get_or_create_profile(telegram_user) -> dict:
    """
    telegram_user: شیء User تلگرام (update.effective_user)
    اگر پروفایل کاربر وجود نداشته باشد می‌سازد، در غیر این صورت آن را برمی‌گرداند.
    """
    telegram_id = telegram_user.id
    existing = (
        supabase.table("profiles")
        .select("*")
        .eq("telegram_id", telegram_id)
        .maybe_single()
        .execute()
    )
    if existing and existing.data:
        return existing.data

    new_profile = {
        "telegram_id": telegram_id,
        "username": telegram_user.username,
        "first_name": telegram_user.first_name,
        "last_name": telegram_user.last_name,
        "xp": 0,
        "level": 1,
        "games_played": 0,
        "wins": 0,
        "losses": 0,
        "score": 0,
    }
    created = supabase.table("profiles").insert(new_profile).execute()
    return created.data[0]


def get_profile_by_telegram_id(telegram_id: int) -> dict | None:
    res = (
        supabase.table("profiles")
        .select("*")
        .eq("telegram_id", telegram_id)
        .maybe_single()
        .execute()
    )
    return res.data if res else None


def get_leaderboard(limit: int = 10) -> list[dict]:
    res = (
        supabase.table("profiles")
        .select("telegram_id, username, first_name, level, xp, wins")
        .order("xp", desc=True)
        .limit(limit)
        .execute()
    )
    return res.data or []


def get_user_rank(telegram_id: int) -> int | None:
    all_profiles = (
        supabase.table("profiles")
        .select("telegram_id, xp")
        .order("xp", desc=True)
        .execute()
    )
    rows = all_profiles.data or []
    for idx, row in enumerate(rows, start=1):
        if row["telegram_id"] == telegram_id:
            return idx
    return None


def get_game_by_id(game_id: str) -> dict | None:
    res = (
        supabase.table("games")
        .select("*")
        .eq("id", game_id)
        .maybe_single()
        .execute()
    )
    return res.data if res else None
