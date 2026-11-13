## Description

HarborHR is a payroll engine for Nigerian SME businesses to record, manage and pay employees efficiently. It should provide visibility and be reproduceable.

## Data Models

### Role

| Columns | Type | Constraints |
|---|---|---|
| id | UUID(7) | pk |
| name | string | not-null, unique |
| updated_at | timestamp | nullable |
| created_at | timestamp | not-null |

### Organization

| Columns | Type | Constraints |
|---|---|---|
| id | UUID(7) | pk |
| name | string | not-null |
| country | string | not-null |
| updated_at | timestamp | nullable |
| created_at | timestamp | not-null |

### User

| Columns | Type | Constraints |
|---|---|---|
| id | UUID(7) | pk |
| email | string | nullable, unique |
| google_email | string | nullable, unique |
| google_id | string | nullable, unique |
| hashed_password | string | nullable |
| employee_id | uuid | fk(on-delete, restrict), nullable |
| role_id | uuid | fk(on-delete, restrict) |
| organization_id | uuid | fk(on-delete, restrict), nullable |
| is_active | bool | not-null (for deactivation) |
| updated_at | timestamp | nullable |
| created_at | timestamp | not-null |

### Employee

| Columns | Type | Constraints |
|---|---|---|
| id | UUID(7) | pk |
| first_name | string | not-null |
| last_name | string | not-null |
| email | string | nullable, unique |
| organization_id | uuid | fk(on-delete, restrict) |
| updated_at | timestamp | nullable |
| created_at | timestamp | not-null |

### Invite

| Columns | Type | Constraints |
|---|---|---|
| id | UUID(7) | pk |
| employee_id | uuid | fk(on-delete, restrict) |
| organization_id | uuid | fk(on-delete, restrict), nullable |
| hashed_token | string | unique, not-null |
| role_id | uuid | fk(on-delete, restrict) |
| created_by | uuid | fk(on-delete, restrict), nullable |
| expires_at | timestamp | not-null |
| status | enum | not-null |
| used_at | timestamp | nullable |
| created_at | timestamp | not-null |

### Employment Period

| Columns | Type | Constraints |
|---|---|---|
| id | UUID(7) | pk |
| employee_id | uuid | fk(on-delete, restrict) |
| start_date | date | not-null |
| end_date | date | nullable |
| created_at | timestamp | not-null |

### Employee Pay

| Columns | Type | Constraints |
|---|---|---|
| id | UUID(7) | pk |
| employee_id | uuid | fk(on-delete, restrict) |
| basic | Decimal(precision=14, scale=2) | not-null |
| housing | Decimal(precision=14, scale=2) | not-null |
| transport | Decimal(precision=14, scale=2) | not-null |
| other_allowance | Decimal(precision=14, scale=2) | nullable |
| other_deduction | Decimal(precision=14, scale=2) | nullable |
| version | integer | not-null |
| effective_from | date | not-null |
| created_at | timestamp | not-null |

### Employee Log (Hold both compensation and emplyee changes)

| Columns | Type | Constraints |
|---|---|---|
| id | UUID(7) | pk |
| employee_id | uuid | fk(on-delete, restrict) |
| previous_values | JSONB | nullable |
| current_values | JSONB | not-null |
| created_by | uuid | fk(on-delete, restrict) |
| reason | string | not-null |
| created_at | timestamp | not-null |

### Statutory Rules

| Columns | Type | Constraints |
|---|---|---|
| id | UUID(7) | pk |
| relief | Decimal(precision=14, scale=2) | not-null |
| relief_percentage | integer | not-null |
| employee_pension_rate | Decimal(precision=3, scale=1) | not-null |
| employer_pension_rate | Decimal(precision=3, scale=1) | not-null |
| tax_bands | JSONB | not-null |
| version | integer | not-null |
| effective_from | date | not-null |
| created_at | timestamp | not-null |

### Payroll Runs

| Columns | Type | Constraints |
|---|---|---|
| id | UUID(7) | pk |
| organization_id | uuid | fk(on-delete, restrict) |
| statutory_version | uuid | fk(on-delete, restrict), not-null |
| started_at | timestamp | not-null |
| ended_at | timestamp | nullable |
| run_status | enum | not-null |
| computation_status | enum | not-null |
| payment_reference | string | nullable |
| period | date | not-null |
| last_enqueued_at | timestamp | not-null |
| created_at | timestamp | not-null |
| updated_at | timestamp | nullable |

### Run Participants

| Columns | Type | Constraints |
|---|---|---|
| id | UUID(7) | pk |
| participant_id | uuid | fk(on-delete, restrict) | <!-- references users.id -->
| payroll_run_id | uuid | fk(on-delete, restrict) |
| action | enum | not-null |
| created_at | timestamp | not-null |

Enum
STARTED - REVIEWED - ADJUSTED - RECALCULATED - SUBMITTED - APPROVED - PAID - CANCELLED

### Run One-Off Values

| Columns | Type | Constraints |
|---|---|---|
| id | UUID(7) | pk |
| run_id | uuid | fk(on-delete, restrict), not-null |
| employee_id | uuid | fk(on-delete, restrict), not-null |
| bonus | Decimal(precision=14, scale=2) | nullable |
| reimbursement | Decimal(precision=14, scale=2) | nullable |
| created_by | uuid | fk(on-delete, restrict), not-null |
| created_at | timestamp | not-null |

Unique: `(run_id, employee_id)`.

These values are accepted when the run starts, but they are stored in a dedicated table once the run exists. They may be recalculated, edited while the run is a draft, and frozen once the run is submitted. The `created_by` value identifies who introduced the one-off value and is used to determine run involvement for validation and approver rules.

### Payslip (parent row)

| Columns | Type | Constraints |
|---|---|---|
| id | UUID(7) | pk |
| payroll_run_id | uuid | fk(on-delete, restrict) |
| employee_id | uuid | fk(on-delete, restrict) |
| gross | Decimal(precision=14, scale=2) | not-null |
| pensionable_pay | Decimal(precision=14, scale=2) | not-null |
| employee_pension | Decimal(precision=14, scale=2) | not-null |
| employer_pension | Decimal(precision=14, scale=2) | not-null |
| monthly_paye | Decimal(precision=14, scale=2) | not-null |
| net_pay | Decimal(precision=14, scale=2) | not-null |
| created_at | timestamp | not-null |
| updated_at | timestamp | nullable |

Unique: `(payroll_run_id, employee_id)`.

### Payslip Segment (child row)

| Columns | Type | Constraints |
|---|---|---|
| id | UUID(7) | pk |
| payslip_id | uuid | fk(on-delete, restrict) |
| segment_num | int | not-null |
| employee_pay_version | uuid | fk(on-delete, restrict), not-null |
| days_paid | integer | not-null |
| gross | Decimal(precision=14, scale=2) | not-null |
| pensionable_pay | Decimal(precision=14, scale=2) | not-null |
| annual_gross | Decimal(precision=14, scale=2) | not-null |
| relief | Decimal(precision=14, scale=2) | not-null |
| annual_taxable_without_bonus | Decimal(precision=14, scale=2) | not-null |
| annual_taxable_with_bonus | Decimal(precision=14, scale=2) | nullable |
| annual_tax | Decimal(precision=14, scale=2) | not-null |
| bonus_tax | Decimal(precision=14, scale=2) | nullable |
| monthly_paye | Decimal(precision=14, scale=2) | not-null |
| created_at | timestamp | not-null |
| updated_at | timestamp | nullable |

The parent payslip holds period-level values; each child segment row holds the segment-specific values and the pay version used for that segment. This lets one payslip reference two versions in a split-month example like Example 4.

### Adjustment

| Columns | Type | Constraints |
|---|---|---|
| id | UUID(7) | pk |
| employee_id | uuid | fk(on-delete, restrict) |
| payroll_run_id | uuid | fk(on-delete, restrict), not-null |
| component_type | enum | not-null |
| amount | Decimal(precision=14, scale=2) | not-null |
| created_by | uuid | fk(on-delete, restrict), not-null |
| reason | string | not-null |
| status | enum | not-null |
| created_at | timestamp | not-null |

`amount` is a single signed value and `component_type` is one component only. This matches R-80 and avoids the multi-component JSONB shape that would allow a single record to mutate more than one component at once.

Enum
PENDING, APPLIED, CANCELLED

### Run Value Log

| Columns | Type | Constraints |
|---|---|---|
| id | UUID(7) | pk |
| payroll_run_id | uuid | fk(on-delete, restrict) |
| employee_id | uuid | fk(on-delete, restrict), nullable |
| previous_values | JSONB | nullable |
| current_values | JSONB | not-null |
| created_by | uuid | fk(on-delete, restrict) |
| reason | string | not-null |
| created_at | timestamp | not-null |

### Run State Log

| Columns | Type | Constraints |
|---|---|---|
| id | UUID(7) | pk |
| payroll_run_id | uuid | fk(on-delete, restrict) |
| previous_value | string | nullable |
| current_value | string | not-null |
| created_by | uuid | fk(on-delete, restrict) nullable |
| reason | string | not-null |
| created_at | timestamp | not-null |

### Request Idempotency Keys

| Columns | Type | Constraints |
|---|---|---|
| id | UUID(7) | pk |
| organization_id | uuid | fk(on-delete, restrict), not-null |
| user_id | uuid | fk(on-delete, restrict), not-null |
| key | string | not-null |
| request_hash | text | not-null |
| response | JSONB | nullable |
| status_code | integer | not-null |
| expires_at | timestamp | not-null |
| created_at | timestamp | not-null |

Unique: `(organization_id, key)`.

This table stores retry keys for every user action that may be retried by the frontend: start, submit, send back, approve, cancel, mark paid, and saving one-off values. The stored response includes the HTTP status code so a duplicate submit can be answered immediately with the original result, and keys expire after a bounded window such as 24 hours.

## Sign Up Flow and Employee Addition

An admin or officer creates the employee record directly, including pay and dates. The email is optional. An invite is sent only for the employee to confirm and get a login. This covers a cleaner without an email address, and pay can be set up before the employee does anything.

### Invite flow

When an employee is created without an account, the backend issues a one-time invite token for the employee to accept their account. The token is stored only as a SHA-256 hash; the raw value is never persisted. The invite has a table with `hashed_token`, `expires_at`, `used_at`, `employee_id`, `created_by`, and the audit record. The acceptance request is a POST to a dedicated endpoint that validates the hash, checks expiry, confirms the token has not already been used, and creates the `users` row for that employee. The first sign-up creates the organization, the employee, and the initial admin user in one transaction, then the invite token is issued for the employee to accept their account.

## PayRoll Run

**Description**

A payroll run for a period can be started by an admin or a payroll officer of an organization. It calculates the net pay for all eligible employees.

**Flow**

When an admin or payroll officer makes a request to start a run for a period, the server receives this request and immediately responds with a 202 accepted status provided the period meets all requirements to begin a run. The request is queued and processed by a background worker and events are sent via a stream endpoint using SSE. The client sees a completed or failed run state.

**Run State Machine**

```text
run state
drafted | cancelled | under_review | approved | paid

calculation state
calculating | calculated | failed
```

- drafted: can be edited and recalculated by an admin or payroll officer.
- cancelled: triggered by an admin or payroll officer on a drafted run.
- under_review: calculated values are frozen and cannot be changed subject to the review of a different admin from the starter, involved in recalculation step or the run's lifecycle. A run under_review can be sent back to drafted with a required reason.
- approved & paid: represents a completed computation of values for the run and are irrevocable
- calculating: a run currently computing values for the employees of the run.
- calculated: represents a completed computation. The run can then be reviewed by an eligible admin
- failed: represents a failed computation to be retried again. A new run cannot be started while at this state. Failed runs start over again as the half completed calculations are rolled back.

**Run Requirements**

- a run can only be started if all previous runs for other periods have been closed (whether it succeeded or not)
- a period can only have one drafted/in_review/calculated/approved/paid/failed run; cancelled runs don't count, and re-running the period creates a new run.

### Client-side idempotency

The client supplies an idempotency key for every action that may be retried by the frontend, including start, submit, send back, approve, cancel, mark paid, and save one-off values. The key is stored in the dedicated `request_idempotency_keys` table together with `organization_id`, a canonical `request_hash`, the serialized `response`, and `created_at`.

The write path is:

- `INSERT INTO request_idempotency_keys (...) VALUES (...) ON CONFLICT (organization_id, key) DO NOTHING`
- If the same organization and key are retried with the same `request_hash`, the `ON CONFLICT` no-op returns the existing response instead of generating a duplicate action.
- If the same key is reused with a different payload hash, the request is rejected with a clear conflict error such as `IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD` and no mutation is applied.

This protects the API against accidental double-submits while still failing loudly if the client tries to reuse the same key for a different request.

**Approved → Paid**

The transition from `approved` to `paid` is triggered by any Admin. The admin can be involved in the run; the involvement rule is only used for number validation and approver eligibility checks earlier in the run lifecycle. The `payment_reference` is a free-form payment identifier supplied by the admin and is not important to the payroll calculation itself; it is only a ledger note for the payment event. A single-person organization cannot run payroll through approval because there is no second eligible approver available to complete the approval path.

**Concurrency**

The backend owns the transition logic. It does not rely on the client to send an expected state. Instead, each action is applied against the current run row with a row-level lock using `SELECT ... FOR UPDATE NOWAIT`. The server infers the allowed next state from the business rule and the current row state. This prevents duplicate transitions and skipped states without trusting client input.

Conflict handling is mapped to distinct machine-readable codes:

- `RUN_LOCKED`: the row lock is not available because another worker or user is already acting on the run. This is retryable; if the action was already recorded in the idempotency table, the stored response is returned immediately; otherwise the caller retries after the first request completes.
- `RUN_STATE_STALE`: the run has already advanced beyond the requested state, or the action is invalid for the current state.

A real double-click on approve arrives while the first request still holds the lock, so the second request gets `RUN_LOCKED`, not the current state. The API either returns the stored response for that key if the original request already completed, or it returns a retryable conflict while the first request is still running. If another actor or another state change already happened, the request fails with `RUN_STATE_STALE`.

**Stuck-Run Recovery**

The recovery decision is a Redis heartbeat plus a sweeper bound check. While a run is in `calculating`, the worker updates a Redis heartbeat key with a short interval and a TTL of 2-3× the interval. The sweeper requeues a run only if it is still in `calculating`, the heartbeat is missing, and `last_enqueued_at` is older than a configured `RUN_MAX_QUEUE_WAIT` bound. This avoids treating queued-but-not-started runs as lost work and prevents duplicate requeue storms.

If the bound is exceeded, the sweeper publishes a new message for that run, but it does not dequeue the original one. Whichever message is picked up first takes the row lock and runs; the losing message exits on the lock or state check.

**At-least-once Delivery**

Messages can be retried and redelivered in the case of failure. Duplicate processing is prevented using idempotency. The idempotent key is celery's task_id since it's the same for a single task run. When retried, the state of the run is checked as well as the presence of the idempotent key in redis to indicate successful run. This prevents a scenario where the transaction was committed but the idempotent key was not marked as successful in redis.

## PaySlip Categories

| **Category** | **Components** | **Notes** |
|---|---|---|
| Earning | Basic Salary, Housing Allowance, Transport Allowance, Other Allowance, Bonus | taxable |
| Earning | Reimbursement |  not taxable, added after tax |
| Deduction | Employee Pension, PAYE, Other Deduction | - |
| Employer contribution | Employer Pension | not deducted from the employee |

## Calculation Engine

Each calculation section are represented as reusable functions that produce the result from the received values using the provided formulas. They are not required to make database queries. This provides flexibility in code and allows easy modification when calculation framework changes.

Money is represented as the python Decimal object for precision purposes and rounded using the quantize method from Decimal with mode set to ROUND_HALF_EVEN for banker's rounding. Formulas are ordered correctly and rounded once after calculation to preserve pay true values.

The calculation transaction runs under PostgreSQL `REPEATABLE READ` to guarantee that each read sees a consistent snapshot of employee compensation, pay versions, statutory rules, and unapplied adjustments while the run is being computed.

**Calculation Flow**

- The worker opens a transaction and locks the run row with FOR UPDATE NOWAIT. If it’s already locked, another worker has it, so this one exits.
- It checks the run is a draft and the calculation state is `calculating`. That is the guard against a redelivered task.
- It reads the inputs, calculates, writes the results and marks the calculation completed, then commits. This is all one transaction.
- If the worker crashes anywhere before the commit, Postgres rolls everything back and releases the lock. The run remains in `calculating` until the sweeper re-evaluates it.
- A sweeper finds runs in `calculating` that have exceeded the configured queue bound and re-queues them. If the original worker is just slow, the re-queued task fails the NOWAIT lock and exits, so two calculations can’t run at once.
- The worker updates a Redis heartbeat while it is running and resets the key TTL every few seconds; if the worker is hung, the heartbeat expires and the sweeper can decide whether to requeue. The requeue updates `last_enqueued_at` so the sweeper does not re-trigger endlessly.
- Celery side: `acks_late` is enabled so unfinished tasks are redelivered, and set a hard timeout so hung workers are eventually reclaimed and marked failed.

### Calculation order

The calculation is executed as a strict pipeline so that every rounded line is produced once at the point the rule requires it, and each downstream value only uses the already-rounded upstream inputs.

1. Determine the employee’s paid days for the period and split the month into compensation segments at effective-date changes.
   - Each segment is evaluated separately using the Africa/Lagos period boundaries and the employee’s active employment dates.
   - For each recurring component, compute the raw prorated amount as: monthly amount × (days paid in that segment ÷ calendar days in month).
   - Round each prorated recurring line once with banker's rounding (half-to-even) to the nearest kobo.
   - This produces the rounded segment values for basic, housing, transport, and other_allowance.

3. Compute the recurring taxable earnings per segment.
   - Gross recurring pay for the segment is the sum of the rounded recurring taxable lines: basic + housing + transport + other_allowance.
   - Pensionable pay for the segment is the sum of the rounded pensionable lines only: basic + housing + transport.
   - `other_deduction` is applied once per month, not once per segment. We take the value from the pay version of the latest segment in the month, and use that amount once in net pay. Earlier segments keep their own `other_deduction` value on the row for reference, but only the latest segment’s deduction is subtracted from the final net pay.

4. Add one-off run values and pending adjustments for the employee.
   - Bonus is added as a run-specific taxable earning, not pensionable.
   - Reimbursement is added as a non-taxable, non-pensionable amount to be added back after PAYE.
   - Pending adjustments are one-off corrections that reference an approved run but apply to the current calculation window; they are not prorated and they are not annualized.
   - A pending adjustment behaves like a bonus correction: if it is taxable, it is taxed using the bonus-difference method; if it is pensionable, it is included in pensionable pay; otherwise it is added after tax as a non-taxable correction.
   - These are not prorated; they are fixed values for the draft run.
   - If the month has multiple salary segments, the bonus and pending adjustments are assigned to the later segment for the purpose of segment-level PAYE allocation; they are not split or prorated across the year.

5. Build the employee gross pay for the month.
   - Gross = sum of the rounded recurring taxable lines + bonus.
   - This is the amount before pensions, tax, and deductions.

6. Calculate pension from the rounded pensionable pay across all segments.
   - Pensionable pay for the month is the sum of the rounded segment pensionable amounts across every segment in the period.
   - Employee pension = 8% × total pensionable pay, rounded once at the end of this step with banker's rounding.
   - Employer pension = 10% × total pensionable pay, rounded once at the end of this step with banker's rounding.
   - This step is month-level and uses the combined pensionable pay from all segments, not the segment-by-segment values.

7. Build the annualized tax base per segment from the segment’s full-month values.
   - For each segment, annual gross (AG) = (segment full-month basic + housing + transport + other_allowance) × 12.
   - For each segment, annual pension contribution = segment full-month employee pension × 12.
   - For each segment, annual relief = 200,000 + 20% × AG.
   - For each segment, annual taxable income = max(AG − annual pension contribution − annual relief, 0).
   - This is computed from the full-month amounts for that segment, not from the prorated segment values.
   - If a bonus exists, it is added to AG as-is, not multiplied by 12. In a two-segment month, the bonus belongs to the later segment for segment-level tax allocation because it is a one-off monthly value, not a spread across the year.

8. Calculate annual tax per segment in progressive bands without rounding intermediate values.
   - Apply the tax bands to each segment’s annual taxable income progressively: each band taxes only the amount inside that band.
   - Sum the band taxes for the segment to get the segment annual tax.
   - If a bonus exists, compute a second tax figure with the bonus included in AG and relief for that segment, then compute bonus tax as the difference:
     - bonus tax = annual tax with bonus − annual tax without bonus.
     - The entire bonus-tax difference is charged in that month and rounded once at the end of this step.

9. Convert annual tax to monthly PAYE.
   - For each segment, compute monthly PAYE from the segment annual tax using the days paid fraction: annual tax × (days paid ÷ (12 × calendar days in month)).
   - Do not round the intermediate fraction; round only once at the end of the step with banker's rounding.
   - If the employee has multiple salary segments, repeat that calculation for each segment and then sum the rounded segment PAYE values.
   - Add the bonus tax to the monthly PAYE in the month where the bonus applies.

10. Calculate net pay from the already-rounded payroll lines.
   - Net pay = gross − employee pension − PAYE − other_deduction + reimbursement.
   - This is the final line that determines whether the run can be submitted.
   - If net pay is negative, the run fails validation with the employee identified and the reason recorded as negative net pay.

11. Freeze and persist the fully calculated row for the run.
    - Store the final rounded values together with the rule version used, the input values, and the calculation metadata needed to reproduce the payslip later.
    - The stored payslip must be immutable once the run is approved or paid.

This order matters because it preserves the finance rules exactly: rounded component lines feed pension and gross, annual tax is built per segment from full-month values, monthly PAYE is prorated only at the end, and net pay is computed last from the finished rounded values.

## Reproducibility Of PaySlip

Payslips are not stored as a snapshot copy. Instead, each payslip row references the authoritative employee pay version, statutory rule version, and run inputs via foreign keys. New pay versions, compensation edits, and rule changes are inserted as new rows; approved and paid payslips keep their original FK references and therefore reproduce exactly the same calculation years later. The run stores the immutable inputs needed for re-derivation, but the historical result remains insert-only and never overwritten.

## Authorization Matrix

| **Staff** | **Admin** | **Payroll Officer** | **Employee** |
|---|---|---|---|
| They are staff of HarborHR and are not associated with any organization | Can view data from their organization | Create and recalculate runs, manage employees and compensation | View only their own payslips, and only for approved or paid runs. |
| Modify statutory values via a staff-only endpoint. | Start and modify payroll run and other actions taken by a payroll officer. The approver must not be any admin involved in the run's calculation up to that state |  Submit runs for review. | Do not need login data to be paid. |
| - | Add payroll officers and employees to their organization. | - | - |

## Async Calculation

Since calculation are asynchronous, clients needs to know the state of runs. Updates are pushed to the clients via a stream endpoint using SSE only after the database transaction commits, so consumers only see final state changes. When a client reconnects, it refetches `/runs/{id}` to recover the current snapshot and then resumes the stream. Disconnected clients can also replay missed events using the Last-Event-ID sent by the browser. This ID is the id from the state log, preventing lost events.

## Trade-Offs

- **Asynchronous calculation vs Synchronous calculation:** Async approach was chosen ahead of sync for performance purposes. A synchronous run would hold the connection for the duration of the run which is affected by other runs currently running and the number of employees the run calculates for. This will also waste resources such as a connection pool for the database/redis and reduce user experience.

- **SSE vs Polling:** SSE is preferred to polling since we only push to the frontend when the run has completed and doesn't require additional work from the client. Polling approach would overload the backend with wasteful requests that gets uncompleted message, affecting the experience of other users and the overall performance of the system.

- **Concurrent Database Writes vs Faster Run Execution:** Having two celery workers each with a concurrency value of 4 produces 16 concurrent bulk writes (with 5000 rows) to the database (assuming each run makes 2 writes) but result in faster execution. It is repeated continously until all 1000 organization run has been completed. This plus other writes from clients to the database happening simultaneously, places load on the database and may raise latency temporarily. Reducing the latency requires the removal of one worker which can reduce the writes happening concurrently but raises the execution time of all runs.

## Risks And Limits

Payroll runs are executed in the background by a celery worker. At peak of 1000 organization with 5000 employees each would take approximately three hours to complete with each run taking 90 seconds in worst case. Each running calculation also holds a database connection and an active transaction for up to 90 seconds, so the pool can become a bottleneck during the same peak window.

**Breakdown:**

2 celery workers with 4 concurrent task execution each = 8 task execution simultaneously
With 1000 organizations, messages are picked 125 times across both workers: 1000 / 8 = 125
Since each run takes 90 seconds, it would take 11250 seconds to execute all 125 picked messages (considering 8 tasks are executed concurrently) = 125 * 90 = 11250
That means it would require ~3hrs to execute all 1000 runs = 11250 / 3600 = 3.125hrs

Under high throughput, postgres becomes a bottleneck as it suffers from concurrent bulk writes with each containing 5000 rows to write.

## Multi-Tenancy

Postgres Row-Level-Security is used as a safety net for organization data isolation. This prevents leaks to unauthorized personnel. The app runtime sets the organization per request using `SET LOCAL app.org_id = ...` via `set_config(..., true)`, because a session-level setting leaks across pooled connections. The app role is not the table owner, so RLS already applies to it. We intentionally do not use `FORCE ROW LEVEL SECURITY` for the runtime role; the app is non-owner and the owner-level migration and sweeper paths can bypass naturally if needed. Celery workers set the org from the task payload when they operate outside the request context.

Where a table does not carry its own `organization_id`, the policy is enforced through joins:

- `employee_pay`, `employment_period`, `payslip`, `payslip_segment`, `adjustment`, `run_participants`, `run_value_log`, and `run_state_log` join to `employee` or `payroll_run`, which then join to `organization`.
- The row-level policy is built from the parent organization and the restriction is applied through the join path rather than storing a redundant org column on every child table.
- This is the default pattern for historical and audit tables, where the source of truth is still the owning organization of the parent entity.

### RLS coverage

RLS is enabled on all tenant-owned application tables whose rows can be read or mutated by an organization member. These tables either carry an `organization_id` directly or are reachable through the employee/payroll-run parent chain:

- Enabled: `organization`, `employee`, `employment_period`, `employee_pay`, `payroll_run`, `run_participants`, `payslip`, `payslip_segment`, `adjustment`, `run_value_log`, and `run_state_log`.
- Reason: each row belongs to exactly one organization, and the data must be filtered by that org even when a child table does not store an `organization_id` column.

RLS is intentionally not enabled on shared/global tables or on identity/onboarding records that are not tenant-owned payroll rows:

- Not enabled: `user`, `invite`, `role`, `permission`, `statutory_rules`, and other reference metadata used across all organizations.
- Reason: `user` and `invite` are identity and onboarding records, not organization-partitioned payroll data. Their access is controlled through authentication, authorization, and membership checks rather than a per-organization row filter. Shared reference metadata is global configuration and is read across organizations, so it is not partitioned by org in the database.

### Database invariants

The following invariants are enforced in the database instead of being left to application checks alone:

- Partial unique index on `(organization_id, period)` for active runs where status is not cancelled.
- Partial unique index on `(employee_id, status)` for active invites where status is active.
- Unique `(organization_id, key)` on `request_idempotency_keys`, with a stored `request_hash` so a reused key with a different payload is rejected.
- Unique `(employee_id, version)` and `(employee_id, effective_from)` on pay rows; the same is enforced on statutory rule versions.
- `employment_period` has a check constraint `end_date IS NULL OR end_date >= start_date`, plus an exclusion constraint on the date range per employee to prevent overlaps.
- `run.statutory_version` is a UUID FK to the statutory rules table.
- Index on `(payroll_run_id, employee_id)` for the approver validation query.
- The first sign-up writes the organization, employee and initial admin user in one database transaction.

## Example 4

**Manually Worked Example**

Same employee as Example 1. Basic rises from ₦300,000 to **₦360,000**, effective **2026-07-16**. July has 31 days, so the segments are days 1–15 (15 days) and days 16–31 (16 days).

| Item | Working | Amount |
|---|---|---|
| Basic, segment 1 | 300,000 × 15/31 = 145,161.2903… → | ₦145,161.29 |
| Basic, segment 2 | 360,000 × 16/31 = 185,806.4516… → | ₦185,806.45 |
| **Basic total** | | **₦330,967.74** |
| Housing, segment 1 | 150,000 × 15/31 = 72,580.6451… → | ₦72,580.65 |
| Housing, segment 2 | 150,000 × 16/31 = 77,419.3548… → | ₦77,419.35 |
| Transport, segment 1 | 50,000 × 15/31 = 24,193.5483… → | ₦24,193.55 |
| Transport, segment 2 | 50,000 × 16/31 = 25,806.4516… → | ₦25,806.45 |
| other_allowance, segment 1 | 100,000 × 15/31 = 48,387.0967… → | ₦48,387.10 |
| other_allowance, segment 2 | 100,000 × 16/31 = 51,612.9032… → | ₦51,612.90 |
| Gross, segment 1 | 145,161.29 + 72,580.65 + 24,193.55 + 48,387.10 | ₦290,322.59 |
| Gross, segment 2 | 185,806.45 + 77,419.35 + 25,806.45 + 51,612.90 | ₦340,645.15 |
| Pensionable pay, segment 1 | 145,161.29 + 72,580.65 + 24,193.55 | ₦241,935.49 |
| Pensionable pay, segment 2 | 185,806.45 + 77,419.35 + 25,806.45 | ₦289,032.25 |
<!---Sum of two pensionable pay (241,935.49 + 289,032.25 = 530,967.74) applied to pension working --->
| Employee pension | 8% × 530,967.74 | ₦42,477.42 |
| Employer pension | 10% × 530,967.74 | ₦53,096.77 |
| Annual gross (AG), segment 1 | 600,000 × 12 | ₦7,200,000 |
| Annual gross (AG), segment 2 | 660,000 × 12 | ₦7,920,000 |
| Relief, segment 1 | 200,000 + 20% × 7,200,000 | ₦1,640,000 |
| Relief, segment 2 | 200,000 + 20% × 7,920,000 | ₦1,784,000 |
| Annual taxable, segment 1 | 7,200,000 − (40,000 × 12) − 1,640,000 | ₦5,080,000 |
| Annual taxable, segment 2 | 7,920,000 − (44,800 × 12) − 1,784,000 | ₦5,598,400 |
| Annual tax, segment 1 | 21,000 + 33,000 + 75,000 + 95,000 + 336,000 + (1,880,000 × 24% = 451,200) | ₦1,011,200 |
| Annual tax, segment 2 | 21,000 + 33,000 + 75,000 + 95,000 + 336,000 + (2,398,400 × 24% = 575,616) | ₦1,135,616 |
| Monthly PAYE, segment 1 | 1,011,200 × 15 ÷ (12 × 31) = 40,774.1935… → | **₦40,774.19** |
| Monthly PAYE, segment 2 | 1,135,616 × 16 ÷ (12 × 31) = 48,843.6989 → | **₦48,843.70** |
| **Monthly PAYE total** | | **₦89,617.89** |
| **Net pay** | 630,967.74 − 42,477.42 − 89,617.89 | **₦498,872.43** |
