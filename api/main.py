"""
Backend API برای BEHI PLAY Mini App.
تمام درخواست‌های حساس (ساخت بازی، join شدن، ثبت نتیجه) از اینجا رد می‌شوند
و initData همیشه سمت سرور اعتبارسنجی می‌شود؛ به داده خام کلاینت اعتماد نمی‌شود.
"""
import uuid
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from api.auth import validate_init_data
from bot.supabase_client import supabase
from bot.config import TELEGRAM_BOT_USERNAME

app = FastAPI(title="BEHI PLAY API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # در پروداکشن بهتر است دامنه Mini App خودتان را مشخص کنید
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- Schemas ----------

class AuthRequest(BaseModel):
    init_data: str


class CreateGameRequest(BaseModel):
    init_data: str
    name: str
    game_type: str = "quiz"
    max_players: int = 8
    is_public: bool = False


class JoinGameRequest(BaseModel):
    init_data: str
    game_id: str


class StartGameRequest(BaseModel):
    init_data: str
    game_id: str


class SubmitAnswerRequest(BaseModel):
    init_data: str
    game_id: str
    question_id: str
    selected_option: int
    time_taken_ms: int


class FinishGameRequest(BaseModel):
    init_data: str
    game_id: str


# ---------- Helpers ----------

XP_PER_CORRECT_ANSWER = 15
XP_PER_WIN = 50


def level_from_xp(xp: int) -> int:
    # هر ۱۰۰ XP یک Level (ساده و قابل تغییر)
    return max(1, xp // 100 + 1)


def auth_or_403(init_data: str) -> dict:
    tg_user = validate_init_data(init_data)
    profile_res = (
        supabase.table("profiles")
        .select("*")
        .eq("telegram_id", tg_user["id"])
        .maybe_single()
        .execute()
    )
    if profile_res and profile_res.data:
        return profile_res.data

    new_profile = {
        "telegram_id": tg_user["id"],
        "username": tg_user.get("username"),
        "first_name": tg_user.get("first_name"),
        "last_name": tg_user.get("last_name"),
        "xp": 0,
        "level": 1,
        "games_played": 0,
        "wins": 0,
        "losses": 0,
        "score": 0,
    }
    created = supabase.table("profiles").insert(new_profile).execute()
    return created.data[0]


# ---------- Routes ----------

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/auth/verify")
def verify(payload: AuthRequest):
    profile = auth_or_403(payload.init_data)
    return {"profile": profile}


@app.get("/profile/{telegram_id}")
def get_profile(telegram_id: int):
    res = (
        supabase.table("profiles")
        .select("*")
        .eq("telegram_id", telegram_id)
        .maybe_single()
        .execute()
    )
    if not res or not res.data:
        raise HTTPException(status_code=404, detail="Profile not found")
    return res.data


@app.get("/leaderboard")
def leaderboard(limit: int = 20):
    res = (
        supabase.table("profiles")
        .select("telegram_id, username, first_name, level, xp, wins")
        .order("xp", desc=True)
        .limit(limit)
        .execute()
    )
    return {"leaderboard": res.data or []}


@app.post("/games")
def create_game(payload: CreateGameRequest):
    profile = auth_or_403(payload.init_data)

    game_id = str(uuid.uuid4())
    game = {
        "id": game_id,
        "name": payload.name,
        "game_type": payload.game_type,
        "max_players": payload.max_players,
        "is_public": payload.is_public,
        "host_id": profile["telegram_id"],
        "status": "waiting",
    }
    supabase.table("games").insert(game).execute()

    supabase.table("game_players").insert(
        {"game_id": game_id, "telegram_id": profile["telegram_id"], "is_host": True}
    ).execute()

    invite_link = f"https://t.me/{TELEGRAM_BOT_USERNAME}?start=game_{game_id}"
    return {"game": game, "invite_link_template": invite_link}


@app.get("/games/{game_id}")
def get_game(game_id: str):
    game_res = supabase.table("games").select("*").eq("id", game_id).maybe_single().execute()
    if not game_res or not game_res.data:
        raise HTTPException(status_code=404, detail="Game not found")

    players_res = (
        supabase.table("game_players")
        .select("telegram_id, is_host, score, profiles(username, first_name, level)")
        .eq("game_id", game_id)
        .execute()
    )
    return {"game": game_res.data, "players": players_res.data or []}


@app.post("/games/{game_id}/join")
def join_game(game_id: str, payload: JoinGameRequest):
    profile = auth_or_403(payload.init_data)

    game_res = supabase.table("games").select("*").eq("id", game_id).maybe_single().execute()
    if not game_res or not game_res.data:
        raise HTTPException(status_code=404, detail="Game not found")
    if game_res.data["status"] != "waiting":
        raise HTTPException(status_code=400, detail="Game already started or finished")

    existing = (
        supabase.table("game_players")
        .select("id")
        .eq("game_id", game_id)
        .eq("telegram_id", profile["telegram_id"])
        .maybe_single()
        .execute()
    )
    if existing and existing.data:
        return {"joined": True, "already_member": True}

    supabase.table("game_players").insert(
        {"game_id": game_id, "telegram_id": profile["telegram_id"], "is_host": False}
    ).execute()
    return {"joined": True, "already_member": False}


@app.post("/games/{game_id}/start")
def start_game(game_id: str, payload: StartGameRequest):
    profile = auth_or_403(payload.init_data)

    game_res = supabase.table("games").select("*").eq("id", game_id).maybe_single().execute()
    if not game_res or not game_res.data:
        raise HTTPException(status_code=404, detail="Game not found")
    if game_res.data["host_id"] != profile["telegram_id"]:
        raise HTTPException(status_code=403, detail="Only the host can start the game")

    supabase.table("games").update({"status": "in_progress"}).eq("id", game_id).execute()
    # این تغییر توسط Supabase Realtime به همه بازیکنان متصل ارسال می‌شود.
    return {"status": "in_progress"}


@app.get("/quiz/{game_id}/questions")
def get_quiz_questions(game_id: str):
    res = (
        supabase.table("quiz_questions")
        .select("id, question_text, options, order_index, time_limit_seconds")
        .eq("game_id", game_id)
        .order("order_index")
        .execute()
    )
    return {"questions": res.data or []}


@app.post("/quiz/answer")
def submit_answer(payload: SubmitAnswerRequest):
    profile = auth_or_403(payload.init_data)

    question_res = (
        supabase.table("quiz_questions")
        .select("*")
        .eq("id", payload.question_id)
        .maybe_single()
        .execute()
    )
    if not question_res or not question_res.data:
        raise HTTPException(status_code=404, detail="Question not found")

    is_correct = question_res.data["correct_option"] == payload.selected_option
    points = XP_PER_CORRECT_ANSWER if is_correct else 0

    supabase.table("quiz_answers").insert(
        {
            "game_id": payload.game_id,
            "question_id": payload.question_id,
            "telegram_id": profile["telegram_id"],
            "selected_option": payload.selected_option,
            "is_correct": is_correct,
            "time_taken_ms": payload.time_taken_ms,
            "points_awarded": points,
        }
    ).execute()

    if points:
        gp_res = (
            supabase.table("game_players")
            .select("score")
            .eq("game_id", payload.game_id)
            .eq("telegram_id", profile["telegram_id"])
            .maybe_single()
            .execute()
        )
        current_score = (gp_res.data or {}).get("score") or 0 if gp_res else 0
        supabase.table("game_players").update({"score": current_score + points}).eq(
            "game_id", payload.game_id
        ).eq("telegram_id", profile["telegram_id"]).execute()

    return {"is_correct": is_correct, "points_awarded": points}


@app.post("/games/{game_id}/finish")
def finish_game(game_id: str, payload: FinishGameRequest):
    profile = auth_or_403(payload.init_data)

    game_res = supabase.table("games").select("*").eq("id", game_id).maybe_single().execute()
    if not game_res or not game_res.data:
        raise HTTPException(status_code=404, detail="Game not found")
    if game_res.data["host_id"] != profile["telegram_id"]:
        raise HTTPException(status_code=403, detail="Only the host can finish the game")

    players_res = (
        supabase.table("game_players")
        .select("telegram_id, score")
        .eq("game_id", game_id)
        .execute()
    )
    players = players_res.data or []
    if not players:
        raise HTTPException(status_code=400, detail="No players in this game")

    top_score = max(p["score"] or 0 for p in players)

    for p in players:
        won = (p["score"] or 0) == top_score and top_score > 0
        gained_xp = (p["score"] or 0) + (XP_PER_WIN if won else 0)

        profile_res = (
            supabase.table("profiles")
            .select("*")
            .eq("telegram_id", p["telegram_id"])
            .maybe_single()
            .execute()
        )
        current = profile_res.data if profile_res and profile_res.data else None
        if not current:
            continue

        new_xp = (current.get("xp") or 0) + gained_xp
        supabase.table("profiles").update(
            {
                "xp": new_xp,
                "level": level_from_xp(new_xp),
                "games_played": (current.get("games_played") or 0) + 1,
                "wins": (current.get("wins") or 0) + (1 if won else 0),
                "losses": (current.get("losses") or 0) + (0 if won else 1),
            }
        ).eq("telegram_id", p["telegram_id"]).execute()

        supabase.table("game_results").insert(
            {
                "game_id": game_id,
                "telegram_id": p["telegram_id"],
                "final_score": p["score"] or 0,
                "won": won,
                "xp_gained": gained_xp,
            }
        ).execute()

    supabase.table("games").update({"status": "finished"}).eq("id", game_id).execute()
    return {"status": "finished"}
