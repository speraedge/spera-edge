"""Review-import rejects invalid batches and safely replays matching events."""
import sqlite3
import unittest

from edge_core.acquisition_review_import import validate_acquisition_import, import_acquisition_review
from edge_core.financial_evidence_ledger import FinancialEvidenceLedger

Q = [{"symbol":"ABC","isin":"INE000A01001","period_end":"2026-09-30",
      "period_type":"Q","basis":"CONSOLIDATED"}]
O = {**Q[0],"acquisition_status":"HTTP_403","certified":False}
P = {"review":[O],"certified":False,"ready_for_trading_signals":False}


class ImportTests(unittest.TestCase):
    def test_valid_and_unverified(self):
        self.assertEqual(validate_acquisition_import(P, Q)[0]["acquisition_status"], "HTTP_403")

    def test_unmatched_rejected_entire_batch(self):
        with self.assertRaises(ValueError):
            validate_acquisition_import({**P,"review":[O,{**O,"isin":"BAD"}]}, Q)

    def test_duplicate_rejected(self):
        with self.assertRaises(ValueError):
            validate_acquisition_import({**P,"review":[O,O]}, Q)

    def test_certification_claim_rejected(self):
        for value in ({**P,"certified":True},
                      {**P,"review":[{**O,"certified":True}]},
                      {**P,"ready_for_trading_signals":True}):
            with self.assertRaises(ValueError):
                validate_acquisition_import(value, Q)

    def test_idempotent_import(self):
        db = sqlite3.connect(":memory:")
        db.row_factory = sqlite3.Row
        def query(sql, params=()):
            cursor = db.execute(sql, params)
            result = [dict(x) for x in cursor] if cursor.description else []
            db.commit()
            return result
        ledger = FinancialEvidenceLedger("owner-a", query)
        ledger.initialize()
        first = import_acquisition_review(ledger, Q, P)
        self.assertEqual(first, import_acquisition_review(ledger, Q, P))
        self.assertEqual(len(ledger.events()), 1)
        db.close()


if __name__ == "__main__":
    unittest.main()
