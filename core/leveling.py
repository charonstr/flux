from core.database import applyxp, ensurelevel, levelstate


MAX_LEVEL = 100
BASE_XP = 100
STEP_XP = 50


def required_xp(level: int) -> int:
    lv = int(level)
    if lv < 1:
        lv = 1
    return BASE_XP + (lv - 1) * STEP_XP


def get_level(user_id: int) -> dict:
    ensurelevel(int(user_id))
    row = levelstate(int(user_id))
    level = int(row[0]) if row else 1
    xp = int(row[1]) if row else 0
    total_xp = int(row[2]) if row else 0
    next_need = 0 if level >= MAX_LEVEL else required_xp(level)
    return {"level": level, "xp": xp, "total_xp": total_xp, "next_level_xp": next_need}


def add_xp(user_id: int, amount: int, reason: str, reference_id: str | None = None) -> dict:
    applied, level, xp, total_xp = applyxp(
        user_id=int(user_id),
        amount=int(amount),
        reason=str(reason),
        reference_id=reference_id,
        max_level=MAX_LEVEL,
        base_xp=BASE_XP,
        step_xp=STEP_XP,
    )
    next_need = 0 if level >= MAX_LEVEL else required_xp(level)
    return {
        "applied": bool(applied),
        "level": int(level),
        "xp": int(xp),
        "total_xp": int(total_xp),
        "next_level_xp": int(next_need),
    }
