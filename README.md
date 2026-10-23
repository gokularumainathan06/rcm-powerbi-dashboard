# Healthcare Revenue Cycle (RCM) Analytics Dashboard | Power BI

An interactive Power BI report that shows where a multi-specialty provider group is losing revenue (claim denials, slow payers, aging AR) and what to fix first.

> **Data note:** the dataset is **synthetic** (generated with Python, script included). It mirrors real RCM structure (claims, payers, CPT codes, denial reasons, appeals, AR follow-up) but contains no real patient or payer data. Snapshot date: **30-Sep-2026**.

---

## Dashboard preview

| Executive Summary | Denial Analysis |

| AR Aging | Insights & Recommendations |

A hidden **Claim Detail** page supports drill-through from the payer, denial category and aging charts down to individual claims.

---

## Business questions

1. Where are we losing money: which payers and which denial reasons?
2. How much of the denied revenue was preventable?
3. How much AR is aging past 90 days and who holds it?
4. Are appeals recovering money, and are we using them enough?
5. Which follow-up actions actually resolve claims?

---

## Key findings

| # | Finding | Evidence |
|---|---|---|
| 1 | **Most denials are preventable** | 76.1% of denied claims (78.2% of denied dollars, **$1.39M** of $1.78M) are preventable. Billing, Coding and Authorization errors are ~84% of preventable dollars. |
| 2 | **Three payers drive denials** | UnitedHealthcare 13.4%, Humana 12.6%, Cigna 12.5% vs Medicare 7.1% (overall 10.15%). UnitedHealthcare alone: $488K denied, $373K preventable. |
| 3 | **Aged AR sits with two payers** | Open AR $1.53M, 34.7% ($531K) older than 90 days, $367K older than 120 days. UnitedHealthcare + Cigna hold 58.5% of 90+ day AR. |
| 4 | **Appeals work but are under-used** | 830 appeals, 65.7% success, $644K recovered. 295 denied claims ($447K) were written off without an appeal. |

## Recommendations (with estimated impact)

| Recommendation | Estimated impact* |
|---|---|
| Pre-submission claim scrubber for billing/coding errors, prior-auth check at scheduling | Preventing 30% of preventable denials avoids ~$417K |
| Payer-specific submission rules, monthly denial-code review with UnitedHealthcare | Bringing UnitedHealthcare to the overall denial rate = ~65 fewer denials, ~$118K |
| Work the 90+ day queue first (UnitedHealthcare, Cigna), escalate at 60 days | Collecting 25% of 90+ day AR recovers ~$133K |
| Appeal review before any write-off | Appealing half of unappealed write-offs at the observed 65.7% success rate recovers ~$147K |

\*Illustrative, based on allowed amounts. The estimates overlap and should not be added together.

---

## Data model

Star schema, 2 fact tables and 5 dimensions plus a DAX date table.

| Table | Type | Rows | Notes |
|---|---|---|---|
| `fact_claims` | Fact | 12,000 | One row per claim: dates, charge/allowed/paid amounts, status, denial code, appeal flag |
| `fact_ar_followup` | Fact | ~3,200 | One row per AR follow-up action (agent, action type, outcome, minutes) |
| `dim_payer` | Dim | 8 | Payer name, payer type |
| `dim_provider` | Dim | 8 | Provider, specialty, department |
| `dim_denial_reason` | Dim | 9 | Denial code, category, preventable flag |
| `dim_cpt` | Dim | 12 | CPT code, category |
| `dim_agent` | Dim | 6 | AR agent |
| `Dim_Date` | Date (DAX) | 638 | Jan 2025 to Sep 2026 |

`fact_claims` connects to `Dim_Date` on three dates. **Submission date** is the active relationship; **date of service** and **payment date** are inactive and used with `USERELATIONSHIP` (see `Cash Collected (by Payment Date)`).

Calculated columns (Power Query): `Days_To_Pay`, `Days_Outstanding` (vs 30-Sep-2026), `Aging_Bucket`, `Aging_Sort`.

## KPI definitions

| KPI | Meaning | Value |
|---|---|---|
| Total Charges | Gross billed charges | $30.70M |
| Net Collection Rate | Payments / expected payer payment on closed claims | 93.0% |
| Denial Rate | Claims denied on first pass / total claims | 10.15% |
| First Pass Resolution Rate | 1 minus Denial Rate | 89.85% |
| Open AR | Allowed amount of Pending, Denied and In-Appeal claims | $1.53M |
| Days in AR | Open AR / average daily allowed amount | 56 |
| AR > 90 Days % | Share of Open AR older than 90 days | 34.7% |
| Write-off % | Written-off amount / total allowed | 4.0% |
| Appeal Success Rate | Paid-after-appeal claims / appealed claims | 65.7% |

All measures are listed in [`dax_measures.md`](dax_measures.md).

## Report pages

1. **Executive Summary** – headline KPIs, monthly payments and net collection rate, payments by payer, claim status mix
2. **Denial Analysis** – denial rate by payer, denied dollars by code and category, specialty vs category heatmap, preventable %, appeal recovery
3. **AR Aging** – aging buckets, open AR by payer and bucket, top 20 open claims, cash collected by payment date, agent scorecard, follow-up outcomes
4. **Insights & Recommendations** – findings and estimated impact
5. **Claim Detail** (hidden, drill-through) – claim-level table for any payer, denial category or aging bucket

Navigation buttons, a reset-filters button and synced slicers (Payer Type, Year, Department) are on every page.

---

## Tools

Power BI Desktop · Power Query · DAX · Data modelling (star schema) · Python (Pandas, NumPy) for the synthetic data · GitHub

## How to open

1. Download `powerbi/RCM_Dashboard.pbix` and open it in Power BI Desktop.
2. If Power BI asks for the data location: **Transform data → Data source settings → Change source** and point to the `data/` folder.
3. To regenerate the data: `pip install -r scripts/requirements.txt` then `python scripts/generate_rcm_data.py data`. The output is identical to the CSVs in `data/`.

## Notes and limitations

- Synthetic data. Agent-level metrics are illustrative and not meaningful performance comparisons.
- AR aging is calculated as of the snapshot date, 30-Sep-2026, so bucket values do not change with the Year slicer.
- Latest months (2026-08, 2026-09) are excluded from the monthly trend chart because many claims are still pending.
- Impact estimates are directional and overlap.

## Author

**Gokul Selvam K A** · Coimbatore · [www.linkedin.com/in/gokul-selvam07] · [GitHub](#)
