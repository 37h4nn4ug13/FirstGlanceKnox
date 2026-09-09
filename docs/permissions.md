# Permissions

| Workflow | Administrator | Salesperson | Cleaner | Customer |
| --- | --- | --- | --- | --- |
| CRM and leads | All | Assigned/created leads and related customers | No | Own linked portal records only |
| Estimates | All and pricing approval | Authorized leads/estimates | No | Own sent documents and response |
| New booking | Yes | Authorized accepted estimate | No | View own appointments |
| Reschedule/cancel | Yes | No | No | No |
| Create/withdraw offers | Yes | No | No | No |
| Accept/decline offer | Only if also the offered cleaner | Only if also the offered cleaner | Own offer | No |
| Job progress | Yes | No unless assigned cleaner | Accepted assignments | No |
| Completion approval | Yes | No | No | No |
| Invoices/payments | All | No company-wide invoice access | No | Own issued documents |
| Compensation | All | Own commission entries | Own payout entries | No |
| Reports, audit, price book | Yes | No | No | No |
| Staff invitations, profiles, roles, deactivation | Yes, with self/owner safeguards | No | No | No |
| Recurring plan edits/generation, unavailable-time changes | Yes | No | No | No |
| Email delivery processing/retry | Yes | No | No | No |

Staff removal deactivates access instead of deleting records. Existing sessions and passwords are invalidated; rehire requires a fresh invitation/password. Role removal/deactivation hands off open leads and upcoming cleaner assignments while preserving work in progress and financial history. A nonowner cannot modify protected owner privileges, and an administrator cannot remove their own access. Workspace Admin does not grant Django superuser or configuration-administration privileges.

Multiple roles combine authorized staff capabilities. Inactive accounts/profiles are denied staff access. Django superusers have administrator access. Template visibility is only a convenience: views and domain functions enforce permissions independently.

Job evidence is served through authenticated retrieval with object-level checks. Public media is a separate explicit publication process. Token document endpoints apply purpose, expiration, revocation, and visible-state rules.

The new job-management tests exercise GET and POST denial for salespeople, cleaners, and customers, preservation on invalid input, terminal-state rejection, and private notification destinations after withdrawal/supersession.
