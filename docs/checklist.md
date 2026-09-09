# Implementation checklist

Updated September 9, 2026. The [master prompt](../firstglanceknox-codex-master-prompt.md) remains the full roadmap. Checked items describe implemented local scope; they do not certify production readiness.

## Implemented and verified locally

- [x] Django foundation, original logo, frozen dependencies, migrations, synthetic demo command, and setup documentation.
- [x] Public pages, responsive navigation, consent-controlled gallery, persisted quote requests, and keyboard/lightbox checks.
- [x] Email accounts, role-aware staff access, CRM, estimates, approval snapshots, conflict-checked booking, and domain authorization tests.
- [x] Fixed-pay offers, accept/reject, work status/checklist, completion approval, invoice issue, manual payments/reversals, and separate compensation ledgers.
- [x] Customer portal and document screens; repeat request implementation.
- [x] Administrator rescheduling, cancellation, and offer withdrawal screens, with required reasons and state/permission validation.
- [x] Changes preserve original agreements/history and require fresh acceptance after rescheduling. No-op reschedules cannot retire agreements.
- [x] Role-aware mobile menu reaches all desktop sections, works without JavaScript, and supports keyboard dismissal.
- [x] Invoice layout overflow and customer sign-out contrast fixes; offer notification destinations remain accessible after declined/withdrawn offers.
- [x] Public, staff, and customer browser layout checks at 320, 375, 390, 768, 820, 1280, and 1440 pixels in Chromium.

## Remaining product and release work

- [x] Unaccepted estimate revisions, custom descriptions/prices/units, add/delete lines, old-link revocation, and retained originals. Accepted terms cannot be overwritten.
- [ ] Full draft invoice editor and authorized adjustment workflow beyond issuing from the approved estimate.
- [x] Recurring-plan editing/pause/resume and manual next-visit generation, stale-submit/conflict tests, and availability-block edit/removal with audit history.
- [x] Staff directory, invitations/reissues/revocation, profile/role/default commission editing, deactivation/rehire, protected owner/self-access safeguards, and work handoff.
- [x] Estimate/invoice delivery queue, delivery attempts, explicit processing/retry, and rejection of obsolete estimate messages.
- [ ] Comprehensive invitation, password recovery, customer onboarding, push, token, evidence, and offline integration tests.
- [x] Offline outbox review/discard, pending-update sign-out guard, and preservation of new leads added during synchronization.
- [ ] Editing rejected offline updates, multi-tab/account-switch recovery, and actual-phone offline validation.
- [ ] Broader reporting/filtering and remaining CRM administration requested in the master prompt.
- [ ] PDF visual/long-document QA, email-provider retry checks, and delivery failure visibility.
- [ ] Cross-browser checks (Safari, Firefox, Edge), real-device installation/push checks, 200% text enlargement, and a complete accessibility audit.
- [ ] PostgreSQL concurrency tests, production infrastructure, security deployment checks, monitoring, backups, and restore validation.
- [ ] Owner-approved images, copy, prices, contact information, policies, and business claims.

## Validation

Run the commands in [README.md](../README.md). Public browser tests target the running local preview; staff/customer browser tests use an isolated test database. The test suite includes lifecycle/financial invariants, admin-only changes, rejection rollback, notification access, responsive layouts, keyboard navigation, and an end-to-end mobile reschedule.

September 9 validation: 64 functional/domain tests and 21 opt-in browser checks passed across the verification runs. Ruff and Django system checks passed; migrations have no unrecorded changes. Static assets were collected successfully. Browser coverage is Chromium-only and is not a complete accessibility or security audit.

The subsequent manuals-driven pass passed 113 tests in one run, including all domain/functional tests and the expanded 21 crew/customer browser checks. The unchanged public browser suite was excluded from that run. Ruff, Django checks, migration consistency, static collection, and manual-link validation also passed. See [the improvement review](manual-improvements.md) for scope and remaining gaps.

No deployment, real customer contact, or live payment integration has occurred.
