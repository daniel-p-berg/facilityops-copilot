from datetime import datetime


BLANK_VALUES = {"", "null", "none", "n/a"}
DEFAULT_STALE_AFTER_SECONDS = 300
ANALOG_OPERATORS = {">", ">=", "<", "<="}
MATCH_OPERATORS = {"==", "!="}
TRUE_VALUES = {"true", "1", "yes", "on"}
FALSE_VALUES = {"false", "0", "no", "off"}
INELIGIBLE_EVALUATION_STATUSES = {
    "BAD_QUALITY",
    "UNCERTAIN_QUALITY",
    "STALE",
    "OVERRIDDEN",
    "OUT_OF_SERVICE",
}


def has_value(value):
    """Return True when a field contains a meaningful value."""
    if value is None:
        return False

    return str(value).strip().lower() not in BLANK_VALUES


def normalize_text(value):
    """Normalize optional values to stripped strings for comparison."""
    if value is None:
        return ""

    return str(value).strip()


def parse_number(value):
    """Safely parse a numeric point or threshold value."""
    if not has_value(value):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_boolean(value):
    """Safely parse a boolean-style point or threshold value."""
    if not has_value(value):
        return None

    normalized_value = normalize_text(value).lower()
    if normalized_value in TRUE_VALUES:
        return True
    if normalized_value in FALSE_VALUES:
        return False

    return None


def compare_values(current_value, threshold_value, operator):
    """Compare parsed values with a supported operator."""
    if operator == "==":
        return current_value == threshold_value
    if operator == "!=":
        return current_value != threshold_value
    if operator == ">":
        return current_value > threshold_value
    if operator == ">=":
        return current_value >= threshold_value
    if operator == "<":
        return current_value < threshold_value
    if operator == "<=":
        return current_value <= threshold_value

    return False


def quality_status(quality):
    """Return an evaluation status for non-GOOD point quality."""
    normalized_quality = normalize_text(quality).upper()
    if normalized_quality == "UNKNOWN":
        normalized_quality = "UNCERTAIN"
    if normalized_quality == "BAD":
        return "BAD_QUALITY"
    if normalized_quality == "UNCERTAIN":
        return "UNCERTAIN_QUALITY"
    if normalized_quality == "STALE":
        return "STALE"

    return "UNCERTAIN_QUALITY"


def evaluation_result(is_triggered, evaluation_status):
    """Create a consistent rule evaluation result."""
    return {
        "is_triggered": is_triggered,
        "evaluation_status": evaluation_status,
    }


def parse_stale_after_value(value):
    """Parse sample stale window for evaluation, falling back to the default."""
    if not has_value(value):
        return DEFAULT_STALE_AFTER_SECONDS

    try:
        stale_after_seconds = int(float(value))
    except (TypeError, ValueError):
        return DEFAULT_STALE_AFTER_SECONDS

    return max(stale_after_seconds, 0)


def parse_timestamp(value):
    """Parse local ISO-style UTC timestamps used by the app."""
    if not has_value(value):
        return None

    try:
        return datetime.fromisoformat(normalize_text(value))
    except ValueError:
        return None


def sample_is_stale(
    source_timestamp=None,
    received_timestamp=None,
    stale_after_seconds=None,
    evaluation_timestamp=None,
):
    """Return True when a sample is older than its stale window."""
    sample_timestamp = parse_timestamp(received_timestamp) or parse_timestamp(source_timestamp)
    evaluated_at = parse_timestamp(evaluation_timestamp)
    if sample_timestamp is None or evaluated_at is None:
        return False

    elapsed_seconds = (evaluated_at - sample_timestamp).total_seconds()
    return elapsed_seconds > parse_stale_after_value(stale_after_seconds)


def sample_flag_is_true(value):
    """Return True for boolean-like sample flags."""
    if isinstance(value, bool):
        return value
    if value is None:
        return False

    normalized_value = normalize_text(value).lower()
    if normalized_value in TRUE_VALUES:
        return True
    if normalized_value in FALSE_VALUES or not normalized_value:
        return False

    return bool(value)


def sample_eligibility_status(
    quality,
    source_timestamp=None,
    received_timestamp=None,
    stale_after_seconds=None,
    overridden=False,
    out_of_service=False,
    evaluation_timestamp=None,
):
    """Return a process-alarm eligibility status for a current point sample."""
    if sample_flag_is_true(overridden):
        return "OVERRIDDEN"
    if sample_flag_is_true(out_of_service):
        return "OUT_OF_SERVICE"

    normalized_quality = normalize_text(quality).upper()
    if normalized_quality == "UNKNOWN":
        normalized_quality = "UNCERTAIN"
    if normalized_quality != "GOOD":
        return quality_status(normalized_quality)
    if sample_is_stale(
        source_timestamp=source_timestamp,
        received_timestamp=received_timestamp,
        stale_after_seconds=stale_after_seconds,
        evaluation_timestamp=evaluation_timestamp,
    ):
        return "STALE"

    return "ELIGIBLE"


def evaluate_alarm_rule(
    rule_type,
    operator,
    threshold_value,
    current_value,
    quality,
    enabled=True,
    source_timestamp=None,
    received_timestamp=None,
    stale_after_seconds=None,
    overridden=False,
    out_of_service=False,
    evaluation_timestamp=None,
):
    """Evaluate one alarm rule against one current point value."""
    if not enabled:
        return evaluation_result(False, "Disabled")

    if not has_value(current_value):
        return evaluation_result(False, "No current value")

    eligibility_status = sample_eligibility_status(
        quality,
        source_timestamp=source_timestamp,
        received_timestamp=received_timestamp,
        stale_after_seconds=stale_after_seconds,
        overridden=overridden,
        out_of_service=out_of_service,
        evaluation_timestamp=evaluation_timestamp,
    )
    if eligibility_status != "ELIGIBLE":
        return evaluation_result(False, eligibility_status)

    if rule_type == "analog_limit":
        if operator not in ANALOG_OPERATORS:
            return evaluation_result(False, "Unsupported operator")

        parsed_current_value = parse_number(current_value)
        parsed_threshold_value = parse_number(threshold_value)
        if parsed_current_value is None or parsed_threshold_value is None:
            return evaluation_result(False, "Invalid analog value")

        is_triggered = compare_values(
            parsed_current_value,
            parsed_threshold_value,
            operator,
        )
        return evaluation_result(is_triggered, "Triggered" if is_triggered else "Normal")

    if rule_type == "boolean_state":
        if operator not in MATCH_OPERATORS:
            return evaluation_result(False, "Unsupported operator")

        parsed_current_value = parse_boolean(current_value)
        parsed_threshold_value = parse_boolean(threshold_value)
        if parsed_current_value is None or parsed_threshold_value is None:
            return evaluation_result(False, "Invalid boolean value")

        is_triggered = compare_values(
            parsed_current_value,
            parsed_threshold_value,
            operator,
        )
        return evaluation_result(is_triggered, "Triggered" if is_triggered else "Normal")

    if rule_type == "enum_match":
        if operator not in MATCH_OPERATORS:
            return evaluation_result(False, "Unsupported operator")

        is_triggered = compare_values(
            normalize_text(current_value).lower(),
            normalize_text(threshold_value).lower(),
            operator,
        )
        return evaluation_result(is_triggered, "Triggered" if is_triggered else "Normal")

    return evaluation_result(False, "Unsupported rule type")


def parse_delay_seconds(value):
    """Parse rule delay seconds, treating blank or invalid values as no delay."""
    if not has_value(value):
        return 0

    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def pending_delay_has_elapsed(pending_started_at, delay_seconds, timestamp):
    """Return True when a pending alarm has satisfied its configured delay."""
    if delay_seconds <= 0:
        return True

    started_at = parse_timestamp(pending_started_at)
    evaluated_at = parse_timestamp(timestamp)
    if started_at is None or evaluated_at is None:
        return True

    elapsed_seconds = (evaluated_at - started_at).total_seconds()
    return elapsed_seconds >= delay_seconds


def active_generated_alarm_should_clear(evaluation):
    """Return True when an existing active generated alarm should clear."""
    if evaluation is None:
        return True

    if not evaluation["enabled"]:
        return True

    if evaluation["is_triggered"]:
        return False

    if evaluation["evaluation_status"] in INELIGIBLE_EVALUATION_STATUSES:
        return False

    if evaluation["rule_type"] != "analog_limit":
        return True

    if not has_value(evaluation["clear_value"]):
        return True

    if evaluation["operator"] not in ANALOG_OPERATORS:
        return True

    if normalize_text(evaluation["quality"]).upper() != "GOOD":
        return False

    parsed_current_value = parse_number(evaluation["current_value"])
    parsed_clear_value = parse_number(evaluation["clear_value"])
    if parsed_clear_value is None:
        return True
    if parsed_current_value is None:
        return False

    if evaluation["operator"] in {">", ">="}:
        return parsed_current_value < parsed_clear_value

    return parsed_current_value > parsed_clear_value


def active_generated_alarm_note(evaluation):
    """Return the note to store while an active generated alarm remains active."""
    if (
        evaluation["rule_type"] == "analog_limit"
        and has_value(evaluation["clear_value"])
        and evaluation["evaluation_status"] == "Normal"
    ):
        return "Waiting for clear value"

    return evaluation["evaluation_status"]
