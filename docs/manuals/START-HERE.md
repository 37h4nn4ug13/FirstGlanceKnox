# FirstGlanceKnox staff instruction manuals

**Edition: September 9, 2026 · Matches the current local website**

Updated for Staff management, estimate revisions, recurring-plan controls, delivery tracking, and device-outbox recovery. Use these manuals for the staff workspace, customer handoffs, and office administration. They describe the current controls, including features that still need an office or technical handoff.

## Choose your manual

| Your role | Manual | Main responsibility |
| --- | --- | --- |
| Administrator / owner | [Administrator manual](administrator.md) | Pricing, assignments, schedule changes, completion approval, billing, and team access |
| Salesperson | [Salesperson manual](salesperson.md) | Capture leads, maintain follow-ups, prepare estimates, and book approved work |
| Cleaner | [Cleaner manual](cleaner.md) | Review offers, perform accepted work, report issues, and submit completion |
| Everyone who speaks to customers | [Customer interactions and response guide](customer-interactions.md) | Understand the customer experience and use the appropriate response and handoff |

If you have both Salesperson and Cleaner roles, use both manuals. Those permissions combine, but they do not give you administrator permissions.

## Start each session

1. Open [Staff sign-in](http://127.0.0.1:8765/accounts/login/) and use your own email/password.
2. Open [the crew workspace](http://127.0.0.1:8765/crew/).
3. On a computer, use the left navigation. On a phone, use the bottom shortcuts and the top **Menu** for all permitted sections.
4. Review **Notifications** (called **Inbox** in the phone shortcuts), then open the relevant record. **Mark all read** clears unread indicators; it does not complete the work.
5. Check the connection notice before relying on a recently saved update.

**All appointment times are Knoxville local time.** A customer's preferred date is a request, not a reservation.

## Two administration areas

**Crew workspace:** the everyday operating system at `/crew/`. Use it for lead updates, estimates, bookings, job offers, completion, invoices, and compensation.

**Administration:** the configuration area at `/admin/`. Authorized administrators use it for account access, certain customer/property settings, and marketing content. Permission to use the Admin role in the workspace does not automatically grant access to this separate area. Ask the owner if you cannot enter it.

## Read this before using the current preview

- These links work on the computer hosting the local preview. A `127.0.0.1` link will not take a customer on another device to this website. Public access requires a deployed address.
- Demo records and prices are synthetic. Private demo credentials are stored separately in `.local/demo-access.txt`; this manual intentionally contains no passwords or customer links.
- The configured email backend currently writes email files on this computer. **Send estimate** and **Queue invoice email** do not mean a real customer received an email.
- The site has no customer messaging inbox, live payment checkout, or payroll transfer. Use the business's approved communication/payment methods outside the site and record the outcome inside it.
- Push and background processing require configuration. Check the actual record and notification center; do not assume a phone alert or scheduled email was delivered.

## Who handles what?

| Task | Admin | Salesperson | Cleaner |
| --- | --- | --- | --- |
| Work leads and build estimates | All authorized records | Own assigned/created pipeline | Only with Salesperson role |
| Book an accepted estimate | Yes | Authorized estimate | No |
| Change prices or approve pricing exceptions | Yes | Request approval | No |
| Reschedule/cancel a job; create/withdraw offers | Yes | Request office action | Request office action |
| Accept an offer | Only when personally offered as cleaner | Only with Cleaner role and own offer | Own offers |
| Update work progress | Yes | Only as assigned cleaner | Accepted assignments |
| Approve completion, issue invoices, record payments | Yes | No | No |
| View compensation | All | Own commission | Own job pay |

## Good recordkeeping

Use the displayed lead, estimate, job, and invoice numbers when handing work to someone else. Record what the customer requested, what you agreed, who owns the next step, and the next follow-up date. Keep customer-facing **Terms** and **Customer notes** free of private office comments and staff pay information.

If a button is unavailable or a change is rejected, read the message and check the record's status. Do not recreate payments, leads, or jobs just to bypass an error.

## Troubleshooting

| Symptom | What to do |
| --- | --- |
| A section is missing | Open the phone **Menu**; verify your role with the owner if it is still absent. |
| CSRF verification failure on a shared estimate | Refresh the shared-link page and submit again. This preview includes the referrer-policy fix. If it persists, report the time and estimate number to the owner; do not disable security settings. |
| Expired/unavailable customer link | Ask the office for a fresh link after it checks the document status. |
| Email not received | Check **Email deliveries** for estimate/invoice delivery attempts. Staff invitation failures appear on the employee page. In this preview, delivery writes local files. In a deployed system, have the office verify recipient and delivery status. Do not repeatedly press Send. |
| Offline/update waiting | Keep the same account signed in, reconnect, and wait for successful synchronization. Review the **Device outbox** and resolve or explicitly discard obsolete updates. Sign-out is blocked until it is empty. |
| Permission denied | Ask the administrator to perform or authorize the action. Never borrow another staff member's account. |

For development status, see the [remaining-work checklist](../checklist.md). Read the customer-interaction guide alongside your role manual.
