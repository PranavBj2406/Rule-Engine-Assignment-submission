"""
Softlend Rule Engine
====================
    python engine.py --mode gap_analysis --input report.json
    python engine.py --mode eligibility  --input profile.json

Every threshold lives in rules.yaml. Add a rule = add a YAML entry,
no code changes needed.
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from typing import Optional

import yaml

RULES_PATH = Path(__file__).parent / "rules.yaml"


class MissingFieldError(Exception):
    def __init__(self, field: str):
        self.field = field
        super().__init__(f"Missing required field: '{field}'")


# ---------------- Operators ----------------
def _gt(v, r, d):      return v > r["value"]
def _lt(v, r, d):      return v < r["value"]
def _gte(v, r, d):     return v >= r["value"]
def _lte(v, r, d):     return v <= r["value"]
def _eq(v, r, d):      return v == r["value"]
def _between(v, r, d): return r["min"] <= v <= r["max"]
def _in(v, r, d):      return v in r["values"]

def _lte_multiplier(v, r, d):
    other = d.get(r["multiplier_field"])
    if other is None:
        raise MissingFieldError(r["multiplier_field"])
    return v <= other * r["multiplier"]

OPERATORS = {
    "gt": _gt, "lt": _lt, "gte": _gte, "lte": _lte, "eq": _eq,
    "between": _between, "in": _in, "lte_multiplier": _lte_multiplier,
}


def evaluate(operator: str, value, rule: dict, data: dict) -> bool:
    if operator not in OPERATORS:
        raise ValueError(f"Unknown operator '{operator}'. Supported: {sorted(OPERATORS)}")
    return OPERATORS[operator](value, rule, data)


def load_rules(path: Path = RULES_PATH) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


# ---------------- Stage 1: Gap analysis ----------------
IMPACT_ORDER = {"high": 0, "medium": 1, "low": 2}


def run_gap_analysis(report: dict, config: dict) -> dict:
    gaps = []
    for rule in config.get("gap_rules", []):
        field = rule["field"]
        if field not in report:
            raise MissingFieldError(field)
        current_value = report[field]
        if evaluate(rule["operator"], current_value, rule, report):
            gaps.append({
                "id": rule["id"],
                "impact": rule["impact"],
                "estimated_score_gain": rule["estimated_score_gain"],
                "action": rule["action_template"].format(current_value=current_value),
            })

    gaps.sort(key=lambda g: (IMPACT_ORDER[g["impact"]], -g["estimated_score_gain"]))

    return {
        "customer_id": report.get("customer_id"),
        "mode": "gap_analysis",
        "gaps_found": len(gaps),
        "total_potential_score_gain": sum(g["estimated_score_gain"] for g in gaps),
        "gaps": gaps,
    }


# ---------------- Stage 2: Eligibility ----------------
def _evaluate_single_rule(rule: dict, profile: dict) -> tuple[bool, Optional[str]]:
    field = rule["field"]
    if field not in profile:
        raise MissingFieldError(field)
    passed = evaluate(rule["operator"], profile[field], rule, profile)
    return passed, (None if passed else rule.get("message", f"Rule '{rule['id']}' failed"))


def run_eligibility(profile: dict, config: dict) -> dict:
    results, fail_reasons, group_results = [], [], []
    failed_weight = total_weight = 0.0

    for group in config.get("eligibility_rules", []):
        logic = group.get("logic", "AND").upper()
        outcomes = []
        for rule in group["rules"]:
            passed, reason = _evaluate_single_rule(rule, profile)
            weight = rule.get("weight", 0)
            total_weight += weight
            if not passed:
                failed_weight += weight
                fail_reasons.append(rule["id"])
            outcomes.append(passed)
            entry = {"rule": rule["id"], "passed": passed}
            if reason:
                entry["reason"] = reason
            results.append(entry)
        group_results.append(all(outcomes) if logic == "AND" else any(outcomes))

    eligible = all(group_results) if group_results else False
    risk_score = round((failed_weight / total_weight) * 100, 2) if total_weight else 0.0

    next_step = None
    if not eligible:
        if "cibil_score" in fail_reasons:
            score_rule = next(r for g in config["eligibility_rules"] for r in g["rules"] if r["id"] == "cibil_score")
            needed = score_rule["value"] - profile.get("cibil_score", 0)
            next_step = f"Improve CIBIL score by at least {needed} points. See gap analysis for the fastest path."
        else:
            next_step = "Resolve the failed rule(s) above and re-check eligibility."

    out = {
        "customer_id": profile.get("customer_id"),
        "mode": "eligibility",
        "eligible": eligible,
        "rules": results,
        "fail_reasons": fail_reasons,
        "risk_score": risk_score,
    }
    if next_step:
        out["next_step"] = next_step
    return out


# ---------------- CLI ----------------
def main():
    parser = argparse.ArgumentParser(description="Softlend Rule Engine")
    parser.add_argument("--mode", required=True, choices=["gap_analysis", "eligibility"])
    parser.add_argument("--input", required=True, help="Path to input JSON file")
    parser.add_argument("--rules", default=str(RULES_PATH), help="Path to rules.yaml")
    args = parser.parse_args()

    config = load_rules(Path(args.rules))
    with open(args.input) as f:
        data = json.load(f)

    try:
        result = run_gap_analysis(data, config) if args.mode == "gap_analysis" else run_eligibility(data, config)
    except MissingFieldError as e:
        print(json.dumps({"error": str(e), "code": "MISSING_FIELD"}, indent=2))
        sys.exit(1)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()