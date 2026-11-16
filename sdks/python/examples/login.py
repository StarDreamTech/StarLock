"""Call these functions from your own business routes and server-side session."""
import os
from dataclasses import asdict

from starlock import Client

client = Client(api_base=os.environ['STARLOCK_API_BASE'],
                site_key=os.environ['STARLOCK_SITE_KEY'], site_secret=os.environ['STARLOCK_SITE_SECRET'])
allowed_origin = os.environ['STARLOCK_APP_ORIGIN']


def create_login_challenge(trusted_context_id: str) -> dict:
    return asdict(client.create_session(action='login', context_id=trusted_context_id,
                                       origin=allowed_origin, challenge_type='semantic_grid'))


def verify_login(token: str, trusted_context_id: str) -> bool:
    # Load trusted_context_id from your server-side session before calling this function.
    result = client.siteverify(token=token, action='login', context_id=trusted_context_id)
    return result.success
