import math
import unittest
from copy import deepcopy
from decimal import Decimal
from itertools import permutations

from backend.domain.observation_semantics import (
    ORDER_AFTER,
    ORDER_BEFORE,
    ORDER_EQUAL,
    ORDER_UNORDERED,
    TIMESTAMP_INVALID,
    TIMESTAMP_MISSING,
    TIMESTAMP_VALID,
    canonical_json_bytes,
    canonical_json_sha256,
    canonical_json_text,
    compare_rfc3339_instants,
    decode_signed_int32_be,
    normalize_decimal,
    normalize_decimal_text,
    normalize_direct_enum,
    normalize_strict_boolean,
    observation_ordering_facts,
    observation_temporal_facts,
    parse_rfc3339_timestamp,
)
from backend.domain.reported_observation_projection import (
    CONFLICT_PRESENT,
    EVENT_TIME_AFTER_AS_OF,
    EVENT_TIME_INVALID,
    EVENT_TIME_MISSING,
    NO_ELIGIBLE_REPORT,
    NO_OBSERVATION,
    REPORTED,
    UNORDERED,
    project_reported_observation,
)


AS_OF = "2026-07-23T11:00:00Z"
KNOWN_BY = "2026-07-23T11:30:00Z"


def canonical_candidate(
    candidate_id,
    *,
    observed_at="2026-07-23T10:00:00Z",
    observed_at_status=TIMESTAMP_VALID,
    received_at="2026-07-23T10:01:00Z",
    sequence=1,
    epoch="BOOT-1",
    event_group=None,
    variant_digest=None,
    value="1.00",
    source_native_record_ids=None,
):
    if observed_at_status != TIMESTAMP_VALID:
        observed_at = None
    return {
        "canonical_observation_id": candidate_id,
        "source_native_record_ids": (
            source_native_record_ids
            if source_native_record_ids is not None
            else [f"NATIVE-{candidate_id}"]
        ),
        "facility_id": "FACILITY-FLAGSHIP",
        "replay_execution_id": "REPLAY-1",
        "source_binding_id": "SOURCE-BINDING-1",
        "channel": "CHANNEL-1",
        "point_id": "POINT-1",
        "mapping_id": "MAPPING-1",
        "mapping_version": "1.0.0",
        "mapping_digest": "a" * 64,
        "source_event_group_key": event_group,
        "source_event_variant_digest": variant_digest,
        "source_sequence": sequence,
        "source_epoch": epoch,
        "observed_at_status": observed_at_status,
        "observed_at_utc": observed_at,
        "received_at_utc": received_at,
        "normalized_value_type": "DECIMAL",
        "normalized_value": value,
        "unit": "Pa",
        "time_basis": "SOURCE_REPORTED",
        "source_quality": {"raw": "GOOD"},
    }


class CanonicalJsonTests(unittest.TestCase):
    def test_canonical_json_has_sorted_keys_utf8_and_no_padding(self):
        value = {"z": [3, 2, 1], "é": True, "a": {"b": None}}

        self.assertEqual(
            canonical_json_text(value),
            '{"a":{"b":null},"z":[3,2,1],"é":true}',
        )
        self.assertEqual(
            canonical_json_bytes(value),
            '{"a":{"b":null},"z":[3,2,1],"é":true}'.encode("utf-8"),
        )
        self.assertEqual(len(canonical_json_sha256(value)), 64)
        self.assertEqual(
            canonical_json_sha256(value),
            canonical_json_sha256(
                {"é": True, "a": {"b": None}, "z": [3, 2, 1]}
            ),
        )

    def test_canonical_json_rejects_ambiguous_keys_and_nonfinite_numbers(self):
        with self.assertRaisesRegex(ValueError, "key"):
            canonical_json_text({1: "not a JSON object key"})
        with self.assertRaisesRegex(ValueError, "canonical-JSON"):
            canonical_json_text({"value": math.nan})


class TimestampSemanticsTests(unittest.TestCase):
    def test_rfc3339_parser_preserves_offset_and_fractional_precision(self):
        parsed = parse_rfc3339_timestamp(
            "2026-07-23T12:34:56.1200+07:30"
        )

        self.assertEqual(parsed["status"], TIMESTAMP_VALID)
        self.assertEqual(
            parsed["raw_text"],
            "2026-07-23T12:34:56.1200+07:30",
        )
        self.assertEqual(parsed["raw_offset"], "+07:30")
        self.assertEqual(parsed["precision"], "FRACTIONAL_SECOND")
        self.assertEqual(parsed["fractional_second_digits"], 4)
        self.assertEqual(parsed["utc"], "2026-07-23T05:04:56.1200Z")
        self.assertIsNone(parsed["error"])

    def test_rfc3339_parser_keeps_missing_and_invalid_distinct(self):
        missing_null = parse_rfc3339_timestamp(None)
        missing_empty = parse_rfc3339_timestamp("")
        invalid = parse_rfc3339_timestamp("2026-02-30T10:00:00Z")
        invalid_with_precision = parse_rfc3339_timestamp(
            "2026-02-30T10:00:00.120+07:00"
        )

        self.assertEqual(missing_null["status"], TIMESTAMP_MISSING)
        self.assertIsNone(missing_null["utc"])
        self.assertEqual(missing_empty["status"], TIMESTAMP_MISSING)
        self.assertEqual(missing_empty["raw_text"], "")
        self.assertEqual(invalid["status"], TIMESTAMP_INVALID)
        self.assertEqual(invalid["raw_text"], "2026-02-30T10:00:00Z")
        self.assertIsNone(invalid["utc"])
        self.assertNotIn("received", invalid)
        self.assertEqual(invalid_with_precision["raw_offset"], "+07:00")
        self.assertEqual(
            invalid_with_precision["fractional_second_digits"],
            3,
        )

    def test_rfc3339_comparison_retains_more_than_microsecond_precision(self):
        self.assertEqual(
            compare_rfc3339_instants(
                "2026-07-23T10:00:00.123456789Z",
                "2026-07-23T10:00:00.123456788Z",
            ),
            ORDER_AFTER,
        )
        self.assertEqual(
            compare_rfc3339_instants(
                "2026-07-23T17:00:00+07:00",
                "2026-07-23T10:00:00Z",
            ),
            ORDER_EQUAL,
        )


class MappingNormalizationTests(unittest.TestCase):
    def test_decimal_scaling_and_half_even_quantization_are_exact(self):
        self.assertEqual(
            normalize_decimal("1005", factor="0.001", quantum="0.01"),
            Decimal("1.00"),
        )
        self.assertEqual(
            normalize_decimal_text(
                "1015",
                factor="0.001",
                quantum="0.01",
            ),
            "1.02",
        )
        self.assertEqual(
            normalize_decimal_text(
                "-125",
                factor="0.1",
                quantum="1",
            ),
            "-12",
        )

    def test_decimal_normalization_rejects_implicit_or_nonfinite_inputs(self):
        with self.assertRaisesRegex(ValueError, "boolean"):
            normalize_decimal(True, factor="1", quantum="0.1")
        with self.assertRaisesRegex(ValueError, "finite"):
            normalize_decimal("NaN", factor="1", quantum="0.1")
        with self.assertRaisesRegex(ValueError, "quantum"):
            normalize_decimal("1", factor="1", quantum="0")

    def test_signed_int32_big_endian_decode_preserves_signedness(self):
        self.assertEqual(decode_signed_int32_be(0x0000, 0x0001), 1)
        self.assertEqual(decode_signed_int32_be(0x7FFF, 0xFFFF), 2147483647)
        self.assertEqual(decode_signed_int32_be(0x8000, 0x0000), -2147483648)
        self.assertEqual(decode_signed_int32_be(0xFFFF, 0xFFFF), -1)
        with self.assertRaisesRegex(ValueError, "high_word"):
            decode_signed_int32_be(0x10000, 0)
        with self.assertRaisesRegex(ValueError, "low_word"):
            decode_signed_int32_be(0, True)

    def test_boolean_and_enum_normalization_are_mapping_strict(self):
        self.assertTrue(normalize_strict_boolean(True))
        self.assertFalse(normalize_strict_boolean(False))
        with self.assertRaisesRegex(ValueError, "declared"):
            normalize_strict_boolean(1)

        self.assertTrue(
            normalize_strict_boolean(
                "ON",
                true_values=("ON",),
                false_values=("OFF",),
            )
        )
        with self.assertRaisesRegex(ValueError, "declared"):
            normalize_strict_boolean(
                "on",
                true_values=("ON",),
                false_values=("OFF",),
            )

        mapping = {"SOURCE_ON": "ON", "SOURCE_OFF": "OFF"}
        self.assertEqual(
            normalize_direct_enum("SOURCE_ON", mapping),
            "ON",
        )
        with self.assertRaisesRegex(ValueError, "not declared"):
            normalize_direct_enum("source_on", mapping)


class OrderingFactTests(unittest.TestCase):
    def test_source_order_and_out_of_order_arrival_are_separate_facts(self):
        older = canonical_candidate(
            "CANONICAL-OLDER",
            observed_at="2026-07-23T10:00:00Z",
            received_at="2026-07-23T10:03:00Z",
            sequence=10,
        )
        newer = canonical_candidate(
            "CANONICAL-NEWER",
            observed_at="2026-07-23T10:01:00Z",
            received_at="2026-07-23T10:02:00Z",
            sequence=11,
        )

        facts = observation_ordering_facts(older, newer)

        self.assertEqual(facts["observed_at_relation"], ORDER_BEFORE)
        self.assertEqual(facts["sequence_relation"], ORDER_BEFORE)
        self.assertEqual(facts["relation"], ORDER_BEFORE)
        self.assertTrue(facts["out_of_order_arrival"])

    def test_sequence_time_disagreement_is_unordered(self):
        by_time_older = canonical_candidate(
            "CANONICAL-A",
            observed_at="2026-07-23T10:00:00Z",
            sequence=12,
        )
        by_time_newer = canonical_candidate(
            "CANONICAL-B",
            observed_at="2026-07-23T10:01:00Z",
            sequence=11,
        )

        facts = observation_ordering_facts(by_time_older, by_time_newer)

        self.assertTrue(facts["sequence_time_disagreement"])
        self.assertFalse(facts["ambiguous_sequence_reset"])
        self.assertEqual(facts["relation"], ORDER_UNORDERED)

    def test_declared_epoch_reset_uses_time_but_missing_epoch_is_ambiguous(self):
        before_reset = canonical_candidate(
            "CANONICAL-A",
            observed_at="2026-07-23T10:00:00Z",
            sequence=100,
            epoch="BOOT-A",
        )
        declared_reset = canonical_candidate(
            "CANONICAL-B",
            observed_at="2026-07-23T10:01:00Z",
            sequence=1,
            epoch="BOOT-B",
        )
        ambiguous_before = deepcopy(before_reset)
        ambiguous_after = deepcopy(declared_reset)
        ambiguous_before["source_epoch"] = None
        ambiguous_after["source_epoch"] = None

        declared_facts = observation_ordering_facts(
            before_reset,
            declared_reset,
        )
        ambiguous_facts = observation_ordering_facts(
            ambiguous_before,
            ambiguous_after,
        )

        self.assertEqual(declared_facts["relation"], ORDER_BEFORE)
        self.assertFalse(declared_facts["ambiguous_sequence_reset"])
        self.assertTrue(ambiguous_facts["ambiguous_sequence_reset"])
        self.assertEqual(ambiguous_facts["relation"], ORDER_UNORDERED)

    def test_source_timestamp_after_receipt_is_a_visible_fact_only(self):
        candidate = canonical_candidate(
            "CANONICAL-A",
            observed_at="2026-07-23T10:02:00Z",
            received_at="2026-07-23T10:01:00Z",
        )

        facts = observation_temporal_facts(candidate)

        self.assertEqual(
            facts["observed_at_received_at_relation"],
            ORDER_AFTER,
        )
        self.assertTrue(facts["observed_at_after_received_at"])
        self.assertTrue(facts["has_declared_sequence_order"])


class ReportedObservationProjectionTests(unittest.TestCase):
    def project(self, candidates, *, as_of=AS_OF, known_by=KNOWN_BY):
        return project_reported_observation(
            candidates,
            as_of_observed_at=as_of,
            known_by_received_at=known_by,
        )

    def test_no_observation_and_no_eligible_report_are_distinct(self):
        no_observation = self.project([])
        missing_time = canonical_candidate(
            "CANONICAL-MISSING",
            observed_at_status=TIMESTAMP_MISSING,
        )
        no_eligible_report = self.project([missing_time])

        self.assertEqual(no_observation["disposition"], NO_OBSERVATION)
        self.assertEqual(
            no_eligible_report["disposition"],
            NO_ELIGIBLE_REPORT,
        )
        self.assertEqual(
            no_eligible_report["visible_candidates"][0][
                "event_time_eligibility"
            ],
            EVENT_TIME_MISSING,
        )
        self.assertIsNone(no_eligible_report["selected_value"])

    def test_older_report_received_later_does_not_displace_newer_report(self):
        newer = canonical_candidate(
            "CANONICAL-NEWER",
            observed_at="2026-07-23T10:02:00Z",
            received_at="2026-07-23T10:03:00Z",
            sequence=2,
            value="2.00",
        )
        older_late_arrival = canonical_candidate(
            "CANONICAL-OLDER",
            observed_at="2026-07-23T10:01:00Z",
            received_at="2026-07-23T10:04:00Z",
            sequence=1,
            value="1.00",
        )

        projection = self.project([newer, older_late_arrival])

        self.assertEqual(projection["disposition"], REPORTED)
        self.assertEqual(projection["selected_value"]["value"], "2.00")
        self.assertEqual(
            projection["selected_candidate"]["canonical_observation_id"],
            "CANONICAL-NEWER",
        )
        self.assertTrue(
            any(
                facts["out_of_order_arrival"]
                for facts in projection["ordering_facts"]
            )
        )

    def test_event_and_knowledge_cutoffs_are_bitemporal(self):
        older = canonical_candidate(
            "CANONICAL-OLDER",
            observed_at="2026-07-23T10:00:00Z",
            received_at="2026-07-23T10:01:00Z",
            sequence=1,
            value="1.00",
        )
        later_delivery = canonical_candidate(
            "CANONICAL-NEWER",
            observed_at="2026-07-23T10:02:00Z",
            received_at="2026-07-23T10:10:00Z",
            sequence=2,
            value="2.00",
        )

        early_knowledge = self.project(
            [older, later_delivery],
            known_by="2026-07-23T10:05:00Z",
        )
        later_knowledge = self.project(
            [older, later_delivery],
            known_by="2026-07-23T10:11:00Z",
        )
        early_event_view = self.project(
            [older, later_delivery],
            as_of="2026-07-23T10:01:00Z",
            known_by="2026-07-23T10:11:00Z",
        )

        self.assertEqual(early_knowledge["selected_value"]["value"], "1.00")
        self.assertEqual(len(early_knowledge["visible_candidates"]), 1)
        self.assertEqual(later_knowledge["selected_value"]["value"], "2.00")
        self.assertEqual(early_event_view["selected_value"]["value"], "1.00")
        future = next(
            candidate
            for candidate in early_event_view["visible_candidates"]
            if candidate["canonical_observation_id"] == "CANONICAL-NEWER"
        )
        self.assertEqual(
            future["event_time_eligibility"],
            EVENT_TIME_AFTER_AS_OF,
        )

    def test_exact_redelivery_is_one_logical_candidate(self):
        first_delivery = canonical_candidate(
            "CANONICAL-1",
            event_group="EVENT-1",
            variant_digest="a" * 64,
            source_native_record_ids=["NATIVE-1"],
        )
        exact_redelivery = deepcopy(first_delivery)
        exact_redelivery["received_at_utc"] = "2026-07-23T10:02:00Z"
        exact_redelivery["source_native_record_ids"] = ["NATIVE-2"]

        projection = self.project([first_delivery, exact_redelivery])

        self.assertEqual(projection["disposition"], REPORTED)
        self.assertEqual(projection["known_candidate_count"], 2)
        self.assertEqual(projection["logical_candidate_count"], 1)
        self.assertEqual(projection["exact_redelivery_count"], 1)
        self.assertEqual(
            projection["selected_candidate"]["source_native_record_ids"],
            ["NATIVE-1", "NATIVE-2"],
        )

    def test_conflicting_redelivery_appears_only_after_knowledge_cutoff(self):
        first_variant = canonical_candidate(
            "CANONICAL-A",
            event_group="EVENT-1",
            variant_digest="a" * 64,
            received_at="2026-07-23T10:01:00Z",
            value="1.00",
        )
        conflicting_variant = canonical_candidate(
            "CANONICAL-B",
            event_group="EVENT-1",
            variant_digest="b" * 64,
            received_at="2026-07-23T10:05:00Z",
            value="2.00",
        )

        before_conflict_was_known = self.project(
            [first_variant, conflicting_variant],
            known_by="2026-07-23T10:03:00Z",
        )
        after_conflict_was_known = self.project(
            [first_variant, conflicting_variant],
            known_by="2026-07-23T10:06:00Z",
        )

        self.assertEqual(before_conflict_was_known["disposition"], REPORTED)
        self.assertEqual(before_conflict_was_known["conflict_groups"], [])
        self.assertEqual(
            len(before_conflict_was_known["visible_candidates"]),
            1,
        )
        self.assertEqual(
            after_conflict_was_known["disposition"],
            CONFLICT_PRESENT,
        )
        self.assertEqual(len(after_conflict_was_known["conflict_groups"]), 1)
        self.assertIsNone(after_conflict_was_known["selected_candidate"])
        self.assertIsNone(after_conflict_was_known["selected_value"])

    def test_precomputed_conflict_survives_an_undecodable_native_variant(self):
        only_decodable_variant = canonical_candidate(
            "CANONICAL-A",
            event_group="EVENT-1",
            variant_digest="a" * 64,
            value="1.00",
        )
        # The cutoff-aware store found another native variant for EVENT-1,
        # but that variant produced no canonical candidate.
        only_decodable_variant["source_event_conflict"] = True

        projection = self.project([only_decodable_variant])

        self.assertEqual(projection["disposition"], CONFLICT_PRESENT)
        self.assertIsNone(projection["selected_candidate"])
        self.assertIsNone(projection["selected_value"])
        self.assertTrue(
            projection["visible_candidates"][0]["source_event_conflict"]
        )
        self.assertEqual(len(projection["conflict_groups"]), 1)
        conflict_group = projection["conflict_groups"][0]
        self.assertTrue(
            conflict_group["precomputed_source_event_conflict"]
        )
        self.assertTrue(
            conflict_group[
                "conflicting_variant_without_canonical_candidate"
            ]
        )
        self.assertEqual(
            conflict_group["known_canonical_variant_count"],
            1,
        )
        self.assertEqual(
            conflict_group["known_native_variant_count_lower_bound"],
            2,
        )

    def test_identityless_many_to_one_reports_never_deduplicate_by_content(self):
        first_register_pair = canonical_candidate(
            "CANONICAL-PAIR-A",
            event_group=None,
            variant_digest="a" * 64,
            source_native_record_ids=[
                "NATIVE-A-HIGH",
                "NATIVE-A-LOW",
            ],
            value="42.00",
        )
        second_register_pair = canonical_candidate(
            "CANONICAL-PAIR-B",
            event_group=None,
            variant_digest="a" * 64,
            source_native_record_ids=[
                "NATIVE-B-HIGH",
                "NATIVE-B-LOW",
            ],
            value="42.00",
        )

        projection = self.project(
            [first_register_pair, second_register_pair]
        )

        self.assertEqual(projection["disposition"], REPORTED)
        self.assertEqual(projection["known_candidate_count"], 2)
        self.assertEqual(projection["logical_candidate_count"], 2)
        self.assertEqual(projection["exact_redelivery_count"], 0)
        self.assertEqual(projection["conflict_groups"], [])
        self.assertEqual(
            projection["selected_candidate"]["canonical_observation_ids"],
            ["CANONICAL-PAIR-A", "CANONICAL-PAIR-B"],
        )
        self.assertTrue(
            all(
                candidate["source_event_group_key"] is None
                for candidate in projection["visible_candidates"]
            )
        )

    def test_equal_order_material_difference_has_no_scalar(self):
        left = canonical_candidate(
            "CANONICAL-A",
            event_group="EVENT-A",
            variant_digest="a" * 64,
            value="1.00",
        )
        right = canonical_candidate(
            "CANONICAL-B",
            event_group="EVENT-B",
            variant_digest="b" * 64,
            value="2.00",
        )

        projection = self.project([left, right])

        self.assertEqual(projection["disposition"], CONFLICT_PRESENT)
        self.assertIsNone(projection["selected_value"])

    def test_equal_order_equivalent_reports_do_not_use_id_as_tie_breaker(self):
        left = canonical_candidate(
            "CANONICAL-A",
            event_group="EVENT-A",
            variant_digest="a" * 64,
            value="1.00",
        )
        right = canonical_candidate(
            "CANONICAL-B",
            event_group="EVENT-B",
            variant_digest="b" * 64,
            value="1.00",
        )

        projection = self.project([left, right])

        self.assertEqual(projection["disposition"], REPORTED)
        self.assertEqual(projection["selected_value"]["value"], "1.00")
        self.assertIsNone(
            projection["selected_candidate"]["canonical_observation_id"]
        )
        self.assertEqual(
            projection["selected_candidate"]["canonical_observation_ids"],
            ["CANONICAL-A", "CANONICAL-B"],
        )

    def test_sequence_time_disagreement_has_no_scalar(self):
        by_time_older = canonical_candidate(
            "CANONICAL-A",
            observed_at="2026-07-23T10:00:00Z",
            sequence=2,
            value="1.00",
        )
        by_time_newer = canonical_candidate(
            "CANONICAL-B",
            observed_at="2026-07-23T10:01:00Z",
            sequence=1,
            value="2.00",
        )

        projection = self.project([by_time_older, by_time_newer])

        self.assertEqual(projection["disposition"], UNORDERED)
        self.assertIsNone(projection["selected_value"])
        self.assertTrue(
            projection["ordering_facts"][0][
                "sequence_time_disagreement"
            ]
        )

    def test_sequence_time_disagreement_cannot_be_bridged_out_of_frontier(self):
        first = canonical_candidate(
            "CANONICAL-A",
            observed_at="2026-07-23T10:00:00Z",
            sequence=1,
            value="1.00",
        )
        bridge = canonical_candidate(
            "CANONICAL-B",
            observed_at="2026-07-23T10:01:00Z",
            sequence=None,
            value="2.00",
        )
        same_sequence_later_time = canonical_candidate(
            "CANONICAL-C",
            observed_at="2026-07-23T10:02:00Z",
            sequence=1,
            value="3.00",
        )

        projection = self.project([first, bridge, same_sequence_later_time])

        self.assertEqual(projection["disposition"], UNORDERED)
        self.assertIsNone(projection["selected_candidate"])
        self.assertIsNone(projection["selected_value"])
        self.assertTrue(
            any(
                facts["sequence_time_disagreement"]
                for facts in projection["ordering_facts"]
            )
        )
        for reordered in permutations(
            [first, bridge, same_sequence_later_time]
        ):
            self.assertEqual(self.project(reordered), projection)

    def test_resolved_older_disagreement_does_not_poison_clear_newer_report(self):
        older_by_time = canonical_candidate(
            "CANONICAL-A",
            observed_at="2026-07-23T10:00:00Z",
            sequence=2,
            value="1.00",
        )
        newer_by_time = canonical_candidate(
            "CANONICAL-B",
            observed_at="2026-07-23T10:01:00Z",
            sequence=1,
            value="2.00",
        )
        clear_newest = canonical_candidate(
            "CANONICAL-C",
            observed_at="2026-07-23T10:02:00Z",
            sequence=3,
            value="3.00",
        )

        projection = self.project(
            [older_by_time, newer_by_time, clear_newest]
        )

        self.assertEqual(projection["disposition"], REPORTED)
        self.assertEqual(
            projection["selected_candidate"]["canonical_observation_id"],
            "CANONICAL-C",
        )
        self.assertEqual(projection["selected_value"]["value"], "3.00")

    def test_ambiguous_reset_is_unordered_but_declared_epoch_reset_is_not(self):
        before_reset = canonical_candidate(
            "CANONICAL-A",
            observed_at="2026-07-23T10:00:00Z",
            sequence=100,
            epoch=None,
            value="1.00",
        )
        after_reset = canonical_candidate(
            "CANONICAL-B",
            observed_at="2026-07-23T10:01:00Z",
            sequence=1,
            epoch=None,
            value="2.00",
        )
        declared_before = deepcopy(before_reset)
        declared_after = deepcopy(after_reset)
        declared_before["source_epoch"] = "BOOT-A"
        declared_after["source_epoch"] = "BOOT-B"

        ambiguous = self.project([before_reset, after_reset])
        declared = self.project([declared_before, declared_after])

        self.assertEqual(ambiguous["disposition"], UNORDERED)
        self.assertTrue(
            ambiguous["ordering_facts"][0]["ambiguous_sequence_reset"]
        )
        self.assertEqual(declared["disposition"], REPORTED)
        self.assertEqual(declared["selected_value"]["value"], "2.00")

    def test_missing_and_invalid_times_remain_visible_but_unselected(self):
        valid = canonical_candidate(
            "CANONICAL-VALID",
            sequence=3,
            value="3.00",
        )
        missing = canonical_candidate(
            "CANONICAL-MISSING",
            observed_at_status=TIMESTAMP_MISSING,
            sequence=1,
            value="1.00",
        )
        invalid = canonical_candidate(
            "CANONICAL-INVALID",
            observed_at_status=TIMESTAMP_INVALID,
            sequence=None,
            value="2.00",
        )

        projection = self.project([valid, missing, invalid])

        self.assertEqual(projection["disposition"], REPORTED)
        self.assertEqual(projection["selected_value"]["value"], "3.00")
        eligibility_by_id = {
            candidate["canonical_observation_id"]: candidate[
                "event_time_eligibility"
            ]
            for candidate in projection["visible_candidates"]
        }
        self.assertEqual(
            eligibility_by_id["CANONICAL-MISSING"],
            EVENT_TIME_MISSING,
        )
        self.assertEqual(
            eligibility_by_id["CANONICAL-INVALID"],
            EVENT_TIME_INVALID,
        )

    def test_newer_declared_sequence_without_valid_time_blocks_fallback(self):
        valid = canonical_candidate(
            "CANONICAL-VALID",
            sequence=3,
            value="3.00",
        )
        missing_newer = canonical_candidate(
            "CANONICAL-MISSING",
            observed_at_status=TIMESTAMP_MISSING,
            sequence=4,
            value="4.00",
        )

        projection = self.project([valid, missing_newer])

        self.assertEqual(projection["disposition"], UNORDERED)
        self.assertIsNone(projection["selected_value"])
        self.assertTrue(
            any(
                facts.get("issue")
                == "NEWER_SEQUENCE_HAS_NO_VALID_OBSERVED_AT"
                for facts in projection["ordering_facts"]
            )
        )

    def test_same_declared_sequence_without_valid_time_blocks_fallback(self):
        valid = canonical_candidate(
            "CANONICAL-VALID",
            sequence=4,
            value="4.00",
        )
        missing_same_sequence = canonical_candidate(
            "CANONICAL-MISSING",
            observed_at_status=TIMESTAMP_MISSING,
            sequence=4,
            value="5.00",
        )

        projection = self.project([valid, missing_same_sequence])

        self.assertEqual(projection["disposition"], UNORDERED)
        self.assertIsNone(projection["selected_candidate"])
        self.assertIsNone(projection["selected_value"])
        self.assertTrue(
            any(
                facts.get("issue")
                == "SAME_SEQUENCE_HAS_NO_VALID_OBSERVED_AT"
                for facts in projection["ordering_facts"]
            )
        )
        for reordered in permutations([valid, missing_same_sequence]):
            self.assertEqual(self.project(reordered), projection)

    def test_projection_rebuild_is_input_order_independent(self):
        candidates = [
            canonical_candidate(
                "CANONICAL-A",
                observed_at="2026-07-23T10:00:00Z",
                sequence=1,
                value="1.00",
            ),
            canonical_candidate(
                "CANONICAL-B",
                observed_at="2026-07-23T10:01:00Z",
                sequence=2,
                value="2.00",
            ),
        ]

        forward = self.project(candidates)
        reverse = self.project(reversed(candidates))

        self.assertEqual(forward, reverse)

    def test_projection_rejects_cross_scope_candidates(self):
        left = canonical_candidate("CANONICAL-A")
        right = canonical_candidate("CANONICAL-B")
        right["source_binding_id"] = "SOURCE-BINDING-2"

        with self.assertRaisesRegex(ValueError, "source_binding_id"):
            self.project([left, right])


if __name__ == "__main__":
    unittest.main()
