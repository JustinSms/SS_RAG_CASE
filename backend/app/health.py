from pathlib import Path

from fastapi import APIRouter, Request
from sqlalchemy import text

from app.db.session import engine
from env.config import settings

router = APIRouter()

MEMINFO = Path("/proc/meminfo")
KB_PER_GB = 1024 * 1024

KEY_PROBLEMS = {
    "missing": "ANTHROPIC_API_KEY is not set. Add it to env/.env and restart the api container.",
    "invalid": "ANTHROPIC_API_KEY was rejected by Anthropic. Check the key in env/.env and restart.",
    "unreachable": "Could not reach the Anthropic API to check the key. Check the network and restart.",
}


def check_db() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        return False
    return True


def total_memory_gb() -> float | None:
    """Memory visible to the container (the Docker VM). None if it cannot be read."""
    try:
        for line in MEMINFO.read_text().splitlines():
            if line.startswith("MemTotal:"):
                return int(line.split()[1]) / KB_PER_GB
    except (OSError, ValueError):
        pass
    return None


def find_problems(key_status: str) -> list[dict]:
    problems = []
    if not check_db():
        problems.append({"code": "db_unreachable", "level": "error",
                         "message": "The database is not reachable."})
    if key_status != "ok":
        problems.append({"code": f"api_key_{key_status}", "level": "error",
                         "message": KEY_PROBLEMS[key_status]})
    memory = total_memory_gb()
    if memory is not None and memory < settings.MIN_MEMORY_GB:
        problems.append({"code": "low_memory", "level": "warning",
                         "message": f"Only {memory:.1f} GB memory is available to Docker; "
                                    f"{settings.MIN_MEMORY_GB:g} GB or more is recommended."})
    return problems


@router.get("/api/health")
def health(request: Request):
    # Always 200 while the app is up, so the web container can start and show the problems.
    problems = find_problems(request.app.state.key_status)
    return {"healthy": not any(p["level"] == "error" for p in problems), "problems": problems}
