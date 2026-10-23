# DAX Measures

All measures live in the `_measures` table. Date table: `Dim_Date`.
Column names use underscores (`Days_Outstanding`, `Days_To_Pay`).

## Date table

```DAX
Dim_Date =
ADDCOLUMNS (
    CALENDAR ( DATE ( 2025, 1, 1 ), DATE ( 2026, 9, 30 ) ),
    "Year", YEAR ( [Date] ),
    "Quarter", "Q" & QUARTER ( [Date] ),
    "Month No", MONTH ( [Date] ),
    "Month", FORMAT ( [Date], "MMM" ),
    "Year-Month", FORMAT ( [Date], "YYYY-MM" )
)
```

## Volume and revenue

```DAX
Total Claims = COUNTROWS ( fact_claims )
Total Charges = SUM ( fact_claims[charge_amount] )
Total Allowed = SUM ( fact_claims[allowed_amount] )
Total Payments = SUM ( fact_claims[paid_amount] )
```

## Denials

```DAX
Denied Claims = CALCULATE ( [Total Claims], fact_claims[first_pass_flag] = 0 )

Denial Rate = DIVIDE ( [Denied Claims], [Total Claims] )

First Pass Resolution Rate = 1 - [Denial Rate]

Denied Amount = CALCULATE ( [Total Allowed], fact_claims[first_pass_flag] = 0 )

Preventable Denial % =
DIVIDE (
    CALCULATE ( [Denied Claims], dim_denial_reason[preventable] = 1 ),
    [Denied Claims]
)

Preventable Denied Amount =
CALCULATE ( [Denied Amount], dim_denial_reason[preventable] = 1 )
```

## Appeals

```DAX
Appealed Claims = CALCULATE ( [Total Claims], fact_claims[appealed] = TRUE () )

Appeal Success Rate =
DIVIDE (
    CALCULATE ( [Total Claims], fact_claims[claim_status] = "Paid After Appeal" ),
    [Appealed Claims]
)

Appeal Recovery $ =
CALCULATE ( [Total Payments], fact_claims[claim_status] = "Paid After Appeal" )
```

## Collections

```DAX
Expected Payer Payment =
CALCULATE (
    SUMX ( fact_claims, fact_claims[allowed_amount] - fact_claims[patient_responsibility] ),
    fact_claims[claim_status] <> "Pending"
)

Net Collection Rate = DIVIDE ( [Total Payments], [Expected Payer Payment] )

Write-off Amount = SUM ( fact_claims[writeoff_amount] )

Write-off % = DIVIDE ( [Write-off Amount], [Total Allowed] )
```

## AR and speed

```DAX
Open AR =
CALCULATE (
    [Total Allowed],
    fact_claims[claim_status] IN { "Pending", "Denied", "Denied - In Appeal" }
)

AR > 90 Days % =
DIVIDE ( CALCULATE ( [Open AR], fact_claims[Days_Outstanding] > 90 ), [Open AR] )

Days in AR =
VAR DaysInPeriod =
    DATEDIFF ( MIN ( Dim_Date[Date] ), MAX ( Dim_Date[Date] ), DAY ) + 1
RETURN
    DIVIDE ( [Open AR], DIVIDE ( [Total Allowed], DaysInPeriod ) )

Avg Days to Pay = AVERAGE ( fact_claims[Days_To_Pay] )
```

## Time intelligence

```DAX
Payments PM = CALCULATE ( [Total Payments], DATEADD ( Dim_Date[Date], -1, MONTH ) )

Payments MoM % = DIVIDE ( [Total Payments] - [Payments PM], [Payments PM] )

Payments YTD = TOTALYTD ( [Total Payments], Dim_Date[Date] )

Cash Collected (by Payment Date) =
CALCULATE (
    [Total Payments],
    USERELATIONSHIP ( fact_claims[payment_date], Dim_Date[Date] )
)
```

## AR team productivity

```DAX
Follow-up Actions = COUNTROWS ( fact_ar_followup )

Avg Minutes per Action = AVERAGE ( fact_ar_followup[minutes_spent] )

Resolution Rate =
DIVIDE (
    CALCULATE ( [Follow-up Actions], fact_ar_followup[outcome] = "Claim Paid" ),
    [Follow-up Actions]
)
```

## Power Query columns (M)

```
Days_To_Pay      = Duration.Days([payment_date] - [submission_date])
Days_Outstanding = Duration.Days(#date(2026, 9, 30) - [submission_date])
Aging_Bucket     = if [Days_Outstanding] <= 30 then "0-30"
                   else if [Days_Outstanding] <= 60 then "31-60"
                   else if [Days_Outstanding] <= 90 then "61-90"
                   else if [Days_Outstanding] <= 120 then "91-120"
                   else "120+"
```

`Aging_Bucket` is sorted by `Aging_Sort` (1 to 5).
