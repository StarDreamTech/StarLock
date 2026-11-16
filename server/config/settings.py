import os
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DEVELOPMENT_KEY = "starlock-public-local-development-key-do-not-use-in-production"


@dataclass(frozen=True)
class Settings:
    debug: bool = False
    secret_key: str = ""
    redis_url: str = "redis://127.0.0.1:6391/0"
    redis_prefix: str = "starlock:dev:"
    database_path: Path = BASE_DIR / "db.sqlite3"
    sdk_directory: Path = BASE_DIR.parent / "dist" / "sdk"
    allowed_hosts: tuple[str, ...] = ("localhost", "127.0.0.1", "[::1]", "testserver")
    session_ttl: int = 300
    challenge_ttl: int = 120
    token_ttl: int = 120
    max_attempts: int = 3
    max_body_bytes: int = 32768
    demo_enabled: bool = False
    admin_token: str = ""
    demo_origins: tuple[str, ...] = ("http://127.0.0.1:5178", "http://localhost:5178",
                                     "http://127.0.0.1:5179", "http://localhost:5179")

    def __post_init__(self):
        if not self.secret_key:
            if not self.debug:
                raise RuntimeError("Set STARLOCK_SECRET_KEY; local development needs STARLOCK_DEBUG=1")
            object.__setattr__(self, "secret_key", DEVELOPMENT_KEY)
        if not self.debug and self.secret_key == DEVELOPMENT_KEY:
            raise RuntimeError("The public development key cannot be used outside debug mode")
        if self.demo_enabled and not self.debug:
            raise RuntimeError("Demo routes require debug mode")
        if self.admin_token and len(self.admin_token) < 32:
            raise RuntimeError("STARLOCK_ADMIN_TOKEN must contain at least 32 characters")

    @classmethod
    def from_env(cls):
        debug = os.environ.get("STARLOCK_DEBUG") == "1"
        return cls(
            debug=debug,
            secret_key=os.environ.get("STARLOCK_SECRET_KEY", ""),
            redis_url=os.environ.get("STARLOCK_REDIS_URL", cls.redis_url),
            redis_prefix=os.environ.get("STARLOCK_REDIS_PREFIX", cls.redis_prefix),
            database_path=Path(os.environ.get("STARLOCK_DATABASE_PATH", str(BASE_DIR / "db.sqlite3"))),
            sdk_directory=Path(os.environ.get("STARLOCK_SDK_DIRECTORY", str(cls.sdk_directory))),
            allowed_hosts=tuple(part.strip() for part in os.environ.get(
                "STARLOCK_ALLOWED_HOSTS", ",".join(cls.allowed_hosts)).split(",") if part.strip()),
            demo_enabled=debug and os.environ.get("STARLOCK_DEMO") == "1",
            admin_token=os.environ.get("STARLOCK_ADMIN_TOKEN", ""),
        )
