"""Deterministic execution of allowlisted synthetic observation replays."""

from __future__ import annotations

import json
import uuid
from collections import defaultdict
from copy import deepcopy
from functools import cmp_to_key
from pathlib import Path
from typing import Any

from backend.domain.observation_semantics import (
    ORDER_AFTER,
    ORDER_BEFORE,
    ORDER_EQUAL,
    ORDER_UNORDERED,
    canonical_json_sha256,
    canonical_json_text,
    compare_rfc3339_instants,
    decode_signed_int32_be,
    normalize_decimal_text,
    normalize_direct_enum,
    normalize_strict_boolean,
    observation_ordering_facts,
    observation_temporal_facts,
    parse_rfc3339_timestamp,
)
from backend.domain.reported_observation_projection import (
    build_reported_observation_projection,
)
from backend.services.observation_package_service import (
    CANONICALIZER_VERSION,
    load_replay_package,
)
from backend.services.observation_store import (
    get_canonical_lineage,
    get_canonical_observation,
    get_replay_execution,
    get_reproducibility_manifest,
    get_source_native_record,
    list_canonical_observations,
    list_redelivery_groups,
    list_source_native_records,
    persist_replay_execution,
    projection_candidates,
    require_projection_scope,
)


MAX_IDEMPOTENCY_KEY_LENGTH = 256
EXECUTION_ID_PREFIX = "REPLAY-EXECUTION-"

SOURCE_REPORTED_TIME_BASIS = "SOURCE_REPORTED_OBSERVED_AT"


def execute_replay_package(
    db_path: Path | str,
    *,
    facility_id: str,
    package_id: str,
    package_version: str,
    idempotency_key: str,
    replay_execution_id: str | None = None,
    inject_failure_after_native_record: int | None = None,
) -> dict[str, Any]:
    """Validate, canonicalize, and atomically publish one replay execution."""

    idempotency_key = _require_idempotency_key(idempotency_key)
    loaded = load_replay_package(facility_id, package_id, package_version)
    execution_id = (
        _require_execution_id(replay_execution_id)
        if replay_execution_id is not None
        else f"{EXECUTION_ID_PREFIX}{uuid.uuid4()}"
    )
    plan = build_replay_plan(
        loaded,
        replay_execution_id=execution_id,
        requested_replay_execution_id=replay_execution_id,
        idempotency_key=idempotency_key,
    )
    persisted = persist_replay_execution(
        db_path,
        plan,
        inject_failure_after_native_record=inject_failure_after_native_record,
    )
    stored_execution = get_replay_execution(
        db_path,
        facility_id,
        persisted["replay_execution_id"],
    )
    return {
        "replay_execution": stored_execution,
        "idempotent_replay": persisted["idempotent_replay"],
        "statement": (
            "This synthetic replay demonstrates deterministic software "
            "handling of source reports. It does not establish physical "
            "equipment, system, facility, compliance, safety, authorization, "
            "or recovery outcomes."
        ),
    }


def build_replay_plan(
    loaded: dict[str, Any],
    *,
    replay_execution_id: str,
    requested_replay_execution_id: str | None,
    idempotency_key: str,
) -> dict[str, Any]:
    """Prepare a complete replay plan without opening a database."""

    replay_execution_id = _require_execution_id(replay_execution_id)
    if requested_replay_execution_id is not None:
        requested_replay_execution_id = _require_execution_id(
            requested_replay_execution_id
        )
        if requested_replay_execution_id != replay_execution_id:
            raise ValueError(
                "requested_replay_execution_id must match the resolved "
                "replay_execution_id"
            )
    idempotency_key = _require_idempotency_key(idempotency_key)
    facility_id = loaded["facility_id"]
    topology = loaded["topology"]
    mappings = loaded["mapping_package"]["mappings"]
    source_bindings = loaded["mapping_package"]["source_bindings"]
    mapping_by_identity = {
        (mapping["mapping_id"], mapping["mapping_version"]): mapping
        for mapping in mappings
    }
    binding_by_id = {
        binding["source_binding_id"]: binding for binding in source_bindings
    }

    request_material = {
        "facility_id": facility_id,
        "package_id": loaded["package_id"],
        "package_version": loaded["package_version"],
        "package_digest": loaded["content_digest"],
        "requested_replay_execution_id": requested_replay_execution_id,
    }
    request_digest = canonical_json_sha256(request_material)

    native_contexts, event_groups, deliveries = _prepare_native_records(
        loaded,
        replay_execution_id=replay_execution_id,
        facility_id=facility_id,
        mapping_by_identity=mapping_by_identity,
        binding_by_id=binding_by_id,
    )
    _attach_ordering_facts(native_contexts)
    canonical_rows, lineage_specs, decode_issues = _canonicalize_native_records(
        native_contexts,
        replay_execution_id=replay_execution_id,
        facility_id=facility_id,
        mapping_by_identity=mapping_by_identity,
    )
    lineage_rows = _lineage_rows(
        lineage_specs,
        canonical_rows=canonical_rows,
    )
    annotations = _annotation_rows(
        loaded["narrative"],
        replay_execution_id=replay_execution_id,
    )
    projection_summary = _projection_summary(
        canonical_rows,
        lineage_rows=lineage_rows,
        native_contexts=native_contexts,
        binding_by_id=binding_by_id,
        oracle=loaded["oracle"],
    )
    _validate_structural_oracle_against_plan(
        loaded=loaded,
        event_groups=event_groups,
        deliveries=deliveries,
        native_contexts=native_contexts,
        canonical_rows=canonical_rows,
        lineage_rows=lineage_rows,
    )
    normalized_semantic_digest, semantic_digests = _normalized_semantic_digest(
        loaded=loaded,
        native_contexts=native_contexts,
        deliveries=deliveries,
        canonical_rows=canonical_rows,
        lineage_rows=lineage_rows,
        decode_issues=decode_issues,
        annotations=annotations,
        projection_summary=projection_summary,
    )
    recorded_at = _latest_timestamp(
        [context["native_row"]["received_at_utc"] for context in native_contexts]
    )
    execution = {
        "replay_execution_id": replay_execution_id,
        "facility_id": facility_id,
        "package_id": loaded["package_id"],
        "package_version": loaded["package_version"],
        "package_digest": loaded["content_digest"],
        "topology_id": topology["topology_id"],
        "topology_version": topology["topology_version"],
        "topology_digest": topology["content_digest"],
        "canonicalizer_version": CANONICALIZER_VERSION,
        "request_digest": request_digest,
        "status": "COMPLETED",
        "recorded_at": recorded_at,
        "normalized_semantic_digest": normalized_semantic_digest,
    }
    manifest = _build_reproducibility_manifest(
        loaded=loaded,
        execution=execution,
        native_contexts=native_contexts,
        deliveries=deliveries,
        canonical_rows=canonical_rows,
        lineage_rows=lineage_rows,
        decode_issues=decode_issues,
        annotations=annotations,
        projection_summary=projection_summary,
        semantic_digests=semantic_digests,
    )
    manifest_digest = canonical_json_sha256(manifest)
    manifest["manifest_digest"] = manifest_digest

    return {
        "request": {"idempotency_key": idempotency_key},
        "topology_snapshot": {
            "topology_id": topology["topology_id"],
            "topology_version": topology["topology_version"],
            "content_digest": topology["content_digest"],
            "facility_id": facility_id,
            "manifest_json": canonical_json_text(loaded["topology_manifest"]),
        },
        "source_bindings": [
            {
                "facility_id": facility_id,
                "source_binding_id": binding["source_binding_id"],
                "source_id": binding["source_id"],
                "channel": binding["channel"],
                "dependency_provenance_json": canonical_json_text(
                    binding["dependency_provenance"]
                ),
            }
            for binding in source_bindings
        ],
        "mapping_snapshots": [
            {
                "mapping_id": mapping["mapping_id"],
                "mapping_version": mapping["mapping_version"],
                "content_digest": mapping["content_digest"],
                "facility_id": facility_id,
                "topology_id": topology["topology_id"],
                "topology_version": topology["topology_version"],
                "topology_digest": topology["content_digest"],
                "source_binding_id": mapping["source_binding_id"],
                "definition_json": canonical_json_text(mapping),
            }
            for mapping in mappings
        ],
        "package_snapshot": {
            "package_id": loaded["package_id"],
            "package_version": loaded["package_version"],
            "content_digest": loaded["content_digest"],
            "facility_id": facility_id,
            "topology_id": topology["topology_id"],
            "topology_version": topology["topology_version"],
            "topology_digest": topology["content_digest"],
            "manifest_json": canonical_json_text(loaded["manifest"]),
        },
        "execution": execution,
        "source_event_groups": event_groups,
        "deliveries": deliveries,
        "source_native_records": [
            context["native_row"] for context in native_contexts
        ],
        "canonical_observations": canonical_rows,
        "lineage": lineage_rows,
        "decode_issues": decode_issues,
        "annotations": annotations,
        "reproducibility_manifest": {
            "replay_execution_id": replay_execution_id,
            "manifest_digest": manifest_digest,
            "normalized_semantic_digest": normalized_semantic_digest,
            "manifest_json": canonical_json_text(manifest),
        },
    }


def get_reported_observation_projection(
    db_path: Path | str,
    *,
    facility_id: str,
    replay_execution_id: str,
    source_binding_id: str,
    point_id: str,
    mapping_id: str,
    mapping_version: str,
    mapping_digest: str,
    as_of_observed_at: str,
    known_by_received_at: str,
) -> dict[str, Any]:
    """Rebuild one source-scoped reported-observation projection."""

    get_replay_execution(db_path, facility_id, replay_execution_id)
    resolved_scope = require_projection_scope(
        db_path,
        facility_id,
        replay_execution_id,
        source_binding_id=source_binding_id,
        point_id=point_id,
        mapping_id=mapping_id,
        mapping_version=mapping_version,
        mapping_digest=mapping_digest,
    )
    candidates = projection_candidates(
        db_path,
        facility_id,
        replay_execution_id,
        source_binding_id=source_binding_id,
        point_id=point_id,
        mapping_id=mapping_id,
        mapping_version=mapping_version,
        mapping_digest=mapping_digest,
        known_by_received_at=known_by_received_at,
    )
    projection = build_reported_observation_projection(
        candidates,
        as_of_observed_at=as_of_observed_at,
        known_by_received_at=known_by_received_at,
    )
    if not candidates:
        projection["projection_scope"].update(
            {
                **resolved_scope,
            }
        )
    return projection


def _prepare_native_records(
    loaded: dict[str, Any],
    *,
    replay_execution_id: str,
    facility_id: str,
    mapping_by_identity: dict[tuple[str, str], dict[str, Any]],
    binding_by_id: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    native_contexts = []
    event_groups: list[dict[str, Any]] = []
    deliveries: list[dict[str, Any]] = []
    group_rows: dict[str, dict[str, Any]] = {}
    group_variants: dict[str, set[str]] = defaultdict(set)

    for ingestion_ordinal, delivery in enumerate(loaded["deliveries"], start=1):
        delivery_id = delivery["delivery_id"]
        binding_id = delivery["source_binding_id"]
        binding = binding_by_id[binding_id]
        mapping_pin = delivery["mapping"]
        mapping = mapping_by_identity[
            (mapping_pin["mapping_id"], mapping_pin["mapping_version"])
        ]
        source_event = delivery["source_event"]
        group_key, identity_kind = _source_event_group_key(
            facility_id=facility_id,
            binding=binding,
            source_event=source_event,
            delivery_id=delivery_id,
        )
        material = {
            "payload": delivery["payload"],
            "observed_at": delivery.get("observed_at"),
            "source_event": source_event,
            "source_quality": delivery["source_quality"],
            "source_metadata": delivery["source_metadata"],
        }
        variant_digest = canonical_json_sha256(material)
        if identity_kind == "NO_STABLE_ID":
            classification = "NO_STABLE_ID"
        elif not group_variants[group_key]:
            classification = "NEW_EVENT"
        elif variant_digest in group_variants[group_key]:
            classification = "EXACT_REDELIVERY"
        else:
            classification = "CONFLICTING_REDELIVERY"
        group_variants[group_key].add(variant_digest)

        if group_key not in group_rows:
            group_row = {
                "replay_execution_id": replay_execution_id,
                "source_event_group_key": group_key,
                "facility_id": facility_id,
                "source_binding_id": binding_id,
                "identity_kind": identity_kind,
                "source_event_id": source_event.get("event_id"),
                "source_session_epoch": source_event.get("session_epoch"),
                "source_sequence": source_event.get("sequence"),
            }
            group_rows[group_key] = group_row
            event_groups.append(group_row)

        observed = parse_rfc3339_timestamp(delivery.get("observed_at"))
        received = parse_rfc3339_timestamp(delivery["received_at"])
        if received["status"] != "VALID":  # package validation guards this
            raise ValueError(f"Delivery {delivery_id} has invalid received_at")
        source_native_record_id = _run_scoped_id(
            "SOURCE-NATIVE",
            replay_execution_id,
            delivery_id,
        )
        payload_digest = canonical_json_sha256(delivery["payload"])
        native_row = {
            "source_native_record_id": source_native_record_id,
            "replay_execution_id": replay_execution_id,
            "delivery_id": delivery_id,
            "facility_id": facility_id,
            "source_binding_id": binding_id,
            "source_event_group_key": group_key,
            "source_event_variant_digest": variant_digest,
            "mapping_id": mapping["mapping_id"],
            "mapping_version": mapping["mapping_version"],
            "mapping_digest": mapping["content_digest"],
            "payload_json": canonical_json_text(delivery["payload"]),
            "payload_digest": payload_digest,
            "original_observed_at_text": (
                delivery.get("observed_at")
                if isinstance(delivery.get("observed_at"), str)
                else None
            ),
            "original_timezone_offset": observed["raw_offset"],
            "timestamp_precision": observed["precision"],
            "fractional_second_digits": observed["fractional_second_digits"],
            "observed_at_status": observed["status"],
            "observed_at_utc": observed["utc"],
            "received_at_utc": received["utc"],
            "source_sequence": source_event.get("sequence"),
            "source_session_epoch": source_event.get("session_epoch"),
            "source_quality_json": canonical_json_text(
                delivery["source_quality"]
            ),
            "source_metadata_json": canonical_json_text(
                delivery["source_metadata"]
            ),
            "transport_provenance_json": canonical_json_text(
                delivery["transport_provenance"]
            ),
            "synthetic_provenance_json": canonical_json_text(
                {
                    **delivery["synthetic_provenance"],
                    "replay_package_id": loaded["package_id"],
                    "replay_package_version": loaded["package_version"],
                    "replay_package_digest": loaded["content_digest"],
                }
            ),
            "ordering_facts_json": "{}",
        }
        delivery_request_digest = canonical_json_sha256(
            {
                "delivery_id": delivery_id,
                "received_at": received["utc"],
                "material": material,
                "mapping": mapping_pin,
            }
        )
        delivery_row = {
            "replay_execution_id": replay_execution_id,
            "delivery_id": delivery_id,
            "facility_id": facility_id,
            "ingestion_ordinal": ingestion_ordinal,
            "idempotency_key": f"repository-package:{delivery_id}",
            "request_digest": delivery_request_digest,
            "source_binding_id": binding_id,
            "source_event_group_key": group_key,
            "redelivery_classification": classification,
            "received_at_utc": received["utc"],
            "source_native_record_id": source_native_record_id,
        }
        deliveries.append(delivery_row)
        native_contexts.append(
            {
                "delivery": delivery,
                "delivery_row": delivery_row,
                "native_row": native_row,
                "binding": binding,
                "mapping": mapping,
                "identity_kind": identity_kind,
                "classification": classification,
                "source_event": source_event,
            }
        )
    return native_contexts, event_groups, deliveries


def _source_event_group_key(
    *,
    facility_id: str,
    binding: dict[str, Any],
    source_event: dict[str, Any],
    delivery_id: str,
) -> tuple[str, str]:
    event_id = source_event.get("event_id")
    sequence = source_event.get("sequence")
    epoch = source_event.get("session_epoch")
    namespace = {
        "facility_id": facility_id,
        "source_id": binding["source_id"],
        "channel": binding["channel"],
        "source_session_epoch": epoch,
    }
    if event_id is not None:
        identity_kind = "SOURCE_EVENT_ID"
        identity = {**namespace, "source_event_id": event_id}
    elif sequence is not None and epoch is not None:
        identity_kind = "SEQUENCE_IN_DECLARED_EPOCH"
        identity = {**namespace, "source_sequence": sequence}
    else:
        identity_kind = "NO_STABLE_ID"
        identity = {**namespace, "delivery_id": delivery_id}
    return (
        f"EVENT-GROUP-{canonical_json_sha256(identity)[:32]}",
        identity_kind,
    )


def _attach_ordering_facts(native_contexts: list[dict[str, Any]]) -> None:
    prior_by_binding: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for context in native_contexts:
        native = context["native_row"]
        candidate = {
            "source_native_record_id": native["source_native_record_id"],
            "facility_id": native["facility_id"],
            "source_binding_id": native["source_binding_id"],
            "channel": context["binding"]["channel"],
            "observed_at_status": native["observed_at_status"],
            "observed_at_utc": native["observed_at_utc"],
            "received_at_utc": native["received_at_utc"],
            "source_sequence": native["source_sequence"],
            "source_session_epoch": native["source_session_epoch"],
        }
        comparisons = [
            observation_ordering_facts(prior, candidate)
            for prior in prior_by_binding[native["source_binding_id"]]
        ]
        native["ordering_facts_json"] = canonical_json_text(
            {
                "temporal_facts": observation_temporal_facts(candidate),
                "comparisons_with_prior_deliveries": comparisons,
                "out_of_order_arrival": any(
                    fact["out_of_order_arrival"] for fact in comparisons
                ),
                "sequence_time_disagreement": any(
                    fact["sequence_time_disagreement"] for fact in comparisons
                ),
                "ambiguous_sequence_reset": any(
                    fact["ambiguous_sequence_reset"] for fact in comparisons
                ),
            }
        )
        prior_by_binding[native["source_binding_id"]].append(candidate)


def _canonicalize_native_records(
    native_contexts: list[dict[str, Any]],
    *,
    replay_execution_id: str,
    facility_id: str,
    mapping_by_identity: dict[tuple[str, str], dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    canonical_rows: list[dict[str, Any]] = []
    lineage_specs: list[dict[str, Any]] = []
    decode_issues: list[dict[str, Any]] = []
    direct_observations: dict[tuple[Any, ...], dict[str, Any]] = {}
    issue_keys: set[tuple[Any, ...]] = set()
    register_groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)

    for context in native_contexts:
        mapping = context["mapping"]
        transformation = mapping["transformation"]
        if transformation["kind"] == "FIELD_SET":
            _canonicalize_field_set(
                context,
                transformation=transformation,
                replay_execution_id=replay_execution_id,
                facility_id=facility_id,
                canonical_rows=canonical_rows,
                lineage_specs=lineage_specs,
                decode_issues=decode_issues,
                direct_observations=direct_observations,
                issue_keys=issue_keys,
            )
        elif transformation["kind"] == "REGISTER_PAIR_SIGNED_INT32_BE":
            decode_group_id = _lookup_declared_field(
                context,
                transformation["decode_group_field"],
            )
            group_key = (
                mapping["mapping_id"],
                mapping["mapping_version"],
                mapping["content_digest"],
                decode_group_id,
            )
            register_groups[group_key].append(context)
        else:  # package validation guards this
            raise ValueError(
                f"Unsupported transformation {transformation['kind']!r}"
            )

    for group_key, contexts in sorted(register_groups.items(), key=lambda item: str(item[0])):
        mapping = mapping_by_identity[(group_key[0], group_key[1])]
        _canonicalize_register_pair(
            contexts,
            mapping=mapping,
            decode_group_id=group_key[3],
            replay_execution_id=replay_execution_id,
            facility_id=facility_id,
            canonical_rows=canonical_rows,
            lineage_specs=lineage_specs,
            decode_issues=decode_issues,
        )
    return canonical_rows, lineage_specs, decode_issues


def _canonicalize_field_set(
    context: dict[str, Any],
    *,
    transformation: dict[str, Any],
    replay_execution_id: str,
    facility_id: str,
    canonical_rows: list[dict[str, Any]],
    lineage_specs: list[dict[str, Any]],
    decode_issues: list[dict[str, Any]],
    direct_observations: dict[tuple[Any, ...], dict[str, Any]],
    issue_keys: set[tuple[Any, ...]],
) -> None:
    native = context["native_row"]
    mapping = context["mapping"]
    payload = context["delivery"]["payload"]
    stable_identity = context["identity_kind"] != "NO_STABLE_ID"
    logical_source_key = (
        native["source_event_group_key"]
        if stable_identity
        else native["delivery_id"]
    )
    for output in transformation["outputs"]:
        found, raw_value = _field_value(payload, output["source_field"])
        if not found:
            continue
        observation_key = (
            mapping["mapping_id"],
            mapping["mapping_version"],
            mapping["content_digest"],
            logical_source_key,
            native["source_event_variant_digest"],
            output["target_point_id"],
        )
        try:
            normalized_value = _normalize_output_value(raw_value, output)
        except ValueError as exc:
            issue_key = observation_key + (str(exc),)
            if issue_key not in issue_keys:
                issue_keys.add(issue_key)
                decode_issues.append(
                    _decode_issue_row(
                        replay_execution_id=replay_execution_id,
                        issue_number=len(decode_issues) + 1,
                        source_native_record_id=native[
                            "source_native_record_id"
                        ],
                        mapping=mapping,
                        issue_code="FIELD_NORMALIZATION_ERROR",
                        detail={
                            "source_field": output["source_field"],
                            "target_point_id": output["target_point_id"],
                            "error": str(exc),
                        },
                    )
                )
            continue

        existing = direct_observations.get(observation_key)
        if existing is None:
            derivation_key = _semantic_derivation_key(
                {
                    "kind": "FIELD_SET",
                    "mapping_id": mapping["mapping_id"],
                    "mapping_version": mapping["mapping_version"],
                    "mapping_digest": mapping["content_digest"],
                    "logical_source_key": logical_source_key,
                    "variant_digest": native["source_event_variant_digest"],
                    "source_field": output["source_field"],
                    "target_point_id": output["target_point_id"],
                }
            )
            row = _canonical_row(
                replay_execution_id=replay_execution_id,
                facility_id=facility_id,
                native=native,
                mapping=mapping,
                target_point_id=output["target_point_id"],
                value_type=output["value_type"],
                normalized_value=normalized_value,
                unit=output.get("unit"),
                derivation_key=derivation_key,
                source_event_group_key=native["source_event_group_key"],
                source_quality_provenance=json.loads(
                    native["source_quality_json"]
                ),
                synthetic_provenance=json.loads(
                    native["synthetic_provenance_json"]
                ),
                ordering_facts=json.loads(native["ordering_facts_json"]),
            )
            canonical_rows.append(row)
            existing = {"row": row}
            direct_observations[observation_key] = existing
        lineage_specs.append(
            {
                "derivation_key": existing["row"]["derivation_key"],
                "target_point_id": output["target_point_id"],
                "source_native_record_id": native["source_native_record_id"],
                "delivery_id": native["delivery_id"],
                "input_ordinal": 1,
                "lineage_role": (
                    "EXACT_REDELIVERY_SOURCE_FIELD"
                    if context["classification"] == "EXACT_REDELIVERY"
                    else "SOURCE_FIELD"
                ),
                "source_field_path": output["source_field"],
            }
        )


def _canonicalize_register_pair(
    contexts: list[dict[str, Any]],
    *,
    mapping: dict[str, Any],
    decode_group_id: Any,
    replay_execution_id: str,
    facility_id: str,
    canonical_rows: list[dict[str, Any]],
    lineage_specs: list[dict[str, Any]],
    decode_issues: list[dict[str, Any]],
) -> None:
    transformation = mapping["transformation"]
    if not isinstance(decode_group_id, str) or not decode_group_id:
        decode_issues.append(
            _decode_issue_row(
                replay_execution_id=replay_execution_id,
                issue_number=len(decode_issues) + 1,
                source_native_record_id=contexts[0]["native_row"][
                    "source_native_record_id"
                ],
                mapping=mapping,
                issue_code="MISSING_DECODE_GROUP_ID",
                detail={"decode_group_id": decode_group_id},
            )
        )
        return
    contexts_by_role: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for context in contexts:
        role = _lookup_declared_field(
            context,
            transformation["component_role_field"],
        )
        if isinstance(role, str):
            contexts_by_role[role].append(context)
    required_roles = (
        transformation["high_role"],
        transformation["low_role"],
    )
    if any(role not in contexts_by_role for role in required_roles):
        decode_issues.append(
            _decode_issue_row(
                replay_execution_id=replay_execution_id,
                issue_number=len(decode_issues) + 1,
                source_native_record_id=contexts[0]["native_row"][
                    "source_native_record_id"
                ],
                mapping=mapping,
                issue_code="INCOMPLETE_REGISTER_PAIR",
                detail={
                    "decode_group_id": decode_group_id,
                    "present_roles": sorted(contexts_by_role),
                    "required_roles": list(required_roles),
                },
            )
        )
        return

    variants_by_role: dict[str, list[dict[str, Any]]] = {}
    for role in required_roles:
        logical_variants: dict[tuple[str, ...], list[dict[str, Any]]] = (
            defaultdict(list)
        )
        for context in contexts_by_role[role]:
            native = context["native_row"]
            if context["identity_kind"] == "NO_STABLE_ID":
                logical_key = ("DELIVERY", native["delivery_id"])
            else:
                logical_key = (
                    "SOURCE_EVENT_VARIANT",
                    native["source_event_group_key"],
                    native["source_event_variant_digest"],
                )
            logical_variants[logical_key].append(context)

        variants_by_role[role] = []
        for logical_key, grouped_contexts in sorted(
            logical_variants.items(),
            key=lambda item: item[0],
        ):
            representative = sorted(
                grouped_contexts,
                key=cmp_to_key(_compare_context_receipts),
            )[0]
            variants_by_role[role].append(
                {
                    "logical_key": logical_key,
                    "contexts": grouped_contexts,
                    "representative": representative,
                }
            )

    role_ordinals = {
        transformation["high_role"]: 1,
        transformation["low_role"]: 2,
    }
    for high_variant in variants_by_role[required_roles[0]]:
        for low_variant in variants_by_role[required_roles[1]]:
            selected_variants = {
                required_roles[0]: high_variant,
                required_roles[1]: low_variant,
            }
            selected = {
                role: variant["representative"]
                for role, variant in selected_variants.items()
            }
            source_session_epochs = {
                role: context["native_row"]["source_session_epoch"]
                for role, context in selected.items()
            }
            declared_source_epochs = {
                epoch
                for epoch in source_session_epochs.values()
                if epoch is not None
            }
            if len(declared_source_epochs) > 1:
                decode_issues.append(
                    _decode_issue_row(
                        replay_execution_id=replay_execution_id,
                        issue_number=len(decode_issues) + 1,
                        source_native_record_id=selected[
                            required_roles[0]
                        ]["native_row"]["source_native_record_id"],
                        mapping=mapping,
                        issue_code="REGISTER_PAIR_SOURCE_EPOCH_MISMATCH",
                        detail={
                            "decode_group_id": decode_group_id,
                            "component_logical_keys": {
                                role: list(variant["logical_key"])
                                for role, variant in sorted(
                                    selected_variants.items()
                                )
                            },
                            "source_session_epochs": dict(
                                sorted(source_session_epochs.items())
                            ),
                        },
                    )
                )
                continue

            temporal_signatures = {
                (
                    context["native_row"]["observed_at_status"],
                    context["native_row"]["observed_at_utc"],
                )
                for context in selected.values()
            }
            if len(temporal_signatures) != 1:
                decode_issues.append(
                    _decode_issue_row(
                        replay_execution_id=replay_execution_id,
                        issue_number=len(decode_issues) + 1,
                        source_native_record_id=selected[
                            required_roles[0]
                        ]["native_row"]["source_native_record_id"],
                        mapping=mapping,
                        issue_code="REGISTER_PAIR_TEMPORAL_MISMATCH",
                        detail={
                            "decode_group_id": decode_group_id,
                            "component_logical_keys": {
                                role: list(variant["logical_key"])
                                for role, variant in sorted(
                                    selected_variants.items()
                                )
                            },
                            "temporal_signatures": sorted(
                                [
                                    list(signature)
                                    for signature in temporal_signatures
                                ],
                                key=str,
                            ),
                        },
                    )
                )
                continue

            try:
                high_value = _declared_value(
                    selected[required_roles[0]],
                    transformation["value_field"],
                )
                low_value = _declared_value(
                    selected[required_roles[1]],
                    transformation["value_field"],
                )
                decoded_integer = decode_signed_int32_be(
                    high_value,
                    low_value,
                )
                normalized_value = normalize_decimal_text(
                    decoded_integer,
                    factor=transformation["factor"],
                    quantum=transformation["quantum"],
                )
            except ValueError as exc:
                decode_issues.append(
                    _decode_issue_row(
                        replay_execution_id=replay_execution_id,
                        issue_number=len(decode_issues) + 1,
                        source_native_record_id=selected[
                            required_roles[0]
                        ]["native_row"]["source_native_record_id"],
                        mapping=mapping,
                        issue_code="REGISTER_PAIR_DECODE_ERROR",
                        detail={
                            "decode_group_id": decode_group_id,
                            "component_logical_keys": {
                                role: list(variant["logical_key"])
                                for role, variant in sorted(
                                    selected_variants.items()
                                )
                            },
                            "error": str(exc),
                        },
                    )
                )
                continue

            component_material = [
                {
                    "role": role,
                    "logical_key": list(variant["logical_key"]),
                    "source_event_variant_digest": variant[
                        "representative"
                    ]["native_row"]["source_event_variant_digest"],
                }
                for role, variant in sorted(selected_variants.items())
            ]
            derivation_key = _semantic_derivation_key(
                {
                    "kind": "REGISTER_PAIR_SIGNED_INT32_BE",
                    "mapping_id": mapping["mapping_id"],
                    "mapping_version": mapping["mapping_version"],
                    "mapping_digest": mapping["content_digest"],
                    "decode_group_id": decode_group_id,
                    "components": component_material,
                    "target_point_id": transformation["target_point_id"],
                }
            )
            composite_variant_digest = canonical_json_sha256(
                {
                    "decode_group_id": decode_group_id,
                    "components": component_material,
                }
            )
            primary_native = selected[required_roles[0]]["native_row"]
            composite_native = {
                **primary_native,
                "source_event_variant_digest": composite_variant_digest,
                "received_at_utc": _latest_timestamp(
                    [
                        context["native_row"]["received_at_utc"]
                        for context in selected.values()
                    ]
                ),
                "source_sequence": None,
                "source_session_epoch": None,
            }
            row = _canonical_row(
                replay_execution_id=replay_execution_id,
                facility_id=facility_id,
                native=composite_native,
                mapping=mapping,
                target_point_id=transformation["target_point_id"],
                value_type="DECIMAL",
                normalized_value=normalized_value,
                unit=transformation["unit"],
                derivation_key=derivation_key,
                source_event_group_key=None,
                source_quality_provenance={
                    "component_reports": [
                        {
                            "role": role,
                            "source_quality": json.loads(
                                context["native_row"][
                                    "source_quality_json"
                                ]
                            ),
                        }
                        for role, context in sorted(selected.items())
                    ]
                },
                synthetic_provenance={
                    "synthetic": True,
                    "composite_decode": "REGISTER_PAIR_SIGNED_INT32_BE",
                    "decode_group_id": decode_group_id,
                },
                ordering_facts={
                    "time_basis": SOURCE_REPORTED_TIME_BASIS,
                    "composite_source_order": "UNORDERED",
                    "reason": (
                        "The canonical value combines distinct declared "
                        "source records and does not invent a single "
                        "source-event identity."
                    ),
                },
            )
            canonical_rows.append(row)
            for role, variant in sorted(selected_variants.items()):
                for context in variant["contexts"]:
                    lineage_specs.append(
                        {
                            "derivation_key": derivation_key,
                            "target_point_id": transformation[
                                "target_point_id"
                            ],
                            "source_native_record_id": context[
                                "native_row"
                            ]["source_native_record_id"],
                            "delivery_id": context["native_row"][
                                "delivery_id"
                            ],
                            "input_ordinal": role_ordinals[role],
                            "lineage_role": role,
                            "source_field_path": transformation[
                                "value_field"
                            ],
                        }
                    )


def _canonical_row(
    *,
    replay_execution_id: str,
    facility_id: str,
    native: dict[str, Any],
    mapping: dict[str, Any],
    target_point_id: str,
    value_type: str,
    normalized_value: Any,
    unit: str | None,
    derivation_key: str,
    source_event_group_key: str | None,
    source_quality_provenance: dict[str, Any],
    synthetic_provenance: dict[str, Any],
    ordering_facts: dict[str, Any],
) -> dict[str, Any]:
    values = {
        "value_boolean": None,
        "value_integer": None,
        "value_decimal": None,
        "value_text": None,
    }
    if value_type == "BOOLEAN":
        values["value_boolean"] = 1 if normalized_value else 0
    elif value_type == "INTEGER":
        values["value_integer"] = normalized_value
    elif value_type == "DECIMAL":
        values["value_decimal"] = normalized_value
    elif value_type in {"TEXT", "ENUM"}:
        values["value_text"] = normalized_value
    else:
        raise ValueError(f"Unsupported canonical value type {value_type!r}")

    report_material = {
        "point_id": target_point_id,
        "mapping_id": mapping["mapping_id"],
        "mapping_version": mapping["mapping_version"],
        "mapping_digest": mapping["content_digest"],
        "observed_at_status": native["observed_at_status"],
        "observed_at_utc": native["observed_at_utc"],
        "source_sequence": native["source_sequence"],
        "source_epoch": native["source_session_epoch"],
        "value_type": value_type,
        "value": normalized_value,
        "unit": unit,
        "time_basis": SOURCE_REPORTED_TIME_BASIS,
        "source_quality": source_quality_provenance,
    }
    return {
        "canonical_observation_id": _run_scoped_id(
            "CANONICAL-OBSERVATION",
            replay_execution_id,
            derivation_key,
            target_point_id,
        ),
        "replay_execution_id": replay_execution_id,
        "facility_id": facility_id,
        "source_binding_id": native["source_binding_id"],
        "source_event_group_key": source_event_group_key,
        "source_event_variant_digest": native[
            "source_event_variant_digest"
        ],
        "canonical_point_definition_id": target_point_id,
        "mapping_id": mapping["mapping_id"],
        "mapping_version": mapping["mapping_version"],
        "mapping_digest": mapping["content_digest"],
        "canonicalizer_version": CANONICALIZER_VERSION,
        "derivation_key": derivation_key,
        "value_type": value_type,
        **values,
        "unit": unit,
        "time_basis": SOURCE_REPORTED_TIME_BASIS,
        "observed_at_status": native["observed_at_status"],
        "observed_at_utc": native["observed_at_utc"],
        "received_at_utc": native["received_at_utc"],
        "source_sequence": native["source_sequence"],
        "source_session_epoch": native["source_session_epoch"],
        "source_quality_provenance_json": canonical_json_text(
            source_quality_provenance
        ),
        "synthetic_provenance_json": canonical_json_text(
            synthetic_provenance
        ),
        "report_material_digest": canonical_json_sha256(report_material),
        "ordering_facts_json": canonical_json_text(ordering_facts),
    }


def _lineage_rows(
    lineage_specs: list[dict[str, Any]],
    *,
    canonical_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    observation_by_key = {
        (
            row["derivation_key"],
            row["canonical_point_definition_id"],
        ): row["canonical_observation_id"]
        for row in canonical_rows
    }
    return [
        {
            "canonical_observation_id": observation_by_key[
                (spec["derivation_key"], spec["target_point_id"])
            ],
            "source_native_record_id": spec["source_native_record_id"],
            "input_ordinal": spec["input_ordinal"],
            "lineage_role": spec["lineage_role"],
            "source_field_path": spec["source_field_path"],
        }
        for spec in lineage_specs
    ]


def _decode_issue_row(
    *,
    replay_execution_id: str,
    issue_number: int,
    source_native_record_id: str | None,
    mapping: dict[str, Any],
    issue_code: str,
    detail: dict[str, Any],
) -> dict[str, Any]:
    return {
        "replay_execution_id": replay_execution_id,
        "issue_id": f"DECODE-ISSUE-{issue_number:04d}",
        "source_native_record_id": source_native_record_id,
        "mapping_id": mapping["mapping_id"],
        "mapping_version": mapping["mapping_version"],
        "issue_code": issue_code,
        "detail_json": canonical_json_text(detail),
    }


def _normalize_output_value(raw_value: Any, output: dict[str, Any]) -> Any:
    normalization = output["normalization"]
    kind = normalization["kind"]
    if kind == "STRICT_BOOLEAN":
        return normalize_strict_boolean(
            raw_value,
            true_values=normalization.get("true_values", [True]),
            false_values=normalization.get("false_values", [False]),
        )
    if kind == "DIRECT_ENUM":
        return normalize_direct_enum(raw_value, normalization["mapping"])
    if kind in {"DECIMAL", "DECIMAL_SCALE", "UNIT_CONVERSION"}:
        return normalize_decimal_text(
            raw_value,
            factor=normalization["factor"],
            quantum=normalization["quantum"],
        )
    raise ValueError(f"Unsupported normalization kind {kind!r}")


def _field_value(
    payload: dict[str, Any],
    field_path: str,
) -> tuple[bool, Any]:
    if not field_path.startswith("$."):
        return (
            (True, payload[field_path])
            if field_path in payload
            else (False, None)
        )
    current: Any = payload
    for component in field_path[2:].split("."):
        if not isinstance(current, dict) or component not in current:
            return False, None
        current = current[component]
    return True, current


def _lookup_declared_field(
    context: dict[str, Any],
    field_path: str,
) -> Any:
    if field_path.startswith("$."):
        found, value = _field_value(context["delivery"]["payload"], field_path)
        return value if found else None
    source_event = context["source_event"]
    if field_path in source_event:
        return source_event[field_path]
    if field_path in context["delivery"]["source_metadata"]:
        return context["delivery"]["source_metadata"][field_path]
    if field_path in context["delivery"]["payload"]:
        return context["delivery"]["payload"][field_path]
    return None


def _declared_value(context: dict[str, Any], field_path: str) -> Any:
    if field_path.startswith("$."):
        found, value = _field_value(context["delivery"]["payload"], field_path)
        if not found:
            raise ValueError(f"Declared field {field_path!r} is missing")
        return value
    value = _lookup_declared_field(context, field_path)
    if value is None:
        raise ValueError(f"Declared field {field_path!r} is missing")
    return value


def _annotation_rows(
    narrative: dict[str, Any],
    *,
    replay_execution_id: str,
) -> list[dict[str, Any]]:
    kind_mapping = {
        "ACTION_CONTEXT": "ASSERTED_ACTION",
        "ASSERTED_ACTION": "ASSERTED_ACTION",
    }
    rows = []
    for event in narrative["events"]:
        annotation_kind = kind_mapping.get(event.get("kind"))
        if annotation_kind is None:
            continue
        rows.append(
            {
                "replay_execution_id": replay_execution_id,
                "narrative_event_id": event["event_id"],
                "annotation_kind": annotation_kind,
                "annotation_json": canonical_json_text(event),
            }
        )
    return rows


def _projection_summary(
    canonical_rows: list[dict[str, Any]],
    *,
    lineage_rows: list[dict[str, Any]],
    native_contexts: list[dict[str, Any]],
    binding_by_id: dict[str, dict[str, Any]],
    oracle: dict[str, Any],
) -> dict[str, Any]:
    if not canonical_rows:
        return {
            "as_of_observed_at": None,
            "known_by_received_at": None,
            "scope_count": 0,
            "disposition_counts": {},
            "scopes": [],
        }
    valid_observed = [
        row["observed_at_utc"]
        for row in canonical_rows
        if row["observed_at_status"] == "VALID"
        and row["observed_at_utc"] is not None
    ]
    known_by = _latest_timestamp(
        [
            context["native_row"]["received_at_utc"]
            for context in native_contexts
        ]
    )
    as_of = (
        _latest_timestamp(valid_observed) if valid_observed else known_by
    )
    lineage_by_observation: dict[str, list[str]] = defaultdict(list)
    for lineage in lineage_rows:
        lineage_by_observation[lineage["canonical_observation_id"]].append(
            lineage["source_native_record_id"]
        )
    native_by_id = {
        context["native_row"]["source_native_record_id"]: context[
            "native_row"
        ]
        for context in native_contexts
    }
    variant_receipts_by_group: dict[
        str,
        list[tuple[str, str]],
    ] = defaultdict(list)
    for context in native_contexts:
        native = context["native_row"]
        if native["source_event_group_key"] is not None:
            variant_receipts_by_group[
                native["source_event_group_key"]
            ].append(
                (
                    native["source_event_variant_digest"],
                    native["received_at_utc"],
                )
            )

    def candidates_at_knowledge_cutoff(
        candidates: list[dict[str, Any]],
        cutoff: str,
    ) -> list[dict[str, Any]]:
        resolved = []
        for candidate in candidates:
            source_native_ids = lineage_by_observation[
                candidate["canonical_observation_id"]
            ]
            component_group_keys = {
                native_by_id[source_native_id]["source_event_group_key"]
                for source_native_id in source_native_ids
                if native_by_id[source_native_id][
                    "source_event_group_key"
                ]
                is not None
            }
            source_event_conflict = False
            for group_key in component_group_keys:
                known_variants = {
                    variant_digest
                    for variant_digest, received_at in (
                        variant_receipts_by_group[group_key]
                    )
                    if compare_rfc3339_instants(received_at, cutoff)
                    in {ORDER_BEFORE, ORDER_EQUAL}
                }
                if len(known_variants) > 1:
                    source_event_conflict = True
                    break
            resolved.append(
                {
                    **candidate,
                    "source_event_conflict": source_event_conflict,
                }
            )
        return resolved

    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in canonical_rows:
        binding = binding_by_id[row["source_binding_id"]]
        scope = (
            row["facility_id"],
            row["replay_execution_id"],
            row["source_binding_id"],
            binding["channel"],
            row["canonical_point_definition_id"],
            row["mapping_id"],
            row["mapping_version"],
            row["mapping_digest"],
        )
        source_native_ids = lineage_by_observation[
            row["canonical_observation_id"]
        ]
        base_candidate = {
            "canonical_observation_id": row["canonical_observation_id"],
            "facility_id": row["facility_id"],
            "replay_execution_id": row["replay_execution_id"],
            "source_binding_id": row["source_binding_id"],
            "channel": binding["channel"],
            "point_id": row["canonical_point_definition_id"],
            "mapping_id": row["mapping_id"],
            "mapping_version": row["mapping_version"],
            "mapping_digest": row["mapping_digest"],
            "source_event_group_key": row["source_event_group_key"],
            "source_event_variant_digest": row[
                "source_event_variant_digest"
            ],
            "source_event_conflict": False,
            "source_sequence": row["source_sequence"],
            "source_session_epoch": row["source_session_epoch"],
            "observed_at_status": row["observed_at_status"],
            "observed_at_utc": row["observed_at_utc"],
            "received_at_utc": row["received_at_utc"],
            "normalized_value_type": row["value_type"],
            "normalized_value": _row_value(row),
            "unit": row["unit"],
            "time_basis": row["time_basis"],
            "report_material_digest": row["report_material_digest"],
        }
        if row["source_event_group_key"] is not None:
            for source_native_id in source_native_ids:
                grouped[scope].append(
                    {
                        **base_candidate,
                        "source_native_record_ids": [source_native_id],
                        "received_at_utc": native_by_id[source_native_id][
                            "received_at_utc"
                        ],
                    }
                )
        else:
            grouped[scope].append(
                {
                    **base_candidate,
                    "source_native_record_ids": source_native_ids,
                }
            )
    scopes = []
    disposition_counts: dict[str, int] = defaultdict(int)
    for scope, candidates in sorted(grouped.items(), key=lambda item: str(item[0])):
        projection = build_reported_observation_projection(
            candidates_at_knowledge_cutoff(candidates, known_by),
            as_of_observed_at=as_of,
            known_by_received_at=known_by,
        )
        disposition_counts[projection["disposition"]] += 1
        scopes.append(
            {
                "facility_id": scope[0],
                "source_binding_id": scope[2],
                "channel": scope[3],
                "point_id": scope[4],
                "mapping_id": scope[5],
                "mapping_version": scope[6],
                "mapping_digest": scope[7],
                "disposition": projection["disposition"],
                "selected_value": projection["selected_value"],
                "known_candidate_count": projection[
                    "known_candidate_count"
                ],
                "logical_candidate_count": projection[
                    "logical_candidate_count"
                ],
            }
        )
    checkpoint_results = []
    for checkpoint in oracle.get("projection_expectations", []):
        checkpoint_scope = checkpoint["scope"]
        matching_groups = [
            candidates
            for scope, candidates in grouped.items()
            if scope[2] == checkpoint_scope["source_binding_id"]
            and scope[4] == checkpoint_scope["point_id"]
            and scope[5] == checkpoint_scope["mapping_id"]
            and scope[6] == checkpoint_scope["mapping_version"]
        ]
        if len(matching_groups) != 1:
            raise ValueError(
                "Replay structural oracle projection scope did not resolve "
                f"exactly once: {checkpoint['name']}"
            )
        projection = build_reported_observation_projection(
            candidates_at_knowledge_cutoff(
                matching_groups[0],
                checkpoint["known_by_received_at"],
            ),
            as_of_observed_at=checkpoint["as_of_observed_at"],
            known_by_received_at=checkpoint["known_by_received_at"],
        )
        if projection["disposition"] != checkpoint["expected_disposition"]:
            raise ValueError(
                "Replay structural oracle projection disposition mismatch: "
                f"{checkpoint['name']}"
            )
        expected_logical_count = checkpoint.get(
            "expected_logical_candidate_count"
        )
        if (
            expected_logical_count is not None
            and projection["logical_candidate_count"]
            != expected_logical_count
        ):
            raise ValueError(
                "Replay structural oracle logical-candidate count mismatch: "
                f"{checkpoint['name']}"
            )
        checkpoint_results.append(
            {
                "name": checkpoint["name"],
                "scope": deepcopy(checkpoint_scope),
                "as_of_observed_at": checkpoint["as_of_observed_at"],
                "known_by_received_at": checkpoint[
                    "known_by_received_at"
                ],
                "disposition": projection["disposition"],
                "selected_value": projection["selected_value"],
                "known_candidate_count": projection[
                    "known_candidate_count"
                ],
                "logical_candidate_count": projection[
                    "logical_candidate_count"
                ],
                "matches_structural_oracle": True,
            }
        )
    return {
        "as_of_observed_at": as_of,
        "known_by_received_at": known_by,
        "scope_count": len(scopes),
        "disposition_counts": dict(sorted(disposition_counts.items())),
        "scopes": scopes,
        "oracle_checkpoints": checkpoint_results,
    }


def _validate_structural_oracle_against_plan(
    *,
    loaded: dict[str, Any],
    event_groups: list[dict[str, Any]],
    deliveries: list[dict[str, Any]],
    native_contexts: list[dict[str, Any]],
    canonical_rows: list[dict[str, Any]],
    lineage_rows: list[dict[str, Any]],
) -> None:
    """Validate every semantic oracle declaration against derived plan rows."""

    _validate_oracle_identity_groups(
        loaded["oracle"],
        deliveries=deliveries,
        native_contexts=native_contexts,
        canonical_rows=canonical_rows,
    )
    _validate_oracle_decode_lineage(
        loaded["oracle"],
        native_contexts=native_contexts,
        canonical_rows=canonical_rows,
        lineage_rows=lineage_rows,
    )
    _validate_oracle_ordering_facts(
        loaded["oracle"],
        native_contexts=native_contexts,
        canonical_rows=canonical_rows,
        lineage_rows=lineage_rows,
    )
    _validate_structural_oracle_counts(
        loaded=loaded,
        event_groups=event_groups,
        deliveries=deliveries,
        native_contexts=native_contexts,
        canonical_rows=canonical_rows,
        lineage_rows=lineage_rows,
    )


def _validate_oracle_identity_groups(
    oracle: dict[str, Any],
    *,
    deliveries: list[dict[str, Any]],
    native_contexts: list[dict[str, Any]],
    canonical_rows: list[dict[str, Any]],
) -> None:
    delivery_by_id = {
        delivery["delivery_id"]: delivery for delivery in deliveries
    }
    context_by_delivery_id = {
        context["native_row"]["delivery_id"]: context
        for context in native_contexts
    }
    delivery_ids_by_group: dict[str, set[str]] = defaultdict(set)
    for delivery in deliveries:
        delivery_ids_by_group[
            delivery["source_event_group_key"]
        ].add(delivery["delivery_id"])
    canonical_ids_by_group: dict[str, set[str]] = defaultdict(set)
    for row in canonical_rows:
        group_key = row["source_event_group_key"]
        if group_key is not None:
            canonical_ids_by_group[group_key].add(
                row["canonical_observation_id"]
            )

    for index, group in enumerate(oracle["identity_groups"]):
        label = (
            "Replay structural oracle identity-group mismatch at "
            f"identity_groups[{index}]"
        )
        group_kind = group["group_kind"]
        expected_delivery_ids = set(group["delivery_ids"])
        contexts = [
            context_by_delivery_id[delivery_id]
            for delivery_id in group["delivery_ids"]
        ]
        group_keys = {
            context["native_row"]["source_event_group_key"]
            for context in contexts
        }

        if group_kind in {
            "EXACT_REDELIVERY",
            "CONFLICTING_REDELIVERY",
        }:
            if len(group_keys) != 1:
                raise ValueError(
                    f"{label}: referenced deliveries do not share one "
                    "derived source-event group"
                )
            group_key = next(iter(group_keys))
            if delivery_ids_by_group[group_key] != expected_delivery_ids:
                raise ValueError(
                    f"{label}: delivery_ids do not describe the complete "
                    "derived source-event group"
                )
            variants = {
                context["native_row"]["source_event_variant_digest"]
                for context in contexts
            }
            derived_kind = (
                "EXACT_REDELIVERY"
                if len(contexts) > 1 and len(variants) == 1
                else (
                    "CONFLICTING_REDELIVERY"
                    if len(variants) > 1
                    else "NOT_A_REDELIVERY_GROUP"
                )
            )
            if derived_kind != group_kind:
                raise ValueError(
                    f"{label}: expected {group_kind}, derived "
                    f"{derived_kind}"
                )
            derived_source_event_ids = {
                context["source_event"].get("event_id")
                for context in contexts
            }
            if derived_source_event_ids != {group["source_event_id"]}:
                raise ValueError(
                    f"{label}: declared source_event_id differs from the "
                    "prepared plan"
                )
            actual_counts = {
                "expected_source_native_records": len(contexts),
                "expected_logical_variants": len(variants),
                "expected_canonical_observations": len(
                    canonical_ids_by_group[group_key]
                ),
            }
        elif group_kind == "EQUAL_PAYLOAD_DISTINCT_SOURCE_EVENTS":
            declared_source_event_ids = set(group["source_event_ids"])
            source_event_ids_by_group: dict[str, set[str | None]] = (
                defaultdict(set)
            )
            for context in contexts:
                source_event_ids_by_group[
                    context["native_row"]["source_event_group_key"]
                ].add(context["source_event"].get("event_id"))
            if (
                len(source_event_ids_by_group) < 2
                or len(source_event_ids_by_group)
                != len(declared_source_event_ids)
                or any(
                    len(source_event_ids) != 1
                    for source_event_ids in source_event_ids_by_group.values()
                )
                or {
                    next(iter(source_event_ids))
                    for source_event_ids in source_event_ids_by_group.values()
                }
                != declared_source_event_ids
            ):
                raise ValueError(
                    f"{label}: declared source events do not map one-to-one "
                    "to distinct source-event groups"
                )
            if any(
                context["identity_kind"] == "NO_STABLE_ID"
                for context in contexts
            ):
                raise ValueError(
                    f"{label}: an equal-payload declaration uses a delivery "
                    "without stable source identity"
                )
            complete_group_delivery_ids = set().union(
                *(delivery_ids_by_group[group_key] for group_key in group_keys)
            )
            if complete_group_delivery_ids != expected_delivery_ids:
                raise ValueError(
                    f"{label}: delivery_ids do not describe the complete "
                    "derived source-event groups"
                )
            payload_digests = {
                context["native_row"]["payload_digest"]
                for context in contexts
            }
            if len(payload_digests) != 1:
                raise ValueError(
                    f"{label}: referenced source-event groups do not have "
                    "equal payloads"
                )
            actual_counts = {
                "expected_source_event_groups": len(group_keys),
                "expected_canonical_observations": len(
                    set().union(
                        *(
                            canonical_ids_by_group[group_key]
                            for group_key in group_keys
                        )
                    )
                ),
            }
        else:  # package validation guards this
            raise ValueError(
                f"{label}: unsupported group_kind {group_kind!r}"
            )

        _require_matching_oracle_counts(
            label,
            expected=group,
            actual=actual_counts,
        )
        if any(
            delivery_by_id[delivery_id]["source_binding_id"]
            != group["source_binding_id"]
            for delivery_id in expected_delivery_ids
        ):
            raise ValueError(
                f"{label}: source binding differs from the prepared plan"
            )


def _validate_oracle_decode_lineage(
    oracle: dict[str, Any],
    *,
    native_contexts: list[dict[str, Any]],
    canonical_rows: list[dict[str, Any]],
    lineage_rows: list[dict[str, Any]],
) -> None:
    context_by_delivery_id = {
        context["native_row"]["delivery_id"]: context
        for context in native_contexts
    }
    row_by_observation_id = {
        row["canonical_observation_id"]: row for row in canonical_rows
    }
    lineage_by_observation_id: dict[str, list[dict[str, Any]]] = (
        defaultdict(list)
    )
    for edge in lineage_rows:
        lineage_by_observation_id[edge["canonical_observation_id"]].append(
            edge
        )

    for index, expectation in enumerate(oracle["decode_lineage"]):
        label = (
            "Replay structural oracle decode-lineage mismatch at "
            f"decode_lineage[{index}]"
        )
        contexts = [
            context_by_delivery_id[delivery_id]
            for delivery_id in expectation["source_delivery_ids"]
        ]
        decode_group_id = expectation["decode_group_id"]
        if any(
            context["source_event"].get("decode_group_id")
            != decode_group_id
            for context in contexts
        ):
            raise ValueError(
                f"{label}: source delivery decode-group declarations differ"
            )
        mapping_identities = {
            (
                context["mapping"]["mapping_id"],
                context["mapping"]["mapping_version"],
                context["mapping"]["content_digest"],
            )
            for context in contexts
        }
        if len(mapping_identities) != 1:
            raise ValueError(
                f"{label}: source deliveries do not use one mapping "
                "derivation"
            )
        transformation = contexts[0]["mapping"]["transformation"]
        if (
            transformation["kind"]
            != "REGISTER_PAIR_SIGNED_INT32_BE"
            or transformation["target_point_id"]
            != expectation["target_point_id"]
        ):
            raise ValueError(
                f"{label}: mapping transformation does not produce the "
                "declared target point"
            )
        expected_native_ids = {
            context["native_row"]["source_native_record_id"]
            for context in contexts
        }
        matching_observation_ids = []
        for observation_id, edges in lineage_by_observation_id.items():
            row = row_by_observation_id[observation_id]
            if (
                row["canonical_point_definition_id"]
                == expectation["target_point_id"]
                and {
                    edge["source_native_record_id"] for edge in edges
                }
                == expected_native_ids
            ):
                matching_observation_ids.append(observation_id)
        if len(matching_observation_ids) != 1:
            raise ValueError(
                f"{label}: expected exactly one canonical observation with "
                "the declared source-native lineage"
            )
        observation_id = matching_observation_ids[0]
        edges = lineage_by_observation_id[observation_id]
        _require_matching_oracle_counts(
            label,
            expected=expectation,
            actual={"expected_lineage_edges": len(edges)},
        )

        expected_signed_raw_value = expectation.get(
            "expected_signed_raw_value"
        )
        if expected_signed_raw_value is not None:
            contexts_by_role: dict[str, list[dict[str, Any]]] = defaultdict(
                list
            )
            for context in contexts:
                role = _lookup_declared_field(
                    context,
                    transformation["component_role_field"],
                )
                if isinstance(role, str):
                    contexts_by_role[role].append(context)
            high_values = {
                _declared_value(
                    context,
                    transformation["value_field"],
                )
                for context in contexts_by_role[
                    transformation["high_role"]
                ]
            }
            low_values = {
                _declared_value(
                    context,
                    transformation["value_field"],
                )
                for context in contexts_by_role[
                    transformation["low_role"]
                ]
            }
            if len(high_values) != 1 or len(low_values) != 1:
                raise ValueError(
                    f"{label}: signed raw-value validation requires one "
                    "logical value for each declared register role"
                )
            actual_signed_raw_value = decode_signed_int32_be(
                next(iter(high_values)),
                next(iter(low_values)),
            )
            if actual_signed_raw_value != expected_signed_raw_value:
                raise ValueError(
                    f"{label}: expected signed raw value "
                    f"{expected_signed_raw_value}, derived "
                    f"{actual_signed_raw_value}"
                )

        expected_normalized_value = expectation.get(
            "expected_normalized_value"
        )
        if (
            expected_normalized_value is not None
            and _row_value(row_by_observation_id[observation_id])
            != expected_normalized_value
        ):
            raise ValueError(
                f"{label}: expected normalized value "
                f"{expected_normalized_value!r}, derived "
                f"{_row_value(row_by_observation_id[observation_id])!r}"
            )


def _validate_oracle_ordering_facts(
    oracle: dict[str, Any],
    *,
    native_contexts: list[dict[str, Any]],
    canonical_rows: list[dict[str, Any]],
    lineage_rows: list[dict[str, Any]],
) -> None:
    context_by_delivery_id = {
        context["native_row"]["delivery_id"]: context
        for context in native_contexts
    }
    row_by_observation_id = {
        row["canonical_observation_id"]: row for row in canonical_rows
    }
    report_material_by_native_and_point: dict[
        str,
        dict[str, set[tuple[Any, ...]]],
    ] = defaultdict(lambda: defaultdict(set))
    for edge in lineage_rows:
        row = row_by_observation_id[edge["canonical_observation_id"]]
        report_material_by_native_and_point[
            edge["source_native_record_id"]
        ][row["canonical_point_definition_id"]].add(
            (
                row["value_type"],
                _row_value(row),
                row["unit"],
            )
        )

    for index, fact in enumerate(oracle["ordering_facts"]):
        fact_kind = fact["fact_kind"]
        label = (
            "Replay structural oracle ordering-fact mismatch at "
            f"ordering_facts[{index}] ({fact_kind})"
        )
        if fact_kind == "OUT_OF_ORDER_ARRIVAL":
            older = _ordering_candidate(
                context_by_delivery_id[fact["older_delivery_id"]]
            )
            newer = _ordering_candidate(
                context_by_delivery_id[fact["newer_delivery_id"]]
            )
            comparison = observation_ordering_facts(older, newer)
            if not (
                comparison["relation"] == ORDER_BEFORE
                and comparison["received_at_relation"] == ORDER_AFTER
                and comparison["out_of_order_arrival"]
            ):
                raise ValueError(
                    f"{label}: referenced delivery orientation is not an "
                    "older source report received after the newer report"
                )
        elif fact_kind == "SEQUENCE_TIME_DISAGREEMENT":
            earlier = _ordering_candidate(
                context_by_delivery_id[fact["earlier_delivery_id"]]
            )
            later = _ordering_candidate(
                context_by_delivery_id[fact["later_delivery_id"]]
            )
            comparison = observation_ordering_facts(earlier, later)
            if not (
                comparison["same_source_binding"]
                and comparison["relation"] == ORDER_UNORDERED
                and comparison["sequence_relation"] == ORDER_BEFORE
                and comparison["observed_at_relation"] == ORDER_AFTER
                and comparison["sequence_time_disagreement"]
            ):
                raise ValueError(
                    f"{label}: the later source sequence does not carry an "
                    "older observed time"
                )
        elif fact_kind == "DECLARED_SEQUENCE_RESET":
            context = context_by_delivery_id[fact["delivery_id"]]
            native = context["native_row"]
            prior_contexts = [
                prior
                for prior in native_contexts
                if prior["delivery_row"]["ingestion_ordinal"]
                < context["delivery_row"]["ingestion_ordinal"]
                and prior["native_row"]["source_binding_id"]
                == native["source_binding_id"]
                and prior["native_row"]["source_session_epoch"] is not None
                and prior["native_row"]["source_session_epoch"]
                != native["source_session_epoch"]
                and prior["native_row"]["source_sequence"] is not None
            ]
            if not (
                native["source_session_epoch"] is not None
                and native["source_sequence"] is not None
                and any(
                    prior["native_row"]["source_sequence"]
                    > native["source_sequence"]
                    for prior in prior_contexts
                )
            ):
                raise ValueError(
                    f"{label}: the prepared plan has no explicit new epoch "
                    "with a reset source sequence"
                )
        elif fact_kind == "AMBIGUOUS_SEQUENCE_RESET":
            context = context_by_delivery_id[fact["delivery_id"]]
            ordering = json.loads(
                context["native_row"]["ordering_facts_json"]
            )
            if not ordering["ambiguous_sequence_reset"]:
                raise ValueError(
                    f"{label}: prepared ordering facts do not identify an "
                    "ambiguous reset"
                )
        elif fact_kind == "EQUAL_OBSERVED_TIME_DIFFERENT_REPORTS":
            contexts = [
                context_by_delivery_id[delivery_id]
                for delivery_id in fact["delivery_ids"]
            ]
            native_rows = [
                context["native_row"] for context in contexts
            ]
            observed_signatures = {
                (
                    native["observed_at_status"],
                    native["observed_at_utc"],
                )
                for native in native_rows
            }
            group_keys = {
                native["source_event_group_key"] for native in native_rows
            }
            common_points = set.intersection(
                *(
                    set(
                        report_material_by_native_and_point[
                            native["source_native_record_id"]
                        ]
                    )
                    for native in native_rows
                )
            )
            has_different_report = any(
                len(
                    set().union(
                        *(
                            report_material_by_native_and_point[
                                native["source_native_record_id"]
                            ][point_id]
                            for native in native_rows
                        )
                    )
                )
                > 1
                for point_id in common_points
            )
            if not (
                observed_signatures
                and len(observed_signatures) == 1
                and next(iter(observed_signatures))[0] == "VALID"
                and len(group_keys) == len(native_rows)
                and all(
                    native["source_sequence"] is None
                    for native in native_rows
                )
                and has_different_report
            ):
                raise ValueError(
                    f"{label}: deliveries are not distinct, differently "
                    "reported source events at one valid observed time"
                )
        elif fact_kind in {
            "MISSING_OBSERVED_TIME",
            "INVALID_OBSERVED_TIME",
        }:
            native = context_by_delivery_id[fact["delivery_id"]][
                "native_row"
            ]
            expected_status = (
                "MISSING"
                if fact_kind == "MISSING_OBSERVED_TIME"
                else "INVALID"
            )
            if native["observed_at_status"] != expected_status:
                raise ValueError(
                    f"{label}: expected observed-at status "
                    f"{expected_status}, derived "
                    f"{native['observed_at_status']}"
                )
        elif fact_kind == "SOURCE_TIME_AFTER_RECEIPT":
            context = context_by_delivery_id[fact["delivery_id"]]
            temporal = json.loads(
                context["native_row"]["ordering_facts_json"]
            )["temporal_facts"]
            if temporal["observed_at_after_received_at"] is not True:
                raise ValueError(
                    f"{label}: source time is not after receipt time"
                )
        elif fact_kind == "MAPPING_VERSION_TRANSITION":
            context = context_by_delivery_id[fact["delivery_id"]]
            mapping = context["mapping"]
            prior_versions = {
                prior["mapping"]["mapping_version"]
                for prior in native_contexts
                if prior["delivery_row"]["ingestion_ordinal"]
                < context["delivery_row"]["ingestion_ordinal"]
                and prior["native_row"]["source_binding_id"]
                == context["native_row"]["source_binding_id"]
                and prior["mapping"]["mapping_id"] == fact["mapping_id"]
            }
            if not (
                mapping["mapping_id"] == fact["mapping_id"]
                and mapping["mapping_version"] == fact["to_version"]
                and fact["from_version"] in prior_versions
                and fact["from_version"] != fact["to_version"]
            ):
                raise ValueError(
                    f"{label}: the referenced delivery does not transition "
                    "from the declared prior mapping version"
                )
        else:  # package validation guards this
            raise ValueError(
                f"{label}: unsupported fact_kind {fact_kind!r}"
            )


def _ordering_candidate(context: dict[str, Any]) -> dict[str, Any]:
    native = context["native_row"]
    return {
        "source_native_record_id": native["source_native_record_id"],
        "facility_id": native["facility_id"],
        "source_binding_id": native["source_binding_id"],
        "channel": context["binding"]["channel"],
        "observed_at_status": native["observed_at_status"],
        "observed_at_utc": native["observed_at_utc"],
        "received_at_utc": native["received_at_utc"],
        "source_sequence": native["source_sequence"],
        "source_session_epoch": native["source_session_epoch"],
    }


def _require_matching_oracle_counts(
    label: str,
    *,
    expected: dict[str, Any],
    actual: dict[str, int],
) -> None:
    mismatches = {
        field_name: {
            "expected": expected.get(field_name),
            "actual": actual_count,
        }
        for field_name, actual_count in actual.items()
        if expected.get(field_name) != actual_count
    }
    if mismatches:
        raise ValueError(
            f"{label}: " + canonical_json_text(mismatches)
        )


def _validate_structural_oracle_counts(
    *,
    loaded: dict[str, Any],
    event_groups: list[dict[str, Any]],
    deliveries: list[dict[str, Any]],
    native_contexts: list[dict[str, Any]],
    canonical_rows: list[dict[str, Any]],
    lineage_rows: list[dict[str, Any]],
) -> None:
    expected = loaded["oracle"].get("expected_counts")
    if not isinstance(expected, dict):
        raise ValueError(
            "Replay structural oracle must declare expected_counts"
        )
    narrative_events = loaded["narrative"]["events"]
    variants_by_group: dict[str, set[str]] = defaultdict(set)
    for context in native_contexts:
        native = context["native_row"]
        variants_by_group[native["source_event_group_key"]].add(
            native["source_event_variant_digest"]
        )
    decode_groups = {
        context["source_event"].get("decode_group_id")
        for context in native_contexts
        if context["source_event"].get("decode_group_id") is not None
    }
    actual = {
        "narrative_events": len(narrative_events),
        "executed_narrative_events": sum(
            event["executed"] for event in narrative_events
        ),
        "executed_observation_groups": sum(
            event["executed"]
            and event.get("kind") == "OBSERVATION_GROUP"
            for event in narrative_events
        ),
        "deliveries": len(deliveries),
        "source_native_records": len(native_contexts),
        "source_event_groups": len(event_groups),
        "logical_source_event_variants": sum(
            len(variants) for variants in variants_by_group.values()
        ),
        "canonical_observations": len(canonical_rows),
        "lineage_edges": len(lineage_rows),
        "canonical_point_definitions_represented": len(
            {
                row["canonical_point_definition_id"]
                for row in canonical_rows
            }
        ),
        "source_bindings": len(
            loaded["mapping_package"]["source_bindings"]
        ),
        "mapping_versions": len(loaded["mapping_package"]["mappings"]),
        "register_decode_groups": len(decode_groups),
        "exact_redelivery_groups": len(
            {
                context["native_row"]["source_event_group_key"]
                for context in native_contexts
                if context["classification"] == "EXACT_REDELIVERY"
            }
        ),
        "conflicting_redelivery_groups": len(
            {
                context["native_row"]["source_event_group_key"]
                for context in native_contexts
                if context["classification"] == "CONFLICTING_REDELIVERY"
            }
        ),
        "missing_observed_at_records": sum(
            context["native_row"]["observed_at_status"] == "MISSING"
            for context in native_contexts
        ),
        "invalid_observed_at_records": sum(
            context["native_row"]["observed_at_status"] == "INVALID"
            for context in native_contexts
        ),
    }
    missing_counts = sorted(set(actual) - set(expected))
    unknown_counts = sorted(set(expected) - set(actual))
    if missing_counts or unknown_counts:
        detail = []
        if missing_counts:
            detail.append("missing " + ", ".join(missing_counts))
        if unknown_counts:
            detail.append("unsupported " + ", ".join(unknown_counts))
        raise ValueError(
            "Replay structural oracle expected-count inventory mismatch: "
            + "; ".join(detail)
        )
    mismatches = {
        key: {"expected": expected[key], "actual": actual[key]}
        for key in expected
        if expected[key] != actual[key]
    }
    if mismatches:
        raise ValueError(
            "Replay structural oracle count mismatch: "
            + canonical_json_text(mismatches)
        )


def _normalized_semantic_digest(
    *,
    loaded: dict[str, Any],
    native_contexts: list[dict[str, Any]],
    deliveries: list[dict[str, Any]],
    canonical_rows: list[dict[str, Any]],
    lineage_rows: list[dict[str, Any]],
    decode_issues: list[dict[str, Any]],
    annotations: list[dict[str, Any]],
    projection_summary: dict[str, Any],
) -> tuple[str, dict[str, str]]:
    delivery_semantics = [
        {
            key: value
            for key, value in delivery.items()
            if key
            not in {
                "replay_execution_id",
                "source_native_record_id",
            }
        }
        for delivery in deliveries
    ]
    native_semantics = []
    for context in native_contexts:
        semantic_row = {
            key: value
            for key, value in context["native_row"].items()
            if key
            not in {
                "source_native_record_id",
                "replay_execution_id",
            }
        }
        semantic_row["ordering_facts_json"] = canonical_json_text(
            _strip_run_scoped_fact_ids(
                json.loads(semantic_row["ordering_facts_json"])
            )
        )
        native_semantics.append(semantic_row)
    canonical_semantics = []
    for row in canonical_rows:
        semantic_row = {
            key: value
            for key, value in row.items()
            if key
            not in {
                "canonical_observation_id",
                "replay_execution_id",
            }
        }
        semantic_row["ordering_facts_json"] = canonical_json_text(
            _strip_run_scoped_fact_ids(
                json.loads(semantic_row["ordering_facts_json"])
            )
        )
        canonical_semantics.append(semantic_row)
    derivation_by_observation = {
        row["canonical_observation_id"]: (
            row["derivation_key"],
            row["canonical_point_definition_id"],
        )
        for row in canonical_rows
    }
    delivery_by_native = {
        context["native_row"]["source_native_record_id"]: context[
            "native_row"
        ]["delivery_id"]
        for context in native_contexts
    }
    lineage_semantics = [
        {
            "derivation_key": derivation_by_observation[
                row["canonical_observation_id"]
            ][0],
            "target_point_id": derivation_by_observation[
                row["canonical_observation_id"]
            ][1],
            "delivery_id": delivery_by_native[row["source_native_record_id"]],
            "input_ordinal": row["input_ordinal"],
            "lineage_role": row["lineage_role"],
            "source_field_path": row["source_field_path"],
        }
        for row in lineage_rows
    ]
    issue_semantics = [
        {
            key: value
            for key, value in issue.items()
            if key not in {"replay_execution_id", "source_native_record_id"}
        }
        for issue in decode_issues
    ]
    annotation_semantics = [
        {
            key: value
            for key, value in annotation.items()
            if key != "replay_execution_id"
        }
        for annotation in annotations
    ]
    semantic_digests = {
        "delivery_records_digest": canonical_json_sha256(delivery_semantics),
        "source_native_records_digest": canonical_json_sha256(native_semantics),
        "canonical_observations_digest": canonical_json_sha256(
            canonical_semantics
        ),
        "canonical_lineage_digest": canonical_json_sha256(lineage_semantics),
        "decode_issues_digest": canonical_json_sha256(issue_semantics),
        "annotations_digest": canonical_json_sha256(annotation_semantics),
        "projection_summary_digest": canonical_json_sha256(
            projection_summary
        ),
    }
    semantic_material = {
        "replay_package": {
            "package_id": loaded["package_id"],
            "package_version": loaded["package_version"],
            "content_digest": loaded["content_digest"],
        },
        "topology": loaded["topology"],
        "mapping_package": {
            "package_id": loaded["mapping_package"]["package_id"],
            "package_version": loaded["mapping_package"]["package_version"],
            "content_digest": loaded["mapping_package"]["content_digest"],
        },
        "canonicalizer_version": CANONICALIZER_VERSION,
        "digests": semantic_digests,
        "record_counts": {
            "deliveries": len(deliveries),
            "source_native_records": len(native_contexts),
            "canonical_observations": len(canonical_rows),
            "canonical_lineage_records": len(lineage_rows),
            "decode_issues": len(decode_issues),
            "annotations": len(annotations),
        },
    }
    return canonical_json_sha256(semantic_material), semantic_digests


def _build_reproducibility_manifest(
    *,
    loaded: dict[str, Any],
    execution: dict[str, Any],
    native_contexts: list[dict[str, Any]],
    deliveries: list[dict[str, Any]],
    canonical_rows: list[dict[str, Any]],
    lineage_rows: list[dict[str, Any]],
    decode_issues: list[dict[str, Any]],
    annotations: list[dict[str, Any]],
    projection_summary: dict[str, Any],
    semantic_digests: dict[str, str],
) -> dict[str, Any]:
    by_group: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for context in native_contexts:
        by_group[context["native_row"]["source_event_group_key"]].append(context)
    exact_groups = []
    conflict_groups = []
    for group_key, contexts in sorted(by_group.items()):
        variants = {
            context["native_row"]["source_event_variant_digest"]
            for context in contexts
        }
        item = {
            "source_event_group_key": group_key,
            "delivery_ids": [
                context["native_row"]["delivery_id"] for context in contexts
            ],
            "delivery_count": len(contexts),
            "variant_count": len(variants),
        }
        if len(contexts) > 1 and len(variants) == 1:
            exact_groups.append(item)
        if len(variants) > 1:
            conflict_groups.append(item)

    return {
        "schema_version": 1,
        "replay_execution_id": execution["replay_execution_id"],
        "replay_package": {
            "package_id": loaded["package_id"],
            "package_version": loaded["package_version"],
            "content_digest": loaded["content_digest"],
        },
        "topology": deepcopy(loaded["topology"]),
        "mapping_package": {
            "package_id": loaded["mapping_package"]["package_id"],
            "package_version": loaded["mapping_package"]["package_version"],
            "content_digest": loaded["mapping_package"]["content_digest"],
        },
        "source_bindings": [
            {
                "source_binding_id": binding["source_binding_id"],
                "source_binding_version": binding[
                    "source_binding_version"
                ],
                "content_digest": binding["content_digest"],
                "source_id": binding["source_id"],
                "channel": binding["channel"],
            }
            for binding in loaded["mapping_package"]["source_bindings"]
        ],
        "mappings": [
            {
                "mapping_id": mapping["mapping_id"],
                "mapping_version": mapping["mapping_version"],
                "content_digest": mapping["content_digest"],
                "source_binding_id": mapping["source_binding_id"],
            }
            for mapping in loaded["mapping_package"]["mappings"]
        ],
        "canonicalizer_version": CANONICALIZER_VERSION,
        "input": {
            "delivery_count": len(deliveries),
            "source_native_record_count": len(native_contexts),
            "package_deliveries_digest": canonical_json_sha256(
                loaded["deliveries"]
            ),
            "delivery_records_digest": semantic_digests[
                "delivery_records_digest"
            ],
            "source_native_records_digest": semantic_digests[
                "source_native_records_digest"
            ],
        },
        "derived": {
            "canonical_observation_count": len(canonical_rows),
            "canonical_lineage_record_count": len(lineage_rows),
            "decode_issue_count": len(decode_issues),
            "annotation_count": len(annotations),
            "canonical_observations_digest": semantic_digests[
                "canonical_observations_digest"
            ],
            "canonical_lineage_digest": semantic_digests[
                "canonical_lineage_digest"
            ],
            "decode_issues_digest": semantic_digests[
                "decode_issues_digest"
            ],
            "annotations_digest": semantic_digests["annotations_digest"],
            "normalized_semantic_digest": execution[
                "normalized_semantic_digest"
            ],
        },
        "redelivery_summary": {
            "exact_redelivery_groups": exact_groups,
            "conflict_groups": conflict_groups,
        },
        "projection_summary": projection_summary,
        "structural_oracle": deepcopy(loaded["oracle"]),
        "limitations": [
            "The manifest hash establishes reproducibility and integrity of "
            "the represented data only. It does not establish authenticity, "
            "correctness, applicability, independence, or physical truth.",
            "The replay is synthetic laboratory evidence. No equipment, "
            "system, pressure-cascade, containment, facility, conformance, "
            "safety, authorization, or recovery conclusion is computed.",
        ],
    }


def _row_value(row: dict[str, Any]) -> Any:
    if row["value_type"] == "BOOLEAN":
        return bool(row["value_boolean"])
    if row["value_type"] == "INTEGER":
        return row["value_integer"]
    if row["value_type"] == "DECIMAL":
        return row["value_decimal"]
    return row["value_text"]


def _strip_run_scoped_fact_ids(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _strip_run_scoped_fact_ids(nested)
            for key, nested in value.items()
            if key not in {"left_candidate_id", "right_candidate_id"}
        }
    if isinstance(value, list):
        return [_strip_run_scoped_fact_ids(nested) for nested in value]
    return value


def _semantic_derivation_key(material: dict[str, Any]) -> str:
    return f"DERIVATION-{canonical_json_sha256(material)}"


def _run_scoped_id(prefix: str, *parts: str) -> str:
    return f"{prefix}-{canonical_json_sha256(list(parts))[:32]}"


def _compare_context_receipts(
    left: dict[str, Any],
    right: dict[str, Any],
) -> int:
    relation = compare_rfc3339_instants(
        left["native_row"]["received_at_utc"],
        right["native_row"]["received_at_utc"],
    )
    if relation == ORDER_BEFORE:
        return -1
    if relation == ORDER_AFTER:
        return 1
    left_delivery_id = left["native_row"]["delivery_id"]
    right_delivery_id = right["native_row"]["delivery_id"]
    return (left_delivery_id > right_delivery_id) - (
        left_delivery_id < right_delivery_id
    )


def _latest_timestamp(values: list[str]) -> str:
    if not values:
        raise ValueError("At least one timestamp is required")

    def compare(left: str, right: str) -> int:
        relation = compare_rfc3339_instants(left, right)
        if relation == ORDER_BEFORE:
            return -1
        if relation == ORDER_AFTER:
            return 1
        return 0

    return sorted(values, key=cmp_to_key(compare))[-1]


def _require_idempotency_key(value: Any) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > MAX_IDEMPOTENCY_KEY_LENGTH
    ):
        raise ValueError(
            "idempotency_key must be a bounded non-blank string without "
            "outer whitespace"
        )
    return value


def _require_execution_id(value: Any) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > 256
    ):
        raise ValueError(
            "replay_execution_id must be a bounded non-blank string without "
            "outer whitespace"
        )
    return value


__all__ = [
    "build_replay_plan",
    "execute_replay_package",
    "get_canonical_lineage",
    "get_canonical_observation",
    "get_replay_execution",
    "get_reported_observation_projection",
    "get_reproducibility_manifest",
    "get_source_native_record",
    "list_canonical_observations",
    "list_redelivery_groups",
    "list_source_native_records",
]
