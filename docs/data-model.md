# Data model

All operational entities share one database. Most operational records use UUID keys and creation/update timestamps.

| Area | Main entities and relationships |
| --- | --- |
| Identity | `User` has group roles and optional `StaffProfile`; `StaffInvitation` controls onboarding |
| CRM | `Customer` has contacts, properties, and optionally a portal user; `Lead` belongs to one customer/property and has `LeadVisit` history |
| Estimating | `PriceBookItem` supplies defaults; `Estimate` has `EstimateLine` rows and an accepted snapshot |
| Scheduling | `Job` links an accepted estimate/customer/property; `AvailabilityBlock` blocks time; `RecurringPlan` supplies later visits |
| Assignments | `JobOffer` links job, cleaner, crew slot, fixed pay, schedule/scope snapshot, and accepted terms |
| Billing | `Invoice` has immutable issued terms and `InvoiceLine` rows; `Payment` records receipts and linked reversals |
| Compensation | `CleanerPayout` links an accepted offer; `CommissionEntry` links an invoice and commission snapshot |
| Messaging | `Notification` belongs to a recipient; `OutboundMessage` tracks queued email and delivery attempts |
| Audit/access | `AuditEvent` records an actor/action/object; `AccessToken` stores hashed document grants; `OfflineReceipt` deduplicates synchronized changes |
| Marketing | `Service`, `ServiceArea`, `MediaAsset`, `GalleryCollection`, `BeforeAfterPair`, `FeaturedProject`, `Testimonial` |
| Evidence | `JobEvidence` links authenticated private images to jobs |

Use the source model definitions and migrations for field-level details. Money is USD Decimal; display formatting never performs business arithmetic. Payment reversals preserve the original row. Offer withdrawal and rescheduling retain original accepted terms, reverse pending payout status, and require a new agreement before future work.

Rescheduling audit events include the previous and new time windows plus the reason. Cancellations retain a reason on the job and an audit event. Concurrent behavior must be tested on PostgreSQL before production.
