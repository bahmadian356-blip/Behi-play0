"""
اعتبارسنجی initData ارسالی از Telegram Mini App.
هرگز نباید به داده‌ی ارسالی از کلاینت بدون این بررسی اعتماد کرد.
مستندات: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""
import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

from fastapi import HTTPException

from bot.config import TELEGRAM_BOT_TOKEN

MAX_AUTH_AGE_SECONDS = 24 * 60 * 60  # ۲۴ ساعت اعتبار initData


def validate_init_data(init_data: str) -> dict:
    """
    initData را اعتبارسنجی می‌کند و در صورت معتبر بودن، دیکشنری کاربر تلگرام را برمی‌گرداند.
    در غیر این صورت HTTPException می‌زند.
    """
    if not init_data:
        raise HTTPException(status_code=401, detail="initData is missing")

    parsed = dict(parse_qsl(init_data, strict_parsing=True))
    received_hash = parsed.pop("hash", None)
    if not received_hash:
        raise HTTPException(status_code=401, detail="hash is missing from initData")

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))

    secret_key = hmac.new(b"WebAppData", TELEGRAM_BOT_TOKEN.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        raise HTTPException(status_code=401, detail="Invalid initData signature")

    auth_date = int(parsed.get("auth_date", "0"))
    if time.time() - auth_date > MAX_AUTH_AGE_SECONDS:
        raise HTTPException(status_code=401, detail="initData has expired")

    user_raw = parsed.get("user")
    if not user_raw:
        raise HTTPException(status_code=401, detail="user field missing in initData")

    try:
        user = json.loads(user_raw)
    except json.JSONDecodeError:
        raise HTTPException(status_code=401, detail="Malformed user field in initData")

    return user
