"""Pure canonical-observation normalization and ordering semantics.

These helpers normalize source reports.  They do not infer point, equipment,
system, or facility state.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN, localcontext
from typing import Any


TIMESTAMP_VALID = "VALID"
TIMESTAMP_MISSING = "MISSING"
TIMESTAMP_INVALID = "INVALID"

ORDER_BEFORE = "BEFORE"
ORDER_EQUAL = "EQUAL"
ORDER_AFTER = "AFTER"
ORDER_UNORDERED = "UNORDERED"
ORDER_NOT_COMPARABLE = "NOT_COMPARABLE"
ORDER_UNKNOWN = "UNKNOWN"
ORDER_MISSING = "MISSING"

_RFC3339_PATTERN = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})"
    r"[Tt]"
    r"(?P<hour>[01]\d|2[0-3]):"
    r"(?P<minute>[0-5]\d):"
    r"(?P<second>[0-5]\d)"
    r"(?P<fraction>\.\d+)?"
    r"(?P<offset>[Zz]|[+-](?:[01]\d|2[0-3]):[0-5]\d)$"
)


def canonical_json_text(value: Any) -> str:
    """Return the repository's deterministic UTF-8 JSON representation.

    This is a deliberately small canonicalization contract for repository data:
    object keys are strings and sorted, insignificant whitespace is omitted,
    Unicode is emitted directly, and non-finite numbers are rejected.  It is
    not presented as a general implementation of RFC 8785.
    """

    _require_string_object_keys(value)
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise ValueError(f"value is not canonical-JSON encodable: {exc}") from exc


def canonical_json_bytes(value: Any) -> bytes:
    """Return canonical JSON encoded as UTF-8 without a trailing newline."""

    try:
        return canonical_json_text(value).encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError(f"value is not valid UTF-8 JSON text: {exc}") from exc


def canonical_json_sha256(value: Any) -> str:
    """Return a bare, lowercase SHA-256 hex digest of canonical JSON bytes."""

    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _require_string_object_keys(value: Any, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, nested_value in value.items():
            if not isinstance(key, str):
                raise ValueError(
                    f"canonical JSON object key at {path} must be a string"
                )
            _require_string_object_keys(nested_value, f"{path}.{key}")
        return

    if isinstance(value, (list, tuple)):
        for index, nested_value in enumerate(value):
            _require_string_object_keys(nested_value, f"{path}[{index}]")


def parse_rfc3339_timestamp(raw_text: Any) -> dict[str, Any]:
    """Parse one source timestamp without substituting a receipt timestamp.

    The result always preserves the supplied text.  Valid results also retain
    the source offset and exact fractional-second precision while exposing a
    UTC representation.  ``None`` and an empty string are explicit missing
    values; other non-string or malformed values are invalid.
    """

    result = {
        "status": TIMESTAMP_INVALID,
        "raw_text": raw_text,
        "raw_offset": None,
        "precision": None,
        "fractional_second_digits": None,
        "utc": None,
        "error": None,
    }

    if raw_text is None or raw_text == "":
        result["status"] = TIMESTAMP_MISSING
        return result

    if not isinstance(raw_text, str):
        result["error"] = "timestamp must be an RFC 3339 string or null"
        return result

    match = _RFC3339_PATTERN.fullmatch(raw_text)
    if match is None:
        result["error"] = "timestamp is not a supported RFC 3339 value"
        return result

    raw_offset = match.group("offset")
    fraction = match.group("fraction") or ""
    fractional_second_digits = max(len(fraction) - 1, 0)
    result.update(
        {
            "raw_offset": raw_offset,
            "precision": (
                "SECOND" if not fraction else "FRACTIONAL_SECOND"
            ),
            "fractional_second_digits": fractional_second_digits,
        }
    )

    try:
        date_part = datetime.strptime(match.group("date"), "%Y-%m-%d")
        source_whole_second = date_part.replace(
            hour=int(match.group("hour")),
            minute=int(match.group("minute")),
            second=int(match.group("second")),
        )
    except ValueError:
        result["error"] = "timestamp contains an invalid calendar date"
        return result

    offset_delta = _offset_timedelta(raw_offset)
    try:
        utc_whole_second = source_whole_second - offset_delta
    except OverflowError:
        result["error"] = "timestamp cannot be represented as a UTC instant"
        return result

    result.update(
        {
            "status": TIMESTAMP_VALID,
            "utc": utc_whole_second.strftime("%Y-%m-%dT%H:%M:%S")
            + fraction
            + "Z",
        }
    )
    return result


def _offset_timedelta(raw_offset: str) -> timedelta:
    if raw_offset in {"Z", "z"}:
        return timedelta(0)

    sign = 1 if raw_offset[0] == "+" else -1
    hours = int(raw_offset[1:3])
    minutes = int(raw_offset[4:6])
    return sign * timedelta(hours=hours, minutes=minutes)


def require_valid_rfc3339_utc(value: Any, *, field_name: str) -> str:
    """Return normalized UTC text or raise for a missing/invalid required time."""

    parsed = parse_rfc3339_timestamp(value)
    if parsed["status"] != TIMESTAMP_VALID:
        raise ValueError(
            f"{field_name} must be an explicit valid RFC 3339 timestamp"
        )
    return parsed["utc"]


def compare_rfc3339_instants(left: str, right: str) -> str:
    """Compare two valid RFC 3339 instants without losing source precision."""

    left_key = _rfc3339_instant_key(left, field_name="left timestamp")
    right_key = _rfc3339_instant_key(right, field_name="right timestamp")
    return _three_way_relation(left_key, right_key)


def _rfc3339_instant_key(
    value: Any,
    *,
    field_name: str,
) -> tuple[datetime, Decimal]:
    normalized = require_valid_rfc3339_utc(value, field_name=field_name)
    match = _RFC3339_PATTERN.fullmatch(normalized)
    if match is None:  # pragma: no cover - guarded by the parser above
        raise ValueError(f"{field_name} could not be normalized")

    whole_second = datetime.strptime(
        f"{match.group('date')}T{match.group('hour')}:"
        f"{match.group('minute')}:{match.group('second')}",
        "%Y-%m-%dT%H:%M:%S",
    )
    fraction = match.group("fraction")
    fractional_second = Decimal(f"0{fraction}") if fraction else Decimal(0)
    return whole_second, fractional_second


def normalize_decimal(
    value: Any,
    *,
    factor: Any,
    quantum: Any,
) -> Decimal:
    """Scale and quantize a numeric source value exactly.

    Decimal conversion is based on the supplied decimal spelling (or the
    round-trip spelling of a JSON float), never on a binary-float expansion.
    Quantization always uses ``ROUND_HALF_EVEN``.
    """

    decimal_value = _as_finite_decimal(value, field_name="value")
    decimal_factor = _as_finite_decimal(factor, field_name="factor")
    decimal_quantum = _as_finite_decimal(quantum, field_name="quantum")

    if decimal_factor == 0:
        raise ValueError("factor must be non-zero")
    if decimal_quantum <= 0:
        raise ValueError("quantum must be greater than zero")

    precision = max(
        50,
        _decimal_working_digits(decimal_value)
        + _decimal_working_digits(decimal_factor)
        + _decimal_working_digits(decimal_quantum)
        + 10,
    )
    try:
        with localcontext() as context:
            context.prec = precision
            scaled_value = decimal_value * decimal_factor
            return scaled_value.quantize(
                decimal_quantum,
                rounding=ROUND_HALF_EVEN,
            )
    except InvalidOperation as exc:
        raise ValueError("scaled value cannot be represented at the declared quantum") from exc


def normalize_decimal_text(
    value: Any,
    *,
    factor: Any,
    quantum: Any,
) -> str:
    """Return the exact normalized Decimal as non-exponential JSON text."""

    return format(
        normalize_decimal(value, factor=factor, quantum=quantum),
        "f",
    )


def _as_finite_decimal(value: Any, *, field_name: str) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be numeric, not boolean")

    if isinstance(value, Decimal):
        parsed = value
    elif isinstance(value, int):
        parsed = Decimal(value)
    elif isinstance(value, float):
        parsed = Decimal(str(value))
    elif isinstance(value, str):
        if value != value.strip() or not value:
            raise ValueError(
                f"{field_name} must not be empty or contain surrounding whitespace"
            )
        try:
            parsed = Decimal(value)
        except InvalidOperation as exc:
            raise ValueError(f"{field_name} is not a decimal value") from exc
    else:
        raise ValueError(f"{field_name} is not a supported decimal value")

    if not parsed.is_finite():
        raise ValueError(f"{field_name} must be finite")
    return parsed


def _decimal_working_digits(value: Decimal) -> int:
    value_tuple = value.as_tuple()
    return len(value_tuple.digits) + abs(value_tuple.exponent)


def decode_signed_int32_be(high_word: Any, low_word: Any) -> int:
    """Decode high/low unsigned 16-bit words as one signed big-endian int32."""

    high = _require_unsigned_word(high_word, field_name="high_word")
    low = _require_unsigned_word(low_word, field_name="low_word")
    unsigned_value = (high << 16) | low
    if unsigned_value & 0x80000000:
        return unsigned_value - 0x100000000
    return unsigned_value


def _require_unsigned_word(value: Any, *, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer from 0 through 65535")
    if value < 0 or value > 0xFFFF:
        raise ValueError(f"{field_name} must be an integer from 0 through 65535")
    return value


def normalize_strict_boolean(
    value: Any,
    *,
    true_values: Iterable[Any] = (True,),
    false_values: Iterable[Any] = (False,),
) -> bool:
    """Normalize only explicitly declared, type-exact Boolean source tokens."""

    if isinstance(true_values, (str, bytes)) or isinstance(
        false_values,
        (str, bytes),
    ):
        raise ValueError(
            "true_values and false_values must be collections of exact tokens"
        )
    declared_true_values = tuple(true_values)
    declared_false_values = tuple(false_values)
    if not declared_true_values or not declared_false_values:
        raise ValueError("both true_values and false_values must be declared")

    for true_value in declared_true_values:
        if any(
            _same_typed_token(true_value, false_value)
            for false_value in declared_false_values
        ):
            raise ValueError("true_values and false_values must not overlap")

    if any(_same_typed_token(value, token) for token in declared_true_values):
        return True
    if any(_same_typed_token(value, token) for token in declared_false_values):
        return False
    raise ValueError("value does not match a declared Boolean source token")


def _same_typed_token(left: Any, right: Any) -> bool:
    return type(left) is type(right) and left == right


def normalize_direct_enum(value: Any, mapping: Mapping[str, str]) -> str:
    """Apply an exact, case-sensitive source-enum mapping."""

    if not isinstance(value, str):
        raise ValueError("enum source value must be a string")
    if not isinstance(mapping, Mapping) or not mapping:
        raise ValueError("enum mapping must be a non-empty mapping")

    for source_value, normalized_value in mapping.items():
        if (
            not isinstance(source_value, str)
            or not source_value
            or not isinstance(normalized_value, str)
            or not normalized_value
        ):
            raise ValueError(
                "enum mapping keys and normalized values must be non-empty strings"
            )

    if value not in mapping:
        raise ValueError("enum source value is not declared by the mapping")
    return mapping[value]


def observation_ordering_facts(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
) -> dict[str, Any]:
    """Return source-order and arrival-order facts for two reports.

    Receipt time is included only as an arrival fact.  It never changes the
    source-order relation used by a reported-observation projection.
    """

    same_source_binding = _same_source_binding(left, right)
    observed_relation = _observed_time_relation(left, right)
    sequence_relation, raw_sequence_relation, sequence_comparable = (
        _sequence_relations(left, right)
    )
    sequence_time_disagreement = (
        sequence_comparable
        and (
            (
                observed_relation in {ORDER_BEFORE, ORDER_AFTER}
                and sequence_relation
                in {ORDER_BEFORE, ORDER_EQUAL, ORDER_AFTER}
                and sequence_relation != observed_relation
            )
        )
    )
    ambiguous_reset = _has_ambiguous_sequence_reset(
        left,
        right,
        observed_relation=observed_relation,
        raw_sequence_relation=raw_sequence_relation,
    )

    if not same_source_binding:
        relation = ORDER_NOT_COMPARABLE
    elif observed_relation == ORDER_UNKNOWN:
        relation = ORDER_UNORDERED
    elif sequence_time_disagreement or ambiguous_reset:
        relation = ORDER_UNORDERED
    elif sequence_comparable and sequence_relation in {
        ORDER_BEFORE,
        ORDER_AFTER,
    }:
        relation = sequence_relation
    else:
        relation = observed_relation

    received_relation = _received_time_relation(left, right)
    out_of_order_arrival = (
        relation in {ORDER_BEFORE, ORDER_AFTER}
        and received_relation in {ORDER_BEFORE, ORDER_AFTER}
        and relation != received_relation
    )

    return {
        "left_candidate_id": _candidate_identifier(left),
        "right_candidate_id": _candidate_identifier(right),
        "same_source_binding": same_source_binding,
        "observed_at_relation": observed_relation,
        "sequence_relation": sequence_relation,
        "raw_sequence_relation": raw_sequence_relation,
        "sequence_comparable": sequence_comparable,
        "sequence_time_disagreement": sequence_time_disagreement,
        "ambiguous_sequence_reset": ambiguous_reset,
        "received_at_relation": received_relation,
        "out_of_order_arrival": out_of_order_arrival,
        "relation": relation,
    }


def observation_temporal_facts(
    candidate: Mapping[str, Any],
) -> dict[str, Any]:
    """Return single-report event/receipt facts without judging the report."""

    observed_at_status = candidate.get("observed_at_status")
    observed_at_utc = candidate.get("observed_at_utc")
    if observed_at_status is None:
        if observed_at_utc is None:
            observed_at_status = TIMESTAMP_MISSING
        else:
            parsed_observed_at = parse_rfc3339_timestamp(observed_at_utc)
            observed_at_status = parsed_observed_at["status"]
            observed_at_utc = parsed_observed_at["utc"]

    received_at = candidate.get(
        "received_at_utc",
        candidate.get("received_at"),
    )
    received_parse = parse_rfc3339_timestamp(received_at)
    if (
        observed_at_status == TIMESTAMP_VALID
        and observed_at_utc is not None
        and received_parse["status"] == TIMESTAMP_VALID
    ):
        observed_received_relation = compare_rfc3339_instants(
            observed_at_utc,
            received_parse["utc"],
        )
    else:
        observed_received_relation = ORDER_UNKNOWN

    source_sequence = candidate.get("source_sequence")
    _validate_optional_sequence(source_sequence)
    source_epoch = _source_epoch(candidate)
    return {
        "observed_at_status": observed_at_status,
        "observed_at_utc": observed_at_utc,
        "received_at_utc": received_parse["utc"],
        "observed_at_received_at_relation": observed_received_relation,
        "observed_at_after_received_at": (
            observed_received_relation == ORDER_AFTER
            if observed_received_relation != ORDER_UNKNOWN
            else None
        ),
        "source_sequence": source_sequence,
        "source_epoch": source_epoch,
        "has_declared_sequence_order": (
            source_sequence is not None and source_epoch is not None
        ),
    }


def _same_source_binding(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
) -> bool:
    binding_fields = ("facility_id", "source_binding_id", "channel")
    for field_name in binding_fields:
        left_value = left.get(field_name)
        right_value = right.get(field_name)
        if (
            left_value is not None
            and right_value is not None
            and left_value != right_value
        ):
            return False
    return True


def _observed_time_relation(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
) -> str:
    left_status = left.get("observed_at_status")
    right_status = right.get("observed_at_status")
    left_time = left.get("observed_at_utc")
    right_time = right.get("observed_at_utc")
    if left_status is None:
        left_status = (
            parse_rfc3339_timestamp(left_time)["status"]
            if left_time is not None
            else TIMESTAMP_MISSING
        )
    if right_status is None:
        right_status = (
            parse_rfc3339_timestamp(right_time)["status"]
            if right_time is not None
            else TIMESTAMP_MISSING
        )
    if (
        left_status != TIMESTAMP_VALID
        or right_status != TIMESTAMP_VALID
        or left_time is None
        or right_time is None
    ):
        return ORDER_UNKNOWN
    return compare_rfc3339_instants(left_time, right_time)


def _sequence_relations(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
) -> tuple[str, str, bool]:
    left_sequence = left.get("source_sequence")
    right_sequence = right.get("source_sequence")
    _validate_optional_sequence(left_sequence)
    _validate_optional_sequence(right_sequence)

    if left_sequence is None or right_sequence is None:
        return ORDER_MISSING, ORDER_MISSING, False

    raw_relation = _three_way_relation(left_sequence, right_sequence)
    left_epoch = _source_epoch(left)
    right_epoch = _source_epoch(right)
    sequence_comparable = (
        left_epoch is not None
        and right_epoch is not None
        and left_epoch == right_epoch
    )
    if not sequence_comparable:
        return ORDER_NOT_COMPARABLE, raw_relation, False
    return raw_relation, raw_relation, True


def _has_ambiguous_sequence_reset(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    *,
    observed_relation: str,
    raw_sequence_relation: str,
) -> bool:
    if (
        observed_relation not in {ORDER_BEFORE, ORDER_AFTER}
        or raw_sequence_relation not in {ORDER_BEFORE, ORDER_AFTER}
        or observed_relation == raw_sequence_relation
    ):
        return False

    left_epoch = _source_epoch(left)
    right_epoch = _source_epoch(right)
    return left_epoch is None or right_epoch is None


def _source_epoch(candidate: Mapping[str, Any]) -> Any:
    source_epoch = candidate.get("source_epoch")
    session_epoch = candidate.get("source_session_epoch")
    if (
        source_epoch is not None
        and session_epoch is not None
        and source_epoch != session_epoch
    ):
        raise ValueError("source_epoch and source_session_epoch disagree")
    return source_epoch if source_epoch is not None else session_epoch


def _received_time_relation(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
) -> str:
    left_received_at = left.get("received_at_utc", left.get("received_at"))
    right_received_at = right.get("received_at_utc", right.get("received_at"))
    if left_received_at is None or right_received_at is None:
        return ORDER_UNKNOWN
    return compare_rfc3339_instants(left_received_at, right_received_at)


def _validate_optional_sequence(value: Any) -> None:
    if value is not None and (
        isinstance(value, bool) or not isinstance(value, int)
    ):
        raise ValueError("source_sequence must be an integer or null")


def _candidate_identifier(candidate: Mapping[str, Any]) -> Any:
    return candidate.get(
        "logical_candidate_key",
        candidate.get("canonical_observation_id", candidate.get("candidate_id")),
    )


def _three_way_relation(left: Any, right: Any) -> str:
    if left < right:
        return ORDER_BEFORE
    if left > right:
        return ORDER_AFTER
    return ORDER_EQUAL
