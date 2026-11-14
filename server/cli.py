"""Local site management. Never prints a server credential."""
import argparse
import json
import os
import re
import secrets
from pathlib import Path

from config.settings import Settings
from verification.errors import VerificationError
from verification.generators import TYPES
from verification.models import Site, SiteStore
from verification.service import normalize_origin


def main():
    parser = argparse.ArgumentParser(description="StarLock site management")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init-db", help="Initialize the site table without deleting existing data")
    create = commands.add_parser("create-site")
    create.add_argument("--name", required=True)
    create.add_argument("--origin", action="append", required=True)
    create.add_argument("--action", action="append", required=True)
    create.add_argument("--challenge-type", action="append", choices=TYPES)
    types = commands.add_parser("set-site-types", help="Explicitly replace one site's allowed challenge types")
    types.add_argument("site_key")
    types.add_argument("--challenge-type", action="append", required=True, choices=TYPES)
    disable = commands.add_parser("disable-site")
    disable.add_argument("site_key")
    options = parser.parse_args()
    settings = Settings.from_env()
    store = SiteStore(settings.database_path)
    store.initialize()
    if options.command == "init-db":
        print("Site table ready; existing data retained.")
        return
    if options.command == "disable-site":
        site = store.get_active(options.site_key)
        site.active = False
        store.save(site)
        print(f"Disabled {site.key}")
        return
    if options.command == "set-site-types":
        site = store.get_active(options.site_key)
        site.challenge_types = list(dict.fromkeys(options.challenge_type))
        store.save(site)
        print(f"Updated challenge types for {site.key}: {', '.join(site.challenge_types)}")
        return
    origins = [normalize_origin(value) for value in options.origin]
    if not settings.debug and any(not origin.startswith("https://") for origin in origins):
        parser.error("Production origins require HTTPS")
    if not all(re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", value) for value in options.action):
        parser.error("Actions must contain 1-64 letters, digits, underscores or hyphens")
    site = Site(name=options.name, origins=origins, actions=options.action)
    if options.challenge_type:
        site.challenge_types = list(dict.fromkeys(options.challenge_type))
    secret = "ss_" + secrets.token_urlsafe(32)
    site.set_secret(secret)
    directory = Path.home() / ".local/share/starlock/credentials"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    destination = directory / f"{site.key}.json"
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w") as stream:
            json.dump({"site_key": site.key, "site_secret": secret}, stream)
        store.create(site)
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    print(f"Created {site.key}; private server credential saved to {destination}")


if __name__ == "__main__":
    try:
        main()
    except VerificationError as error:
        raise SystemExit(error.message)
