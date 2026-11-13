# HarborHR: Payroll Engine Brief

**From:** Product (PM) and Engineering (Tech Lead)
**To:** Backend Engineer (you)
**Date:** 2026-11-03
**Status:** Ready for design. No code until Deliverable 1 is approved.

---

## 1. Company context

HarborHR sells HR software to Nigerian small and medium businesses (10–500 employees). Today, most customers run payroll in spreadsheets. Every month someone copies salaries, works out tax by hand, and makes mistakes. Those mistakes are expensive: employees get paid wrongly, tax is remitted wrongly, and nobody can explain afterwards how a number was reached.

We're building **Payroll**: a backend that calculates each employee's pay for a month, takes the run through an approval process, and produces payslips that can be trusted and reproduced years later.

### Who you'll work with

| Role | What they care about |
|---|---|
| **PM (me)** | Scope, business rules, deadlines. Answers questions about *what* the system should do. |
| **Finance lead** | Calculation rules. Every number has to match their worked examples **to the kobo**. |
| **Frontend lead** | Builds the web dashboard against **your API contract**. Needs it stable, predictable and documented before building. |
| **Tech lead (me)** | Reviews your design and PRs. Owns quality and standards. |

---

## 2. Payroll in plain language (read this first)

You don't need to know payroll already. These are the only concepts you need:

- **Gross pay:** everything the employee earns this month before anything is taken out (basic salary + allowances + any bonus).
- **Pensionable pay:** the part of gross that pension is calculated on. For us, it's basic + housing + transport only.
- **Pension:** retirement savings. The employee contributes 8% of pensionable pay, which is **deducted** from their pay. The employer contributes another 10%, which is **not** deducted from the employee. It's an extra cost to the company, but we still report it.
- **PAYE (Pay As You Earn):** income tax, deducted every month. It's calculated on a yearly basis and then split into monthly amounts.
- **Relief:** an amount of income that isn't taxed. It lowers the income that tax is calculated on.
- **Net pay:** what actually reaches the employee's bank account: gross − employee pension − PAYE − other deductions.
- **Proration:** paying only for the days worked. Someone who joins on the 11th of a 30-day month gets 20/30 of the monthly amount.
- **Payroll run:** one month's payroll for the whole company. It's prepared, checked, approved and then paid.
- **Payslip:** one employee's breakdown for one run.
- **Adjustment:** a correction for a mistake in a past run. **Approved runs are never edited.** Instead, the correction is added as extra lines in the next run, the way accountants correct ledgers.

**Why immutability matters:** once a run is approved, money has moved and tax has been reported to the government. If a past payslip could change, the company couldn't prove what it paid. So a past result has to stay exactly the same forever, even if the tax rules change later.

---

## 3. Users and roles

| Role | Can do |
|---|---|
| **Admin** | Everything a Payroll Officer can do, and also: approve runs, mark runs as paid, manage users. |
| **Payroll Officer** | Manage employees and compensation, create and recalculate runs, submit runs for review, create adjustments. |
| **Employee** | View **only their own** payslips, and **only for approved or paid runs**. |

Each customer company is an **organization**. **Data must never cross organizations.** A user from org A must never see, change or even confirm that org B's data exists.

---

## 4. Scope (MVP)

**In scope:**
1. Organization and user management (roles above). Use your auth template for authentication; it's not part of this project.
2. Employees: create, update, deactivate (with hire date and exit date).
3. Compensation per employee, with **effective dates**, so salary history is kept.
4. Statutory rule tables (tax bands, relief, pension rates), **versioned by effective date**.
5. Payroll runs: create, calculate, recalculate, review, approve, mark paid, cancel.
6. Payslips (JSON, not PDF).
7. Adjustments for corrections.
8. Reports: run summary, and a statutory remittance summary (PAYE and pension totals).
9. Audit log.

**Out of scope (don't build):**
- Real bank transfers or payment integrations. "Mark as paid" just records a reference string.
- Matching real Nigerian tax law. **Use only the rules in this brief.** Finance has simplified them on purpose.
- PDF payslips, email notifications, leave/attendance, overtime, loans, multi-currency.

---

## 5. Business rules

These are **fixed**. If a rule looks wrong or unclear, **ask**. Don't reinterpret it. Each rule has an ID; your tests should reference those IDs.

### Money and rounding
- **R-01:** All money is in Naira (NGN), stored and calculated with **kobo precision** (1 Naira = 100 kobo). Never use binary floating point for money.
- **R-02:** Rounding is **half-to-even ("banker's rounding") to the nearest kobo**. Example: 0.5 kobo → 0, 1.5 kobo → 2, 2.5 kobo → 2.
- **R-03:** Each **line** is rounded once, at the point described in each rule. Totals are the **sum of rounded lines**. Never round a total separately.

### Pay components
- **R-10:** Recurring monthly components: `basic`, `housing`, `transport` (all **pensionable** and **taxable**), and `other_allowance` (**taxable, not pensionable**).
- **R-11:** One-off components for a specific run: `bonus` (taxable, not pensionable) and `reimbursement` (**not taxable, not pensionable**; added to net pay).
- **R-12:** Recurring deductions: `other_deduction` (a fixed monthly amount, such as a staff cooperative contribution). It comes out of net pay and doesn't affect tax.

### Proration (joiners, leavers, salary changes)
- **R-20:** An employee is paid for the days in the period that fall between their **hire date** and their **exit date**, both **inclusive**.
- **R-21:** For each recurring component: prorated amount = monthly amount × (days paid ÷ calendar days in month), rounded per R-02.
- **R-22:** If compensation changes mid-month, the month is split into **segments** at the effective date. Each segment is prorated separately with its own amounts (R-21), and the rounded segment lines are added together.
- **R-23:** Period boundaries use the **Africa/Lagos** timezone.
- **R-24:** An employee hired after the period ends, or who left before it started, is **not included** in the run.

### Pension
- **R-30:** Employee pension = 8% of the period's **pensionable pay** (the sum of the rounded, prorated basic + housing + transport lines), rounded per R-02.
- **R-31:** Employer pension = 10% of the same pensionable pay, rounded per R-02. It is **not deducted** from the employee, but it must appear on the payslip and in reports.

### PAYE (income tax)
Tax is calculated on an **annualized full-month** basis, then converted to the month.

- **R-40:** Annual gross (AG) = (full-month basic + housing + transport + other_allowance) × 12. This uses the **unprorated** monthly amounts.
- **R-41:** Annual relief = ₦200,000 + 20% of AG.
- **R-42:** Annual taxable income = AG − (full-month employee pension × 12) − annual relief. If the result is negative, use 0.
- **R-43:** Annual tax uses these bands, applied **progressively** (each band only taxes the income inside it):

  | Band | Annual taxable income | Rate |
  |---|---|---|
  | 1 | first ₦300,000 | 7% |
  | 2 | next ₦300,000 | 11% |
  | 3 | next ₦500,000 | 15% |
  | 4 | next ₦500,000 | 19% |
  | 5 | next ₦1,600,000 | 21% |
  | 6 | above ₦3,200,000 | 24% |

- **R-44:** Monthly PAYE = annual tax × (days paid ÷ (12 × calendar days in month)). **Round only once, at the end** (per R-02). Don't round the intermediate values.
- **R-45:** If the month has salary segments (R-22), calculate R-40 to R-44 **for each segment**, using that segment's full-month amounts and day count. PAYE is the **sum of the rounded segment amounts**.
- **R-46:** **Bonus tax:** recalculate annual tax with the bonus added to AG (so it also increases relief under R-41). Bonus tax = annual tax with the bonus − annual tax without it. **The whole difference is charged in this month**, not split across the year. It's rounded per R-02 and added to that month's PAYE.

### Net pay
- **R-50:** Net pay = gross − employee pension − PAYE − other_deduction + reimbursement.
- **R-51:** If any employee's net pay would be **negative**, the run **can't be submitted for review**. It must report the employee and the reason.

### Payroll run lifecycle
- **R-60:** States: `draft` → `in_review` → `approved` → `paid`. A `draft` run can also go to `cancelled`.
- **R-61:** **One run per organization per period** (calendar month, `YYYY-MM`), not counting cancelled runs.
- **R-62:** A new run can only be created if **every earlier run** for the organization is `approved`, `paid` or `cancelled`. Only one run can be open (`draft` or `in_review`) at a time.
- **R-63:** A `draft` run can be recalculated at any time. Recalculation picks up the latest employee data, compensation and adjustments.
- **R-64:** Submitting for review (`draft` → `in_review`) is done by a Payroll Officer or Admin. It **freezes** the results. A reviewer can send it back to `draft` with a **required reason**.
- **R-65:** Approving (`in_review` → `approved`) is **Admin only**, and **the user who submitted the run for review cannot approve it.**
- **R-66:** An `approved` or `paid` run, and its payslips, **can never be changed or deleted, by anyone, through any endpoint.**
- **R-67:** Marking as paid (`approved` → `paid`) is Admin only, and needs a payment reference.
- **R-68:** If two users try to act on the same run at the same moment, exactly one of them succeeds. The other gets a clear conflict error. **No duplicate or skipped transitions.**

### Rule versioning and reproducibility
- **R-70:** Statutory tables (tax bands, relief formula values, pension rates) are **versioned**, each with an `effective_from` date.
- **R-71:** A run uses the version that's in effect on the **first day of its period**.
- **R-72:** Adding a new version **never** changes approved or paid runs. A draft run only switches to the new version when it's recalculated.
- **R-73:** Every payslip must contain enough stored information (inputs, rule version, intermediate values) to **reproduce exactly the same result years later**, even after employees, compensation or rules have changed.

### Adjustments
- **R-80:** An adjustment belongs to an employee, references the **approved or paid run** it corrects, has a signed amount (positive or negative), a component type (e.g. `basic`, `bonus`, `reimbursement`), and a required reason.
- **R-81:** Unapplied adjustments are **automatically included in the next draft run** for that organization when it's calculated, and they're marked as applied only when that run is **approved**.
- **R-82:** An adjustment's tax and pension treatment follows its component type (R-10, R-11).

### Visibility and audit
- **R-90:** Employees can only see their own payslips, and only from runs that are `approved` or `paid`.
- **R-91:** These are written to an audit log with who, when, what, and the before and after values: every run state change, every compensation change, every adjustment, and every employee create or update. **The audit log can't be edited through the API.**

---

## 6. Worked examples (acceptance tests from Finance)

All examples use rule version **2026-01** (the table in R-43). Your test suite must reproduce each example **to the kobo**.

### Example 1: full month
Period **2026-05**. Employee in place all month.
Monthly: basic ₦300,000.00 · housing ₦150,000.00 · transport ₦50,000.00 · other_allowance ₦100,000.00

| Item | Working | Amount |
|---|---|---|
| Gross | 300,000 + 150,000 + 50,000 + 100,000 | ₦600,000.00 |
| Pensionable pay | 300,000 + 150,000 + 50,000 | ₦500,000.00 |
| Employee pension | 8% × 500,000 | ₦40,000.00 |
| Employer pension | 10% × 500,000 | ₦50,000.00 |
| Annual gross (AG) | 600,000 × 12 | ₦7,200,000.00 |
| Relief | 200,000 + 20% × 7,200,000 | ₦1,640,000.00 |
| Annual taxable | 7,200,000 − (40,000 × 12) − 1,640,000 | ₦5,080,000.00 |
| Annual tax | 21,000 + 33,000 + 75,000 + 95,000 + 336,000 + (1,880,000 × 24% = 451,200) | ₦1,011,200.00 |
| Monthly PAYE | 1,011,200 ÷ 12 = 84,266.666… → | **₦84,266.67** |
| **Net pay** | 600,000 − 40,000 − 84,266.67 | **₦475,733.33** |

### Example 2: mid-month joiner
Same pay as Example 1. Hire date **2026-06-11**. June has 30 days, so the employee is paid for days 11–30 = **20 days**.

| Item | Working | Amount |
|---|---|---|
| Basic | 300,000 × 20/30 | ₦200,000.00 |
| Housing | 150,000 × 20/30 | ₦100,000.00 |
| Transport | 50,000 × 20/30 = 33,333.333… → | ₦33,333.33 |
| Other allowance | 100,000 × 20/30 = 66,666.666… → | ₦66,666.67 |
| Gross | sum of rounded lines | ₦400,000.00 |
| Pensionable pay | 200,000 + 100,000 + 33,333.33 | ₦333,333.33 |
| Employee pension | 8% × 333,333.33 = 26,666.6664 → | ₦26,666.67 |
| Employer pension | 10% × 333,333.33 = 33,333.333 → | ₦33,333.33 |
| Monthly PAYE | 1,011,200 × 20 ÷ (12 × 30) = 56,177.777… → | **₦56,177.78** |
| **Net pay** | 400,000 − 26,666.67 − 56,177.78 | **₦317,155.55** |

Note: PAYE uses the full-month annual tax from Example 1 (R-40 to R-43 use unprorated amounts) and is prorated once, at the end (R-44).

### Example 3: one-off bonus
Same employee as Example 1, period **2026-08**, with a one-off **bonus of ₦500,000.00**.

| Item | Working | Amount |
|---|---|---|
| Gross | 600,000 + 500,000 | ₦1,100,000.00 |
| Employee pension | unchanged (bonus isn't pensionable) | ₦40,000.00 |
| AG with bonus | 7,200,000 + 500,000 | ₦7,700,000.00 |
| Relief with bonus | 200,000 + 20% × 7,700,000 | ₦1,740,000.00 |
| Annual taxable with bonus | 7,700,000 − 480,000 − 1,740,000 | ₦5,480,000.00 |
| Bonus tax | the extra 400,000 of taxable income is all in band 6: 400,000 × 24% | ₦96,000.00 |
| Monthly PAYE | 84,266.67 + 96,000.00 | **₦180,266.67** |
| **Net pay** | 1,100,000 − 40,000 − 180,266.67 | **₦879,733.33** |

### Example 4: mid-month salary change (partly for you to complete)
Same employee as Example 1. Basic rises from ₦300,000 to **₦360,000**, effective **2026-07-16**. July has 31 days, so the segments are days 1–15 (15 days) and days 16–31 (16 days).

Finance has confirmed the basic line:

| Item | Working | Amount |
|---|---|---|
| Basic, segment 1 | 300,000 × 15/31 = 145,161.290… → | ₦145,161.29 |
| Basic, segment 2 | 360,000 × 16/31 = 185,806.451… → | ₦185,806.45 |
| **Basic total** | | **₦330,967.74** |

**Your task:** work out the rest of this payslip by hand (pensionable pay, both pensions, segment PAYE under R-45, net), and **send it to Finance (me) for sign-off before you encode it as a test.** That's how it works in real companies: you confirm your reading of the rules with the person who owns them.

### Example 5: negative net blocks review
Employee with basic ₦100,000 only, and `other_deduction` ₦150,000.
Expected: the run calculates, **submitting it for review fails**, and the error identifies the employee and states that net pay is negative (R-51).

### Example 6: rounding unit cases (R-02)
| Raw value (kobo) | Rounded |
|---|---|
| 10.5 | 10 |
| 11.5 | 12 |
| 10.4999 | 10 |
| 10.5001 | 11 |

---

## 7. What the frontend team needs (from the Frontend lead)

> "We'll build the payroll screens against your contract while you build the backend, so the contract has to be right first. Specifically:"

1. **Contract first:** an OpenAPI spec we can generate types and mocks from, **before** you implement. After we start building, any change is **additive only** unless we agree otherwise.
2. **No money as floats in JSON.** Choose a representation and use it everywhere, consistently.
3. **One error format everywhere,** with a stable machine-readable `code`. We show different UI per code, so never make us parse messages.
4. **Validation errors for a whole run in one response.** If 12 employees have problems, give us all 12 with a code each, not just the first.
5. **Allowed actions on a run** for the current user. We don't want to duplicate your permission and state rules in the UI. Tell us what this user can do with this run right now.
6. **Calculating a 500-employee run must not hold an HTTP request open for long.** Tell us how we find out it's finished: polling, an event, or something else. Your call, but document it.
7. **Double-clicks happen.** Approve, mark paid, and other actions must be safe to retry.
8. **Cursor pagination** on every list, in one consistent shape.
9. **Run summary:** headcount, total gross, total employee pension, total employer pension, total PAYE, total deductions, total net.
10. **Payslip line items** with labels and categories (earning, deduction, employer contribution), so we can display them without hardcoding any calculation logic.
11. **Dates in ISO 8601.** Tell us the timezone for anything that isn't a date-only value.

---

## 8. Non-functional requirements

| Area | Requirement |
|---|---|
| Correctness | Every rule (R-xx) is covered by at least one test that references its ID. All Finance examples pass to the kobo. |
| Performance | Calculating a 500-employee run takes < 10s on your laptop (record the hardware). Read endpoints p95 < 300ms under a k6 test of 50 virtual users. |
| Isolation | Automated tests prove a user can't read or change another organization's data on **any** endpoint. |
| Concurrency | A test fires concurrent approve / submit / recalculate requests at the same run and proves R-68 holds. |
| Immutability | A test tries to change an approved run through every write endpoint and proves it fails. |
| Reproducibility | A test changes compensation and adds a new rule version after approval, then proves the stored payslip still reproduces exactly. |
| Observability | Structured logs with request ID, a health endpoint, and calculation duration recorded per run. |
| Engineering | Docker Compose setup, CI with tests, type checking and linting, Alembic migrations, a README covering setup, design decisions and limits. |
| Data retention | Payslips and runs are never hard-deleted. Employees are deactivated, never deleted. |

---

## 9. Design decisions that are yours

We've specified **what**. You decide **how**, and justify it in the design doc:

- The schema and how effective-dated compensation is modelled.
- How rule versions are stored and selected.
- What a payslip stores so it can be reproduced (R-73).
- How you represent money in the database, in code, and in JSON.
- Where the calculation logic lives, and how you keep it testable on its own, without the database.
- How run state transitions stay correct under concurrent requests (R-68).
- How you enforce immutability: in the application, in the database, or both.
- How organization isolation is enforced.
- Whether calculation is synchronous or asynchronous, and how the frontend learns it has finished.
- How idempotency works for state-changing actions.
- The authorization model and where checks happen.

**Note:** this brief has **gaps on purpose**, as real briefs do. Finding them and asking good questions is part of the job, and part of how you'll be assessed.

---

## 10. Deliverable 1: design doc + API contract (due before any code)

Submit both for review. **Don't start implementing until they're approved.**

### A. Design doc (max ~4 pages, Markdown)
1. **Overview:** the system in one paragraph.
2. **Data model:** entities, relationships and key constraints (a diagram is welcome), and how you handle effective dates and rule versions.
3. **Run state machine:** a diagram plus the rules for each transition (who, when, and what's checked).
4. **Calculation engine:** inputs, outputs, how the rule IDs map to code, and your money and rounding approach.
5. **Consistency and concurrency:** how R-61, R-62, R-66 and R-68 are guaranteed.
6. **Reproducibility:** what's stored, and how a payslip can be recalculated later.
7. **Authorization matrix:** role × action.
8. **Async calculation:** your approach, and what the frontend sees.
9. **Trade-offs:** at least 3 decisions, each with the alternative you didn't choose and why.
10. **Risks and limits:** what breaks first at 10× scale (5,000 employees, 1,000 organizations).
11. **Questions for the PM:** every ambiguity you found in this brief.

### B. OpenAPI contract (YAML)
Every MVP endpoint, with request and response schemas, error responses with codes, pagination shape, and examples for the run summary and payslip using **Example 1's numbers**.

### C. Example 4 completed by hand
For Finance sign-off.

---

## 11. What happens after Deliverable 1 (for your planning)

After approval, the work will be split into tickets, roughly:
1. Org, users, employees, effective-dated compensation
2. Rule versioning + the calculation engine as pure logic, with all Finance examples as tests
3. The run lifecycle (state machine, concurrency, immutability)
4. Payslips, adjustments, employee visibility
5. Reports, audit log, hardening, the load test

Each ticket goes through a PR review. **Expect requirement changes while you're building.** That's normal, and handling them without breaking the frontend contract is part of the job.

---

## 12. PM decisions log

Decisions made after the brief was issued. Where one conflicts with an earlier section, this log wins.

- **D-01 (amends R-65):** The approver cannot be anyone who started, recalculated or submitted that run. Any Payroll Officer or Admin may still submit (R-64).
- **D-02 (R-12):** `other_deduction` is a fixed monthly amount and is not prorated. It is recurring and effective-dated.
- **D-03 (R-11):** Bonus and reimbursement are entered per employee against a specific draft run, by a Payroll Officer or Admin, and freeze at submission. The frontend needs to enter many in one request.
- **D-04 (run inclusion):** Role is a system permission, not employment status. Whether someone is paid is decided by employment dates and compensation (R-20, R-24), whatever their role.
- **D-05 (rehire):** A returning employee stays the same person with a new employment period. Past payslips never change, and gaps are unpaid. Two employment periods can fall in one month.
- **D-06 (statutory rules):** Statutory rules are platform-wide. Organizations can read them but not change them.
- **D-07 (scale assumption):** For the risks section, assume 1,000 organizations in total, the largest with 5,000 employees, and 80% of runs happening in the last 3 working days of the month.
- **D-08 (departed organizations):** Payroll records are retained when an organization leaves; the organization is deactivated. Handling of personal data after departure is out of scope for the MVP. Document it as a known limit.
- **D-09 (employee records):** Employee management stays in scope, but only for what payroll needs. Officers and Admins own employment and pay data. An employee can be paid without having a login. Login is only needed to view their own payslips.
- **D-10 (organization size):** No size limit is enforced. 10–500 in the brief describes our market, not a product rule.
- **D-11 (amends D-01):** The approver cannot be anyone who started, recalculated or submitted that run, entered its one-off values, or created an adjustment included in it.
- **D-12 (approver's own pay):** An eligible approver may approve a run containing their own pay. The audit log must flag that this happened.
- **D-13 (statutory rule changes):** Only HarborHR staff can add statutory rule versions. No customer role can. The mechanism is an engineering decision.
- **D-14 (no eligible approver):** Starting and submitting a run are not blocked by how many approvers exist. If nobody eligible can approve under D-11, the approve attempt fails with a specific error code, and the organization resolves it by adding another Admin. Sending a run back does not clear anyone's prior involvement.
- **D-15 (HarborHR staff):** Staff manage statutory rule versions only. They have no role in the run lifecycle and no access to customer payroll or employee data in the MVP.
- **D-16 (bonus in a split month):** For R-45 and R-46, the bonus is attributed to the latest salary segment of the month.
- **D-17 (other_deduction in a split month):** The pay version of the latest segment supplies `other_deduction`, and it is applied once for the month.
- **D-18 (cancelled runs):** Cancelled is a terminal state. Re-running a period creates a new run; a cancelled run is never reopened.
- **D-19 (mark paid):** Any Admin may mark a run paid (R-67). The non-involvement rule in D-11 applies to approval only.
- **Example 4:** signed off by Finance on 2026-11-12. Net pay ₦498,872.43, PAYE ₦89,617.89, employee pension ₦42,477.42, employer pension ₦53,096.77.
- **D-20 (adjustment treatment):** Adjustments are one-off amounts in the run that applies them. They are never prorated and never annualized ×12. A taxable adjustment is taxed with the same difference method as a bonus (R-46). A pensionable adjustment adds to that month's pensionable pay.
- **D-21 (negative adjustments):** A negative taxable adjustment goes through the bonus difference method and produces a negative difference that reduces that month's PAYE. A negative pensionable adjustment reduces that month's pensionable pay. Monthly PAYE and pensionable pay are each floored at ₦0.
- **D-22 (employee scope):** A person is an employee of at most one organization. `employee.email` stays globally unique.
