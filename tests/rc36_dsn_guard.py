"""Fail-closed RC3.6 Neon endpoint guard.

Only the dedicated branch endpoint created for the RC3.6 PG16 gate is accepted.
Never accept RC3.5, default, preview, pooled, or arbitrary PostgreSQL targets.
"""
from __future__ import annotations
import re
import shlex
from urllib.parse import parse_qs, unquote, urlsplit

EXPECTED_ENDPOINT = 'ep-holy-star-bbv8lyg7'
EXPECTED_HOST = EXPECTED_ENDPOINT + '.c-15.us-east-1.aws.neon.tech'
EXPECTED_DATABASE = 'industrial_v19b_preview'
EXPECTED_ROLE = 'v19b_app_runtime'
EXPECTED_PORT = 5432
EXPECTED_BRANCH_ID = 'br-green-glade-bbnahfli'
EXPECTED_BRANCH_NAME = 'rc36-pg16-isolated-20261106'
EXPECTED_PROJECT_ID = 'super-glade-55757112'


class GuardError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def normalize_dsn(raw: str) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise GuardError('EMPTY_CONNECTION_STRING')
    value = raw.strip()
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
        hostname = (parsed.hostname or '').lower().rstrip('.')
        database = unquote(parsed.path[1:]) if parsed.path.startswith('/') else ''
        username = unquote(parsed.username or '')
        port = parsed.port
    except (ValueError, TypeError):
        raise GuardError('URL_PARSE_FAILED') from None
    if parsed.scheme not in ('postgresql', 'postgres') or not parsed.netloc or not hostname or not username or not database:
        raise GuardError('URL_PARSE_FAILED')
    if hostname != EXPECTED_HOST:
        raise GuardError('HOST_NOT_RC36_ISOLATED_ENDPOINT')
    if port not in (None, EXPECTED_PORT):
        raise GuardError('PORT_NOT_ALLOWED')
    if username != EXPECTED_ROLE:
        raise GuardError('ROLE_NOT_RC36_RUNTIME')
    if hostname.startswith(EXPECTED_ENDPOINT + '-pooler.') or '-pooler.' in hostname:
        raise GuardError('POOLER_NOT_ALLOWED')
    if database != EXPECTED_DATABASE:
        raise GuardError('DATABASE_NOT_ALLOWED')
    if parsed.fragment:
        raise GuardError('URL_FRAGMENT_NOT_ALLOWED')
    query = parse_qs(parsed.query)
    allowed_query_keys = {'sslmode', 'channel_binding', 'application_name', 'connect_timeout'}
    if set(query) - allowed_query_keys:
        raise GuardError('URL_QUERY_PARAM_NOT_ALLOWED')
    sslmodes = query.get('sslmode', [])
    if not sslmodes:
        raise GuardError('SSL_REQUIRED')
    if len(sslmodes) != 1:
        raise GuardError('SSL_MODE_MUST_BE_SINGLE')
    if sslmodes[0].lower() not in {'require', 'verify-ca', 'verify-full'}:
        raise GuardError('SSL_REQUIRED')
    return value


def safe_target() -> dict:
    return {
        'project_id': EXPECTED_PROJECT_ID,
        'branch_id': EXPECTED_BRANCH_ID,
        'branch_name': EXPECTED_BRANCH_NAME,
        'endpoint_id': EXPECTED_ENDPOINT,
        'database': EXPECTED_DATABASE,
        'runtime_role': EXPECTED_ROLE,
    }
