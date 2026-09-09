# Review of gaps exposed by the instruction manuals

Implemented September 9, 2026. The manuals were checked against the actual forms, services, permissions, and customer flows.

| Manual workaround or failure | Change implemented |
| --- | --- |
| Inviting staff was disconnected from daily operations; editing/removing staff required raw administration. | Added Staff directory, search/status filters, invitation/reissue/revocation, employee profile/role/default commission editing, and deactivation/rehire. |
| Departure or role removal could leave unclear ownership of work. | Open assigned leads are released; upcoming offers are withdrawn with saved history; in-progress work remains intact with an admin handoff notification and visible work links. |
| Reusing an old invitation/session after deactivation could restore unintended access. | Serialized invitation/access changes; deactivation revokes pending invitations and changes the password hash; rehire requires a new invitation/password. |
| Correcting an unaccepted estimate required manually replacing it and explaining which copy applied. | Added explicit revisions with saved starting terms, editable/custom lines, add/delete controls, reason, old-link revocation, and links between versions. Accepted estimates remain immutable. |
| Old queued estimates could still be delivered after revision/revocation. | Delivery detects retired/current-version mismatches and blocks obsolete messages. |
| Saving a recurring plan gave no immediate local way to create a visit or recover from a conflict. | Added edit, pause/resume, explicit next-visit generation, transactional conflict recovery, and stale-submit protection. |
| Incorrect unavailable time could not be changed from the workspace. | Added edit/removal with audit history and checks against booked appointments/accepted assignments. |
| Queued customer email was easy to confuse with delivered email. | Added Email deliveries with pending/delivered views, attempts/errors, and processing/retry. Local backend behavior is stated explicitly. |
| Offline updates could be lost when new work was captured during synchronization, or discarded by sign-out without review. | Re-read device storage after each response, added visible review/discard controls, and block normal workspace sign-out while updates remain. |
| Inactive staff profiles were inconsistently reflected by role checks. | Unified the user-level role helper with domain access checks. |

## Still outside this completed pass

- Draft invoice line-item editing and a full accepted/billed-work change-order workflow.
- Complete staff payout adjustment controls and completed-job reopening/rework management.
- Customer portal account creation/linking from the workspace, rather than authorized configuration administration.
- Editing rejected offline updates and advanced multi-tab/account-switch recovery.
- Production deployment, verified outbound delivery, real payment processing, and real-device/cross-browser release validation.

These remain visible in the manuals/checklist; the new screens do not pretend to provide them. No real employees or customer records were changed by testing, and no production email or payment service was enabled.

Validation: 113 functional/domain/crew-browser tests passed in one run, including mobile staff onboarding/deactivation, revisions, responsive screens, offline queue preservation, and permission checks. Existing public browser checks were not repeated because the public marketing surface was unchanged.
