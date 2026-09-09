# FirstGlanceKnox Django Platform — Master Codex Build Prompt

You are Codex running **GPT-6 Astra with ultra reasoning effort**. Act as the lead product engineer, Django architect, frontend engineer, UX designer, and test engineer for this project. Build a production-quality, responsive business platform for **FirstGlanceKnox**, a Knoxville-area window-cleaning company. The owner currently serves primarily residential customers and wants to expand into commercial work.

This is not only a marketing website. It is one connected platform with:

1. A polished, media-heavy public website that attracts residential and commercial customers.
2. A customer portal for estimates, appointments, invoices, and service history.
3. An installable crew web app for salespeople, cleaners, and admins.
4. A private operations system for CRM, estimating, scheduling, job assignments, invoicing, commissions, cleaner compensation, notifications, and reporting.

The central business lifecycle is:

**Lead → Estimate → Customer approval → Scheduling → Cleaner job offer → Accept/reject → Work → Completion approval → Invoice → Payment record → Commission/cleaner payout → Review or repeat service**

Build this as a cohesive Django application with one authoritative database. Do not create unrelated mini-apps or duplicate customer/job/payment data between interfaces.

---

## 1. How to work on this project

Before changing files:

1. Inspect the entire repository, including any `README`, `AGENTS.md`, dependency files, configuration, existing Django project, templates, tests, and supplied media.
2. Preserve existing user work and follow repository instructions.
3. If the repository is empty, initialize the project cleanly.
4. Write a concise implementation plan with ordered milestones, then begin implementing. Do not stop after producing a plan or scaffold.
5. Work in complete vertical slices: model, business rules, permissions, views, UI, tests, and documentation for a workflow before calling it complete.
6. Make reasonable, reversible assumptions when details are missing. Record those assumptions in `docs/decisions.md`. Ask only questions that genuinely block safe implementation.
7. Keep a checklist in the repository and update it as work proceeds.
8. Run relevant tests, linters, migrations, accessibility checks, and responsive browser checks after each milestone.
9. Do not deploy, push to a remote repository, contact real customers, send production email/push notifications, or connect paid services without explicit approval.
10. Never place secrets, production customer information, or real staff compensation data in source control or fixtures.

Create and maintain at least:

- `README.md`
- `.env.example`
- `docs/product-spec.md`
- `docs/architecture.md`
- `docs/data-model.md`
- `docs/workflows.md`
- `docs/permissions.md`
- `docs/decisions.md`
- `docs/deployment.md`

Use current supported dependency versions that are mutually compatible. Pin them reproducibly and document the chosen versions. Prefer a currently supported Django LTS release unless the repository already has an intentional supported Django version.

---

## 2. Product boundaries

### Build now

- Public marketing site
- Residential and commercial service presentation
- Media library and gallery
- Quote-request workflow
- Customer, organization, contact, and property CRM
- Door-to-door lead capture
- Estimates and customer approval
- Scheduling and availability
- Staff profiles and role-based access
- Cleaner job offers with agreed fixed compensation and accept/reject behavior
- Cleaner job workflow
- Sales commission tracking
- Branded invoice creation, PDF generation, email delivery, and status tracking
- Manual recording of customer payments
- Customer portal
- In-app and crew push notifications
- Responsive layouts across phones, tablets, laptops, and desktops
- PWA installation and useful limited offline behavior for field staff
- Audit logs and essential business reports

### Explicitly defer

- Stripe or another live payment processor
- Payroll execution or direct deposits
- Full general-ledger accounting
- Production SMS provider integration
- Automatic route optimization
- Continuous employee location tracking
- Native iOS or Android applications

Design clean extension points for deferred capabilities, but do not create nonfunctional “Pay now” controls or pretend an integration exists.

---

## 3. Technical direction

Unless the existing repository establishes a compatible alternative, use:

- Django with Python
- PostgreSQL
- Django templates for the primary UI
- HTMX for focused partial-page interactions
- Alpine.js or small framework-free JavaScript modules only where client-side state is genuinely needed
- A maintainable, mobile-first CSS system; Tailwind CSS is acceptable if a frontend build step is documented and kept simple
- Redis and Celery for background email, notifications, reminders, media work, and scheduled jobs
- A standards-based web app manifest and service worker for the crew PWA
- Standards-based Web Push with VAPID configuration stored in environment variables
- Pillow for image validation and responsive derivative generation
- WeasyPrint or another well-supported HTML-to-PDF solution for branded invoice and estimate PDFs
- S3-compatible object storage in production, with local filesystem storage in development
- Django’s configurable email backend, using console/file output in development and a transactional provider only when configured
- `pytest`, `pytest-django`, model factories, and Playwright-based responsive end-to-end tests

Avoid a separate single-page application unless the existing project already requires one. The crew experience should feel app-like, but it can remain server-rendered with targeted JavaScript and JSON endpoints for push, uploads, and offline synchronization.

Organize domain logic in explicit service functions or service classes rather than hiding important state transitions in templates, signals, or model `save()` methods. Use database constraints and atomic transactions for money, scheduling, invoice numbering, assignment acceptance, and state transitions.

Suggested Django app boundaries, which may be adjusted after inspecting the repository:

- `core`: shared utilities, settings, audit events, business configuration
- `accounts`: custom user, staff profiles, roles, invitations, authentication
- `marketing`: public pages, services, service areas, testimonials, media, SEO
- `crm`: customers, organizations, contacts, properties, notes, documents
- `leads`: web leads, door-to-door leads, territories, visits, follow-ups
- `estimates`: price book, estimates, line items, approval, revisions
- `scheduling`: availability, time off, schedule blocks, recurring plans
- `jobs`: jobs, visits, assignment offers, checklists, photos, completion
- `billing`: invoices, line items, PDFs, delivery events, payment records
- `compensation`: commission agreements/entries and cleaner payout entries
- `notifications`: in-app notifications, push subscriptions, delivery attempts
- `portal`: customer-facing secure estimate, appointment, and invoice access

Do not fragment the code merely to match this list. Keep dependencies directional and document them.

---

## 4. Brand and visual direction

Use the supplied FirstGlanceKnox logo. Place the provided original asset in an appropriate brand/static directory. Do not redraw, reinterpret, or replace it with a generated logo. If the logo is not available in the project workspace, ask me to attach it instead of fabricating a substitute. If a higher-resolution SVG or transparent PNG becomes available later, make replacement easy.

The supplied JPEG suggests this working palette:

- Bright cyan: approximately `#03A7FC`
- Deep blue: approximately `#1F7198`
- Charcoal: approximately `#293237`
- Black: `#000000`
- White: `#FFFFFF`

Because the source is a compressed JPEG, treat the non-black values as initial design tokens rather than immutable brand specifications. Define colors through centralized CSS variables. Use bright cyan primarily for accents, active states, links, focus indication, and primary calls to action. Do not use bright cyan as small body text on white when contrast is inadequate; use deep blue, charcoal, or black for readable text.

The visual character should feel:

- Clean
- Precise
- Trustworthy
- Local and personable
- Modern without feeling like a generic software company
- Suggestive of clear glass, light, and reflections without excessive glassmorphism

Use generous space, strong photography, restrained motion, crisp typography, and clear calls to action. Avoid crowded layouts, excessive gradients, generic stock photos, fake awards, fake review content, invented years of experience, or unverified “licensed and insured” claims. Business claims must come from configured content supplied by the owner.

Use the logo consistently in:

- Public navigation and footer
- Authentication screens
- Crew app shell
- Customer portal
- Estimate and invoice PDFs
- Email templates
- PWA icons when a suitable approved icon crop is available

---

## 5. Responsive and cross-device requirements

Every customer, crew, portal, and admin workflow must function on:

- Small phones beginning at approximately 320 CSS pixels wide
- Typical iPhone and Android phone sizes
- Tablets in portrait and landscape
- Laptops
- Large desktop monitors

Do not create a desktop application that merely shrinks on mobile. Design mobile-first and progressively enhance.

### Responsive behavior

- Never rely on hover for required information or actions.
- Avoid unintended horizontal page scrolling.
- Use minimum touch targets of approximately 44 by 44 CSS pixels for field workflows.
- Keep editable field text at least 16 CSS pixels on mobile to avoid unwanted browser zoom.
- Make quote, lead, job, and invoice forms one-column on phones and intelligently grouped on wider screens.
- Use a bottom navigation bar for the main crew phone experience and a sidebar or expanded navigation on larger screens.
- Convert dense admin tables into readable cards, stacked rows, or carefully controlled table overflow on narrow screens.
- Make modal workflows full-screen or nearly full-screen on phones.
- Keep the primary action reachable without forcing excessive scrolling.
- Preserve clear loading, empty, offline, success, and error states.
- Support device rotation and browser text zoom.
- Use responsive typography and spacing without making desktop content excessively wide.

### Browser support

Support current versions of:

- Safari on iOS and macOS
- Chrome on Android and desktop
- Edge
- Firefox

Use feature detection for PWA, push, camera, geolocation, and sharing capabilities. Provide a graceful browser fallback when a capability is not available.

### Responsive verification

Create repeatable browser tests or screenshot checks at representative widths such as:

- 320×568
- 375×812
- 390×844
- 768×1024
- 820×1180
- 1280×800
- 1440×900

At a minimum, verify public navigation, homepage, gallery, quote form, customer portal, salesperson quick lead, estimate creation, cleaner job offer, cleaner job detail, admin schedule, invoice editor, and invoice view.

---

## 6. Media-heavy public website

The owner has many real photos and videos of completed work. The public site should make that media a central sales tool while remaining fast on cellular connections.

### Public page inventory

Build:

- Homepage
- Residential window cleaning page
- Commercial window cleaning page
- Individual service pages
- Gallery/media page
- Before-and-after page or gallery mode
- About page
- Service-area page
- Quote-request page
- Contact page
- FAQ page
- Privacy policy and terms placeholders
- Accessible 404 and 500 pages

### Homepage content structure

The homepage should support:

1. Strong hero media with concise positioning and a prominent “Request a Free Quote” call to action.
2. Residential and commercial pathways.
3. A trust section populated only with verified business information.
4. Service overview.
5. Featured before-and-after work.
6. A short video showcase or project reel.
7. A clear description of the process.
8. Real testimonials managed by an admin.
9. Knoxville-area service coverage.
10. A final quote-request call to action.

### Media models and administration

Create manageable content models such as:

- `MediaAsset`
- `GalleryCollection`
- `BeforeAfterPair`
- `Service`
- `ServiceArea`
- `Testimonial`
- `FeaturedProject`

`MediaAsset` should distinguish:

- Image or video
- Title and caption
- Descriptive alt text
- Poster/thumbnail
- Residential or commercial category
- Associated customer/property/job when appropriate
- Display order
- Draft/published status
- Visibility: internal only, customer-visible, or public marketing
- Confirmation that the media is approved for marketing use
- Capture date and optional location label without exposing a private residential address
- Image dimensions, video duration, and file metadata when available

Job evidence photos must not automatically become public gallery photos. Publishing requires an explicit admin action and a marketing-approval/consent field.

### Image behavior

- Generate responsive image sizes and use `srcset`/`sizes`.
- Prefer modern formats such as AVIF or WebP when supported, with a safe fallback.
- Preserve the original file privately or in archival storage when practical.
- Set width and height or aspect ratio to prevent layout shift.
- Load the primary hero/LCP image deliberately and lazy-load below-the-fold images.
- Do not send full-resolution originals to phone-sized screens.
- Provide an accessible lightbox that works with touch, keyboard, and screen readers.
- Allow gallery filtering without making content unavailable when JavaScript fails.
- Provide an accessible before/after component with labels and a noninteractive side-by-side fallback.

### Video behavior

- Never autoplay audible video.
- Use `playsinline`, controls where appropriate, a poster image, and conservative preload behavior.
- If a muted hero background video is used, offer a pause control and a static image fallback.
- Disable decorative autoplay for reduced-motion and data-saving users.
- Support captions or transcripts for meaningful spoken content.
- Lazy-load video players and avoid loading several full videos on initial page render.
- Validate MIME type, extension, and upload limits.
- Do not transcode large videos synchronously in a web request.
- If FFmpeg-based processing is available, run thumbnail/transcoding work asynchronously. Otherwise require or generate a poster and document supported upload formats.
- Keep the storage and processing interface replaceable so direct-to-object-storage uploads or a specialist media service can be added later.

### Performance expectations

The site is media-heavy, but video and oversized photography must not block the basic page experience. Test using a throttled mobile connection. Prioritize good Core Web Vitals, stable layout, responsive media, caching, CDN-compatible URLs, and quick access to the quote action. A user should be able to read the offer and open the quote form even if optional media is still loading or fails.

### SEO and sharing

- Use semantic HTML and one clear page heading.
- Support editable page titles, meta descriptions, canonical URLs, Open Graph media, and social descriptions.
- Add appropriate local-business/service structured data using only verified business details.
- Generate sitemap and robots endpoints.
- Keep business name, phone, service areas, and URLs consistent.
- Create useful, genuine location/service content rather than doorway-page spam.
- Give every published image an intentional alt-text decision; decorative images should use empty alt text.

---

## 7. Accounts, profiles, and roles

Create a custom user model at the beginning of the project. Prefer email-based login unless existing project constraints indicate otherwise.

Each staff member has a `StaffProfile` with fields such as:

- User
- Display name
- Profile image
- Phone number
- Active/inactive status
- One or more roles
- Optional skills/certifications
- Notification preferences
- Default sales commission percentage when applicable
- Onboarding/invitation state
- Internal notes visible only to authorized admins

Primary roles are:

- **Salesperson**
- **Cleaner**
- **Admin**

A person may hold multiple roles. Implement roles using Django Groups and granular permissions, not a single mutually exclusive string field.

### Permission baseline

#### Salesperson

- Create door-to-door and other leads.
- View and manage their own assigned/created leads.
- Record visits, outcomes, notes, photos, and follow-ups.
- Build estimates within configured pricing and discount limits.
- View safe availability slots and schedule eligible jobs or on-site estimates.
- View the status of their own sales.
- View their own commission ledger.
- Cannot change their commission percentage or mark commissions paid.
- Cannot browse unrelated customers, staff pay, or full company financial data.

#### Cleaner

- View their own offered and accepted assignments.
- See enough scope, schedule, location, and compensation information to make an informed accept/reject decision.
- Accept or reject their own valid offers.
- View only customer/property data needed for assigned work.
- Update en-route, arrival, in-progress, issue, and completion statuses.
- Complete checklists and upload job photos/notes.
- View their own accepted job compensation and payout status.
- Cannot alter job pay, invoice amounts, commissions, or unrelated customer records.

#### Admin

- Full operational control subject to explicit permissions.
- Manage customers, leads, estimates, price book, schedules, jobs, assignments, invoices, payment records, commission entries, cleaner payouts, public media, staff, and settings.
- Assign and reassign work.
- Approve completion and compensation.
- View reports and audit events.

Use object-level authorization checks in services and views. Hiding a button is not authorization. Add permission tests for every sensitive workflow.

---

## 8. CRM and customer structure

Separate people, organizations, and service properties so the design supports both residential and commercial customers.

Suggested concepts:

### Customer/account

- Residential customer or commercial organization
- Status and tags
- Lead source
- Billing preferences
- Default payment terms
- Tax treatment configuration without hardcoding legal conclusions
- Marketing communication preference/consent
- Internal notes

### Contact

- Name
- Role/title
- Email
- Phone
- Preferred communication channel
- Billing contact flag
- Site contact flag
- Primary contact flag

### Property/service location

- Structured address
- Optional latitude/longitude and geocoding metadata
- Residential/commercial type
- Access and parking instructions
- Building stories and approximate window information
- Hazards or equipment requirements
- Service notes
- Customer-visible notes versus staff-only notes
- Service history
- Media and documents

One customer can own or manage multiple properties. A commercial organization can have separate billing and on-site contacts.

Do not store sensitive access instructions in push-notification bodies or broadly visible list pages.

---

## 9. Leads and door-to-door sales

Support leads from:

- Public quote form
- Door-to-door canvassing
- Phone
- Email
- Referral
- Repeat customer
- Commercial outreach
- Other configurable sources

Suggested lead states:

- New
- Contacted
- Qualified
- Follow-up due
- Estimate requested
- Estimate sent
- Won/scheduled
- Lost
- Do not contact

### Door-to-door quick capture

The salesperson’s mobile flow must be extremely fast. The first screen should require only what is necessary:

- Address, map selection, or current-location-assisted address
- Customer or business name when known
- Phone or email when provided
- Residential or commercial
- Visit outcome
- Short note
- Follow-up date/time

Allow expansion for:

- Number of stories
- Approximate window count
- Interior, exterior, or both
- Screens, tracks, sills, hard-water treatment, or other configured services
- Photos
- Preferred dates
- Preliminary estimate

Suggested visit outcomes:

- No answer
- Not interested
- Follow up later
- Interested
- Estimate requested
- Estimate sent
- Scheduled
- Existing customer
- Do not contact

Create `CanvassingTerritory`, `CanvassingSession`, and `LeadVisit` concepts if appropriate. Preserve every visit rather than overwriting history. Detect likely duplicate addresses, customers, phone numbers, and emails. Warn before creating a duplicate. Display do-not-contact and previous-visit information prominently.

Do not implement continuous salesperson tracking by default. Geolocation should be requested only for an explicit action such as using the current location or recording a visit. Document that the business must verify applicable solicitation and permit requirements for each jurisdiction.

### On-the-spot estimating and booking

From an interested lead, a salesperson should be able to:

1. Convert or link the lead to a customer and property.
2. Select services from a configurable price book.
3. Enter quantities and permitted adjustments.
4. Generate an estimate.
5. Capture customer approval or send a secure approval link.
6. View safe availability without seeing unrelated customer identities.
7. Schedule a confirmed service job or an on-site estimate.
8. Trigger customer confirmation and admin visibility.

Enforce admin-configured discount limits and approval requirements for large, commercial, difficult-access, or unusually priced jobs.

---

## 10. Price book and estimates

Create configurable services and pricing rather than embedding prices in code.

Possible services include:

- Exterior window cleaning
- Interior window cleaning
- Screen cleaning
- Tracks and sills
- Hard-water treatment
- Skylights
- Multi-story or difficult-access charges
- Recurring residential service
- Recurring commercial service

An estimate should support:

- Customer and service property
- Salesperson attribution
- Configurable line items
- Quantities, units, rates, discounts, tax settings, and notes
- Customer-visible and internal notes
- Expiration date
- Terms
- Revision history
- PDF generation
- Email delivery and delivery log
- Secure view/approve/decline link
- Optional typed signature or explicit acceptance record

Suggested states:

- Draft
- Sent
- Viewed
- Accepted
- Declined
- Expired
- Superseded

After acceptance, preserve an immutable commercial snapshot. Later price-book changes must not alter the accepted estimate. Revisions should supersede prior versions rather than silently rewriting history.

---

## 11. Scheduling

Support:

- Staff availability
- Time off
- Business hours
- Admin schedule blocks
- Job duration
- Travel buffers
- Service zones
- Required crew size or skills
- Tentative versus confirmed events
- Recurring service plans
- Rescheduling and cancellation reasons

Salespeople should see available appointment slots, not private details about other appointments.

When a slot is selected, prevent double booking with atomic database operations, constraints, and locking as appropriate. Never rely solely on a browser-side availability check.

Distinguish:

- **On-site estimate appointment:** scope or price still requires inspection.
- **Confirmed service job:** customer has approved scope and price.

Build a responsive admin calendar/list combination. The calendar must remain usable on phones, but a chronological agenda view may become the default on small screens.

---

## 12. Cleaner job offers and assignment acceptance

Cleaners are paid a fixed amount agreed for a specific assigned job. This is not a percentage of the invoice.

Model the `Job` separately from each cleaner’s `JobAssignment` or `JobOffer`. A job may eventually require multiple cleaners, so do not assume only one assignment record can ever exist.

Each assignment offer should store:

- Job
- Cleaner
- Admin who offered it
- Offered fixed amount
- Scope summary snapshot
- Scheduled start/arrival window and expected duration
- Offer status
- Offered timestamp
- Expiration timestamp
- Response timestamp
- Optional rejection reason
- Accepted terms/version
- Superseded or withdrawn relationship
- Relevant notification events

Suggested states:

- Draft
- Offered
- Accepted
- Rejected
- Expired
- Withdrawn
- Superseded
- Completed

### Required behavior

1. An admin schedules a job and selects an eligible cleaner.
2. The admin enters the agreed fixed amount and sends an offer.
3. The cleaner receives an in-app notification and, when enabled, a push notification.
4. The cleaner opens a mobile-friendly offer showing date/time, approximate duration, location, work scope, relevant requirements, and offered amount.
5. The cleaner accepts or rejects it.
6. Acceptance is recorded atomically with timestamp and terms snapshot.
7. Rejection optionally records a reason and immediately returns the job to the admin assignment queue.
8. The admin can create a new offer for another cleaner without deleting the rejected offer.
9. Expired or withdrawn offers cannot be accepted.
10. By default, allow only one active offer for a particular required crew slot. Protect against competing acceptances at the database level.
11. A material change to pay, scope, date/time, or expected duration supersedes the accepted offer and requires fresh acceptance.
12. Every offer, response, revision, withdrawal, and reassignment remains in the audit history.

The cleaner’s accepted pay amount must not change because the invoice changes. Treat it as a separate contractual snapshot for that assignment.

### Cleaner payout lifecycle

Create a `CleanerPayoutEntry` tied to the accepted assignment, with:

- Cleaner
- Assignment
- Agreed amount snapshot
- Adjustments with reason and actor
- Status
- Completion date
- Approval date and approver
- Paid date and payment reference/note

Suggested states:

- Pending
- Payable
- Paid
- Adjusted
- Reversed

For the initial implementation, cleaner pay becomes **payable after the cleaner submits completion and an admin approves the completed work**, independently of whether the customer has paid the invoice. Keep this policy centralized and documented so it can be changed deliberately later.

---

## 13. Cleaner field workflow

The cleaner PWA should emphasize speed, clarity, and large touch controls.

Primary screens:

- Offered jobs
- Offer detail with accept/reject
- Today’s assignments
- Upcoming schedule
- Job detail
- Directions/open in maps
- Customer contact action
- Checklist
- Before-and-after photo capture/upload
- Notes
- Report an issue
- Start/en-route/arrived/in-progress/complete actions
- Personal job-pay ledger
- Notifications
- Profile and notification settings

Only show the customer information necessary for the cleaner’s assigned work. Separate safe customer-visible notes, crew instructions, and admin-only notes.

Completion should require configured evidence, such as checklist items or photos, when the job/service requires it. Allow the cleaner to flag an exception rather than falsifying completion. Admins should have a queue for completion review, issues, and payout approval.

---

## 14. Sales commissions

A salesperson has a default commission percentage in their profile, but historical commissions must never be recalculated from the current profile value.

Use an effective-dated `CommissionAgreement` or equivalent and create immutable rate snapshots on attributed sales.

Create `CommissionEntry` with fields such as:

- Salesperson
- Lead
- Accepted estimate
- Related invoice/payment record
- Commission rate snapshot
- Commissionable revenue base
- Calculated amount
- Status
- Earned date
- Paid date
- Adjustment/reversal reason
- Admin actor and audit metadata

Suggested states:

- Pending
- Earned
- Paid
- Reversed

Initial policy:

- Attribute the sale to the salesperson responsible for the accepted estimate.
- Snapshot the applicable percentage when the estimate is accepted.
- Commission becomes earned when the related invoice is fully paid.
- Calculate using configured commissionable service revenue after discounts and before tax and tips.
- An admin marks the commission paid; this platform records the ledger but does not execute payroll.
- Refunds or reversals create explicit reversing entries rather than deleting history.

Keep policy choices centralized and configurable enough to support future commercial rules such as initial-sale-only commission, recurring commission, limited-duration commission, or split credit. Do not implement every future policy before the basic ledger works.

Salespeople should see:

- Booked sales
- Collected sales
- Pending commissions
- Earned commissions
- Paid commissions
- Lead funnel and conversion metrics
- Their own door-to-door activity

They must not be able to modify rate snapshots, commission bases, or paid status.

---

## 15. Jobs and completion

A job should include:

- Customer/account
- Service property
- Accepted estimate or source
- Service scope snapshot
- Scheduled window
- Expected duration
- Required crew count/skills
- Assigned staff offers/assignments
- Status
- Customer-visible notes
- Crew instructions
- Admin-only notes
- Access/safety information
- Checklist template and completed items
- Before/after media
- Arrival, start, completion, and approval timestamps
- Cancellation/reschedule information
- Recurrence relationship when applicable

Suggested job states:

- Draft
- Tentative
- Scheduled/unassigned
- Assignment pending
- Confirmed
- En route
- In progress
- Completion submitted
- Approved/completed
- Canceled

Use explicit validated transitions. Do not let arbitrary form posts jump between incompatible states.

---

## 16. Invoices without Stripe

Do not implement Stripe yet. Build a complete provider-neutral invoice system that can later connect to a payment gateway.

An invoice should support:

- Concurrency-safe unique invoice number
- Customer and organization snapshot
- Billing and service address snapshots
- One or more related jobs where appropriate
- Issue date and due date
- Commercial payment terms such as due on receipt, Net 15, or Net 30
- PO number
- Line-item snapshots
- Quantities, rates, discounts, tax settings, deposits, credits, and adjustments
- Subtotal, tax, total, amount paid, and balance due
- Customer-visible notes and payment instructions
- Internal notes
- PDF generation
- Email delivery
- Secure customer portal link
- Delivery, view, revision, and status event history

Suggested invoice states:

- Draft
- Issued
- Sent
- Viewed
- Partially paid
- Paid
- Overdue
- Void

Use `Decimal`, never floating-point values, for money. Put calculations in tested domain services. Use database constraints where appropriate.

Once issued, an invoice must be treated as an accounting record. Correct it with a controlled revision, void, credit, or replacement workflow rather than silently overwriting financial history.

### Manual payment records

Until a payment portal is added, admins can record:

- Cash
- Check
- Bank transfer
- External card payment
- Other configured method

Each payment record should include amount, received date, method, reference, notes, recorder, status, and audit data. Partial payments update the invoice balance. Reversals remain visible.

The customer invoice page should show the invoice, payment history, balance, downloadable PDF, and configured offline payment instructions. It must not show a fake payment button.

### Invoice delivery

- Generate a branded, print-friendly PDF using the FirstGlanceKnox logo and palette.
- Queue invoice email rather than blocking the request.
- Store email attempts and outcomes.
- Support resend with audit history.
- Provide configurable templates for invoice issued, reminder, overdue, and receipt messages.
- Do not send real email in tests or default development configuration.

Design a narrow payment-provider interface or integration boundary for later use, but keep it dormant until a provider is intentionally selected.

---

## 17. Customer portal

Provide a responsive customer experience for:

- Viewing and approving/declining estimates
- Viewing upcoming appointments
- Viewing job status when appropriate
- Viewing/downloading invoices
- Viewing payment records and balance
- Viewing service history
- Requesting repeat service
- Updating permitted contact preferences

Support secure expiring signed links for simple estimate/invoice access and optionally authenticated customer accounts. Do not put sequential database IDs in public URLs. Define expiration, revocation, and single-use behavior where relevant.

The customer portal must be simpler than the staff system and must never expose internal notes, cleaner pay, sales commission, staff schedules, or other customers.

---

## 18. Notifications and crew PWA

Create one persistent in-app `Notification` record as the source of truth, then fan out to allowed channels.

Suggested models:

- `Notification`
- `NotificationPreference`
- `PushSubscription`
- `NotificationDeliveryAttempt`

Each notification should have recipient, type, title, safe body, related object, deep link, created/read timestamps, priority, and delivery results.

### Important notification events

#### Salesperson

- Follow-up due
- Estimate viewed
- Estimate accepted/declined
- Job scheduled or canceled
- Invoice paid
- Commission earned, adjusted, or marked paid

#### Cleaner

- New job offer
- Offer expiring
- Offer withdrawn or revised
- Assignment confirmed
- Tomorrow’s schedule
- Schedule or scope changed
- Customer cancellation
- Completion approved or returned for correction
- Cleaner pay marked payable or paid

#### Admin

- New lead
- Estimate requiring approval
- Job awaiting assignment
- Cleaner accepted/rejected/failed to respond
- Scheduling conflict
- Job issue
- Completion awaiting approval
- Invoice overdue
- Customer payment recorded/reversed
- Commission or payout exception

#### Customer

- Estimate ready
- Appointment confirmation/reminder
- Schedule change
- On-the-way notice
- Job completion
- Invoice issued/reminder
- Payment receipt
- Review request

### PWA requirements

- Web app manifest with approved icon assets
- Installable crew experience
- Service worker with versioned cache strategy
- App shell and useful fallback when offline
- Push-subscription onboarding after an explicit user action
- In-app fallback when push is unsupported or denied
- Notification deep links
- Badge count when supported
- Clear subscription/device management
- Logout clears user-specific caches and invalidates or detaches push subscriptions

On iPhone/iPad, explain within onboarding that push requires adding the web app to the Home Screen and then enabling notifications. Use feature detection rather than user-agent assumptions.

Push content must be privacy-conscious. For example, use “Your job assignment was updated” rather than putting gate codes or sensitive addresses on the lock screen.

### Limited offline behavior

At minimum:

- Cache the app shell.
- Cache a deliberately limited summary of the signed-in cleaner’s current assignments.
- Permit door-to-door quick leads and simple job status/notes to enter a local outbox when offline.
- Synchronize queued work when connectivity returns.
- Show clear unsynced/conflict state.
- Avoid caching the entire customer database or unnecessary sensitive details.
- Treat large photo/video uploads separately with visible retry state.
- Never claim an update is saved to the server until synchronization succeeds.

---

## 19. Commercial-account readiness

The initial product can focus on residential operations, but the structure must support:

- Organizations with multiple properties
- Separate billing and site contacts
- Multiple authorized contacts
- Recurring service contracts
- Monthly, quarterly, or custom schedules
- Purchase-order numbers
- Net payment terms
- Consolidated or property-specific invoicing
- Contract, W-9, and certificate-of-insurance document storage
- Site access and safety requirements
- After-hours service windows
- Completion photos/reports
- Commercial-specific price-book entries

Do not overbuild contract automation in the first milestone. Ensure that residential-only assumptions are not embedded in core tables or permissions.

---

## 20. Admin and crew interface inventory

### Shared staff features

- Secure login/logout/password reset
- Profile
- Notification center
- Role-aware navigation
- Search within authorized objects
- Helpful empty/error/offline states

### Salesperson screens

- Personal dashboard
- Quick lead
- Territory/map or address-assisted canvassing view
- Lead list and detail
- Follow-up queue
- Estimate builder
- Customer approval/send action
- Availability and booking
- Personal sales funnel
- Personal commission ledger

### Cleaner screens

- Offered jobs
- Offer detail and accept/reject
- Today’s work
- Upcoming schedule
- Job detail
- Directions/contact
- Job checklist
- Photo upload/camera capture
- Notes/issues
- Job completion
- Personal cleaner-pay ledger

### Admin screens

- Operational dashboard
- Customer and organization CRM
- Properties and contacts
- Lead and follow-up pipeline
- Canvassing territories/activity
- Price book
- Estimate approval and history
- Calendar and agenda
- Unassigned jobs and assignment offer queue
- Completion-review queue
- Invoice editor/list/aging
- Manual payment records
- Commission review/payment reporting
- Cleaner payout review/payment reporting
- Staff and permissions
- Marketing pages, media, galleries, testimonials, and service areas
- Business/invoice/email/notification settings
- Audit log and reports

Keep Django Admin available for trusted technical administration, but build a purpose-designed operations interface for daily business work.

---

## 21. Reporting

Provide useful initial reports without building a generic business-intelligence system:

- New leads by source
- Door-to-door visits and outcomes
- Lead-to-estimate conversion
- Estimate acceptance rate
- Booked versus collected sales by salesperson
- Pending, earned, and paid commissions
- Offered, accepted, rejected, completed, payable, and paid cleaner assignments
- Upcoming and completed jobs
- Invoice aging and outstanding balance
- Revenue by service and residential/commercial segment
- Repeat customers and customers due for recurring service

Respect permissions and use the same financial/domain services as operational screens so report totals do not drift.

---

## 22. Accessibility

Target WCAG 2.2 AA for public and authenticated interfaces.

Required practices:

- Semantic landmarks and headings
- Keyboard access to navigation, dialogs, gallery, before/after controls, calendars, and menus
- Visible focus styles
- Correct labels, descriptions, errors, and instructions for forms
- Sufficient color contrast
- Status not conveyed by color alone
- Alt text workflow for images
- Captions/transcripts for meaningful video
- Reduced-motion support
- Accessible authentication and validation errors
- Announced dynamic updates for HTMX/offline synchronization where appropriate
- Accessible PDF structure as far as the chosen PDF tool permits, plus an equivalent HTML invoice view

Run automated accessibility checks and perform keyboard/manual checks for critical workflows.

---

## 23. Security, privacy, and reliability

Protect customer addresses, phone numbers, property instructions, staff commissions, and cleaner pay.

Implement and test:

- CSRF protection
- Secure sessions and cookies in production
- HTTPS-only production behavior
- Role and object-level authorization
- Rate limiting for login, public quote, and secure-link endpoints
- Secure password reset and invitation flows
- Expiring/revocable public tokens
- File type, size, and content validation
- Randomized storage names rather than trusting upload names
- Separation of public marketing media from private job evidence
- Audit events for sensitive state and money changes
- Idempotent background tasks
- Duplicate-send protection for email/push
- Safe webhook/integration boundary for future use
- Environment-based secrets and settings
- Structured logging without leaking PII or tokens
- Error monitoring hook that is disabled until configured
- Database and object-storage backup documentation
- Data retention/deactivation behavior

Use Django’s production deployment checks and document the release checklist. Do not expose development debug pages in production.

---

## 24. Important business invariants

Enforce these in domain services, tests, and database constraints where practical:

1. An accepted estimate preserves its line items, rates, terms, and salesperson/rate attribution.
2. A staff profile commission change cannot alter historical commission entries.
3. A cleaner’s accepted fixed pay cannot change silently.
4. A material assignment change requires a new or superseding offer and fresh acceptance.
5. Rejected, expired, withdrawn, or superseded offers cannot be accepted.
6. Reassigning a job does not erase prior offers or responses.
7. Cleaner pay is independent of the customer invoice amount and customer payment timing.
8. Cleaner pay becomes payable only after configured completion approval in the initial policy.
9. Sales commission becomes earned only according to the configured payment rule; initially, full invoice payment.
10. Issued invoices are not silently edited.
11. Invoice, commission, payment, and payout reversals remain visible.
12. Invoice totals and balances use exact decimal arithmetic.
13. Availability shown to a salesperson cannot override a conflicting confirmed booking.
14. A cleaner cannot access an unassigned customer merely by guessing a URL.
15. Job photos remain private unless deliberately approved and published for marketing.
16. Public quote spam cannot create unlimited expensive media or notification work.

---

## 25. Core workflows to implement and test

### Workflow A: Public residential lead

1. Customer opens a fast media-rich homepage.
2. Customer submits detailed quote request.
3. System creates or matches customer/property and creates a lead.
4. Admin/salesperson receives notification.
5. Salesperson qualifies and creates estimate.
6. Customer securely views and accepts estimate.
7. Job enters scheduling/assignment flow.

### Workflow B: Door-to-door sale

1. Salesperson opens Quick Lead on phone.
2. Address is entered or assisted by current location.
3. System checks duplicate/do-not-contact history.
4. Salesperson records visit outcome.
5. Interested prospect becomes customer/property.
6. Salesperson creates estimate within pricing rules.
7. Customer approves or receives secure link.
8. Salesperson chooses an allowed open slot.
9. Job is created with salesperson attribution.

### Workflow C: Cleaner assignment

1. Admin selects scheduled job, cleaner, and fixed offered amount.
2. Cleaner is notified.
3. Cleaner reviews complete offer details.
4. Cleaner accepts or rejects.
5. Rejection returns job to assignment queue and preserves history.
6. Acceptance confirms assignment and locks terms.
7. Material change requires reacceptance.

### Workflow D: Completion and invoice

1. Cleaner works through job states and checklist.
2. Cleaner uploads required evidence and submits completion.
3. Admin approves or returns the job with a documented issue.
4. Approval makes cleaner compensation payable.
5. Admin creates invoice from job/estimate snapshots.
6. Invoice PDF is generated and email queued.
7. Admin records full or partial manual payment.
8. Customer portal shows accurate balance and history.

### Workflow E: Commission and payout

1. Invoice becomes fully paid.
2. Sales commission entry becomes earned using saved rate/base snapshots.
3. Admin includes earned commission in a payment report and marks it paid.
4. Cleaner payout, already payable after approved completion, is separately marked paid.
5. Both ledgers retain audit history and are visible only to authorized people.

### Workflow F: Commercial recurring customer

1. Admin creates organization, contacts, properties, terms, and recurring service plan.
2. Visits are generated/scheduled without duplicating the organization.
3. Each job follows assignment and completion workflow.
4. Invoice supports PO/terms and the correct billing contact.
5. Service history and documents remain organized by organization/property.

---

## 26. Test strategy

Build tests alongside implementation.

### Domain/unit tests

- Money calculations and rounding
- Estimate snapshot behavior
- Invoice totals, partial payments, balances, void/reversal behavior
- Commission rate snapshots and earning trigger
- Cleaner pay snapshots and payable trigger
- Assignment state transitions
- Stale/expired/withdrawn offer rejection
- Double-acceptance prevention
- Scheduling conflict prevention
- Recurring-job generation idempotency
- Notification deduplication

### Permission tests

- Salesperson cannot view another salesperson’s private leads unless permitted.
- Cleaner cannot view unassigned jobs or customer records.
- Cleaner cannot edit pay.
- Salesperson cannot edit commission rate or paid status.
- Customer cannot view internal notes or another customer’s portal objects.
- Admin-only financial and staff actions reject unauthorized requests.

### Integration tests

- Lead-to-estimate-to-job conversion
- Door-to-door quick capture and deduplication
- Customer estimate approval
- Assignment offer/accept/reject/reassign
- Job completion/admin approval
- Invoice generation/email queue/manual payment
- Commission and cleaner payout lifecycle
- Media publish approval boundary
- Secure token expiration/revocation

### End-to-end tests

Use representative phone, tablet, and desktop viewports. Test critical workflows with keyboard and touch-sized targets. Verify no major overflow, inaccessible menu, unreachable action, hidden validation error, or unusable table.

### Performance/media tests

- Responsive image variants are selected.
- Below-fold media is lazy-loaded.
- Hero fallback works.
- Missing media does not break the page.
- Video does not autoplay with audio.
- Reduced-motion/data-saving behavior is respected where detectable.
- Gallery remains navigable with keyboard and touch.

---

## 27. Development fixtures and demo data

Provide safe synthetic demo data and a documented command to create it:

- One admin
- One salesperson
- One cleaner
- One user with multiple roles
- Residential and commercial customers
- Multiple properties
- Leads in several states
- An accepted and declined estimate
- An offered, accepted, rejected, and expired cleaner assignment
- Jobs in upcoming, active, completion-review, and completed states
- Draft, sent, partial, paid, overdue, and void invoice examples
- Pending/earned/paid commission entries
- Pending/payable/paid cleaner payout entries
- Public and private media examples using clearly marked placeholders

Never use real customer information or fabricate public-facing testimonials as if genuine.

---

## 28. Implementation milestones

Implement in this order unless repository conditions justify a documented change.

### Milestone 0: Discovery and project foundation

- Inspect repository and assets.
- Record architecture decisions.
- Establish settings, environment configuration, PostgreSQL, testing, linting, static/media setup, and development commands.
- Create custom user model before initial production migrations.
- Add base responsive layout and brand tokens.
- Establish CI-friendly checks.

### Milestone 1: Accounts, roles, CRM, and audit foundation

- Staff profiles and multi-role permissions
- Customer/organization/contact/property models
- Authentication/invitations/password reset
- Object-level authorization patterns
- Audit-event foundation
- Synthetic fixtures

### Milestone 2: Media-heavy public site

- Public navigation/footer and page system
- Homepage and residential/commercial pages
- Services, service areas, testimonials
- Media assets, gallery, before/after, videos
- Quote form
- SEO, accessibility, responsive media, and performance checks

### Milestone 3: Leads, canvassing, estimates, and booking

- Lead pipeline
- Door-to-door quick capture
- Visit history, duplicate/do-not-contact behavior
- Price book and estimate builder
- Secure customer approval
- Availability and on-the-spot booking
- Salesperson mobile dashboard

### Milestone 4: Scheduling, cleaner offers, and crew PWA

- Schedule/agenda
- Availability/time off/blocks
- Job models and state transitions
- Fixed-pay assignment offers
- Accept/reject/reassign/revise workflow
- Cleaner mobile screens
- Manifest/service worker/install experience
- In-app and push notifications

### Milestone 5: Completion, invoices, and compensation

- Checklists/photos/issues/completion review
- Cleaner payout ledger
- Invoice editor, numbering, totals, PDFs, and email
- Manual payment records and invoice aging
- Sales commission ledger
- Customer invoice/appointment portal

### Milestone 6: Commercial readiness, offline behavior, reports, and hardening

- Multi-property organization workflows
- Recurring services and commercial terms/documents
- Limited offline outbox and safe caching
- Reports
- Full permission audit
- Responsive and accessibility sweep
- Performance and media sweep
- Deployment/backups/operations documentation

At the end of each milestone:

1. Run tests and checks.
2. Render or open the important pages at phone, tablet, and desktop widths.
3. Fix visible layout problems rather than merely reporting them.
4. Update documentation and the implementation checklist.
5. Summarize what works, what remains, assumptions made, and the next milestone.

---

## 29. Definition of done for the initial functional release

The initial release is not complete until all of the following are true:

- The public site presents real supplied photos/videos professionally and loads acceptably on a phone connection.
- Residential and commercial customers can submit a quote request.
- Admins can manage customers, organizations, properties, leads, services, and media.
- Salespeople can capture door-to-door leads and schedule eligible jobs from a phone.
- Estimates can be created, emailed, viewed, and accepted securely.
- Admins can schedule jobs and send cleaners fixed-pay offers.
- Cleaners can accept or reject offers from the installed web app.
- Rejected offers can be reassigned without losing history.
- Cleaners can complete assigned work with checklists, notes, and photos.
- Admins can approve completion and cleaner pay becomes payable.
- Branded invoices can be created, rendered as PDF, emailed, viewed, and tracked.
- Admins can record partial/full manual payments.
- Sales commissions use historical percentage snapshots and earn according to the configured rule.
- Cleaners and salespeople can view only their own authorized compensation records.
- In-app notifications work, and push behavior works when browser/device support and permission are available.
- Critical workflows work at phone, tablet, and desktop widths.
- Permission, financial, state-transition, and responsive end-to-end tests pass.
- Production configuration, backup expectations, and deployment steps are documented.
- No live payment processor is implied or implemented.

---

## 30. Start now

Begin by inspecting the repository and supplied FirstGlanceKnox logo/media. Then:

1. Report the current repository state concisely.
2. Identify any true blockers.
3. Create or update the implementation checklist and architecture documents.
4. Propose the exact first vertical slice.
5. Immediately implement that slice unless a blocking choice is required.

Favor a reliable, understandable system the owner can actually use over speculative complexity. Preserve clean extension points for payments, accounting, SMS, routing, and deeper commercial automation, but make the core lead-to-job-to-invoice workflow functional first.
