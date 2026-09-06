# Distribution Route Management (FlousFlow)

**Technical name:** `flousflow_distribution_route_management`
**Version:** 19.0.1.0.0 · **Odoo:** 19.0 Community · **License:** LGPL-3
**Author:** Flous Flow — https://flousflow.com

Operational route planning and visit execution for distribution
representatives. Builds on `flousflow_distribution_route_base`.

## Purpose

Distribution managers plan daily routes per representative; the
representative executes the visits in order, records the business result
of each visit, and management reviews planned vs actual performance.

## Dependencies

- `flousflow_distribution_route_base` (areas, visit types, employee
  configuration, security groups)
- `mail` (chatter / activities on route plans)

Deliberately **not** depended on: `sale`, `account`, `stock`,
`point_of_sale`, `fleet` — those integrations come as separate extension
modules.

## Route Plan Workflow

```
Draft ── Confirm Route (manager) ──> Confirmed
Confirmed ── Start Route (assigned user / manager) ──> In Progress
In Progress ── Complete Route (all visits closed) ──> Completed
Any active state ── Cancel (manager, reason mandatory) ──> Cancelled
```

- **Draft**: manager edits employee, area, visits (drag & drop ordering),
  planned times, objectives.
- **Confirmed**: planning data locked for the representative (Python
  guards + record rules); representative can start the route.
- **In Progress**: representative starts/completes/skips visits.
- **Completed**: only when every visit is `done` or `cancelled`.
  Managers may **Force Complete** with a mandatory reason (open visits
  are skipped with that reason).
- **Cancelled**: manager-only, reason mandatory, kept for audit.
  Manager may reopen a cancelled route to draft.

## Visit Workflow

Execution state is deliberately separate from the business result:

| Execution state | Meaning |
|---|---|
| `pending` | Planned, not started |
| `in_progress` | Started (actual start recorded) |
| `done` | Executed — a **Visit Result** captures the outcome |
| `cancelled` | Skipped (skip reason mandatory) |

Example: customer was closed → `state = done`, result
*Customer Closed* (`is_success = False`). This keeps execution analytics
(how many visits were actually attempted) clean and separate from
business success analytics.

### Visit Results

Configurable model `distribution.visit.result` with flags — logic is
never bound to result names:

- `is_success` — successful business outcome
- `requires_notes` — result notes mandatory
- `requires_revisit` — proposes the revisit flag on the wizard

Default results: Visit Completed, Order Taken, Collected (successful);
Customer Closed, Customer Not Available, Customer Refused, Needs
Revisit, Partial Completion, Other (unsuccessful — failure reason
mandatory when closing a visit with them).

### Complete Visit Wizard

Result (required) → failure reason (required for unsuccessful results)
→ result notes (required when `requires_notes`) → employee notes →
revisit flag + suggested revisit date.

## Manager Workflow

1. Create route plan (date, employee, supervisor, area, planned times).
2. Add visits: customer, visit type, planned date/time, planned duration
   (minutes), objective, notes. Reorder with drag & drop.
3. **Confirm Route** — validates: at least one visit, complete visit
   data, customer required by visit type, area assigned to employee,
   company consistency.
4. Monitor execution, review Planned vs Actual, cancel or force complete
   when necessary.

## Representative Workflow

1. *Distribution → Operations → My Routes* — today's route.
2. **Start Route** → **Start Visit** (in order) → **Complete Visit**
   (wizard) or **Skip Visit** (reason).
3. Repeat until all visits closed → **Complete Route**.

## Security

Groups are owned by the base module:
`Distribution Route User` / `Distribution Route Manager`.

- **User**: read/write only on own routes & visits (real record rules
  `[('employee_id', 'in', user.employee_ids.ids)]`); cannot create or
  delete plans/visits, cannot modify planning data after confirm
  (Python write guards), cannot cancel/confirm routes.
- **Manager**: full CRUD within allowed companies.
- **Multi-company**: global rules `company_id in company_ids` on all
  models; visit results with empty company are shared.
- Actual datetimes / completion time are written **only** through
  actions — manual editing is blocked for representatives.

## Planned vs Actual

- Visit: planned time, planned duration (minutes), actual start/end,
  actual duration, `arrival_variance_minutes` (positive = late).
- Route: planned start/end, actual start/end, duration (minutes).

## Reporting

- Route Analysis (pivot/graph): visits, executed, execution rate,
  success rate by employee/date.
- Visits Analysis (pivot/graph): by employee, area, visit type, result,
  state, customer, day.
- Calendar on visits (`planned_datetime`) and plans (`date`).
- Kanban of My Routes with visit progress.

## Smart Buttons

- Contact → *Visits* (full visit history of the customer).
- Employee → *Routes* and *Visits*.

## Future Extensions (no architectural change needed)

- **GPS module** (`flousflow_distribution_route_gps`): add
  check-in/check-out coordinates via `_inherit` on
  `distribution.route.visit` and override `action_start_visit` /
  `action_finalize_visit` / `action_skip_visit` calling `super()`.
- **Sales/Collection module**: add `sale_order_id` / `payment_id` on the
  visit model via inheritance; results stay flag-driven.
- **Vehicle/Warehouse/POS module**: extend `distribution.route.plan`
  with `vehicle_id`, `warehouse_id`, `pos_config_id`.

## Installation

```bash
# base module must be present
odoo -d DB -i flousflow_distribution_route_management --stop-after-init
```

Fresh installs together with `flousflow_distribution_route_base` work out
of the box (the base module exposes its employee fields on
`hr.employee.public` as non-stored related fields).

## Testing

```bash
odoo -d DB -u flousflow_distribution_route_management \
     --test-enable --stop-after-init
```

28 automated tests cover: creation & sequence, confirm validation,
required customer, employee/area consistency, execution flow, result
rules (required result / notes / failure reason), duration & variance
maths, route completion & force complete, counters & rates, user vs
manager record rules, write guards, multi-company isolation, duplicate
reset, partner & employee history, planned-date consistency.
