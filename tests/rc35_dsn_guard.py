"""RC3.5 isolated Neon DSN parser and fail-closed endpoint allowlist.

No network, logging, or credential persistence. Diagnostic codes only.
"""
from __future__ import annotations
import re
import shlex
from urllib.parse import urlsplit, unquote

EXPECTED_ENDPOINT = 'ep-patient-wind-bbme3mck'
EXPECTED_DATABASE = 'industrial_v19b_preview'

class GuardError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def normalize_dsn(raw: str) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise GuardError('EMPTY_CONNECTION_STRING')
    value = raw.strip()
    # Neon Connect dialog may copy a shell command instead of just the URL.
    if re.match(r'^psql\s', value, flags=re.IGNORECASE):
        try:
            args = shlex.split(value, posix=True)
        except ValueError:
            raise GuardError('PSQL_COMMAND_FORMAT_INVALID') from None
        if len(args) == 2 and args[0].lower() == 'psql':
            value = args[1]
        elif len(args) == 3 and args[0].lower() == 'psql' and args[1] in ('-d', '--dbname'):
            value = args[2]
        else:
            raise GuardError('PSQL_COMMAND_UNSUPPORTED')
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
        value = value[1:-1]
    if any(c.isspace() for c in value) or any(ord(c) < 32 for c in value):
        raise GuardError('CONNECTION_STRING_WHITESPACE')
    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
        db = unquote(parsed.path[1:]) if parsed.path.startswith('/') else ''
        username = parsed.username
        port = parsed.port  # Force validation of malformed port.
    except (ValueError, TypeError):
        raise GuardError('URL_PARSE_FAILED') from None
    if parsed.scheme not in ('postgresql', 'postgres') or not parsed.netloc or not hostname or not username or not db:
        raise GuardError('URL_PARSE_FAILED')
    host = hostname.lower().rstrip('.')
    if host != EXPECTED_ENDPOINT + '.neon.tech' and not (host.startswith(EXPECTED_ENDPOINT + '.') and host.endswith('.neon.tech')):
        raise GuardError('HOST_NOT_ALLOWED')
    if host.startswith(EXPECTED_ENDPOINT + '-pooler.'):
        raise GuardError('POOLER_NOT_ALLOWED')
    if db != EXPECTED_DATABASE:
        raise GuardError('DATABASE_NOT_ALLOWED')
    # No arbitrary command/URL fragments, which could hide a second target.
    if parsed.fragment:
        raise GuardError('URL_FRAGMENT_NOT_ALLOWED')
    return value
