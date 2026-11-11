"""Unapproved trust-claim schemas. No trust registration or key verifier exists."""
from dataclasses import dataclass
from market_data.snapshots import timestamp, validate_timestamp_text

MAX_EVIDENCES = 64
MAX_EVIDENCE_BYTES = 64 * 1024
MAX_TOTAL_BYTES = 1024 * 1024
MAX_TEXT_CHARS = 256
MAX_TARGET_VERSIONS = 4096


def text(value):
    if type(value) is not str or not 1 <= len(value) <= MAX_TEXT_CHARS:
        raise ValueError('invalid bounded text')
    if not value.strip():
        raise ValueError('invalid bounded text')


def finite_tuple(value, limit):
    if type(value) is not tuple or len(value) > limit:
        raise ValueError('invalid bounded tuple')


@dataclass(frozen=True)
class TrustClaim:
    schema_version: str
    issuer: str
    authorities: tuple[str, ...]
    registration_reference: str
    approval_history: tuple[str, ...]
    allowed_methods: tuple[str, ...]
    key_id: str
    valid_from: str
    valid_until: str
    revocation: str
    environment: str

    def __post_init__(self):
        for name in ('schema_version','issuer','registration_reference','key_id',
                     'revocation','environment'):
            text(getattr(self,name))
        for values in (self.authorities,self.approval_history,self.allowed_methods):
            finite_tuple(values,64)
            for v in values:text(v)
        for value in (self.valid_from,self.valid_until):validate_timestamp_text(value)
        if self.schema_version != 'trust/1' or self.environment not in ('synthetic','unapproved'):
            raise ValueError('unsupported trust claim')
        if self.revocation not in ('unknown','active','revoked'):
            raise ValueError('invalid revocation claim')
        if timestamp(self.valid_from) >= timestamp(self.valid_until):
            raise ValueError('invalid trust period')
