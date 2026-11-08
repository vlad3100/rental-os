from rental_copilot.config import REPO_ROOT, load_settings
from rental_copilot.evals import run_eval


def test_eval_set_with_mock_has_no_hard_gate_violations():
    """Regression guard: any change that lets an unsafe draft through fails CI."""
    settings = load_settings(llm_provider="mock", db_path=":memory:")
    meta, summary, results = run_eval(REPO_ROOT / "evals" / "cases_v1.json", settings)
    assert meta["dataset_version"] == "1.0.0"
    assert summary["hard_gate_violations"] == 0
    failed = [r.case_id for r in results if not r.passed]
    assert failed == [], f"failed cases: {failed}"
