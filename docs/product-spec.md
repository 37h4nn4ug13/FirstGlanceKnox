# Product specification

The [original master prompt](../firstglanceknox-codex-master-prompt.md) is the authoritative product roadmap. The user's supplied logo must be retained, and other initial media may use temporary URLs.

## Product surfaces

1. Public marketing pages and persistent quote requests for Knoxville homes and businesses.
2. Customer portal with estimates, approval, appointments, invoices, and repeat requests.
3. Role-aware crew workspace with CRM, estimates, schedules, offers, completion, billing, and ledgers.
4. Django administration for business records, staff, and approved marketing content.

The shared lifecycle is lead → estimate → acceptance → appointment → accepted cleaner offer → completion review → invoice → manual payment record → compensation record.

## Business boundaries

- Customer approval preserves the accepted scope and prices.
- Cleaner compensation is fixed agreed pay, separate from the customer invoice. It becomes payable on administrator-approved completion.
- Sales commissions use an agreement snapshot and earn on full invoice payment.
- Payment and payout screens record transactions already made outside the application. They do not transfer funds.
- Private job evidence never becomes public automatically. Gallery publishing requires explicit marketing approval.
- A changed appointment requires fresh cleaner offers and acceptance.
- No invented reviews, insurance claims, business contact details, service coverage, or public prices.

The current implementation is tracked separately in [checklist.md](checklist.md). A model or backend service alone does not mean its entire requested user workflow is finished.
