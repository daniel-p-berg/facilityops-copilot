import hashlib
import json
import sqlite3
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from backend.domain.observation_semantics import canonical_json_text
from backend.services.observation_store import (
    IdempotencyConflictError,
    ImmutableIdentityConflictError,
    ObservationStoreError,
    get_canonical_lineage,
    get_canonical_observation,
    get_replay_execution,
    get_source_native_record,
    initialize_observation_store,
    list_canonical_observations,
    list_redelivery_groups,
    list_source_native_records,
    persist_replay_execution,
    projection_candidates,
)


FACILITY_ID = "FACILITY-TEST"
EXECUTION_ID = "REPLAY-EXECUTION-1"


def digest(label):
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def json_text(value):
    return canonical_json_text(value)


def replay_plan():
    topology_digest = digest("topology")
    mapping_digest = digest("mapping")
    package_digest = digest("package")
    request_digest = digest("request")
    semantic_digest = digest("semantic")
    observed_text = "2026-07-23T17:00:00+07:00"
    observed_utc = "2026-07-23T10:00:00Z"

    groups = []
    deliveries = []
    native_records = []
    delivery_specs = (
        (
            "DELIVERY-1",
            "NATIVE-1",
            "GROUP-EXACT",
            "SOURCE_EVENT_ID",
            "EVENT-1",
            1,
            digest("variant-exact"),
            "NEW_EVENT",
            "2026-07-23T10:00:01Z",
            {"value": True},
        ),
        (
            "DELIVERY-2",
            "NATIVE-2",
            "GROUP-EXACT",
            "SOURCE_EVENT_ID",
            "EVENT-1",
            1,
            digest("variant-exact"),
            "EXACT_REDELIVERY",
            "2026-07-23T10:00:02Z",
            {"value": True},
        ),
        (
            "DELIVERY-3",
            "NATIVE-3",
            "GROUP-HIGH",
            "SOURCE_EVENT_ID",
            "EVENT-HIGH",
            2,
            digest("variant-high"),
            "NEW_EVENT",
            "2026-07-23T10:00:03Z",
            {"register": 0},
        ),
        (
            "DELIVERY-4",
            "NATIVE-4",
            "GROUP-LOW",
            "SOURCE_EVENT_ID",
            "EVENT-LOW",
            3,
            digest("variant-low"),
            "NEW_EVENT",
            "2026-07-23T10:00:04Z",
            {"register": 125},
        ),
    )
    seen_groups = set()
    for (
        delivery_id,
        native_id,
        group_key,
        identity_kind,
        event_id,
        sequence,
        variant_digest,
        redelivery_classification,
        received_at,
        payload,
    ) in delivery_specs:
        if group_key not in seen_groups:
            groups.append(
                {
                    "replay_execution_id": EXECUTION_ID,
                    "source_event_group_key": group_key,
                    "facility_id": FACILITY_ID,
                    "source_binding_id": "SOURCE-BINDING-1",
                    "identity_kind": identity_kind,
                    "source_event_id": event_id,
                    "source_session_epoch": "BOOT-1",
                    "source_sequence": sequence,
                }
            )
            seen_groups.add(group_key)
        deliveries.append(
            {
                "replay_execution_id": EXECUTION_ID,
                "delivery_id": delivery_id,
                "facility_id": FACILITY_ID,
                "ingestion_ordinal": len(deliveries) + 1,
                "idempotency_key": f"DELIVERY-KEY-{len(deliveries) + 1}",
                "request_digest": digest(f"delivery-{delivery_id}"),
                "source_binding_id": "SOURCE-BINDING-1",
                "source_event_group_key": group_key,
                "redelivery_classification": redelivery_classification,
                "received_at_utc": received_at,
                "source_native_record_id": native_id,
            }
        )
        native_records.append(
            {
                "source_native_record_id": native_id,
                "replay_execution_id": EXECUTION_ID,
                "delivery_id": delivery_id,
                "facility_id": FACILITY_ID,
                "source_binding_id": "SOURCE-BINDING-1",
                "source_event_group_key": group_key,
                "source_event_variant_digest": variant_digest,
                "mapping_id": "MAPPING-1",
                "mapping_version": "1.0.0",
                "mapping_digest": mapping_digest,
                "payload_json": json_text(payload),
                "payload_digest": digest(json_text(payload)),
                "original_observed_at_text": observed_text,
                "original_timezone_offset": "+07:00",
                "timestamp_precision": "SECOND",
                "fractional_second_digits": 0,
                "observed_at_status": "VALID",
                "observed_at_utc": observed_utc,
                "received_at_utc": received_at,
                "source_sequence": sequence,
                "source_session_epoch": "BOOT-1",
                "source_quality_json": json_text({"raw": "GOOD"}),
                "source_metadata_json": json_text(
                    {"event_id": event_id}
                ),
                "transport_provenance_json": json_text(
                    {"transport": "REPOSITORY_REPLAY"}
                ),
                "synthetic_provenance_json": json_text(
                    {"synthetic": True}
                ),
                "ordering_facts_json": json_text([]),
            }
        )

    canonical_observations = [
        {
            "canonical_observation_id": "CANONICAL-1",
            "replay_execution_id": EXECUTION_ID,
            "facility_id": FACILITY_ID,
            "source_binding_id": "SOURCE-BINDING-1",
            "source_event_group_key": "GROUP-EXACT",
            "source_event_variant_digest": digest("variant-exact"),
            "canonical_point_definition_id": "POINT-BOOLEAN",
            "mapping_id": "MAPPING-1",
            "mapping_version": "1.0.0",
            "mapping_digest": mapping_digest,
            "canonicalizer_version": "facilityops-canonicalizer/1.0.0",
            "derivation_key": "DERIVATION-1",
            "value_type": "BOOLEAN",
            "value_boolean": True,
            "value_integer": None,
            "value_decimal": None,
            "value_text": None,
            "unit": None,
            "time_basis": "SOURCE_REPORTED_OBSERVED_AT",
            "observed_at_status": "VALID",
            "observed_at_utc": observed_utc,
            "received_at_utc": "2026-07-23T10:00:01Z",
            "source_sequence": 1,
            "source_session_epoch": "BOOT-1",
            "source_quality_provenance_json": json_text(
                {"raw": "GOOD"}
            ),
            "synthetic_provenance_json": json_text({"synthetic": True}),
            "report_material_digest": digest("report-boolean"),
            "ordering_facts_json": json_text([]),
        },
        {
            "canonical_observation_id": "CANONICAL-2",
            "replay_execution_id": EXECUTION_ID,
            "facility_id": FACILITY_ID,
            "source_binding_id": "SOURCE-BINDING-1",
            "source_event_group_key": None,
            "source_event_variant_digest": digest("register-pair"),
            "canonical_point_definition_id": "POINT-DECIMAL",
            "mapping_id": "MAPPING-1",
            "mapping_version": "1.0.0",
            "mapping_digest": mapping_digest,
            "canonicalizer_version": "facilityops-canonicalizer/1.0.0",
            "derivation_key": "DERIVATION-2",
            "value_type": "DECIMAL",
            "value_boolean": None,
            "value_integer": None,
            "value_decimal": "1.25",
            "value_text": None,
            "unit": "A",
            "time_basis": "SOURCE_REPORTED_OBSERVED_AT",
            "observed_at_status": "VALID",
            "observed_at_utc": observed_utc,
            "received_at_utc": "2026-07-23T10:00:04Z",
            "source_sequence": None,
            "source_session_epoch": "BOOT-1",
            "source_quality_provenance_json": json_text(
                {"raw": ["GOOD", "GOOD"]}
            ),
            "synthetic_provenance_json": json_text({"synthetic": True}),
            "report_material_digest": digest("report-decimal"),
            "ordering_facts_json": json_text([]),
        },
    ]
    lineage = [
        {
            "canonical_observation_id": "CANONICAL-1",
            "source_native_record_id": "NATIVE-1",
            "input_ordinal": 1,
            "lineage_role": "DIRECT_FIELD",
            "source_field_path": "$.value",
        },
        {
            "canonical_observation_id": "CANONICAL-1",
            "source_native_record_id": "NATIVE-2",
            "input_ordinal": 1,
            "lineage_role": "EXACT_REDELIVERY",
            "source_field_path": "$.value",
        },
        {
            "canonical_observation_id": "CANONICAL-2",
            "source_native_record_id": "NATIVE-3",
            "input_ordinal": 1,
            "lineage_role": "HIGH_WORD",
            "source_field_path": "$.register",
        },
        {
            "canonical_observation_id": "CANONICAL-2",
            "source_native_record_id": "NATIVE-4",
            "input_ordinal": 2,
            "lineage_role": "LOW_WORD",
            "source_field_path": "$.register",
        },
    ]

    return {
        "request": {"idempotency_key": "REPLAY-REQUEST-KEY-1"},
        "topology_snapshot": {
            "topology_id": "TOPOLOGY-1",
            "topology_version": "1.0.0",
            "content_digest": topology_digest,
            "facility_id": FACILITY_ID,
            "manifest_json": json_text({"topology": "TOPOLOGY-1"}),
        },
        "source_bindings": [
            {
                "facility_id": FACILITY_ID,
                "source_binding_id": "SOURCE-BINDING-1",
                "source_id": "SOURCE-1",
                "channel": "CHANNEL-1",
                "dependency_provenance_json": json_text(
                    {"upstream_dependency": "UNKNOWN"}
                ),
            }
        ],
        "mapping_snapshots": [
            {
                "mapping_id": "MAPPING-1",
                "mapping_version": "1.0.0",
                "content_digest": mapping_digest,
                "facility_id": FACILITY_ID,
                "topology_id": "TOPOLOGY-1",
                "topology_version": "1.0.0",
                "topology_digest": topology_digest,
                "source_binding_id": "SOURCE-BINDING-1",
                "definition_json": json_text({"kind": "DIRECT_AND_PAIR"}),
            }
        ],
        "package_snapshot": {
            "package_id": "PACKAGE-1",
            "package_version": "1.0.0",
            "content_digest": package_digest,
            "facility_id": FACILITY_ID,
            "topology_id": "TOPOLOGY-1",
            "topology_version": "1.0.0",
            "topology_digest": topology_digest,
            "manifest_json": json_text({"package": "PACKAGE-1"}),
        },
        "execution": {
            "replay_execution_id": EXECUTION_ID,
            "facility_id": FACILITY_ID,
            "package_id": "PACKAGE-1",
            "package_version": "1.0.0",
            "package_digest": package_digest,
            "topology_id": "TOPOLOGY-1",
            "topology_version": "1.0.0",
            "topology_digest": topology_digest,
            "canonicalizer_version": "facilityops-canonicalizer/1.0.0",
            "request_digest": request_digest,
            "status": "COMPLETED",
            "recorded_at": "2026-07-23T11:00:00Z",
            "normalized_semantic_digest": semantic_digest,
        },
        "source_event_groups": groups,
        "deliveries": deliveries,
        "source_native_records": native_records,
        "canonical_observations": canonical_observations,
        "lineage": lineage,
        "decode_issues": [],
        "annotations": [],
        "reproducibility_manifest": {
            "replay_execution_id": EXECUTION_ID,
            "manifest_digest": digest("manifest"),
            "normalized_semantic_digest": semantic_digest,
            "manifest_json": json_text(
                {
                    "replay_execution_id": EXECUTION_ID,
                    "disclaimer": (
                        "Synthetic reported indications; no physical-state "
                        "or safety conclusion."
                    ),
                }
            ),
        },
    }


def rekey_execution(plan, execution_id):
    original_id = plan["execution"]["replay_execution_id"]
    plan["execution"]["replay_execution_id"] = execution_id
    plan["reproducibility_manifest"]["replay_execution_id"] = execution_id
    for key in (
        "source_event_groups",
        "deliveries",
        "source_native_records",
        "canonical_observations",
        "decode_issues",
        "annotations",
    ):
        for row in plan[key]:
            if row.get("replay_execution_id") == original_id:
                row["replay_execution_id"] = execution_id
    return plan


class ObservationStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_directory.cleanup)
        self.db_path = Path(self.temp_directory.name) / "observation.sqlite3"

    def test_schema_initialization_is_explicit_and_rollback_capable(self):
        self.assertFalse(self.db_path.exists())

        with self.assertRaisesRegex(RuntimeError, "Injected"):
            initialize_observation_store(
                self.db_path,
                inject_failure_after_statement=5,
            )

        with sqlite3.connect(self.db_path) as connection:
            objects = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type IN ('table', 'trigger', 'index')
                  AND name NOT LIKE 'sqlite_%'
                """
            ).fetchall()
        self.assertEqual(objects, [])

        initialize_observation_store(self.db_path)
        with sqlite3.connect(self.db_path) as connection:
            self.assertEqual(
                connection.execute(
                    """
                    SELECT schema_version
                    FROM observation_store_metadata
                    """
                ).fetchone()[0],
                1,
            )

    def test_persists_typed_records_exact_lineage_and_multi_source_decode(self):
        result = persist_replay_execution(self.db_path, replay_plan())

        self.assertFalse(result["idempotent_replay"])
        execution = get_replay_execution(
            self.db_path,
            FACILITY_ID,
            EXECUTION_ID,
        )
        self.assertEqual(
            execution["record_counts"],
            {
                "deliveries": 4,
                "source_native_records": 4,
                "canonical_observations": 2,
                "decode_issues": 0,
            },
        )

        boolean_observation = get_canonical_observation(
            self.db_path,
            FACILITY_ID,
            "CANONICAL-1",
        )
        self.assertIs(boolean_observation["normalized_value"], True)
        self.assertEqual(
            boolean_observation["time_basis"],
            "SOURCE_REPORTED_OBSERVED_AT",
        )
        pair_observation = get_canonical_observation(
            self.db_path,
            FACILITY_ID,
            "CANONICAL-2",
        )
        self.assertEqual(pair_observation["normalized_value"], "1.25")
        self.assertIsNone(pair_observation["source_event_group_key"])

        exact_lineage = get_canonical_lineage(
            self.db_path,
            FACILITY_ID,
            "CANONICAL-1",
        )
        self.assertEqual(
            {
                row["source_native_record_id"]
                for row in exact_lineage["source_native_lineage"]
            },
            {"NATIVE-1", "NATIVE-2"},
        )
        pair_lineage = get_canonical_lineage(
            self.db_path,
            FACILITY_ID,
            "CANONICAL-2",
        )
        self.assertEqual(
            [
                row["source_native_record_id"]
                for row in pair_lineage["source_native_lineage"]
            ],
            ["NATIVE-3", "NATIVE-4"],
        )

    def test_retry_is_idempotent_only_for_same_key_and_request_digest(self):
        plan = replay_plan()
        persist_replay_execution(self.db_path, plan)

        retry = rekey_execution(deepcopy(plan), "REPLAY-EXECUTION-RETRY")
        result = persist_replay_execution(self.db_path, retry)
        self.assertEqual(
            result,
            {
                "replay_execution_id": EXECUTION_ID,
                "idempotent_replay": True,
            },
        )

        mismatch = deepcopy(retry)
        mismatch["execution"]["request_digest"] = digest("other-request")
        with self.assertRaises(IdempotencyConflictError):
            persist_replay_execution(self.db_path, mismatch)

        reused_execution = deepcopy(plan)
        reused_execution["request"]["idempotency_key"] = "OTHER-KEY"
        with self.assertRaises(IdempotencyConflictError):
            persist_replay_execution(self.db_path, reused_execution)

    def test_injected_failure_exposes_no_partial_execution(self):
        with self.assertRaisesRegex(RuntimeError, "Injected"):
            persist_replay_execution(
                self.db_path,
                replay_plan(),
                inject_failure_after_native_record=2,
            )

        with sqlite3.connect(self.db_path) as connection:
            for table_name in (
                "topology_snapshots",
                "replay_executions",
                "replay_deliveries",
                "source_native_records",
                "canonical_observations",
                "canonical_observation_lineage",
                "reproducibility_manifests",
            ):
                self.assertEqual(
                    connection.execute(
                        f"SELECT COUNT(*) FROM {table_name}"
                    ).fetchone()[0],
                    0,
                )

        result = persist_replay_execution(self.db_path, replay_plan())
        self.assertFalse(result["idempotent_replay"])

    def test_immutable_triggers_block_update_and_delete(self):
        persist_replay_execution(self.db_path, replay_plan())

        with sqlite3.connect(self.db_path) as connection:
            with self.assertRaisesRegex(sqlite3.IntegrityError, "append-only"):
                connection.execute(
                    """
                    UPDATE source_native_records
                    SET payload_digest = ?
                    WHERE source_native_record_id = 'NATIVE-1'
                    """,
                    (digest("changed"),),
                )
            with self.assertRaisesRegex(sqlite3.IntegrityError, "append-only"):
                connection.execute(
                    """
                    DELETE FROM replay_executions
                    WHERE replay_execution_id = ?
                    """,
                    (EXECUTION_ID,),
                )

    def test_lineage_scope_and_exact_redelivery_completeness_are_atomic(self):
        cross_scope = replay_plan()
        cross_scope["lineage"][0]["source_native_record_id"] = "NATIVE-3"
        with self.assertRaisesRegex(
            sqlite3.IntegrityError,
            "lineage crosses",
        ):
            persist_replay_execution(self.db_path, cross_scope)

        self.assertFalse(
            list_source_native_records(
                self.db_path,
                FACILITY_ID,
                EXECUTION_ID,
            )["source_native_records"]
        )

        missing_redelivery = replay_plan()
        missing_redelivery["lineage"] = [
            row
            for row in missing_redelivery["lineage"]
            if not (
                row["canonical_observation_id"] == "CANONICAL-1"
                and row["source_native_record_id"] == "NATIVE-2"
            )
        ]
        with self.assertRaisesRegex(
            ObservationStoreError,
            "exact-redelivery lineage",
        ):
            persist_replay_execution(self.db_path, missing_redelivery)

    def test_typed_values_timestamp_metadata_json_and_digests_are_validated(self):
        invalid_decimal = replay_plan()
        invalid_decimal["canonical_observations"][1]["value_decimal"] = "1e0"
        with self.assertRaisesRegex(ValueError, "non-exponential"):
            persist_replay_execution(self.db_path, invalid_decimal)

        invalid_time = replay_plan()
        invalid_time["source_native_records"][0][
            "original_timezone_offset"
        ] = "Z"
        with self.assertRaisesRegex(ValueError, "timestamp metadata"):
            persist_replay_execution(self.db_path, invalid_time)

        invalid_json = replay_plan()
        invalid_json["source_bindings"][0][
            "dependency_provenance_json"
        ] = '{"value":NaN}'
        with self.assertRaisesRegex(ValueError, "valid JSON"):
            persist_replay_execution(self.db_path, invalid_json)

        invalid_digest = replay_plan()
        invalid_digest["execution"]["request_digest"] = "NOT-A-DIGEST"
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            persist_replay_execution(self.db_path, invalid_digest)

    def test_snapshot_identity_cannot_change_under_same_version(self):
        persist_replay_execution(self.db_path, replay_plan())
        second = rekey_execution(deepcopy(replay_plan()), "REPLAY-EXECUTION-2")
        second["request"]["idempotency_key"] = "REPLAY-REQUEST-KEY-2"
        second["execution"]["request_digest"] = digest("request-2")
        second["source_bindings"][0]["channel"] = "CHANGED-CHANNEL"

        with self.assertRaises(ImmutableIdentityConflictError):
            persist_replay_execution(self.db_path, second)

    def test_lists_are_facility_scoped_bounded_and_deterministically_paged(self):
        persist_replay_execution(self.db_path, replay_plan())

        first_page = list_source_native_records(
            self.db_path,
            FACILITY_ID,
            EXECUTION_ID,
            page=1,
            page_size=2,
        )
        second_page = list_source_native_records(
            self.db_path,
            FACILITY_ID,
            EXECUTION_ID,
            page=2,
            page_size=2,
        )
        self.assertEqual(
            [
                row["source_native_record_id"]
                for row in first_page["source_native_records"]
            ],
            ["NATIVE-1", "NATIVE-2"],
        )
        self.assertEqual(
            {
                (
                    row["identity_kind"],
                    row["source_event_id"],
                )
                for row in first_page["source_native_records"]
            },
            {("SOURCE_EVENT_ID", "EVENT-1")},
        )
        self.assertEqual(
            [
                row["source_native_record_id"]
                for row in second_page["source_native_records"]
            ],
            ["NATIVE-3", "NATIVE-4"],
        )
        self.assertFalse(second_page["pagination"]["has_more"])

        canonical = list_canonical_observations(
            self.db_path,
            FACILITY_ID,
            EXECUTION_ID,
            page_size=1,
        )
        self.assertEqual(canonical["pagination"]["total_records"], 2)
        groups = list_redelivery_groups(
            self.db_path,
            FACILITY_ID,
            EXECUTION_ID,
            page_size=1,
        )
        self.assertEqual(groups["pagination"]["total_records"], 1)
        self.assertEqual(
            groups["redelivery_groups"][0]["exact_redelivery_count"],
            1,
        )

        empty = list_source_native_records(
            self.db_path,
            "OTHER-FACILITY",
            EXECUTION_ID,
        )
        self.assertEqual(empty["source_native_records"], [])
        with self.assertRaisesRegex(ValueError, "1 through 100"):
            list_source_native_records(
                self.db_path,
                FACILITY_ID,
                EXECUTION_ID,
                page_size=101,
            )

    def test_source_native_detail_preserves_source_and_transport_fields(self):
        persist_replay_execution(self.db_path, replay_plan())

        record = get_source_native_record(
            self.db_path,
            FACILITY_ID,
            "NATIVE-1",
        )
        self.assertEqual(record["payload"], {"value": True})
        self.assertEqual(
            record["original_observed_at_text"],
            "2026-07-23T17:00:00+07:00",
        )
        self.assertEqual(record["original_timezone_offset"], "+07:00")
        self.assertEqual(record["observed_at_utc"], "2026-07-23T10:00:00Z")
        self.assertEqual(record["identity_kind"], "SOURCE_EVENT_ID")
        self.assertEqual(record["source_event_id"], "EVENT-1")
        self.assertEqual(
            record["transport_provenance"],
            {"transport": "REPOSITORY_REPLAY"},
        )

    def test_projection_candidates_preserve_scope_time_basis_and_lineage(self):
        plan = replay_plan()
        persist_replay_execution(self.db_path, plan)

        candidates = projection_candidates(
            self.db_path,
            FACILITY_ID,
            EXECUTION_ID,
            source_binding_id="SOURCE-BINDING-1",
            point_id="POINT-BOOLEAN",
            mapping_id="MAPPING-1",
            mapping_version="1.0.0",
            mapping_digest=plan["mapping_snapshots"][0]["content_digest"],
            known_by_received_at="2026-07-23T10:00:02Z",
        )

        self.assertEqual(len(candidates), 2)
        self.assertEqual(
            [
                candidate["source_native_record_ids"]
                for candidate in candidates
            ],
            [["NATIVE-1"], ["NATIVE-2"]],
        )
        self.assertEqual(
            [
                candidate["received_at_utc"]
                for candidate in candidates
            ],
            [
                "2026-07-23T10:00:01Z",
                "2026-07-23T10:00:02Z",
            ],
        )
        self.assertEqual(
            candidates[0]["time_basis"],
            "SOURCE_REPORTED_OBSERVED_AT",
        )
        self.assertFalse(candidates[0]["source_event_conflict"])
        self.assertEqual(candidates[0]["known_source_event_variant_count"], 1)

        pair_candidates = projection_candidates(
            self.db_path,
            FACILITY_ID,
            EXECUTION_ID,
            source_binding_id="SOURCE-BINDING-1",
            point_id="POINT-DECIMAL",
            mapping_id="MAPPING-1",
            mapping_version="1.0.0",
            mapping_digest=plan["mapping_snapshots"][0]["content_digest"],
            known_by_received_at="2026-07-23T10:00:04Z",
        )
        self.assertIsNone(pair_candidates[0]["source_event_group_key"])
        self.assertFalse(pair_candidates[0]["source_event_conflict"])
        self.assertEqual(
            pair_candidates[0]["known_source_event_variant_count"],
            0,
        )
        self.assertEqual(
            pair_candidates[0]["source_native_record_ids"],
            ["NATIVE-3", "NATIVE-4"],
        )

    def test_canonical_time_filter_compares_fractional_instants(self):
        plan = replay_plan()
        plan["canonical_observations"][0][
            "observed_at_utc"
        ] = "2026-07-23T10:00:00Z"
        plan["canonical_observations"][1][
            "observed_at_utc"
        ] = "2026-07-23T10:00:00.1Z"
        persist_replay_execution(self.db_path, plan)

        page = list_canonical_observations(
            self.db_path,
            FACILITY_ID,
            EXECUTION_ID,
            observed_from="2026-07-23T10:00:00.05Z",
            observed_to="2026-07-23T10:00:00.10Z",
        )

        self.assertEqual(page["pagination"]["total_records"], 1)
        self.assertEqual(
            page["canonical_observations"][0][
                "canonical_observation_id"
            ],
            "CANONICAL-2",
        )


if __name__ == "__main__":
    unittest.main()
