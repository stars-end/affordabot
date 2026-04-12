from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = ROOT / "backend" / "scripts" / "verification" / "windmill_bakeoff_domain_boundary.py"

spec = spec_from_file_location("windmill_bakeoff_domain_boundary", SCRIPT_PATH)
module = module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class TestWindmillBakeoffDomainBoundary(unittest.TestCase):
    def test_happy_rerun_is_idempotent_for_chunks_and_analysis(self):
        result = module.run_scenario("happy_rerun")
        first = result["first_run"]
        rerun = result["rerun"]

        self.assertEqual(first["status"], "succeeded")
        self.assertEqual(rerun["status"], "succeeded")

        self.assertGreater(first["step_results"]["index"]["chunks_created"], 0)
        self.assertEqual(rerun["step_results"]["index"]["chunks_created"], 0)

        self.assertEqual(
            first["step_results"]["read_fetch"]["canonical_document_key"],
            rerun["step_results"]["read_fetch"]["canonical_document_key"],
        )
        self.assertEqual(
            first["step_results"]["analyze"]["analysis_id"],
            rerun["step_results"]["analyze"]["analysis_id"],
        )
        self.assertIs(rerun["step_results"]["analyze"]["reused"], True)

    def test_analysis_fails_closed_without_evidence(self):
        store = module.InMemoryDomainStore()
        domain = module.DomainBoundaryService(
            store=store,
            search_client=module.SearxLikeClient(fail_mode=False),
            reader_client=module.ReaderContractClient(fail_mode=False),
            vector_adapter=module.VectorAdapter(),
            analysis_adapter=module.AnalysisAdapter(),
        )
        env = module.Envelope(
            architecture_path="affordabot_domain_boundary",
            windmill_run_id="run-fail-closed",
            windmill_job_id="job-analyze",
            idempotency_key="san-jose-ca:meeting_minutes:2026-04-12",
            jurisdiction="San Jose CA",
            source_family="meeting_minutes",
        )

        result = domain.analyze(env, "Any question")
        self.assertEqual(result["status"], "analysis_error")
        self.assertEqual(result["error"], "insufficient_evidence")

    def test_stale_gate_statuses_are_emitted(self):
        stale_usable = module.run_scenario("stale_usable")
        stale_blocked = module.run_scenario("stale_blocked")

        self.assertEqual(stale_usable["step_results"]["freshness_gate"]["status"], "stale_but_usable")
        self.assertEqual(stale_usable["status"], "succeeded")
        self.assertIn("freshness_gate:stale_but_usable", stale_usable["alerts"])

        self.assertEqual(stale_blocked["step_results"]["freshness_gate"]["status"], "stale_blocked")
        self.assertEqual(stale_blocked["status"], "failed")


if __name__ == "__main__":
    unittest.main()
