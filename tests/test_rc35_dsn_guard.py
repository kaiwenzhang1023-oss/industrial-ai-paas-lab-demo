import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import pytest
from rc35_dsn_guard import normalize_dsn, GuardError

BASE = 'postgresql://v19b_app_runtime:p%40ss%3Aword@ep-patient-wind-bbme3mck.us-east-2.aws.neon.tech/industrial_v19b_preview?sslmode=require'

@pytest.mark.parametrize('raw', [BASE, BASE.replace('postgresql:', 'postgres:'), '  '+BASE+'  ', "psql '"+BASE+"'", 'psql -d '+BASE, '"'+BASE+'"'])
def test_allowed_connection_formats(raw):
    assert normalize_dsn(raw).startswith('postgres')

@pytest.mark.parametrize('raw,code', [
    ('', 'EMPTY_CONNECTION_STRING'),
    ('postgresql://u:p@ep-twilight-violet-bb8pm1v6.us-east-2.aws.neon.tech/industrial_v19b_preview', 'HOST_NOT_ALLOWED'),
    (BASE.replace('industrial_v19b_preview', 'production'), 'DATABASE_NOT_ALLOWED'),
    (BASE.replace('ep-patient-wind-bbme3mck.us-east-2', 'ep-patient-wind-bbme3mck-pooler.us-east-2'), 'HOST_NOT_ALLOWED'),
    ('psql --host evil.example.com', 'PSQL_COMMAND_UNSUPPORTED'),
    ('postgresql://bad host/x', 'CONNECTION_STRING_WHITESPACE'),
    ('postgresql://u:p@evil.example.com/industrial_v19b_preview', 'HOST_NOT_ALLOWED'),
    ('postgresql://u:p@ep-patient-wind-bbme3mck.us-east-2.aws.neon.tech:bad/industrial_v19b_preview', 'URL_PARSE_FAILED'),
])
def test_reject_bad_targets(raw, code):
    with pytest.raises(GuardError) as err:
        normalize_dsn(raw)
    assert err.value.code == code
    assert 'p%40ss' not in str(err.value)
