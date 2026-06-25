import unittest
from engine import run_gap_analysis, run_eligibility, load_rules, MissingFieldError

CONFIG = load_rules()


class TestGapAnalysis(unittest.TestCase):
    def test_sample_report_matches_spec(self):
        report = {
            "customer_id": "C001", "credit_utilisation_pct": 87,
            "missed_payments_12m": 2, "written_off_accounts": 0,
            "credit_age_months": 14, "hard_enquiries_6m": 2,
        }
        r = run_gap_analysis(report, CONFIG)
        self.assertEqual(r["gaps_found"], 3)
        self.assertEqual(r["total_potential_score_gain"], 70)
        self.assertEqual([g["id"] for g in r["gaps"]],
                          ["high_utilisation", "missed_payments", "short_credit_age"])

    def test_all_gap_rules_fire(self):
        report = {
            "customer_id": "C002", "credit_utilisation_pct": 95,
            "missed_payments_12m": 5, "written_off_accounts": 1,
            "credit_age_months": 6, "hard_enquiries_6m": 8,
        }
        r = run_gap_analysis(report, CONFIG)
        self.assertEqual(r["gaps_found"], 5)
        impacts = [g["impact"] for g in r["gaps"]]
        self.assertEqual(impacts, sorted(impacts, key=lambda i: {"high": 0, "medium": 1, "low": 2}[i]))

    def test_no_gaps_found(self):
        report = {
            "customer_id": "C003", "credit_utilisation_pct": 10,
            "missed_payments_12m": 0, "written_off_accounts": 0,
            "credit_age_months": 60, "hard_enquiries_6m": 1,
        }
        r = run_gap_analysis(report, CONFIG)
        self.assertEqual(r["gaps_found"], 0)
        self.assertEqual(r["gaps"], [])

    def test_action_template_substitution(self):
        report = {
            "customer_id": "C004", "credit_utilisation_pct": 87,
            "missed_payments_12m": 0, "written_off_accounts": 0,
            "credit_age_months": 60, "hard_enquiries_6m": 0,
        }
        r = run_gap_analysis(report, CONFIG)
        self.assertIn("87", r["gaps"][0]["action"])

    def test_missing_field_raises(self):
        report = {"customer_id": "C005", "credit_utilisation_pct": 87}
        with self.assertRaises(MissingFieldError):
            run_gap_analysis(report, CONFIG)


class TestEligibility(unittest.TestCase):
    def test_sample_profile_fails_on_score(self):
        profile = {
            "customer_id": "C001", "age": 29, "cibil_score": 620,
            "monthly_income": 60000, "existing_emis": 15000, "foir": 0.25,
            "employment_type": "salaried", "written_off_accounts": 0,
            "requested_amount": 400000,
        }
        r = run_eligibility(profile, CONFIG)
        self.assertFalse(r["eligible"])
        self.assertEqual(r["fail_reasons"], ["cibil_score"])

    def test_all_rules_pass(self):
        profile = {
            "customer_id": "C006", "age": 30, "cibil_score": 720,
            "monthly_income": 60000, "existing_emis": 10000, "foir": 0.2,
            "employment_type": "salaried", "written_off_accounts": 0,
            "requested_amount": 300000,
        }
        r = run_eligibility(profile, CONFIG)
        self.assertTrue(r["eligible"])
        self.assertEqual(r["fail_reasons"], [])

    def test_multiple_rules_fail(self):
        profile = {
            "customer_id": "C007", "age": 19, "cibil_score": 500,
            "monthly_income": 20000, "existing_emis": 15000, "foir": 0.7,
            "employment_type": "freelancer", "written_off_accounts": 1,
            "requested_amount": 500000,
        }
        r = run_eligibility(profile, CONFIG)
        self.assertFalse(r["eligible"])
        self.assertGreaterEqual(len(r["fail_reasons"]), 4)

    def test_missing_field_raises(self):
        profile = {"customer_id": "C008", "age": 30}
        with self.assertRaises(MissingFieldError):
            run_eligibility(profile, CONFIG)


if __name__ == "__main__":
    unittest.main()