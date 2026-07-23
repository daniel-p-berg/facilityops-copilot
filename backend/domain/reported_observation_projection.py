"""Pure, rebuildable reported-observation projection.

The projection selects a source-reported canonical indication inside one
facility/source/channel/point/mapping/replay scope.  It does not infer physical
state and does not use receipt order or database identity as source-order
tie-breakers.

Canonical candidate dictionaries use these fields:

* ``canonical_observation_id`` and optional ``source_native_record_ids``;
* ``facility_id``, ``replay_execution_id``, ``source_binding_id``, ``channel``,
  ``point_id``, and the mapping ``id``/``version``/``digest``;
* ``source_event_group_key`` (``source_event_identity`` is accepted as an
  alias), optional ``source_event_variant_digest``, ``source_sequence``, and
  ``source_epoch``; an optional ``source_event_conflict`` Boolean must already
  reflect the query's knowledge-time cutoff;
* ``observed_at_status``, ``observed_at_utc``, and ``received_at_utc``;
* ``normalized_value_type``, ``normalized_value``, and optional ``unit``.

An exact-redelivery digest must cover exact source payload plus material source
metadata.  Equal content without a source-event identity is never deduplicated.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from copy import deepcopy
from itertools import combinations
from typing import Any

from backend.domain.observation_semantics import (
    ORDER_AFTER,
    ORDER_BEFORE,
    ORDER_EQUAL,
    ORDER_NOT_COMPARABLE,
    ORDER_UNORDERED,
    TIMESTAMP_INVALID,
    TIMESTAMP_MISSING,
    TIMESTAMP_VALID,
    canonical_json_sha256,
    compare_rfc3339_instants,
    observation_ordering_facts,
    observation_temporal_facts,
    parse_rfc3339_timestamp,
    require_valid_rfc3339_utc,
)


NO_OBSERVATION = "NO_OBSERVATION"
NO_ELIGIBLE_REPORT = "NO_ELIGIBLE_REPORT"
REPORTED = "REPORTED"
CONFLICT_PRESENT = "CONFLICT_PRESENT"
UNORDERED = "UNORDERED"

EVENT_TIME_ELIGIBLE = "ELIGIBLE"
EVENT_TIME_AFTER_AS_OF = "AFTER_AS_OF_OBSERVED_AT"
EVENT_TIME_MISSING = "MISSING_OBSERVED_AT"
EVENT_TIME_INVALID = "INVALID_OBSERVED_AT"

_SCOPE_FIELDS = {
    "facility_id": ("facility_id",),
    "replay_execution_id": ("replay_execution_id",),
    "source_binding_id": ("source_binding_id",),
    "channel": ("channel",),
    "point_id": ("point_id", "canonical_point_definition_id"),
    "mapping_id": ("mapping_id",),
    "mapping_version": ("mapping_version",),
    "mapping_digest": ("mapping_digest",),
}

_PASSTHROUGH_FIELDS = (
    "normalized_value_type",
    "value_type",
    "normalized_value",
    "value",
    "normalized_unit",
    "unit",
    "time_basis",
    "source_quality",
    "source_quality_provenance",
    "synthetic",
    "synthetic_provenance",
    "report_material_digest",
    "material_digest",
)


def project_reported_observation(
    candidates: Iterable[Mapping[str, Any]],
    *,
    as_of_observed_at: str,
    known_by_received_at: str,
) -> dict[str, Any]:
    """Rebuild one reported-observation projection at two explicit cutoffs."""

    normalized_as_of = require_valid_rfc3339_utc(
        as_of_observed_at,
        field_name="as_of_observed_at",
    )
    normalized_known_by = require_valid_rfc3339_utc(
        known_by_received_at,
        field_name="known_by_received_at",
    )
    candidate_list = list(candidates)
    if any(not isinstance(candidate, Mapping) for candidate in candidate_list):
        raise ValueError("every projection candidate must be a mapping")

    scope = _projection_scope(candidate_list)
    if not candidate_list:
        return _projection_result(
            disposition=NO_OBSERVATION,
            scope=scope,
            as_of_observed_at=normalized_as_of,
            known_by_received_at=normalized_known_by,
        )

    prepared_candidates = [
        _prepare_candidate(candidate)
        for candidate in candidate_list
    ]
    known_candidates = [
        candidate
        for candidate in prepared_candidates
        if compare_rfc3339_instants(
            candidate["received_at_utc"],
            normalized_known_by,
        )
        in {ORDER_BEFORE, ORDER_EQUAL}
    ]
    if not known_candidates:
        return _projection_result(
            disposition=NO_ELIGIBLE_REPORT,
            scope=scope,
            as_of_observed_at=normalized_as_of,
            known_by_received_at=normalized_known_by,
        )

    logical_candidates = _deduplicate_exact_redeliveries(known_candidates)
    conflict_groups = _mark_known_source_event_conflicts(logical_candidates)
    for candidate in logical_candidates:
        candidate["event_time_eligibility"] = _event_time_eligibility(
            candidate,
            normalized_as_of,
        )
        candidate["selected"] = False
        candidate["unselected_reason"] = candidate["event_time_eligibility"]

    eligible_candidates = [
        candidate
        for candidate in logical_candidates
        if candidate["event_time_eligibility"] == EVENT_TIME_ELIGIBLE
    ]
    if not eligible_candidates:
        return _projection_result(
            disposition=NO_ELIGIBLE_REPORT,
            scope=scope,
            as_of_observed_at=normalized_as_of,
            known_by_received_at=normalized_known_by,
            known_candidate_count=len(known_candidates),
            logical_candidates=logical_candidates,
            conflict_groups=conflict_groups,
        )

    ordering_facts, maximal_candidates = _maximal_candidates(
        eligible_candidates,
        scope=scope,
    )
    identity_conflict_at_frontier = any(
        candidate["source_event_conflict"]
        for candidate in maximal_candidates
    )
    equal_order_material_conflict = _has_equal_order_material_conflict(
        maximal_candidates,
        ordering_facts,
    )
    frontier_ordering_issue = _frontier_has_ordering_issue(
        maximal_candidates,
        ordering_facts,
    )
    unselectable_non_older_facts = _unselectable_non_older_sequence_facts(
        logical_candidates,
        maximal_candidates,
        scope=scope,
    )
    ordering_facts.extend(unselectable_non_older_facts)

    if identity_conflict_at_frontier or equal_order_material_conflict:
        disposition = CONFLICT_PRESENT
    elif frontier_ordering_issue or unselectable_non_older_facts:
        disposition = UNORDERED
    elif len(
        {
            candidate["report_material_digest"]
            for candidate in maximal_candidates
        }
    ) > 1:
        disposition = UNORDERED
    else:
        disposition = REPORTED

    selected_candidate = None
    selected_value = None
    maximal_keys = {
        candidate["logical_candidate_key"]
        for candidate in maximal_candidates
    }
    if disposition == REPORTED:
        selected_candidate = _merge_equivalent_frontier(maximal_candidates)
        selected_value = _reported_value(selected_candidate)
        for candidate in logical_candidates:
            if candidate["logical_candidate_key"] in maximal_keys:
                candidate["selected"] = True
                candidate["unselected_reason"] = None
            elif candidate["event_time_eligibility"] == EVENT_TIME_ELIGIBLE:
                candidate["unselected_reason"] = "OLDER_SOURCE_ORDER"
    else:
        for candidate in logical_candidates:
            if candidate["logical_candidate_key"] in maximal_keys:
                candidate["unselected_reason"] = disposition
            elif candidate["event_time_eligibility"] == EVENT_TIME_ELIGIBLE:
                candidate["unselected_reason"] = "OLDER_SOURCE_ORDER"

    return _projection_result(
        disposition=disposition,
        scope=scope,
        as_of_observed_at=normalized_as_of,
        known_by_received_at=normalized_known_by,
        selected_candidate=selected_candidate,
        selected_value=selected_value,
        known_candidate_count=len(known_candidates),
        logical_candidates=logical_candidates,
        conflict_groups=conflict_groups,
        ordering_facts=ordering_facts,
        eligible_candidate_count=len(eligible_candidates),
    )


def build_reported_observation_projection(
    candidates: Iterable[Mapping[str, Any]],
    *,
    as_of_observed_at: str,
    known_by_received_at: str,
) -> dict[str, Any]:
    """Readable alias used by persistence and API integration."""

    return project_reported_observation(
        candidates,
        as_of_observed_at=as_of_observed_at,
        known_by_received_at=known_by_received_at,
    )


def _prepare_candidate(candidate: Mapping[str, Any]) -> dict[str, Any]:
    canonical_observation_id = _required_identifier(
        candidate,
        "canonical_observation_id",
        aliases=("candidate_id",),
    )
    source_event_group_key = _aliased_value(
        candidate,
        ("source_event_group_key", "source_event_identity"),
    )
    variant_digest = _aliased_value(
        candidate,
        (
            "source_event_variant_digest",
            "source_event_material_digest",
            "redelivery_digest",
            "logical_redelivery_digest",
        ),
    )
    received_at = _aliased_value(
        candidate,
        ("received_at_utc", "received_at"),
    )
    normalized_received_at = require_valid_rfc3339_utc(
        received_at,
        field_name=(
            f"candidate {canonical_observation_id} received_at_utc"
        ),
    )

    observed_at_status, observed_at_utc = _candidate_observed_time(
        candidate,
        canonical_observation_id=canonical_observation_id,
    )
    source_sequence = candidate.get("source_sequence")
    if source_sequence is not None and (
        isinstance(source_sequence, bool)
        or not isinstance(source_sequence, int)
    ):
        raise ValueError(
            f"candidate {canonical_observation_id} source_sequence "
            "must be an integer or null"
        )
    source_epoch = _aliased_value(
        candidate,
        ("source_epoch", "source_session_epoch"),
    )
    source_native_record_ids = candidate.get("source_native_record_ids", [])
    if source_native_record_ids is None:
        source_native_record_ids = []
    if (
        not isinstance(source_native_record_ids, list)
        or any(
            not isinstance(record_id, str) or not record_id
            for record_id in source_native_record_ids
        )
    ):
        raise ValueError(
            f"candidate {canonical_observation_id} "
            "source_native_record_ids must be a list of identifiers"
        )
    source_event_conflict = candidate.get("source_event_conflict", False)
    if not isinstance(source_event_conflict, bool):
        raise ValueError(
            f"candidate {canonical_observation_id} "
            "source_event_conflict must be a Boolean"
        )

    prepared = {
        "canonical_observation_id": canonical_observation_id,
        "source_native_record_ids": list(source_native_record_ids),
        "source_event_group_key": source_event_group_key,
        "source_event_identity": source_event_group_key,
        "source_event_variant_digest": variant_digest,
        "source_sequence": source_sequence,
        "source_epoch": source_epoch,
        "observed_at_status": observed_at_status,
        "observed_at_utc": observed_at_utc,
        "received_at_utc": normalized_received_at,
        "source_event_conflict": source_event_conflict,
    }
    for scope_name, aliases in _SCOPE_FIELDS.items():
        prepared[scope_name] = _aliased_value(candidate, aliases)
    for field_name in _PASSTHROUGH_FIELDS:
        if field_name in candidate:
            prepared[field_name] = deepcopy(candidate[field_name])

    report_material = _report_material(prepared)
    explicit_material_digest = _aliased_value(
        candidate,
        (
            "report_material_digest",
            "canonical_material_digest",
            "material_digest",
        ),
    )
    prepared["report_material_digest"] = (
        explicit_material_digest
        if explicit_material_digest is not None
        else canonical_json_sha256(report_material)
    )
    return prepared


def _candidate_observed_time(
    candidate: Mapping[str, Any],
    *,
    canonical_observation_id: str,
) -> tuple[str, str | None]:
    observed_at_status = candidate.get("observed_at_status")
    observed_at_utc = candidate.get("observed_at_utc")
    if observed_at_status is None:
        if observed_at_utc is None:
            observed_at_status = TIMESTAMP_MISSING
        else:
            parsed = parse_rfc3339_timestamp(observed_at_utc)
            observed_at_status = parsed["status"]
            observed_at_utc = parsed["utc"]

    if observed_at_status not in {
        TIMESTAMP_VALID,
        TIMESTAMP_MISSING,
        TIMESTAMP_INVALID,
    }:
        raise ValueError(
            f"candidate {canonical_observation_id} has unsupported "
            "observed_at_status"
        )

    if observed_at_status == TIMESTAMP_VALID:
        observed_at_utc = require_valid_rfc3339_utc(
            observed_at_utc,
            field_name=(
                f"candidate {canonical_observation_id} observed_at_utc"
            ),
        )
    elif observed_at_utc is not None:
        raise ValueError(
            f"candidate {canonical_observation_id} must not supply "
            "observed_at_utc when observed_at_status is not VALID"
        )
    return observed_at_status, observed_at_utc


def _projection_scope(
    candidates: list[Mapping[str, Any]],
) -> dict[str, Any]:
    scope = {}
    for scope_name, aliases in _SCOPE_FIELDS.items():
        values = [_aliased_value(candidate, aliases) for candidate in candidates]
        supplied_values = [value for value in values if value is not None]
        if not supplied_values:
            scope[scope_name] = None
            continue
        if len(supplied_values) != len(values):
            raise ValueError(
                f"projection candidates do not all declare {scope_name}"
            )
        first_value = supplied_values[0]
        if any(value != first_value for value in supplied_values[1:]):
            raise ValueError(
                f"projection candidates cross {scope_name} scope"
            )
        scope[scope_name] = first_value
    return scope


def _deduplicate_exact_redeliveries(
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    candidate_groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(
        list
    )
    for candidate in candidates:
        source_event_group_key = candidate["source_event_group_key"]
        variant_digest = candidate["source_event_variant_digest"]
        if source_event_group_key is not None and variant_digest is not None:
            deduplication_key = (
                "SOURCE_EVENT_VARIANT",
                source_event_group_key,
                variant_digest,
            )
        else:
            # A stable canonical-record identity can collapse duplicate query
            # rows. Content, a variant digest, timestamps, and values never
            # deduplicate a report that has no stable source-event identity.
            deduplication_key = (
                "CANONICAL_OBSERVATION",
                candidate["canonical_observation_id"],
            )
        candidate_groups[deduplication_key].append(candidate)

    logical_candidates = [
        _merge_exact_redelivery_group(group)
        for group in candidate_groups.values()
    ]
    return sorted(
        logical_candidates,
        key=lambda candidate: candidate["logical_candidate_key"],
    )


def _merge_exact_redelivery_group(
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    first = candidates[0]
    invariant_fields = (
        "source_event_group_key",
        "source_event_variant_digest",
        "source_sequence",
        "source_epoch",
        "observed_at_status",
        "observed_at_utc",
        "report_material_digest",
        *tuple(_SCOPE_FIELDS),
    )
    for candidate in candidates[1:]:
        for field_name in invariant_fields:
            if candidate.get(field_name) != first.get(field_name):
                raise ValueError(
                    "exact-redelivery candidates disagree materially on "
                    f"{field_name}"
                )

    canonical_observation_ids = sorted(
        {
            candidate["canonical_observation_id"]
            for candidate in candidates
        }
    )
    source_native_record_ids = sorted(
        {
            record_id
            for candidate in candidates
            for record_id in candidate["source_native_record_ids"]
        }
    )
    received_values = sorted(
        {
            candidate["received_at_utc"]
            for candidate in candidates
        },
        key=_timestamp_sort_key,
    )
    logical_key_material = (
        {
            "source_event_group_key": first["source_event_group_key"],
            "source_event_variant_digest": first[
                "source_event_variant_digest"
            ],
        }
        if first["source_event_group_key"] is not None
        and first["source_event_variant_digest"] is not None
        else {"canonical_observation_ids": canonical_observation_ids}
    )
    merged = {
        "logical_candidate_key": canonical_json_sha256(logical_key_material),
        "canonical_observation_id": (
            canonical_observation_ids[0]
            if len(canonical_observation_ids) == 1
            else None
        ),
        "canonical_observation_ids": canonical_observation_ids,
        "source_native_record_ids": source_native_record_ids,
        "source_event_group_key": first["source_event_group_key"],
        "source_event_identity": first["source_event_group_key"],
        "source_event_variant_digest": first[
            "source_event_variant_digest"
        ],
        "source_sequence": first["source_sequence"],
        "source_epoch": first["source_epoch"],
        "observed_at_status": first["observed_at_status"],
        "observed_at_utc": first["observed_at_utc"],
        "received_at_utc": received_values[0],
        "first_received_at_utc": received_values[0],
        "latest_redelivery_received_at_utc": received_values[-1],
        "known_received_at_utc_values": received_values,
        "candidate_row_count": len(candidates),
        "exact_redelivery_count": max(len(candidates) - 1, 0),
        "report_material_digest": first["report_material_digest"],
        "source_event_conflict": any(
            candidate["source_event_conflict"]
            for candidate in candidates
        ),
    }
    for field_name in _SCOPE_FIELDS:
        merged[field_name] = first.get(field_name)
    for field_name in _PASSTHROUGH_FIELDS:
        if field_name in first:
            merged[field_name] = deepcopy(first[field_name])
    merged["temporal_facts"] = observation_temporal_facts(merged)
    return merged


def _mark_known_source_event_conflicts(
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    event_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        source_event_group_key = candidate["source_event_group_key"]
        if source_event_group_key is not None:
            event_groups[source_event_group_key].append(candidate)

    conflict_groups = []
    for source_event_group_key, grouped_candidates in event_groups.items():
        variant_keys = {
            _known_variant_key(candidate)
            for candidate in grouped_candidates
        }
        precomputed_conflict = any(
            candidate["source_event_conflict"]
            for candidate in grouped_candidates
        )
        if len(variant_keys) <= 1 and not precomputed_conflict:
            continue
        for candidate in grouped_candidates:
            candidate["source_event_conflict"] = True
        conflict_groups.append(
            {
                "source_event_group_key": source_event_group_key,
                "known_variant_count": len(variant_keys),
                "known_canonical_variant_count": len(variant_keys),
                "known_native_variant_count_lower_bound": max(
                    len(variant_keys),
                    2 if precomputed_conflict else 0,
                ),
                "precomputed_source_event_conflict": precomputed_conflict,
                "conflicting_variant_without_canonical_candidate": (
                    precomputed_conflict and len(variant_keys) <= 1
                ),
                "variant_keys": sorted(variant_keys),
                "logical_candidate_keys": sorted(
                    candidate["logical_candidate_key"]
                    for candidate in grouped_candidates
                ),
                "canonical_observation_ids": sorted(
                    {
                        canonical_observation_id
                        for candidate in grouped_candidates
                        for canonical_observation_id in candidate[
                            "canonical_observation_ids"
                        ]
                    }
                ),
            }
        )

    for candidate in candidates:
        if (
            candidate["source_event_group_key"] is not None
            or not candidate["source_event_conflict"]
        ):
            continue
        conflict_groups.append(
            {
                "source_event_group_key": None,
                "known_variant_count": 1,
                "known_canonical_variant_count": 1,
                "known_native_variant_count_lower_bound": 2,
                "precomputed_source_event_conflict": True,
                "conflicting_variant_without_canonical_candidate": True,
                "variant_keys": [_known_variant_key(candidate)],
                "logical_candidate_keys": [
                    candidate["logical_candidate_key"]
                ],
                "canonical_observation_ids": list(
                    candidate["canonical_observation_ids"]
                ),
            }
        )
    return sorted(
        conflict_groups,
        key=lambda conflict: (
            conflict["source_event_group_key"] is None,
            conflict["source_event_group_key"] or "",
            conflict["logical_candidate_keys"],
        ),
    )


def _known_variant_key(candidate: Mapping[str, Any]) -> str:
    variant_digest = candidate.get("source_event_variant_digest")
    if variant_digest is not None:
        return f"DIGEST:{variant_digest}"
    canonical_ids = ",".join(candidate["canonical_observation_ids"])
    return f"UNDECLARED:{canonical_ids}"


def _event_time_eligibility(
    candidate: Mapping[str, Any],
    as_of_observed_at: str,
) -> str:
    observed_at_status = candidate["observed_at_status"]
    if observed_at_status == TIMESTAMP_MISSING:
        return EVENT_TIME_MISSING
    if observed_at_status == TIMESTAMP_INVALID:
        return EVENT_TIME_INVALID
    observed_relation = compare_rfc3339_instants(
        candidate["observed_at_utc"],
        as_of_observed_at,
    )
    if observed_relation == ORDER_AFTER:
        return EVENT_TIME_AFTER_AS_OF
    return EVENT_TIME_ELIGIBLE


def _maximal_candidates(
    candidates: list[dict[str, Any]],
    *,
    scope: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    dominated_candidate_keys = set()
    ordering_facts = []
    for left, right in combinations(
        sorted(candidates, key=lambda item: item["logical_candidate_key"]),
        2,
    ):
        facts = observation_ordering_facts(left, right)
        facts.update(
            {
                "left_logical_candidate_key": left[
                    "logical_candidate_key"
                ],
                "right_logical_candidate_key": right[
                    "logical_candidate_key"
                ],
                "left_canonical_observation_ids": left[
                    "canonical_observation_ids"
                ],
                "right_canonical_observation_ids": right[
                    "canonical_observation_ids"
                ],
                **dict(scope),
            }
        )
        ordering_facts.append(facts)
        if facts["relation"] == ORDER_BEFORE:
            dominated_candidate_keys.add(left["logical_candidate_key"])
        elif facts["relation"] == ORDER_AFTER:
            dominated_candidate_keys.add(right["logical_candidate_key"])

    maximal_candidates = [
        candidate
        for candidate in candidates
        if candidate["logical_candidate_key"] not in dominated_candidate_keys
    ]
    return ordering_facts, maximal_candidates


def _has_equal_order_material_conflict(
    maximal_candidates: list[dict[str, Any]],
    ordering_facts: list[dict[str, Any]],
) -> bool:
    by_key = {
        candidate["logical_candidate_key"]: candidate
        for candidate in maximal_candidates
    }
    for facts in ordering_facts:
        if facts["relation"] != ORDER_EQUAL:
            continue
        left = by_key.get(facts["left_logical_candidate_key"])
        right = by_key.get(facts["right_logical_candidate_key"])
        if (
            left is not None
            and right is not None
            and left["report_material_digest"]
            != right["report_material_digest"]
        ):
            return True
    return False


def _frontier_has_ordering_issue(
    maximal_candidates: list[dict[str, Any]],
    ordering_facts: list[dict[str, Any]],
) -> bool:
    maximal_keys = {
        candidate["logical_candidate_key"]
        for candidate in maximal_candidates
    }
    return any(
        facts["relation"] in {ORDER_UNORDERED, ORDER_NOT_COMPARABLE}
        and (
            facts["left_logical_candidate_key"] in maximal_keys
            or facts["right_logical_candidate_key"] in maximal_keys
        )
        for facts in ordering_facts
    )


def _unselectable_non_older_sequence_facts(
    logical_candidates: list[dict[str, Any]],
    maximal_candidates: list[dict[str, Any]],
    *,
    scope: Mapping[str, Any],
) -> list[dict[str, Any]]:
    facts = []
    unselectable_candidates = [
        candidate
        for candidate in logical_candidates
        if candidate["event_time_eligibility"]
        in {EVENT_TIME_MISSING, EVENT_TIME_INVALID}
    ]
    for candidate in unselectable_candidates:
        if candidate["source_sequence"] is None or candidate["source_epoch"] is None:
            continue
        for frontier_candidate in maximal_candidates:
            if (
                frontier_candidate["source_sequence"] is None
                or frontier_candidate["source_epoch"]
                != candidate["source_epoch"]
                or candidate["source_sequence"]
                < frontier_candidate["source_sequence"]
            ):
                continue
            facts.append(
                {
                    "relation": ORDER_UNORDERED,
                    "issue": (
                        "NEWER_SEQUENCE_HAS_NO_VALID_OBSERVED_AT"
                        if candidate["source_sequence"]
                        > frontier_candidate["source_sequence"]
                        else "SAME_SEQUENCE_HAS_NO_VALID_OBSERVED_AT"
                    ),
                    "unselectable_logical_candidate_key": candidate[
                        "logical_candidate_key"
                    ],
                    "frontier_logical_candidate_key": frontier_candidate[
                        "logical_candidate_key"
                    ],
                    "unselectable_canonical_observation_ids": candidate[
                        "canonical_observation_ids"
                    ],
                    "frontier_canonical_observation_ids": frontier_candidate[
                        "canonical_observation_ids"
                    ],
                    **dict(scope),
                }
            )
    return sorted(
        facts,
        key=lambda item: (
            item["unselectable_logical_candidate_key"],
            item["frontier_logical_candidate_key"],
        ),
    )


def _merge_equivalent_frontier(
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    candidates = sorted(
        candidates,
        key=lambda candidate: candidate["logical_candidate_key"],
    )
    first = candidates[0]
    merged = deepcopy(first)
    merged["logical_candidate_keys"] = [
        candidate["logical_candidate_key"]
        for candidate in candidates
    ]
    merged["canonical_observation_ids"] = sorted(
        {
            observation_id
            for candidate in candidates
            for observation_id in candidate["canonical_observation_ids"]
        }
    )
    merged["canonical_observation_id"] = (
        merged["canonical_observation_ids"][0]
        if len(merged["canonical_observation_ids"]) == 1
        else None
    )
    merged["source_native_record_ids"] = sorted(
        {
            record_id
            for candidate in candidates
            for record_id in candidate["source_native_record_ids"]
        }
    )
    merged["equivalent_frontier_candidate_count"] = len(candidates)
    if len(candidates) > 1:
        received_values = sorted(
            {
                received_at
                for candidate in candidates
                for received_at in candidate[
                    "known_received_at_utc_values"
                ]
            },
            key=_timestamp_sort_key,
        )
        merged["logical_candidate_key"] = None
        merged["source_event_group_key"] = None
        merged["source_event_identity"] = None
        merged["source_event_variant_digest"] = None
        merged["received_at_utc"] = received_values[0]
        merged["first_received_at_utc"] = received_values[0]
        merged["latest_redelivery_received_at_utc"] = received_values[-1]
        merged["known_received_at_utc_values"] = received_values
        merged["candidate_row_count"] = sum(
            candidate["candidate_row_count"]
            for candidate in candidates
        )
        merged["exact_redelivery_count"] = sum(
            candidate["exact_redelivery_count"]
            for candidate in candidates
        )
        merged["temporal_facts"] = observation_temporal_facts(merged)
    return merged


def _reported_value(candidate: Mapping[str, Any]) -> dict[str, Any]:
    value_type = candidate.get(
        "normalized_value_type",
        candidate.get("value_type"),
    )
    value = (
        candidate["normalized_value"]
        if "normalized_value" in candidate
        else candidate.get("value")
    )
    unit = candidate.get("unit", candidate.get("normalized_unit"))
    return {
        "value_type": value_type,
        "value": deepcopy(value),
        "unit": unit,
    }


def _report_material(candidate: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "point_id": candidate.get("point_id"),
        "mapping_id": candidate.get("mapping_id"),
        "mapping_version": candidate.get("mapping_version"),
        "mapping_digest": candidate.get("mapping_digest"),
        "observed_at_status": candidate.get("observed_at_status"),
        "observed_at_utc": candidate.get("observed_at_utc"),
        "source_sequence": candidate.get("source_sequence"),
        "source_epoch": candidate.get("source_epoch"),
        "value_type": candidate.get(
            "normalized_value_type",
            candidate.get("value_type"),
        ),
        "value": (
            candidate["normalized_value"]
            if "normalized_value" in candidate
            else candidate.get("value")
        ),
        "unit": candidate.get("unit", candidate.get("normalized_unit")),
        "time_basis": candidate.get("time_basis"),
        "source_quality": candidate.get(
            "source_quality",
            candidate.get("source_quality_provenance"),
        ),
    }


def _projection_result(
    *,
    disposition: str,
    scope: Mapping[str, Any],
    as_of_observed_at: str,
    known_by_received_at: str,
    selected_candidate: Mapping[str, Any] | None = None,
    selected_value: Mapping[str, Any] | None = None,
    known_candidate_count: int = 0,
    logical_candidates: list[dict[str, Any]] | None = None,
    conflict_groups: list[dict[str, Any]] | None = None,
    ordering_facts: list[dict[str, Any]] | None = None,
    eligible_candidate_count: int = 0,
) -> dict[str, Any]:
    visible_candidates = sorted(
        (deepcopy(candidate) for candidate in (logical_candidates or [])),
        key=lambda candidate: candidate["logical_candidate_key"],
    )
    return {
        "disposition": disposition,
        "projection_scope": dict(scope),
        "as_of_observed_at": as_of_observed_at,
        "known_by_received_at": known_by_received_at,
        "selected_candidate": (
            deepcopy(selected_candidate)
            if selected_candidate is not None
            else None
        ),
        "selected_value": (
            deepcopy(selected_value)
            if selected_value is not None
            else None
        ),
        "known_candidate_count": known_candidate_count,
        "logical_candidate_count": len(visible_candidates),
        "eligible_candidate_count": eligible_candidate_count,
        "exact_redelivery_count": sum(
            candidate["exact_redelivery_count"]
            for candidate in visible_candidates
        ),
        "visible_candidates": visible_candidates,
        "conflict_groups": deepcopy(conflict_groups or []),
        "ordering_facts": deepcopy(ordering_facts or []),
    }


def _required_identifier(
    candidate: Mapping[str, Any],
    field_name: str,
    *,
    aliases: tuple[str, ...] = (),
) -> str:
    value = _aliased_value(candidate, (field_name, *aliases))
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _aliased_value(
    candidate: Mapping[str, Any],
    aliases: tuple[str, ...],
) -> Any:
    supplied = [
        candidate[alias]
        for alias in aliases
        if alias in candidate and candidate[alias] is not None
    ]
    if not supplied:
        return None
    first_value = supplied[0]
    if any(value != first_value for value in supplied[1:]):
        raise ValueError(f"candidate aliases {aliases!r} disagree")
    return first_value


def _timestamp_sort_key(value: str) -> tuple[str, str]:
    parsed = parse_rfc3339_timestamp(value)
    if parsed["status"] != TIMESTAMP_VALID:  # pragma: no cover - prepared first
        raise ValueError("timestamp sort key requires valid RFC 3339 text")
    normalized = parsed["utc"]
    whole, separator, remainder = normalized.partition(".")
    if not separator:
        return whole, ""
    return whole, remainder.removesuffix("Z").rstrip("0")
