"""
Unit tesztek a compute_critic_hit_rate függvényhez (Phase 2): kísérletenkénti
arány, hány futásban jelzett a critic node legalább egy "kritikus" súlyosságú
issue-t, a critic SAJÁT nyers JSON kimenetéből számolva.
"""
import sys
import os
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from experiment_evaluator import compute_critic_hit_rate


def _run(experiment_id, issues):
    critic_json = json.dumps({"issues": issues, "recommendation": "revízió"})
    return {"experiment_id": experiment_id, "outputs": {"critic": critic_json}}


class TestComputeCriticHitRate:
    def test_all_runs_have_critical_issue(self):
        runs = [
            _run("exp-001", [{"severity": "kritikus", "description": "x"}]),
            _run("exp-001", [{"severity": "kritikus", "description": "y"}, {"severity": "kisebb", "description": "z"}]),
        ]
        result = compute_critic_hit_rate(runs)
        assert result["exp-001"] == 1.0

    def test_no_runs_have_critical_issue(self):
        runs = [
            _run("exp-002", [{"severity": "kisebb", "description": "x"}]),
            _run("exp-002", [{"severity": "közepes", "description": "y"}]),
        ]
        result = compute_critic_hit_rate(runs)
        assert result["exp-002"] == 0.0

    def test_partial_hit_rate(self):
        runs = [
            _run("exp-003", [{"severity": "kritikus", "description": "x"}]),
            _run("exp-003", [{"severity": "kisebb", "description": "y"}]),
        ]
        result = compute_critic_hit_rate(runs)
        assert result["exp-003"] == 0.5

    def test_case_insensitive_severity_match(self):
        runs = [_run("exp-004", [{"severity": "Kritikus", "description": "x"}])]
        result = compute_critic_hit_rate(runs)
        assert result["exp-004"] == 1.0

    def test_malformed_critic_json_treated_as_no_issues(self):
        runs = [{"experiment_id": "exp-005", "outputs": {"critic": "not valid json {{"}}]
        result = compute_critic_hit_rate(runs)
        assert result["exp-005"] == 0.0

    def test_multiple_experiments_independent(self):
        runs = [
            _run("exp-A", [{"severity": "kritikus", "description": "x"}]),
            _run("exp-B", [{"severity": "kisebb", "description": "y"}]),
        ]
        result = compute_critic_hit_rate(runs)
        assert result["exp-A"] == 1.0
        assert result["exp-B"] == 0.0
