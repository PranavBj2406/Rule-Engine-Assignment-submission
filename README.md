# Softlend Rule Engine

A two-stage, config-driven engine that powers Softlend's credit gap
analysis and loan eligibility evaluation. Both stages are driven entirely
by `rules.yaml` — zero thresholds are hardcoded in Python.

## What it does

1. **Gap analysis** — given a customer's credit report, identifies which
   gap rules fire (high utilisation, missed payments, etc.) and returns a
   ranked list of improvement actions with estimated score impact.
2. **Eligibility evaluation** — given a customer profile, checks whether
   they qualify for a loan right now and returns pass/fail per rule with
   reasons, plus a weighted risk score.

## Setup

```bash
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux
pip install pyyaml
```

## Running

**Gap analysis mode:**
```bash
python engine.py --mode gap_analysis --input report.json
```

**Eligibility mode:**
```bash
python engine.py --mode eligibility --input profile.json
```

**Run tests:**
```bash
python -m unittest test_engine.py -v
```

## Project structure

├── engine.py        # Core engine: operators, gap analysis, eligibility, CLI
├── rules.yaml        # All thresholds and rule definitions — single source of truth
├── test_engine.py     # 9 unit tests covering both modes + edge cases
├── report.json        # Sample credit report input (gap_analysis mode)
├── profile.json        # Sample customer profile input (eligibility mode)
└── README.md

## Adding a new rule

No code changes are ever needed — just edit `rules.yaml`.

**To add a gap rule**, add an entry under `gap_rules`:
```yaml
  - id: low_savings_balance
    field: savings_balance
    operator: lt
    value: 10000
    impact: low
    estimated_score_gain: 5
    action_template: "Build a savings buffer above ₹10,000 (currently {current_value})"
```

**To add an eligibility rule**, add it to an existing group's `rules`
list, or create a new group with its own `logic: AND` / `OR`:
```yaml
  - id: min_vintage
    field: account_vintage_months
    operator: gte
    value: 6
    weight: 0.05
    message: "Account vintage {value} is below the minimum {threshold} months"
```

## Operators supported

| Operator         | Meaning                              | Example                                    |
|------------------|----------------------------------------|---------------------------------------------|
| `gt`             | strictly greater than                  | `credit_utilisation_pct > 30`               |
| `lt`             | strictly less than                     | `credit_age_months < 36`                    |
| `gte`            | greater than or equal                  | `cibil_score >= 650`                        |
| `lte`            | less than or equal                     | `foir <= 0.5`                               |
| `eq`             | equal                                  | `written_off_accounts == 0`                 |
| `between`        | inclusive range (`min` / `max`)        | `21 <= age <= 60`                           |
| `in`             | value in a list (`values`)             | `employment_type in [salaried, self_employed]` |
| `lte_multiplier` | field <= another field × multiplier    | `requested_amount <= monthly_income * 10`   |

## Output formats

**Gap analysis:**
```json
{
  "customer_id": "C001",
  "mode": "gap_analysis",
  "gaps_found": 3,
  "total_potential_score_gain": 70,
  "gaps": [ { "id": "...", "impact": "...", "estimated_score_gain": 35, "action": "..." } ]
}
```

**Eligibility:**
```json
{
  "customer_id": "C001",
  "mode": "eligibility",
  "eligible": false,
  "rules": [ { "rule": "cibil_score", "passed": false, "reason": "Score 620 is below required 650" } ],
  "fail_reasons": ["cibil_score"],
  "risk_score": 35.0,
  "next_step": "Improve CIBIL score by at least 30 points. See gap analysis for the fastest path."
}
```

## Error handling

Missing required input fields raise a `MissingFieldError` instead of
crashing. At the CLI level this prints a clean JSON error and exits
non-zero:
```json
{ "error": "Missing required field: 'cibil_score'", "code": "MISSING_FIELD" }
```

## Test coverage

`test_engine.py` includes 9 cases across both modes:
- Sample report/profile matches the spec's expected output exactly
- All gap rules firing, sorted correctly by impact then score gain
- No gaps found → empty list
- `action_template` placeholder substitution
- All eligibility rules passing
- Multiple eligibility rules failing simultaneously
- Missing-field errors in both modes (no crash)
