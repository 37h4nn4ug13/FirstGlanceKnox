# Workflows

## Public request to booking

1. Submit the public quote form; the shared CRM receives the customer, property, and lead.
2. An administrator or authorized salesperson opens the lead and builds an estimate from the price book.
3. Pricing exceptions require administrator approval. Send an estimate to queue local email and obtain a customer link.
4. The customer reviews and accepts the scope; accepted prices and commission terms are saved.
5. Schedule the approved estimate. The server checks the time window and conflicts again when saving.

## Crew offer to completion

1. An administrator offers a job to a cleaner with fixed pay, a crew slot, and an expiration.
2. The cleaner reviews the saved schedule, scope, and amount, then accepts or declines.
3. An accepted offer creates pending cleaner compensation. The cleaner progresses through travel, arrival, work, and submission, completing the checklist and required evidence.
4. An administrator approves completion or returns it for correction. Approval makes cleaner pay payable.

## Change an appointment or assignment

- From job details, an administrator selects **Reschedule appointment**, reviews the existing appointment, enters the new times and a reason, then saves. Conflicts and invalid states leave the existing booking and agreements intact. A successful change supersedes active offers and reverses pending payout agreements; send fresh offers next.
- **Cancel appointment** requires a reason. It releases the booking and withdraws active offers while preserving records. Completed jobs cannot be canceled through this workflow.
- From offer details, **Withdraw offer** requires a reason and is available to administrators. Withdrawal releases the crew slot while preserving the customer's appointment. Work already in progress must be reviewed through the job workflow.
- These changes update in-app records and notifications. They do not contact a customer through an external channel automatically.

## Billing and compensation

Issue an invoice from an approved completed job. Review its customer view/PDF and queue an email if needed. Record payments actually received. Partial payments change the balance; full payment earns the sales commission. Record cleaner and commission payouts separately. Reversals retain the original transaction and adjustment history.

## Customer portal

Linked customer accounts can review their documents and service history and request repeat service. Secure document links are purpose-scoped, expiring, and revocable. Possession of one document link does not grant access to neighboring customer records.

## Phones and offline use

The bottom bar provides frequent crew actions. The top **Menu** exposes every permitted workspace section, profile, and sign-out; it works without JavaScript. Escape closes it and restores keyboard focus when JavaScript is enabled.

Offline updates remain explicitly marked as device-only until the server accepts them. Synchronization checks the account and current business rules. Photos are not queued offline. Use the online notification center if push is unavailable or unconfigured. Offline edge cases and actual mobile installation still require the release checks in the checklist.
