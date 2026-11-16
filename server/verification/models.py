"""Small SQLite site store, compatible with the original local site table."""
import base64
import hashlib
import hmac
import json
import secrets
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from .errors import require


@dataclass
class Site:
    name: str
    key: str = field(default_factory=lambda: "site_" + secrets.token_urlsafe(16))
    secret_hash: str = "!"
    origins: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    challenge_types: list[str] = field(default_factory=lambda: ["text", "digits", "arithmetic", "slider", "bezier_slider", "rotate", "text_click", "semantic_grid"])
    active: bool = True

    def set_secret(self, value):
        iterations, salt = 1_000_000, secrets.token_urlsafe(16)
        encoded = base64.b64encode(hashlib.pbkdf2_hmac(
            "sha256", value.encode(), salt.encode(), iterations)).decode()
        self.secret_hash = f"pbkdf2_sha256${iterations}${salt}${encoded}"

    def accepts_secret(self, value):
        # Keep existing PBKDF2 site credentials valid without a framework dependency.
        try:
            algorithm, iterations, salt, expected = self.secret_hash.split("$")
            if algorithm != "pbkdf2_sha256" or not 1 <= int(iterations) <= 2_000_000:
                return False
            encoded = base64.b64encode(hashlib.pbkdf2_hmac(
                "sha256", value.encode(), salt.encode(), int(iterations))).decode()
            return hmac.compare_digest(expected, encoded)
        except (ValueError, TypeError):
            return False


class SiteStore:
    def __init__(self, database_path):
        self.path = Path(database_path)

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS verification_site (
                    key TEXT PRIMARY KEY, name TEXT NOT NULL, secret_hash TEXT NOT NULL,
                    origins TEXT NOT NULL, actions TEXT NOT NULL,
                    challenge_types TEXT NOT NULL, active INTEGER NOT NULL
                )
            """)

    def get(self, key):
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM verification_site WHERE key = ?", (key,)).fetchone()
        if row is None:
            return None
        return Site(key=row["key"], name=row["name"], secret_hash=row["secret_hash"],
                    origins=json.loads(row["origins"]), actions=json.loads(row["actions"]),
                    challenge_types=json.loads(row["challenge_types"]), active=bool(row["active"]))

    def get_active(self, key):
        site = self.get(key)
        require(site is not None and site.active, "SITE_INVALID", "站点不可用", 403)
        return site

    def allows_origin(self, origin):
        with self.connect() as connection:
            return any(origin in json.loads(row["origins"]) for row in connection.execute(
                "SELECT origins FROM verification_site WHERE active = 1"))

    @staticmethod
    def values(site):
        return (site.key, site.name, site.secret_hash, json.dumps(site.origins),
                json.dumps(site.actions), json.dumps(site.challenge_types), int(site.active))

    def save(self, site):
        with self.connect() as connection:
            connection.execute("""
                INSERT INTO verification_site (key,name,secret_hash,origins,actions,challenge_types,active)
                VALUES (?,?,?,?,?,?,?) ON CONFLICT(key) DO UPDATE SET
                    name=excluded.name, secret_hash=excluded.secret_hash, origins=excluded.origins,
                    actions=excluded.actions, challenge_types=excluded.challenge_types, active=excluded.active
            """, self.values(site))

    def create(self, site):
        with self.connect() as connection:
            connection.execute("""
                INSERT INTO verification_site (key,name,secret_hash,origins,actions,challenge_types,active)
                VALUES (?,?,?,?,?,?,?)
            """, self.values(site))

    def get_or_create(self, site):
        with self.connect() as connection:
            connection.execute("""
                INSERT INTO verification_site (key,name,secret_hash,origins,actions,challenge_types,active)
                VALUES (?,?,?,?,?,?,?) ON CONFLICT(key) DO NOTHING
            """, self.values(site))
        return self.get(site.key)
