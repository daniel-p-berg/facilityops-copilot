import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from urllib.parse import urlencode
from urllib.parse import urlsplit

from backend import main as backend_main
from backend.services.observation_store import IdempotencyConflictError


FLAGSHIP_FACILITY_ID = "FACILITY-ADVANCED-MATERIALS-RESEARCH"
REPLAY_PACKAGE_ID = "flagship-process-exhaust-evidence-sequence"
REPLAY_PACKAGE_VERSION = "1.0.0"
REPLAY_EXECUTION_ID = "REPLAY-EXECUTION-API-TEST"


def request_json_from_asgi_app(app, path, *, method="GET", payload=None):
    async def make_request():
        messages = []
        request_sent = False
        parsed = urlsplit(path)
        body = (
            json.dumps(payload).encode("utf-8")
            if payload is not None
            else b""
        )
        headers = (
            [(b"content-type", b"application/json")]
            if payload is not None
            else []
        )

        async def receive():
            nonlocal request_sent
            if request_sent:
                return {"type": "http.disconnect"}
            request_sent = True
            return {
                "type": "http.request",
                "body": body,
                "more_body": False,
            }

        async def send(message):
            messages.append(message)

        await app(
            {
                "type": "http",
                "asgi": {"version": "3.0"},
                "http_version": "1.1",
                "method": method,
                "scheme": "http",
                "path": parsed.path,
                "raw_path": parsed.path.encode("utf-8"),
                "query_string": parsed.query.encode("utf-8"),
                "headers": headers,
                "client": ("testclient", 50000),
                "server": ("testserver", 80),
                "root_path": "",
            },
            receive,
            send,
        )
        status = next(
            item["status"]
            for item in messages
            if item["type"] == "http.response.start"
        )
        response_body = b"".join(
            item.get("body", b"")
            for item in messages
            if item["type"] == "http.response.body"
        )
        return status, json.loads(response_body.decode("utf-8"))

    return asyncio.run(make_request())


class ObservationReplayApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.observation_db = Path(self.temp_dir.name) / "observations.sqlite3"
        self.database_patch = mock.patch.object(
            backend_main,
            "OBSERVATION_DATABASE_FILE",
            self.observation_db,
        )
        self.database_patch.start()
        self.addCleanup(self.database_patch.stop)
        self.api_base = (
            f"/facilities/{FLAGSHIP_FACILITY_ID}/observation-replay"
        )

    def test_catalog_is_facility_aware_and_returns_allowlisted_packages(self):
        catalog = {
            "replay_packages": [
                {
                    "package_id": REPLAY_PACKAGE_ID,
                    "package_version": REPLAY_PACKAGE_VERSION,
                    "synthetic": True,
                }
            ]
        }
        with mock.patch.object(
            backend_main,
            "list_replay_packages",
            return_value=catalog,
        ) as list_packages:
            status, payload = request_json_from_asgi_app(
                backend_main.app,
                f"{self.api_base}/packages",
            )

        self.assertEqual(status, 200)
        self.assertEqual(payload, catalog)
        list_packages.assert_called_once_with(FLAGSHIP_FACILITY_ID)

    def test_catalog_rejects_facility_without_an_allowlisted_package(self):
        with mock.patch.object(
            backend_main,
            "list_replay_packages",
            return_value={"replay_packages": []},
        ):
            status, payload = request_json_from_asgi_app(
                backend_main.app,
                "/facilities/OTHER-FACILITY/observation-replay/packages",
            )

        self.assertEqual(status, 404)
        self.assertIn("selected facility", payload["error"])

    def test_package_detail_uses_only_allowlisted_identity_not_a_path(self):
        detail = {
            "package_id": REPLAY_PACKAGE_ID,
            "package_version": REPLAY_PACKAGE_VERSION,
            "structural_validation": "VALID",
        }
        with mock.patch.object(
            backend_main,
            "get_replay_package_detail",
            return_value=detail,
        ) as get_detail:
            status, payload = request_json_from_asgi_app(
                backend_main.app,
                f"{self.api_base}/packages/{REPLAY_PACKAGE_ID}/versions/"
                f"{REPLAY_PACKAGE_VERSION}",
            )

        self.assertEqual(status, 200)
        self.assertEqual(payload, detail)
        get_detail.assert_called_once_with(
            FLAGSHIP_FACILITY_ID,
            REPLAY_PACKAGE_ID,
            REPLAY_PACKAGE_VERSION,
        )

    def test_execution_creation_passes_separate_store_and_explicit_identities(self):
        service_result = {
            "replay_execution": {
                "replay_execution_id": REPLAY_EXECUTION_ID,
                "facility_id": FLAGSHIP_FACILITY_ID,
            },
            "idempotent_replay": False,
            "statement": "Synthetic evidence only.",
        }
        request = {
            "package_id": REPLAY_PACKAGE_ID,
            "package_version": REPLAY_PACKAGE_VERSION,
            "idempotency_key": "api-request-001",
            "replay_execution_id": REPLAY_EXECUTION_ID,
        }
        with mock.patch.object(
            backend_main,
            "execute_replay_package",
            return_value=service_result,
        ) as execute:
            status, payload = request_json_from_asgi_app(
                backend_main.app,
                f"{self.api_base}/executions",
                method="POST",
                payload=request,
            )

        self.assertEqual(status, 200)
        self.assertEqual(payload, service_result)
        execute.assert_called_once_with(
            self.observation_db,
            facility_id=FLAGSHIP_FACILITY_ID,
            package_id=REPLAY_PACKAGE_ID,
            package_version=REPLAY_PACKAGE_VERSION,
            idempotency_key="api-request-001",
            replay_execution_id=REPLAY_EXECUTION_ID,
        )

    def test_execution_creation_rejects_arbitrary_package_path_field(self):
        request = {
            "package_id": REPLAY_PACKAGE_ID,
            "package_version": REPLAY_PACKAGE_VERSION,
            "idempotency_key": "api-request-001",
            "package_path": "/tmp/untrusted-package",
        }
        with mock.patch.object(
            backend_main,
            "execute_replay_package",
        ) as execute:
            status, payload = request_json_from_asgi_app(
                backend_main.app,
                f"{self.api_base}/executions",
                method="POST",
                payload=request,
            )

        self.assertEqual(status, 400)
        self.assertIn("unsupported fields", payload["error"])
        execute.assert_not_called()

    def test_idempotency_conflict_maps_to_http_409(self):
        with mock.patch.object(
            backend_main,
            "execute_replay_package",
            side_effect=IdempotencyConflictError(
                "Replay request idempotency key was reused with different content"
            ),
        ):
            status, payload = request_json_from_asgi_app(
                backend_main.app,
                f"{self.api_base}/executions",
                method="POST",
                payload={
                    "package_id": REPLAY_PACKAGE_ID,
                    "package_version": REPLAY_PACKAGE_VERSION,
                    "idempotency_key": "reused-request",
                },
            )

        self.assertEqual(status, 409)
        self.assertIn("different content", payload["error"])

    def test_execution_scoped_list_checks_execution_before_returning_empty_page(self):
        with (
            mock.patch.object(
                backend_main,
                "get_replay_execution",
                side_effect=LookupError(
                    "Replay execution not found for the selected facility"
                ),
            ) as get_execution,
            mock.patch.object(
                backend_main,
                "list_source_native_records",
            ) as list_records,
        ):
            status, payload = request_json_from_asgi_app(
                backend_main.app,
                f"{self.api_base}/executions/{REPLAY_EXECUTION_ID}/"
                "source-native-records?page=1&page_size=100",
            )

        self.assertEqual(status, 404)
        self.assertIn("selected facility", payload["error"])
        get_execution.assert_called_once_with(
            self.observation_db,
            FLAGSHIP_FACILITY_ID,
            REPLAY_EXECUTION_ID,
        )
        list_records.assert_not_called()

    def test_source_native_list_forwards_bounded_filters(self):
        page = {
            "source_native_records": [],
            "pagination": {
                "page": 2,
                "page_size": 25,
                "total_records": 0,
                "has_more": False,
            },
        }
        query = urlencode(
            {
                "page": 2,
                "page_size": 25,
                "source_binding_id": "SOURCE-BINDING-1",
                "source_event_group_key": "SOURCE-EVENT-GROUP-1",
                "observed_at_status": "MISSING",
            }
        )
        with (
            mock.patch.object(
                backend_main,
                "get_replay_execution",
                return_value={"replay_execution_id": REPLAY_EXECUTION_ID},
            ),
            mock.patch.object(
                backend_main,
                "list_source_native_records",
                return_value=page,
            ) as list_records,
        ):
            status, payload = request_json_from_asgi_app(
                backend_main.app,
                f"{self.api_base}/executions/{REPLAY_EXECUTION_ID}/"
                f"source-native-records?{query}",
            )

        self.assertEqual(status, 200)
        self.assertEqual(payload, page)
        list_records.assert_called_once_with(
            self.observation_db,
            FLAGSHIP_FACILITY_ID,
            REPLAY_EXECUTION_ID,
            page=2,
            page_size=25,
            source_binding_id="SOURCE-BINDING-1",
            source_event_group_key="SOURCE-EVENT-GROUP-1",
            observed_at_status="MISSING",
        )

    def test_detail_rejects_record_from_another_replay_execution(self):
        with (
            mock.patch.object(
                backend_main,
                "get_replay_execution",
                return_value={"replay_execution_id": REPLAY_EXECUTION_ID},
            ),
            mock.patch.object(
                backend_main,
                "get_canonical_observation",
                return_value={
                    "canonical_observation_id": "CANONICAL-1",
                    "replay_execution_id": "OTHER-EXECUTION",
                },
            ),
        ):
            status, payload = request_json_from_asgi_app(
                backend_main.app,
                f"{self.api_base}/executions/{REPLAY_EXECUTION_ID}/"
                "canonical-observations/CANONICAL-1",
            )

        self.assertEqual(status, 404)
        self.assertIn("selected replay execution", payload["error"])

    def test_canonical_time_filters_are_normalized_before_store_query(self):
        page = {
            "canonical_observations": [],
            "pagination": {
                "page": 1,
                "page_size": 20,
                "total_records": 0,
                "has_more": False,
            },
        }
        query = urlencode(
            {
                "page": 1,
                "page_size": 20,
                "observed_from": "2026-07-23T13:00:00+01:00",
                "observed_to": "2026-07-23T08:00:00-05:00",
            }
        )
        with (
            mock.patch.object(
                backend_main,
                "get_replay_execution",
                return_value={"replay_execution_id": REPLAY_EXECUTION_ID},
            ),
            mock.patch.object(
                backend_main,
                "list_canonical_observations",
                return_value=page,
            ) as list_observations,
        ):
            status, payload = request_json_from_asgi_app(
                backend_main.app,
                f"{self.api_base}/executions/{REPLAY_EXECUTION_ID}/"
                f"canonical-observations?{query}",
            )

        self.assertEqual(status, 200)
        self.assertEqual(payload, page)
        list_observations.assert_called_once_with(
            self.observation_db,
            FLAGSHIP_FACILITY_ID,
            REPLAY_EXECUTION_ID,
            page=1,
            page_size=20,
            source_binding_id=None,
            point_id=None,
            mapping_id=None,
            observed_from="2026-07-23T12:00:00Z",
            observed_to="2026-07-23T13:00:00Z",
        )

    def test_canonical_time_filter_rejects_invalid_or_reversed_range(self):
        with (
            mock.patch.object(
                backend_main,
                "get_replay_execution",
                return_value={"replay_execution_id": REPLAY_EXECUTION_ID},
            ),
            mock.patch.object(
                backend_main,
                "list_canonical_observations",
            ) as list_observations,
        ):
            invalid_status, _ = request_json_from_asgi_app(
                backend_main.app,
                f"{self.api_base}/executions/{REPLAY_EXECUTION_ID}/"
                "canonical-observations?observed_from=not-a-time",
            )
            reversed_status, reversed_payload = request_json_from_asgi_app(
                backend_main.app,
                f"{self.api_base}/executions/{REPLAY_EXECUTION_ID}/"
                "canonical-observations?"
                + urlencode(
                    {
                        "observed_from": "2026-07-23T13:00:01Z",
                        "observed_to": "2026-07-23T13:00:00Z",
                    }
                ),
            )

        self.assertEqual(invalid_status, 400)
        self.assertEqual(reversed_status, 400)
        self.assertIn("must not be after", reversed_payload["error"])
        list_observations.assert_not_called()

    def test_projection_requires_and_forwards_bitemporal_scope(self):
        query_values = {
            "source_binding_id": "SOURCE-BINDING-1",
            "point_id": "PROCESS_ENABLED_STATUS",
            "mapping_id": "MAPPING-CONTROLLER-CONTEXT",
            "mapping_version": "1.0.0",
            "mapping_digest": "a" * 64,
            "as_of_observed_at": "2026-07-23T12:00:00Z",
            "known_by_received_at": "2026-07-23T12:00:05Z",
        }
        expected = {
            "disposition": "REPORTED",
            "as_of_observed_at": query_values["as_of_observed_at"],
            "known_by_received_at": query_values["known_by_received_at"],
        }
        with (
            mock.patch.object(
                backend_main,
                "get_replay_execution",
                return_value={"replay_execution_id": REPLAY_EXECUTION_ID},
            ) as get_execution,
            mock.patch.object(
                backend_main,
                "get_reported_observation_projection",
                return_value=expected,
            ) as get_projection,
        ):
            status, payload = request_json_from_asgi_app(
                backend_main.app,
                f"{self.api_base}/executions/{REPLAY_EXECUTION_ID}/"
                f"reported-observation-projection?{urlencode(query_values)}",
            )

        self.assertEqual(status, 200)
        self.assertEqual(payload, expected)
        get_execution.assert_called_once_with(
            self.observation_db,
            FLAGSHIP_FACILITY_ID,
            REPLAY_EXECUTION_ID,
        )
        get_projection.assert_called_once_with(
            self.observation_db,
            facility_id=FLAGSHIP_FACILITY_ID,
            replay_execution_id=REPLAY_EXECUTION_ID,
            **query_values,
        )

    def test_missing_projection_cutoffs_are_rejected_before_service_call(self):
        with mock.patch.object(
            backend_main,
            "get_reported_observation_projection",
        ) as get_projection:
            status, payload = request_json_from_asgi_app(
                backend_main.app,
                f"{self.api_base}/executions/{REPLAY_EXECUTION_ID}/"
                "reported-observation-projection",
            )

        self.assertEqual(status, 422)
        self.assertIn("detail", payload)
        get_projection.assert_not_called()

    def test_real_allowlisted_package_round_trips_through_inspection_routes(self):
        catalog_status, catalog = request_json_from_asgi_app(
            backend_main.app,
            f"{self.api_base}/packages",
        )
        self.assertEqual(catalog_status, 200)
        replay_package = catalog["replay_packages"][0]

        create_status, created = request_json_from_asgi_app(
            backend_main.app,
            f"{self.api_base}/executions",
            method="POST",
            payload={
                "package_id": replay_package["package_id"],
                "package_version": replay_package["package_version"],
                "idempotency_key": "api-real-package-round-trip",
                "replay_execution_id": REPLAY_EXECUTION_ID,
            },
        )
        self.assertEqual(create_status, 200)
        self.assertFalse(created["idempotent_replay"])
        run_path = (
            f"{self.api_base}/executions/"
            f"{created['replay_execution']['replay_execution_id']}"
        )

        native_status, native_page = request_json_from_asgi_app(
            backend_main.app,
            f"{run_path}/source-native-records?page_size=100",
        )
        canonical_status, canonical_page = request_json_from_asgi_app(
            backend_main.app,
            f"{run_path}/canonical-observations?page_size=100",
        )
        group_status, group_page = request_json_from_asgi_app(
            backend_main.app,
            f"{run_path}/redelivery-groups?page_size=100",
        )
        manifest_status, manifest = request_json_from_asgi_app(
            backend_main.app,
            f"{run_path}/manifest",
        )
        self.assertEqual(
            (native_status, canonical_status, group_status, manifest_status),
            (200, 200, 200, 200),
        )
        self.assertGreater(native_page["pagination"]["total_records"], 0)
        self.assertTrue(
            all(
                record["identity_kind"]
                for record in native_page["source_native_records"]
            )
        )
        self.assertTrue(
            any(
                record["source_event_id"] is not None
                for record in native_page["source_native_records"]
            )
        )
        self.assertGreater(canonical_page["pagination"]["total_records"], 0)
        self.assertGreater(group_page["pagination"]["total_records"], 0)
        self.assertEqual(
            manifest["reproducibility_manifest"]["replay_execution_id"],
            REPLAY_EXECUTION_ID,
        )

        native_record = native_page["source_native_records"][0]
        native_detail_status, native_detail = request_json_from_asgi_app(
            backend_main.app,
            f"{run_path}/source-native-records/"
            f"{native_record['source_native_record_id']}",
        )
        self.assertEqual(native_detail_status, 200)
        self.assertEqual(
            native_detail["source_native_record"]["source_event_id"],
            native_record["source_event_id"],
        )

        canonical = canonical_page["canonical_observations"][0]
        lineage_status, lineage = request_json_from_asgi_app(
            backend_main.app,
            f"{run_path}/canonical-observations/"
            f"{canonical['canonical_observation_id']}/lineage",
        )
        self.assertEqual(lineage_status, 200)
        self.assertTrue(lineage["source_native_lineage"])

        latest_observed = max(
            observation["observed_at_utc"]
            for observation in canonical_page["canonical_observations"]
            if observation["observed_at_utc"] is not None
        )
        latest_received = max(
            record["received_at_utc"]
            for record in native_page["source_native_records"]
        )
        projection_query = urlencode(
            {
                "source_binding_id": canonical["source_binding_id"],
                "point_id": canonical["canonical_point_definition_id"],
                "mapping_id": canonical["mapping_id"],
                "mapping_version": canonical["mapping_version"],
                "mapping_digest": canonical["mapping_digest"],
                "as_of_observed_at": latest_observed,
                "known_by_received_at": latest_received,
            }
        )
        projection_status, projection = request_json_from_asgi_app(
            backend_main.app,
            f"{run_path}/reported-observation-projection?{projection_query}",
        )
        self.assertEqual(projection_status, 200)
        self.assertIn(
            projection["disposition"],
            {
                "NO_OBSERVATION",
                "NO_ELIGIBLE_REPORT",
                "REPORTED",
                "CONFLICT_PRESENT",
                "UNORDERED",
            },
        )
        self.assertEqual(
            projection["as_of_observed_at"],
            latest_observed,
        )
        self.assertEqual(
            projection["known_by_received_at"],
            latest_received,
        )

        cross_facility_status, _ = request_json_from_asgi_app(
            backend_main.app,
            "/facilities/OTHER-FACILITY/observation-replay/executions/"
            f"{REPLAY_EXECUTION_ID}/canonical-observations",
        )
        self.assertEqual(cross_facility_status, 404)


class ObservationReplayWorkbenchTests(unittest.TestCase):
    def test_workbench_exposes_evidence_inspection_without_state_claims(self):
        html = (
            Path(__file__).resolve().parents[1] / "frontend" / "index.html"
        ).read_text(encoding="utf-8")

        required_terms = (
            "Structurally validated replay package",
            "Source-native records",
            "Canonical observations",
            "Observed time reported by source",
            "FacilityOps receipt time",
            "Reported-observation projection",
            "Unresolved conflict",
            "Reproducibility manifest",
            "NO_FLAGSHIP_OBSERVATION_BASELINE",
        )
        for term in required_terms:
            self.assertIn(term, html)

        self.assertIn(
            "/facilities/${encodeURIComponent(observationReplayFacilityId)}/"
            "observation-replay",
            html,
        )
        self.assertIn("as_of_observed_at", html)
        self.assertIn("known_by_received_at", html)
        self.assertIn("loadCanonicalLineage", html)
        self.assertIn("loadSourceNativeRecordDetail", html)

        prohibited_claims = (
            "actual equipment state",
            "fan failed",
            "fan operating",
            "successful changeover",
            "airflow sufficient",
            "containment maintained",
            "containment lost",
            "pressure cascade adequate",
            "facility safe",
            "recovery verified",
            "authorized action",
            "code compliant",
            "commissioning accepted",
        )
        normalized_html = html.lower()
        for claim in prohibited_claims:
            self.assertNotIn(claim, normalized_html)

    def test_standards_default_remains_separate_from_selected_replay(self):
        html = (
            Path(__file__).resolve().parents[1] / "frontend" / "index.html"
        ).read_text(encoding="utf-8")

        self.assertIn("NO_FLAGSHIP_OBSERVATION_BASELINE", html)
        self.assertIn(
            "Selecting a replay does not\n"
            "        modify the standards package or its default "
            "observation-baseline declaration.",
            html,
        )


if __name__ == "__main__":
    unittest.main()
