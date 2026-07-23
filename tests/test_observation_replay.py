import json
import shutil
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
from unittest import mock

from backend.domain.observation_semantics import canonical_json_sha256
from backend.services import observation_package_service
from backend.services.facility_package_registry import FLAGSHIP_FACILITY_ID
from backend.services.observation_package_service import (
    FLAGSHIP_REPLAY_MANIFEST,
    FLAGSHIP_REPLAY_PACKAGE_ID,
    FLAGSHIP_REPLAY_PACKAGE_VERSION,
    REGISTERED_REPLAY_PACKAGES,
    get_replay_package_detail,
    list_replay_packages,
    load_replay_package,
    package_content_digest,
)
from backend.services.observation_replay_service import (
    build_replay_plan,
    execute_replay_package,
    get_canonical_lineage,
    get_reported_observation_projection,
    get_reproducibility_manifest,
    list_canonical_observations,
    list_redelivery_groups,
    list_source_native_records,
)
from backend.services.observation_store import (
    IdempotencyConflictError,
    get_replay_execution,
    persist_replay_execution,
)


PACKAGE_KEY = (
    FLAGSHIP_FACILITY_ID,
    FLAGSHIP_REPLAY_PACKAGE_ID,
    FLAGSHIP_REPLAY_PACKAGE_VERSION,
)


class ObservationReplayTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.temp_root = Path(self.temp_dir.name)
        self.db_path = self.temp_root / "observation-replay.sqlite3"
        self.loaded = load_replay_package(*PACKAGE_KEY)

    def build_plan(self, execution_id="REPLAY-EXECUTION-TEST-1", key="test-1"):
        return build_replay_plan(
            self.loaded,
            replay_execution_id=execution_id,
            requested_replay_execution_id=execution_id,
            idempotency_key=key,
        )

    def execute(self, execution_id="REPLAY-EXECUTION-TEST-1", key="test-1"):
        return execute_replay_package(
            self.db_path,
            facility_id=FLAGSHIP_FACILITY_ID,
            package_id=FLAGSHIP_REPLAY_PACKAGE_ID,
            package_version=FLAGSHIP_REPLAY_PACKAGE_VERSION,
            idempotency_key=key,
            replay_execution_id=execution_id,
        )

    def mapping(self, mapping_id, version="1.0.0"):
        return next(
            mapping
            for mapping in self.loaded["mapping_package"]["mappings"]
            if mapping["mapping_id"] == mapping_id
            and mapping["mapping_version"] == version
        )

    def projection(
        self,
        execution_id,
        *,
        source_binding_id,
        point_id,
        mapping_id,
        mapping_version="1.0.0",
        as_of,
        known_by,
    ):
        mapping = self.mapping(mapping_id, mapping_version)
        return get_reported_observation_projection(
            self.db_path,
            facility_id=FLAGSHIP_FACILITY_ID,
            replay_execution_id=execution_id,
            source_binding_id=source_binding_id,
            point_id=point_id,
            mapping_id=mapping_id,
            mapping_version=mapping_version,
            mapping_digest=mapping["content_digest"],
            as_of_observed_at=as_of,
            known_by_received_at=known_by,
        )

    def build_and_persist_mutation(self, mutated, execution_id, key):
        plan = build_replay_plan(
            mutated,
            replay_execution_id=execution_id,
            requested_replay_execution_id=execution_id,
            idempotency_key=key,
        )
        persist_replay_execution(self.db_path, plan)
        return plan

    def copied_replay_package(self, name, mutator):
        copied = self.temp_root / name
        shutil.copytree(FLAGSHIP_REPLAY_MANIFEST.parent, copied)
        manifest_path = copied / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        files = {
            role: json.loads(
                (copied / filename).read_text(encoding="utf-8")
            )
            for role, filename in manifest["files"].items()
        }
        mutator(manifest, files)
        for role, filename in manifest["files"].items():
            (copied / filename).write_text(
                json.dumps(files[role], indent=2) + "\n",
                encoding="utf-8",
            )
        manifest["content_digest"] = package_content_digest(manifest, files)
        manifest_path.write_text(
            json.dumps(manifest, indent=2) + "\n",
            encoding="utf-8",
        )
        return manifest_path

    def load_copied_replay_package(self, manifest_path):
        with mock.patch.dict(
            REGISTERED_REPLAY_PACKAGES,
            {PACKAGE_KEY: manifest_path},
        ):
            return load_replay_package(*PACKAGE_KEY)

    def test_allowlisted_catalog_and_detail_pin_exact_package_graph(self):
        catalog = list_replay_packages(FLAGSHIP_FACILITY_ID)
        self.assertEqual(len(catalog["replay_packages"]), 1)
        summary = catalog["replay_packages"][0]
        self.assertEqual(summary["package_id"], FLAGSHIP_REPLAY_PACKAGE_ID)
        self.assertEqual(
            summary["content_digest"],
            "10ca39fe3d98553ee23fc6da46b4064f696c18e9416a794e7221e8a380f4d103",
        )
        self.assertEqual(summary["topology"]["topology_version"], "1.1.0")
        self.assertEqual(
            summary["mapping_package"]["content_digest"],
            "bb911da15d4d4804742bfd5a999623d9e9e8acc7b9c85161dd15cdff7fb18e8a",
        )

        detail = get_replay_package_detail(*PACKAGE_KEY)
        self.assertEqual(detail["structural_validation"], "VALID")
        self.assertEqual(detail["delivery_count"], 41)
        self.assertEqual(len(detail["source_bindings"]), 10)
        self.assertEqual(len(detail["mappings"]), 11)
        self.assertEqual(len(detail["narrative"]["events"]), 20)
        self.assertEqual(
            detail["oracle"]["oracle_type"],
            "STRUCTURAL_OBSERVATION_ONLY",
        )

        with self.assertRaises(LookupError):
            load_replay_package(
                FLAGSHIP_FACILITY_ID,
                "file:///tmp/arbitrary-package",
                "1.0.0",
            )
        with self.assertRaises(LookupError):
            load_replay_package(
                "FACILITY-OTHER",
                FLAGSHIP_REPLAY_PACKAGE_ID,
                FLAGSHIP_REPLAY_PACKAGE_VERSION,
            )

    def test_narrative_contract_allows_only_received_indications_and_action(self):
        events = self.loaded["narrative"]["events"]
        self.assertEqual(len(events), 20)
        self.assertEqual(
            [
                event["event_id"]
                for event in events
                if event["kind"] == "ACTION_CONTEXT"
            ],
            ["E180-HUMAN-ACTION-RECORDED"],
        )
        observation_events = [
            event for event in events if event["kind"] == "OBSERVATION_GROUP"
        ]
        self.assertEqual(len(observation_events), 19)
        self.assertTrue(
            all(
                event["event_id"].endswith(
                    ("-INDICATION-RECEIVED", "-INDICATIONS-RECEIVED")
                )
                for event in observation_events
            )
        )
        self.assertTrue(all(event["executed"] is True for event in events))
        self.assertIn(
            "E220-PROCESS-PERMISSIVE-INDICATION-RECEIVED",
            {event["event_id"] for event in events},
        )

        def unsupported_kind(_manifest, files):
            files["narrative"]["events"][0]["kind"] = "RECOVERY_RESULT"

        def outcome_claim(_manifest, files):
            files["narrative"]["events"][0]["label"] = "Fan failed"

        def unapproved_state_name(_manifest, files):
            files["narrative"]["events"][0][
                "event_id"
            ] = "E010-FAN-RUNNING-INDICATION-RECEIVED"

        def inactive_entry(_manifest, files):
            files["narrative"]["events"][0]["executed"] = False

        def tranche_boundary(_manifest, files):
            files["narrative"]["events"].append(
                {
                    "event_id": "E230-RECOVERY-EVALUATION-REQUESTED",
                    "order": 230,
                    "kind": "TRANCHE_BOUNDARY",
                    "label": "Later capability",
                    "description": "Not implemented",
                    "executed": True,
                }
            )

        cases = (
            ("unsupported-kind", unsupported_kind, "received-indication"),
            ("outcome-claim", outcome_claim, "unapproved physical"),
            (
                "unapproved-state-name",
                unapproved_state_name,
                "recorded-action",
            ),
            ("inactive-entry", inactive_entry, "implemented replay entry"),
            ("tranche-boundary", tranche_boundary, "recorded-action"),
        )
        for name, mutator, expected_error in cases:
            with self.subTest(name=name):
                manifest_path = self.copied_replay_package(name, mutator)
                with self.assertRaisesRegex(ValueError, expected_error):
                    self.load_copied_replay_package(manifest_path)

    def test_package_bounds_and_declared_digest_are_enforced(self):
        with (
            mock.patch.object(
                observation_package_service,
                "MAX_REPOSITORY_PACKAGE_BYTES",
                1,
            ),
            self.assertRaisesRegex(ValueError, "Repository package exceeds"),
        ):
            load_replay_package(*PACKAGE_KEY)

        with (
            mock.patch.object(
                observation_package_service,
                "MAX_PACKAGE_FILE_BYTES",
                1,
            ),
            self.assertRaisesRegex(ValueError, "exceeds the 1-byte limit"),
        ):
            load_replay_package(*PACKAGE_KEY)

        with (
            mock.patch.object(
                observation_package_service,
                "MAX_SOURCE_PAYLOAD_BYTES",
                1,
            ),
            self.assertRaisesRegex(ValueError, "payload exceeds"),
        ):
            load_replay_package(*PACKAGE_KEY)

        manifest_path = self.copied_replay_package(
            "digest-mismatch",
            lambda _manifest, _files: None,
        )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["content_digest"] = "0" * 64
        manifest_path.write_text(
            json.dumps(manifest, indent=2) + "\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "content digest mismatch"):
            self.load_copied_replay_package(manifest_path)

    def test_source_dependency_origins_are_explicit_and_not_sufficiency_claims(self):
        required_fields = {
            "controller_logic_origin",
            "source_device_origin",
            "gateway_origin",
            "measurement_chain_origin",
            "power_origin",
            "timestamp_origin",
            "derivation_origin",
        }
        dependencies = [
            binding["dependency_provenance"]
            for binding in self.loaded["mapping_package"]["source_bindings"]
        ]
        self.assertTrue(dependencies)
        for dependency in dependencies:
            self.assertEqual(set(dependency), required_fields)
            self.assertTrue(
                all(
                    isinstance(value, str) and value
                    for value in dependency.values()
                )
            )
            self.assertNotIn("independent", dependency)
            self.assertNotIn("evidence_sufficient", dependency)
        self.assertTrue(
            any("UNKNOWN" in dependency.values() for dependency in dependencies)
        )

        incomplete = deepcopy(
            self.loaded["mapping_package"]["source_bindings"]
        )
        incomplete[0]["dependency_provenance"].pop("gateway_origin")
        with self.assertRaisesRegex(ValueError, "explicit UNKNOWN.*missing"):
            observation_package_service._validate_source_bindings(
                {"source_bindings": incomplete}
            )

    def test_every_replay_reference_resolves_before_execution(self):
        def missing_identity_delivery(_manifest, files):
            files["oracle"]["identity_groups"][0]["delivery_ids"][
                0
            ] = "DELIVERY-NOT-REGISTERED"

        def missing_identity_binding(_manifest, files):
            files["oracle"]["identity_groups"][0][
                "source_binding_id"
            ] = "SOURCE-BINDING-NOT-REGISTERED"

        def mismatched_source_event(_manifest, files):
            files["oracle"]["identity_groups"][0][
                "source_event_id"
            ] = "SOURCE-EVENT-NOT-REGISTERED"

        def missing_decode_delivery(_manifest, files):
            files["oracle"]["decode_lineage"][0]["source_delivery_ids"][
                0
            ] = "DELIVERY-NOT-REGISTERED"

        def missing_decode_point(_manifest, files):
            files["oracle"]["decode_lineage"][0][
                "target_point_id"
            ] = "POINT-NOT-REGISTERED"

        def missing_projection_mapping(_manifest, files):
            files["oracle"]["projection_expectations"][0]["scope"][
                "mapping_version"
            ] = "9.9.9"

        def missing_ordering_delivery(_manifest, files):
            files["oracle"]["ordering_facts"][0][
                "older_delivery_id"
            ] = "DELIVERY-NOT-REGISTERED"

        def missing_narrative_event(_manifest, files):
            files["deliveries"]["deliveries"][0][
                "narrative_event_id"
            ] = "E999-UNKNOWN-INDICATION-RECEIVED"

        def mismatched_topology(manifest, _files):
            manifest["topology"]["content_digest"] = "0" * 64

        cases = (
            (
                "missing-identity-delivery",
                missing_identity_delivery,
                "unresolved delivery references",
            ),
            (
                "missing-identity-binding",
                missing_identity_binding,
                "unknown source binding",
            ),
            (
                "mismatched-source-event",
                mismatched_source_event,
                "source event does not match",
            ),
            (
                "missing-decode-delivery",
                missing_decode_delivery,
                "unresolved delivery references",
            ),
            (
                "missing-decode-point",
                missing_decode_point,
                "unknown point",
            ),
            (
                "missing-projection-mapping",
                missing_projection_mapping,
                "unresolved mapping",
            ),
            (
                "missing-ordering-delivery",
                missing_ordering_delivery,
                "unresolved delivery references",
            ),
            (
                "missing-narrative-event",
                missing_narrative_event,
                "unknown narrative event",
            ),
            (
                "mismatched-topology",
                mismatched_topology,
                "topology binding does not match",
            ),
        )
        for name, mutator, expected_error in cases:
            with self.subTest(name=name):
                manifest_path = self.copied_replay_package(name, mutator)
                with self.assertRaisesRegex(ValueError, expected_error):
                    self.load_copied_replay_package(manifest_path)

    def test_plan_matches_structural_oracle_and_keeps_identity_boundaries(self):
        plan = self.build_plan()
        self.assertEqual(len(plan["deliveries"]), 41)
        self.assertEqual(len(plan["source_native_records"]), 41)
        self.assertEqual(len(plan["source_event_groups"]), 39)
        self.assertEqual(len(plan["canonical_observations"]), 76)
        self.assertEqual(len(plan["lineage"]), 82)
        self.assertEqual(plan["decode_issues"], [])
        self.assertEqual(len(plan["annotations"]), 1)
        self.assertEqual(
            plan["annotations"][0]["narrative_event_id"],
            "E180-HUMAN-ACTION-RECORDED",
        )
        self.assertEqual(
            plan["annotations"][0]["annotation_kind"],
            "ASSERTED_ACTION",
        )

        delivery_by_id = {
            delivery["delivery_id"]: delivery for delivery in plan["deliveries"]
        }
        exact_a = delivery_by_id["DELIVERY-E030-CONTROLLER-001"]
        exact_b = delivery_by_id[
            "DELIVERY-E030-CONTROLLER-EXACT-REDELIVERY-002"
        ]
        self.assertNotEqual(exact_a["delivery_id"], exact_b["delivery_id"])
        self.assertNotEqual(
            exact_a["source_native_record_id"],
            exact_b["source_native_record_id"],
        )
        self.assertEqual(
            exact_a["source_event_group_key"],
            exact_b["source_event_group_key"],
        )
        self.assertEqual(exact_b["redelivery_classification"], "EXACT_REDELIVERY")

        exact_observations = [
            row
            for row in plan["canonical_observations"]
            if row["source_event_group_key"] == exact_a["source_event_group_key"]
        ]
        self.assertEqual(len(exact_observations), 1)
        exact_lineage = [
            row
            for row in plan["lineage"]
            if row["canonical_observation_id"]
            == exact_observations[0]["canonical_observation_id"]
        ]
        self.assertEqual(len(exact_lineage), 2)
        self.assertEqual({row["input_ordinal"] for row in exact_lineage}, {1})

        conflict_a = delivery_by_id["DELIVERY-E120-CONTROLLER-CONFLICT-A"]
        conflict_b = delivery_by_id["DELIVERY-E120-CONTROLLER-CONFLICT-B"]
        self.assertEqual(
            conflict_a["source_event_group_key"],
            conflict_b["source_event_group_key"],
        )
        self.assertEqual(
            conflict_b["redelivery_classification"],
            "CONFLICTING_REDELIVERY",
        )
        conflict_observations = [
            row
            for row in plan["canonical_observations"]
            if row["source_event_group_key"]
            == conflict_a["source_event_group_key"]
        ]
        self.assertEqual(len(conflict_observations), 2)
        self.assertEqual(
            {row["value_boolean"] for row in conflict_observations},
            {0, 1},
        )

    def test_source_timestamp_and_ordering_facts_remain_explicit(self):
        plan = self.build_plan()
        by_delivery = {
            row["delivery_id"]: row for row in plan["source_native_records"]
        }
        offset_record = by_delivery["DELIVERY-E010-TREATMENT-001"]
        expected_payload = {
            "availability_reported": True,
            "permissive_reported": True,
        }
        self.assertEqual(
            json.loads(offset_record["payload_json"]),
            expected_payload,
        )
        self.assertEqual(
            offset_record["payload_digest"],
            canonical_json_sha256(expected_payload),
        )
        self.assertEqual(
            json.loads(offset_record["source_quality_json"]),
            {
                "raw_code": "OK",
                "raw_meaning": "SOURCE_REPORTED_UNINTERPRETED",
            },
        )
        self.assertEqual(
            json.loads(offset_record["transport_provenance_json"]),
            {
                "external_connection": False,
                "kind": "REPOSITORY_JSON",
            },
        )
        self.assertEqual(
            json.loads(offset_record["synthetic_provenance_json"])[
                "replay_package_digest"
            ],
            self.loaded["content_digest"],
        )
        delivery = next(
            row
            for row in plan["deliveries"]
            if row["delivery_id"] == "DELIVERY-E010-TREATMENT-001"
        )
        self.assertEqual(delivery["ingestion_ordinal"], 1)
        self.assertEqual(
            offset_record["original_observed_at_text"],
            "2026-07-23T17:01:00.000+07:00",
        )
        self.assertEqual(offset_record["original_timezone_offset"], "+07:00")
        self.assertEqual(offset_record["timestamp_precision"], "FRACTIONAL_SECOND")
        self.assertEqual(offset_record["fractional_second_digits"], 3)
        self.assertEqual(
            offset_record["observed_at_utc"],
            "2026-07-23T10:01:00.000Z",
        )

        missing = by_delivery[
            "DELIVERY-E190-MAKEUP-STATUS-MISSING-TIME-001"
        ]
        invalid = by_delivery["DELIVERY-E190-TREATMENT-INVALID-TIME-001"]
        self.assertEqual(missing["observed_at_status"], "MISSING")
        self.assertIsNone(missing["observed_at_utc"])
        self.assertEqual(invalid["observed_at_status"], "INVALID")
        self.assertIsNone(invalid["observed_at_utc"])
        self.assertEqual(
            invalid["original_observed_at_text"],
            "2026-02-30T10:19:00Z",
        )

        out_of_order = json.loads(
            by_delivery[
                "DELIVERY-E110-PROCESS-PATH-OUT-OF-ORDER-001"
            ]["ordering_facts_json"]
        )
        disagreement = json.loads(
            by_delivery["DELIVERY-E130-CONTROLLER-001"][
                "ordering_facts_json"
            ]
        )
        ambiguous = json.loads(
            by_delivery[
                "DELIVERY-E220-CONTROLLER-AMBIGUOUS-RESET-001"
            ]["ordering_facts_json"]
        )
        future = json.loads(
            by_delivery["DELIVERY-E200-CONTROLLER-DECLARED-RESET-001"][
                "ordering_facts_json"
            ]
        )
        self.assertTrue(out_of_order["out_of_order_arrival"])
        self.assertTrue(disagreement["sequence_time_disagreement"])
        self.assertTrue(ambiguous["ambiguous_sequence_reset"])
        self.assertTrue(
            future["temporal_facts"]["observed_at_after_received_at"]
        )
        self.assertEqual(
            by_delivery["DELIVERY-E200-CONTROLLER-DECLARED-RESET-001"][
                "source_session_epoch"
            ],
            "EXHAUST-CONTROLLER-BOOT-02",
        )

    def test_one_to_many_many_to_one_partial_and_mapping_version_lineage(self):
        plan = self.build_plan()
        native_by_delivery = {
            row["delivery_id"]: row for row in plan["source_native_records"]
        }
        lineage_by_native = {}
        for lineage in plan["lineage"]:
            lineage_by_native.setdefault(
                lineage["source_native_record_id"],
                [],
            ).append(lineage)

        vfd_native = native_by_delivery["DELIVERY-E050-DUTY-VFD-001"]
        self.assertEqual(
            len(lineage_by_native[vfd_native["source_native_record_id"]]),
            5,
        )
        self.assertEqual(
            {
                edge["source_field_path"]
                for edge in lineage_by_native[
                    vfd_native["source_native_record_id"]
                ]
            },
            {
                "available",
                "run_status",
                "fault_status",
                "vfd_state",
                "speed_tenths_percent",
            },
        )

        partial_native = native_by_delivery["DELIVERY-E010-PROCESS-PATH-001"]
        partial_observation_ids = {
            edge["canonical_observation_id"]
            for edge in lineage_by_native[
                partial_native["source_native_record_id"]
            ]
        }
        partial_points = {
            row["canonical_point_definition_id"]
            for row in plan["canonical_observations"]
            if row["canonical_observation_id"] in partial_observation_ids
        }
        self.assertEqual(
            partial_points,
            {
                "EXHAUST-SHARED_DUCT_STATIC",
                "EXHAUST-SHARED_DAMPER_POSITION",
            },
        )

        negative_current = next(
            row
            for row in plan["canonical_observations"]
            if row["canonical_point_definition_id"]
            == "FAN-EXHAUST-DUTY_MOTOR_CURRENT"
            and row["value_decimal"] == "-0.25"
        )
        self.assertEqual(negative_current["unit"], "A")
        self.assertIsNone(negative_current["source_event_group_key"])
        current_lineage = [
            edge
            for edge in plan["lineage"]
            if edge["canonical_observation_id"]
            == negative_current["canonical_observation_id"]
        ]
        self.assertEqual(len(current_lineage), 2)
        self.assertEqual(
            {edge["input_ordinal"] for edge in current_lineage},
            {1, 2},
        )
        self.assertEqual(
            {
                (edge["lineage_role"], edge["source_field_path"])
                for edge in current_lineage
            },
            {
                ("HIGH_WORD", "$.register_value"),
                ("LOW_WORD", "$.register_value"),
            },
        )

        process_rows = [
            row
            for row in plan["canonical_observations"]
            if row["canonical_point_definition_id"] == "PROCESS-EXHAUST_AIRFLOW"
        ]
        self.assertEqual(
            {row["mapping_version"] for row in process_rows},
            {"1.0.0", "1.1.0"},
        )
        self.assertTrue(all(row["unit"] == "m3/s" for row in process_rows))
        process_values = {
            (row["mapping_version"], row["value_decimal"])
            for row in process_rows
        }
        self.assertIn(("1.0.0", "2.0058"), process_values)
        self.assertIn(("1.1.0", "2.0150"), process_values)

    def test_identityless_equal_register_components_are_not_deduplicated(self):
        mutated = deepcopy(self.loaded)
        high_component = next(
            delivery
            for delivery in mutated["deliveries"]
            if delivery["delivery_id"]
            == "DELIVERY-E050-DUTY-CURRENT-HIGH-001"
        )
        high_component["source_event"]["event_id"] = None
        high_component["source_event"]["sequence"] = None
        high_component["source_event"]["session_epoch"] = None
        duplicate = deepcopy(high_component)
        duplicate["delivery_id"] = (
            "DELIVERY-E050-DUTY-CURRENT-HIGH-IDENTITYLESS-002"
        )
        duplicate["received_at"] = "2026-07-23T10:05:00.250Z"
        high_index = mutated["deliveries"].index(high_component)
        mutated["deliveries"].insert(high_index + 1, duplicate)
        mutated["oracle"]["expected_counts"].update(
            {
                "deliveries": 42,
                "source_native_records": 42,
                "source_event_groups": 40,
                "logical_source_event_variants": 41,
                "canonical_observations": 77,
                "lineage_edges": 84,
            }
        )

        plan = build_replay_plan(
            mutated,
            replay_execution_id="REPLAY-EXECUTION-IDENTITYLESS-PAIR",
            requested_replay_execution_id=(
                "REPLAY-EXECUTION-IDENTITYLESS-PAIR"
            ),
            idempotency_key="identityless-pair",
        )

        self.assertEqual(plan["decode_issues"], [])
        component_native_ids = {
            row["source_native_record_id"]
            for row in plan["source_native_records"]
            if row["delivery_id"]
            in {
                "DELIVERY-E050-DUTY-CURRENT-HIGH-001",
                "DELIVERY-E050-DUTY-CURRENT-HIGH-IDENTITYLESS-002",
                "DELIVERY-E050-DUTY-CURRENT-LOW-001",
            }
        }
        component_lineage = [
            edge
            for edge in plan["lineage"]
            if edge["source_native_record_id"] in component_native_ids
        ]
        component_observation_ids = {
            edge["canonical_observation_id"] for edge in component_lineage
        }
        self.assertEqual(len(component_observation_ids), 2)
        self.assertEqual(len(component_lineage), 4)
        self.assertEqual(
            len(
                {
                    row["derivation_key"]
                    for row in plan["canonical_observations"]
                    if row["canonical_observation_id"]
                    in component_observation_ids
                }
            ),
            2,
        )

    def test_register_component_conflict_retains_bitemporal_variants(self):
        mutated = deepcopy(self.loaded)
        high_component = next(
            delivery
            for delivery in mutated["deliveries"]
            if delivery["delivery_id"]
            == "DELIVERY-E050-DUTY-CURRENT-HIGH-001"
        )
        low_component = next(
            delivery
            for delivery in mutated["deliveries"]
            if delivery["delivery_id"]
            == "DELIVERY-E050-DUTY-CURRENT-LOW-001"
        )
        conflict = deepcopy(high_component)
        conflict["delivery_id"] = (
            "DELIVERY-E050-DUTY-CURRENT-HIGH-CONFLICT-002"
        )
        conflict["received_at"] = "2026-07-23T10:05:00.400Z"
        conflict["payload"]["register_value"] = 1
        low_index = mutated["deliveries"].index(low_component)
        mutated["deliveries"].insert(low_index + 1, conflict)
        mutated["oracle"]["expected_counts"].update(
            {
                "deliveries": 42,
                "source_native_records": 42,
                "logical_source_event_variants": 41,
                "canonical_observations": 77,
                "lineage_edges": 84,
                "conflicting_redelivery_groups": 2,
            }
        )

        execution_id = "REPLAY-EXECUTION-REGISTER-CONFLICT"
        plan = self.build_and_persist_mutation(
            mutated,
            execution_id,
            "register-conflict",
        )
        self.assertEqual(plan["decode_issues"], [])
        component_rows = [
            row
            for row in plan["canonical_observations"]
            if row["canonical_point_definition_id"]
            == "FAN-EXHAUST-DUTY_MOTOR_CURRENT"
            and row["observed_at_utc"] == "2026-07-23T10:05:00.010Z"
        ]
        self.assertEqual(
            {row["value_decimal"] for row in component_rows},
            {"12.50", "667.86"},
        )
        self.assertEqual(
            {row["received_at_utc"] for row in component_rows},
            {
                "2026-07-23T10:05:00.300Z",
                "2026-07-23T10:05:00.400Z",
            },
        )
        self.assertTrue(
            all(
                row["source_event_group_key"] is None
                for row in component_rows
            )
        )

        scope = {
            "source_binding_id": "SOURCE-BINDING-DUTY-MOTOR-CURRENT",
            "point_id": "FAN-EXHAUST-DUTY_MOTOR_CURRENT",
            "mapping_id": "MAPPING-DUTY-MOTOR-CURRENT",
            "as_of": "2026-07-23T10:05:00.010Z",
        }
        before = self.projection(
            execution_id,
            **scope,
            known_by="2026-07-23T10:05:00.350Z",
        )
        after = self.projection(
            execution_id,
            **scope,
            known_by="2026-07-23T10:05:00.450Z",
        )
        self.assertEqual(before["disposition"], "REPORTED")
        self.assertEqual(before["logical_candidate_count"], 1)
        self.assertEqual(
            before["selected_value"],
            {"value_type": "DECIMAL", "value": "12.50", "unit": "A"},
        )
        self.assertEqual(after["disposition"], "CONFLICT_PRESENT")
        self.assertEqual(after["logical_candidate_count"], 2)
        self.assertIsNone(after["selected_value"])
        self.assertEqual(
            after,
            self.projection(
                execution_id,
                **scope,
                known_by="2026-07-23T10:05:00.450Z",
            ),
        )

    def test_unpairable_register_conflict_keeps_prior_composite(self):
        mutated = deepcopy(self.loaded)
        high_component = next(
            delivery
            for delivery in mutated["deliveries"]
            if delivery["delivery_id"]
            == "DELIVERY-E050-DUTY-CURRENT-HIGH-001"
        )
        low_component = next(
            delivery
            for delivery in mutated["deliveries"]
            if delivery["delivery_id"]
            == "DELIVERY-E050-DUTY-CURRENT-LOW-001"
        )
        conflict = deepcopy(high_component)
        conflict["delivery_id"] = (
            "DELIVERY-E050-DUTY-CURRENT-HIGH-TIME-CONFLICT-002"
        )
        conflict["received_at"] = "2026-07-23T10:05:00.400Z"
        conflict["observed_at"] = "2026-07-23T10:05:00.020Z"
        low_index = mutated["deliveries"].index(low_component)
        mutated["deliveries"].insert(low_index + 1, conflict)
        mutated["oracle"]["expected_counts"].update(
            {
                "deliveries": 42,
                "source_native_records": 42,
                "logical_source_event_variants": 41,
                "conflicting_redelivery_groups": 2,
            }
        )

        execution_id = "REPLAY-EXECUTION-REGISTER-TIME-CONFLICT"
        plan = self.build_and_persist_mutation(
            mutated,
            execution_id,
            "register-time-conflict",
        )
        self.assertEqual(
            [issue["issue_code"] for issue in plan["decode_issues"]],
            ["REGISTER_PAIR_TEMPORAL_MISMATCH"],
        )
        component_rows = [
            row
            for row in plan["canonical_observations"]
            if row["canonical_point_definition_id"]
            == "FAN-EXHAUST-DUTY_MOTOR_CURRENT"
            and row["observed_at_utc"]
            in {
                "2026-07-23T10:05:00.010Z",
                "2026-07-23T10:05:00.020Z",
            }
        ]
        self.assertEqual(len(component_rows), 1)
        self.assertEqual(component_rows[0]["value_decimal"], "12.50")
        prior_lineage = [
            edge
            for edge in plan["lineage"]
            if edge["canonical_observation_id"]
            == component_rows[0]["canonical_observation_id"]
        ]
        self.assertEqual(len(prior_lineage), 2)

        scope = {
            "source_binding_id": "SOURCE-BINDING-DUTY-MOTOR-CURRENT",
            "point_id": "FAN-EXHAUST-DUTY_MOTOR_CURRENT",
            "mapping_id": "MAPPING-DUTY-MOTOR-CURRENT",
            "as_of": "2026-07-23T10:05:00.020Z",
        }
        before = self.projection(
            execution_id,
            **scope,
            known_by="2026-07-23T10:05:00.350Z",
        )
        after = self.projection(
            execution_id,
            **scope,
            known_by="2026-07-23T10:05:00.450Z",
        )
        self.assertEqual(before["disposition"], "REPORTED")
        self.assertEqual(before["logical_candidate_count"], 1)
        self.assertEqual(after["disposition"], "CONFLICT_PRESENT")
        self.assertEqual(after["logical_candidate_count"], 1)
        self.assertIsNone(after["selected_value"])

    def test_exact_register_component_redelivery_keeps_one_composite(self):
        mutated = deepcopy(self.loaded)
        high_component = next(
            delivery
            for delivery in mutated["deliveries"]
            if delivery["delivery_id"]
            == "DELIVERY-E050-DUTY-CURRENT-HIGH-001"
        )
        low_component = next(
            delivery
            for delivery in mutated["deliveries"]
            if delivery["delivery_id"]
            == "DELIVERY-E050-DUTY-CURRENT-LOW-001"
        )
        exact = deepcopy(high_component)
        exact["delivery_id"] = (
            "DELIVERY-E050-DUTY-CURRENT-HIGH-EXACT-002"
        )
        exact["received_at"] = "2026-07-23T10:05:00.400Z"
        low_index = mutated["deliveries"].index(low_component)
        mutated["deliveries"].insert(low_index + 1, exact)
        mutated["oracle"]["expected_counts"].update(
            {
                "deliveries": 42,
                "source_native_records": 42,
                "lineage_edges": 83,
                "exact_redelivery_groups": 2,
            }
        )

        execution_id = "REPLAY-EXECUTION-REGISTER-EXACT"
        plan = self.build_and_persist_mutation(
            mutated,
            execution_id,
            "register-exact",
        )
        self.assertEqual(plan["decode_issues"], [])
        component_rows = [
            row
            for row in plan["canonical_observations"]
            if row["canonical_point_definition_id"]
            == "FAN-EXHAUST-DUTY_MOTOR_CURRENT"
            and row["observed_at_utc"] == "2026-07-23T10:05:00.010Z"
        ]
        self.assertEqual(len(component_rows), 1)
        self.assertEqual(component_rows[0]["value_decimal"], "12.50")
        component_lineage = [
            edge
            for edge in plan["lineage"]
            if edge["canonical_observation_id"]
            == component_rows[0]["canonical_observation_id"]
        ]
        self.assertEqual(len(component_lineage), 3)

        scope = {
            "source_binding_id": "SOURCE-BINDING-DUTY-MOTOR-CURRENT",
            "point_id": "FAN-EXHAUST-DUTY_MOTOR_CURRENT",
            "mapping_id": "MAPPING-DUTY-MOTOR-CURRENT",
            "as_of": "2026-07-23T10:05:00.010Z",
        }
        before = self.projection(
            execution_id,
            **scope,
            known_by="2026-07-23T10:05:00.350Z",
        )
        after = self.projection(
            execution_id,
            **scope,
            known_by="2026-07-23T10:05:00.450Z",
        )
        self.assertEqual(before["disposition"], "REPORTED")
        self.assertEqual(after["disposition"], "REPORTED")
        self.assertEqual(before["logical_candidate_count"], 1)
        self.assertEqual(after["logical_candidate_count"], 1)
        self.assertEqual(
            len(before["selected_candidate"]["source_native_record_ids"]),
            2,
        )
        self.assertEqual(
            len(after["selected_candidate"]["source_native_record_ids"]),
            3,
        )

    def test_source_event_conflict_crosses_mapping_versions(self):
        mutated = deepcopy(self.loaded)
        transition = next(
            delivery
            for delivery in mutated["deliveries"]
            if delivery["delivery_id"]
            == "DELIVERY-E210-PROCESS-PATH-MAPPING-TRANSITION-001"
        )
        transition["source_event"]["event_id"] = "PROCESS-PATH-EVENT-0004"
        mutated["oracle"]["expected_counts"].update(
            {
                "source_event_groups": 38,
                "conflicting_redelivery_groups": 2,
            }
        )
        transition_checkpoint = next(
            checkpoint
            for checkpoint in mutated["oracle"]["projection_expectations"]
            if checkpoint["name"]
            == "mapping transition is a separate derivation scope"
        )
        transition_checkpoint["expected_disposition"] = "CONFLICT_PRESENT"

        execution_id = "REPLAY-EXECUTION-CROSS-MAPPING-CONFLICT"
        plan = self.build_and_persist_mutation(
            mutated,
            execution_id,
            "cross-mapping-conflict",
        )
        self.assertEqual(plan["decode_issues"], [])
        before_v1 = self.projection(
            execution_id,
            source_binding_id="SOURCE-BINDING-PROCESS-PATH",
            point_id="PROCESS-EXHAUST_AIRFLOW",
            mapping_id="MAPPING-PROCESS-PATH-SNAPSHOT",
            as_of="2026-07-23T10:16:00Z",
            known_by="2026-07-23T10:16:00.500Z",
        )
        after_v1 = self.projection(
            execution_id,
            source_binding_id="SOURCE-BINDING-PROCESS-PATH",
            point_id="PROCESS-EXHAUST_AIRFLOW",
            mapping_id="MAPPING-PROCESS-PATH-SNAPSHOT",
            as_of="2026-07-23T10:21:00Z",
            known_by="2026-07-23T10:21:00.500Z",
        )
        after_v11 = self.projection(
            execution_id,
            source_binding_id="SOURCE-BINDING-PROCESS-PATH",
            point_id="PROCESS-EXHAUST_AIRFLOW",
            mapping_id="MAPPING-PROCESS-PATH-SNAPSHOT",
            mapping_version="1.1.0",
            as_of="2026-07-23T10:21:00Z",
            known_by="2026-07-23T10:21:00.500Z",
        )
        self.assertEqual(before_v1["disposition"], "REPORTED")
        self.assertEqual(
            before_v1["selected_value"],
            {"value_type": "DECIMAL", "value": "1.8996", "unit": "m3/s"},
        )
        self.assertEqual(after_v1["disposition"], "CONFLICT_PRESENT")
        self.assertEqual(after_v11["disposition"], "CONFLICT_PRESENT")
        self.assertIsNone(after_v1["selected_value"])
        self.assertIsNone(after_v11["selected_value"])
        self.assertEqual(
            after_v11,
            self.projection(
                execution_id,
                source_binding_id="SOURCE-BINDING-PROCESS-PATH",
                point_id="PROCESS-EXHAUST_AIRFLOW",
                mapping_id="MAPPING-PROCESS-PATH-SNAPSHOT",
                mapping_version="1.1.0",
                as_of="2026-07-23T10:21:00Z",
                known_by="2026-07-23T10:21:00.500Z",
            ),
        )

    def test_distinct_event_identities_can_report_equivalent_material(self):
        mutated = deepcopy(self.loaded)
        original = next(
            delivery
            for delivery in mutated["deliveries"]
            if delivery["delivery_id"] == "DELIVERY-E020-CONTROLLER-001"
        )
        equivalent = deepcopy(original)
        equivalent["delivery_id"] = (
            "DELIVERY-E020-CONTROLLER-EQUIVALENT-002"
        )
        equivalent["received_at"] = "2026-07-23T10:02:00.200Z"
        equivalent["source_event"][
            "event_id"
        ] = "EXHAUST-CONTROLLER-EVENT-9001"
        original_index = mutated["deliveries"].index(original)
        mutated["deliveries"].insert(original_index + 1, equivalent)
        mutated["oracle"]["expected_counts"].update(
            {
                "deliveries": 42,
                "source_native_records": 42,
                "source_event_groups": 40,
                "logical_source_event_variants": 41,
                "canonical_observations": 77,
                "lineage_edges": 83,
            }
        )

        execution_id = "REPLAY-EXECUTION-EQUIVALENT-REPORTS"
        plan = self.build_and_persist_mutation(
            mutated,
            execution_id,
            "equivalent-reports",
        )
        equivalent_rows = [
            row
            for row in plan["canonical_observations"]
            if row["canonical_point_definition_id"]
            == "PROCESS_PERMISSIVE_STATUS"
            and row["observed_at_utc"] == "2026-07-23T10:02:00.000Z"
        ]
        self.assertEqual(len(equivalent_rows), 2)
        self.assertEqual(
            len(
                {
                    row["canonical_observation_id"]
                    for row in equivalent_rows
                }
            ),
            2,
        )
        self.assertEqual(
            len(
                {row["source_event_group_key"] for row in equivalent_rows}
            ),
            2,
        )
        self.assertEqual(
            len(
                {
                    row["source_event_variant_digest"]
                    for row in equivalent_rows
                }
            ),
            2,
        )
        self.assertEqual(
            len(
                {row["report_material_digest"] for row in equivalent_rows}
            ),
            1,
        )

        projection = self.projection(
            execution_id,
            source_binding_id="SOURCE-BINDING-EXHAUST-CONTROLLER",
            point_id="PROCESS_PERMISSIVE_STATUS",
            mapping_id="MAPPING-EXHAUST-CONTROLLER-INDICATIONS",
            as_of="2026-07-23T10:02:00Z",
            known_by="2026-07-23T10:02:00.300Z",
        )
        self.assertEqual(projection["disposition"], "REPORTED")
        self.assertEqual(projection["known_candidate_count"], 2)
        self.assertEqual(projection["logical_candidate_count"], 2)
        self.assertEqual(
            projection["selected_value"],
            {"value_type": "BOOLEAN", "value": True, "unit": None},
        )
        self.assertIsNone(
            projection["selected_candidate"]["canonical_observation_id"]
        )
        self.assertEqual(
            set(
                projection["selected_candidate"][
                    "canonical_observation_ids"
                ]
            ),
            {
                row["canonical_observation_id"]
                for row in equivalent_rows
            },
        )
        self.assertEqual(
            projection["selected_candidate"][
                "equivalent_frontier_candidate_count"
            ],
            2,
        )

    def test_atomic_execution_retry_separate_run_and_manifest_repeatability(self):
        first = self.execute()
        retry = execute_replay_package(
            self.db_path,
            facility_id=FLAGSHIP_FACILITY_ID,
            package_id=FLAGSHIP_REPLAY_PACKAGE_ID,
            package_version=FLAGSHIP_REPLAY_PACKAGE_VERSION,
            idempotency_key="test-1",
            replay_execution_id="REPLAY-EXECUTION-TEST-1",
        )
        second = self.execute(
            execution_id="REPLAY-EXECUTION-TEST-2",
            key="test-2",
        )
        self.assertFalse(first["idempotent_replay"])
        self.assertTrue(retry["idempotent_replay"])
        self.assertEqual(
            retry["replay_execution"]["replay_execution_id"],
            "REPLAY-EXECUTION-TEST-1",
        )
        with self.assertRaises(IdempotencyConflictError):
            execute_replay_package(
                self.db_path,
                facility_id=FLAGSHIP_FACILITY_ID,
                package_id=FLAGSHIP_REPLAY_PACKAGE_ID,
                package_version=FLAGSHIP_REPLAY_PACKAGE_VERSION,
                idempotency_key="test-1",
                replay_execution_id="REPLAY-EXECUTION-DIFFERENT-REQUEST",
            )
        self.assertFalse(second["idempotent_replay"])

        manifest_a = get_reproducibility_manifest(
            self.db_path,
            FLAGSHIP_FACILITY_ID,
            "REPLAY-EXECUTION-TEST-1",
        )
        manifest_b = get_reproducibility_manifest(
            self.db_path,
            FLAGSHIP_FACILITY_ID,
            "REPLAY-EXECUTION-TEST-2",
        )
        self.assertEqual(
            manifest_a["derived"]["normalized_semantic_digest"],
            "4eab13accadd357deca945d970d53e2d34f97d21719ee1d961617b8be1d81bdd",
        )
        self.assertEqual(
            manifest_a["derived"]["normalized_semantic_digest"],
            manifest_b["derived"]["normalized_semantic_digest"],
        )
        unsigned_manifest = deepcopy(manifest_a)
        declared_manifest_digest = unsigned_manifest.pop("manifest_digest")
        self.assertEqual(
            canonical_json_sha256(unsigned_manifest),
            declared_manifest_digest,
        )
        self.assertEqual(
            manifest_a["redelivery_summary"][
                "exact_redelivery_groups"
            ][0]["delivery_count"],
            2,
        )
        self.assertEqual(
            manifest_a["redelivery_summary"]["conflict_groups"][0][
                "variant_count"
            ],
            2,
        )
        self.assertTrue(
            all(
                checkpoint["matches_structural_oracle"]
                for checkpoint in manifest_a["projection_summary"][
                    "oracle_checkpoints"
                ]
            )
        )
        limitations = " ".join(manifest_a["limitations"]).lower()
        self.assertIn("does not establish authenticity", limitations)
        self.assertIn("no equipment", limitations)

    def test_projection_is_bitemporal_rebuildable_and_never_selects_conflict(self):
        execution_id = "REPLAY-EXECUTION-PROJECTION"
        self.execute(execution_id=execution_id, key="projection")
        common = {
            "source_binding_id": "SOURCE-BINDING-EXHAUST-CONTROLLER",
            "point_id": "PROCESS_PERMISSIVE_STATUS",
            "mapping_id": "MAPPING-EXHAUST-CONTROLLER-INDICATIONS",
            "as_of": "2026-07-23T10:12:00Z",
        }
        before_conflict = self.projection(
            execution_id,
            **common,
            known_by="2026-07-23T10:12:00.100Z",
        )
        after_conflict = self.projection(
            execution_id,
            **common,
            known_by="2026-07-23T10:12:00.200Z",
        )
        rebuilt = self.projection(
            execution_id,
            **common,
            known_by="2026-07-23T10:12:00.200Z",
        )
        self.assertEqual(before_conflict["disposition"], "REPORTED")
        self.assertEqual(after_conflict["disposition"], "CONFLICT_PRESENT")
        self.assertIsNone(after_conflict["selected_value"])
        self.assertEqual(after_conflict, rebuilt)

        exact = self.projection(
            execution_id,
            source_binding_id="SOURCE-BINDING-EXHAUST-CONTROLLER",
            point_id="FAN-EXHAUST-DUTY_REQUEST",
            mapping_id="MAPPING-EXHAUST-CONTROLLER-INDICATIONS",
            as_of="2026-07-23T10:03:00Z",
            known_by="2026-07-23T10:03:00.300Z",
        )
        self.assertEqual(exact["disposition"], "REPORTED")
        self.assertEqual(exact["logical_candidate_count"], 1)
        self.assertEqual(exact["exact_redelivery_count"], 1)

    def test_equal_time_out_of_order_missing_time_and_mapping_scopes(self):
        execution_id = "REPLAY-EXECUTION-PROJECTION-EDGES"
        self.execute(execution_id=execution_id, key="projection-edges")
        equal_time = self.projection(
            execution_id,
            source_binding_id="SOURCE-BINDING-PRESSURE",
            point_id="PROCESS-LAB_ZONE_PRESSURE",
            mapping_id="MAPPING-PRESSURE-SNAPSHOT",
            as_of="2026-07-23T10:17:00Z",
            known_by="2026-07-23T10:17:00.300Z",
        )
        missing_time = self.projection(
            execution_id,
            source_binding_id="SOURCE-BINDING-MAKEUP-CONTROLLER",
            point_id="SUPPLY-MAKEUP_STATUS",
            mapping_id="MAPPING-MAKEUP-CONTROLLER-STATUS",
            as_of="2026-07-23T10:20:00Z",
            known_by="2026-07-23T10:20:00Z",
        )
        out_of_order = self.projection(
            execution_id,
            source_binding_id="SOURCE-BINDING-PROCESS-PATH",
            point_id="PROCESS-EXHAUST_AIRFLOW",
            mapping_id="MAPPING-PROCESS-PATH-SNAPSHOT",
            as_of="2026-07-23T10:16:00Z",
            known_by="2026-07-23T10:16:00.500Z",
        )
        mapping_transition = self.projection(
            execution_id,
            source_binding_id="SOURCE-BINDING-PROCESS-PATH",
            point_id="PROCESS-EXHAUST_AIRFLOW",
            mapping_id="MAPPING-PROCESS-PATH-SNAPSHOT",
            mapping_version="1.1.0",
            as_of="2026-07-23T10:21:00Z",
            known_by="2026-07-23T10:21:00.500Z",
        )
        self.assertEqual(equal_time["disposition"], "CONFLICT_PRESENT")
        self.assertIsNone(equal_time["selected_value"])
        self.assertEqual(missing_time["disposition"], "UNORDERED")
        self.assertIsNone(missing_time["selected_value"])
        self.assertEqual(out_of_order["disposition"], "REPORTED")
        self.assertEqual(mapping_transition["disposition"], "REPORTED")
        self.assertEqual(
            mapping_transition["projection_scope"]["mapping_version"],
            "1.1.0",
        )

        with self.assertRaises(LookupError):
            get_reported_observation_projection(
                self.db_path,
                facility_id=FLAGSHIP_FACILITY_ID,
                replay_execution_id=execution_id,
                source_binding_id="SOURCE-BINDING-PROCESS-PATH",
                point_id="PROCESS-EXHAUST_AIRFLOW",
                mapping_id="MAPPING-NOT-REGISTERED",
                mapping_version="1.0.0",
                mapping_digest="0" * 64,
                as_of_observed_at="2026-07-23T10:21:00Z",
                known_by_received_at="2026-07-23T10:21:00.500Z",
            )

    def test_persisted_lists_lineage_groups_and_facility_scope_are_bounded(self):
        execution_id = "REPLAY-EXECUTION-READS"
        self.execute(execution_id=execution_id, key="reads")
        native_page = list_source_native_records(
            self.db_path,
            FLAGSHIP_FACILITY_ID,
            execution_id,
            page=1,
            page_size=7,
        )
        canonical_page = list_canonical_observations(
            self.db_path,
            FLAGSHIP_FACILITY_ID,
            execution_id,
            page=1,
            page_size=9,
        )
        groups = list_redelivery_groups(
            self.db_path,
            FLAGSHIP_FACILITY_ID,
            execution_id,
        )
        self.assertEqual(len(native_page["source_native_records"]), 7)
        self.assertEqual(native_page["pagination"]["total_records"], 41)
        self.assertEqual(len(canonical_page["canonical_observations"]), 9)
        self.assertEqual(canonical_page["pagination"]["total_records"], 76)
        self.assertEqual(groups["pagination"]["total_records"], 2)
        self.assertEqual(
            {group["variant_count"] for group in groups["redelivery_groups"]},
            {1, 2},
        )
        with self.assertRaises(ValueError):
            list_source_native_records(
                self.db_path,
                FLAGSHIP_FACILITY_ID,
                execution_id,
                page_size=101,
            )
        with self.assertRaises(LookupError):
            get_replay_execution(
                self.db_path,
                "FACILITY-CROSS-SCOPE",
                execution_id,
            )

        canonical = next(
            row
            for row in list_canonical_observations(
                self.db_path,
                FLAGSHIP_FACILITY_ID,
                execution_id,
                point_id="FAN-EXHAUST-DUTY_REQUEST",
            )["canonical_observations"]
            if row["source_event_group_key"] is not None
        )
        lineage = get_canonical_lineage(
            self.db_path,
            FLAGSHIP_FACILITY_ID,
            canonical["canonical_observation_id"],
        )
        self.assertGreaterEqual(len(lineage["source_native_lineage"]), 1)

    def test_fault_injection_rolls_back_every_execution_record(self):
        with self.assertRaises(RuntimeError):
            execute_replay_package(
                self.db_path,
                facility_id=FLAGSHIP_FACILITY_ID,
                package_id=FLAGSHIP_REPLAY_PACKAGE_ID,
                package_version=FLAGSHIP_REPLAY_PACKAGE_VERSION,
                idempotency_key="fault",
                replay_execution_id="REPLAY-EXECUTION-FAULT",
                inject_failure_after_native_record=3,
            )
        self.assertTrue(self.db_path.is_file())
        with sqlite3.connect(self.db_path) as connection:
            for table_name in (
                "replay_executions",
                "replay_deliveries",
                "source_native_records",
                "canonical_observations",
                "canonical_observation_lineage",
            ):
                self.assertEqual(
                    connection.execute(
                        f"SELECT COUNT(*) FROM {table_name}"
                    ).fetchone()[0],
                    0,
                )

    def test_replay_manifest_mapping_pins_match_mapping_package(self):
        copied = self.temp_root / "mapping-pin-mismatch"
        shutil.copytree(FLAGSHIP_REPLAY_MANIFEST.parent, copied)
        copied_manifest_path = copied / "manifest.json"
        manifest = json.loads(
            copied_manifest_path.read_text(encoding="utf-8")
        )
        manifest["mappings"][0]["content_digest"] = "0" * 64
        files = {
            role: json.loads(
                (copied / filename).read_text(encoding="utf-8")
            )
            for role, filename in manifest["files"].items()
        }
        manifest["content_digest"] = package_content_digest(manifest, files)
        copied_manifest_path.write_text(
            json.dumps(manifest, indent=2) + "\n",
            encoding="utf-8",
        )

        with mock.patch.dict(
            REGISTERED_REPLAY_PACKAGES,
            {PACKAGE_KEY: copied_manifest_path},
        ):
            with self.assertRaisesRegex(
                ValueError,
                "mapping pins do not match",
            ):
                execute_replay_package(
                    self.db_path,
                    facility_id=FLAGSHIP_FACILITY_ID,
                    package_id=FLAGSHIP_REPLAY_PACKAGE_ID,
                    package_version=FLAGSHIP_REPLAY_PACKAGE_VERSION,
                    idempotency_key="mapping-pin-mismatch",
                    replay_execution_id="REPLAY-EXECUTION-PIN-MISMATCH",
                )
        self.assertFalse(self.db_path.exists())

    def test_malformed_package_is_rejected_before_store_creation(self):
        copied = self.temp_root / "malformed-package"
        shutil.copytree(FLAGSHIP_REPLAY_MANIFEST.parent, copied)
        copied_manifest_path = copied / "manifest.json"
        deliveries_path = copied / "deliveries.json"
        deliveries_file = json.loads(deliveries_path.read_text(encoding="utf-8"))
        deliveries_file["deliveries"][0]["mapping"][
            "content_digest"
        ] = "0" * 64
        deliveries_path.write_text(
            json.dumps(deliveries_file, indent=2) + "\n",
            encoding="utf-8",
        )
        manifest = json.loads(
            copied_manifest_path.read_text(encoding="utf-8")
        )
        files = {
            role: json.loads(
                (copied / filename).read_text(encoding="utf-8")
            )
            for role, filename in manifest["files"].items()
        }
        manifest["content_digest"] = package_content_digest(manifest, files)
        copied_manifest_path.write_text(
            json.dumps(manifest, indent=2) + "\n",
            encoding="utf-8",
        )
        with mock.patch.dict(
            REGISTERED_REPLAY_PACKAGES,
            {PACKAGE_KEY: copied_manifest_path},
        ):
            with self.assertRaises(ValueError):
                execute_replay_package(
                    self.db_path,
                    facility_id=FLAGSHIP_FACILITY_ID,
                    package_id=FLAGSHIP_REPLAY_PACKAGE_ID,
                    package_version=FLAGSHIP_REPLAY_PACKAGE_VERSION,
                    idempotency_key="malformed",
                    replay_execution_id="REPLAY-EXECUTION-MALFORMED",
                )
        self.assertFalse(self.db_path.exists())

    def test_idempotency_key_content_mismatch_is_rejected(self):
        plan = self.build_plan(
            execution_id="REPLAY-EXECUTION-IDEMPOTENCY-A",
            key="same-key",
        )
        persist_replay_execution(self.db_path, plan)
        changed = self.build_plan(
            execution_id="REPLAY-EXECUTION-IDEMPOTENCY-B",
            key="same-key",
        )
        changed["execution"]["request_digest"] = "f" * 64
        with self.assertRaises(IdempotencyConflictError):
            persist_replay_execution(self.db_path, changed)
        self.assertEqual(
            get_replay_execution(
                self.db_path,
                FLAGSHIP_FACILITY_ID,
                "REPLAY-EXECUTION-IDEMPOTENCY-A",
            )["record_counts"]["source_native_records"],
            41,
        )
        with self.assertRaises(LookupError):
            get_replay_execution(
                self.db_path,
                FLAGSHIP_FACILITY_ID,
                "REPLAY-EXECUTION-IDEMPOTENCY-B",
            )

    def test_concurrent_same_request_publishes_once(self):
        def run():
            return execute_replay_package(
                self.db_path,
                facility_id=FLAGSHIP_FACILITY_ID,
                package_id=FLAGSHIP_REPLAY_PACKAGE_ID,
                package_version=FLAGSHIP_REPLAY_PACKAGE_VERSION,
                idempotency_key="concurrent-request",
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: run(), range(2)))
        execution_ids = {
            result["replay_execution"]["replay_execution_id"]
            for result in results
        }
        self.assertEqual(len(execution_ids), 1)
        self.assertEqual(
            sorted(result["idempotent_replay"] for result in results),
            [False, True],
        )
        with sqlite3.connect(self.db_path) as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM replay_executions"
                ).fetchone()[0],
                1,
            )
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM source_native_records"
                ).fetchone()[0],
                41,
            )


if __name__ == "__main__":
    unittest.main()
