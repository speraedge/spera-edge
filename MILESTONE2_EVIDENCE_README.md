# Milestone 2 evidence audit (development branch)

The research application remains **uncertified**. This batch adds review ledgers,
not verified price-adjustment factors, certified financial growth, or SEPA PASS.

## Offline evidence review

Supply an official membership CSV with columns `Symbol` and `ISIN Code`,
plus one or both independently obtained evidence files:

```bash
python -m tools.audit_milestone2_evidence \
  --membership path/to/official_nifty500.csv \
  --corporate-actions path/to/corporate_actions.csv \
  --financials path/to/financial_statements.csv \
  --output data/evidence_review
```

Corporate action columns: `symbol,isin,purpose,ex_date,source_url`.
Financial statement columns: `symbol,isin,period_end,period_type,basis,revenue,pat,source_url,published_on`.

Financial `period_type` must be `FY` or `Q`; `basis` must be
`CONSOLIDATED` or `STANDALONE`. Dates are ISO 8601 (YYYY-MM-DD).

The audit writes a source fingerprint, exception reports, and a manifest.
A URL field alone does **not** authenticate an exchange filing. No
adjustment factors or financial growth metrics are approved automatically.
A complete point-in-time historical archive and independent corporate-action
reconciliation remain outstanding.

This command is deliberately separate from the live snapshot workflow so
unverified evidence cannot silently modify the frozen Momentum V1 research.
