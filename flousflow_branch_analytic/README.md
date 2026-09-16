# flousflow_branch_analytic

Branch / Profit Center analytic tracking for Odoo 19 **Community** — POS + Customer Invoices.

The goal: make Odoo Analytic Accounting work as a **per-branch P&L** system where
Revenue and COGS land on the same analytic account, while balance-sheet lines
(Receivable, Cash, Bank, Tax, Stock Valuation) are **never** polluted.

## What it does

| Area | Behaviour |
|------|-----------|
| POS configuration | Add an `Analytic Account` (branch) on each `pos.config` |
| POS session close | Revenue, refunds, COGS and COGS reversals receive the POS analytic account (100%). Receivable/cash/bank/tax/stock-valuation lines are untouched. |
| Customer invoice | Add an `Analytic Account` header (out_invoice / out_refund). Selecting it applies 100% to invoice product lines. |
| Invoice COGS | Native `stock_account` creates the COGS pair; analytic is retained on the P&L expense line and removed from stock valuation. |
| Credit notes | Same header behaviour; reversals net the branch back to zero. |
| POS-generated invoice | Inherits the POS config analytic account on the header and lines automatically. |
| Enforcement (optional) | Company settings to require an analytic account before closing a POS session / posting a customer invoice. |

## Design — extension points (Odoo 18 source verified)

No core files are modified. Only these hooks are used:

- `pos.config` — new field `analytic_account_id`.
- `pos.session._get_sale_vals()` — adds `analytic_distribution` to revenue/refund lines.
- `pos.session._get_stock_expense_vals()` — adds `analytic_distribution` to COGS/COGS-reversal lines.
- `account.move._stock_account_prepare_realtime_out_lines_vals()` — removes the copied distribution from the generated stock-valuation line while retaining it on the expense COGS line.
- `pos.session._get_stock_valuation_vals()` — intentionally **not** overridden (balance-sheet).
- `pos.session._validate_session()` — optional mandatory-analytic check.
- `pos.order._prepare_invoice_vals()` / `_get_invoice_lines_values()` — inherit analytic on POS invoices.
- `account.move` — new header field `analytic_account_id`, an `onchange` that propagates
  to product lines, and a `_post()` guard for the optional enforcement.
- `res.company` / `res.config.settings` — the two enforcement flags.

COGS on invoices is produced natively by
`stock_account` (`_stock_account_prepare_realtime_out_lines_vals`) creates both
the stock-valuation and expense lines from the invoice line. The module keeps
the distribution on the expense line only, so balance-sheet stock valuation
does not pollute branch P&L.

## Install / Upgrade

```bash
docker exec odoo_clean_web odoo --db_host=db --db_user=odoo --db_password=odoo \
  -i flousflow_branch_analytic -d DB_NAME --stop-after-init
```

## Manual test checklist

1. Settings → Accounting → Analytics: enable the two enforcement flags (optional).
2. Create analytic accounts `Cairo`, `Giza`.
3. Create two POS configs, assign `Cairo` / `Giza`.
4. Sell on Cairo POS → close session → open the session `account.move` → confirm
   the *sales* and *stock expense* lines carry `Cairo` and no other lines do.
5. Refund fully → close → confirm the branch P&L nets to zero.
6. Create a customer invoice with a storable (real-time) product, set the header
   to `Cairo`, post → confirm both the revenue and the `cogs` lines carry `Cairo`.
7. Credit note the invoice → confirm reversal revenue and COGS carry `Cairo`.
8. Generate an invoice from POS → confirm header + lines + COGS are `Cairo`.
9. Analytic report filtered by branch shows correct Revenue − COGS = Gross Profit.

## Known limitations

- A single analytic account per document (100% distribution). Multi-account
  split distribution is not handled by the header shortcut.
- Enforcement only covers POS session close and customer invoice/credit-note
  posting; vendor bills are intentionally left alone.
- POS aggregation keeps one revenue/COGS line group per account/tax/product, so
  a config change mid-session is not possible by design (one session = one config).
