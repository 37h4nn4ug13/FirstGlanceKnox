# Architecture

## Application structure

| Component | Responsibility |
| --- | --- |
| `config` | Environment, routing, middleware, Celery setup, business context |
| `accounts` | Email-based users, staff invitations, roles, preferences, push subscriptions, offline API |
| `marketing` | Public content, consent-controlled media, gallery, quote form |
| `operations` | Authoritative CRM, estimates, bookings, offers, billing, compensation, notifications |
| `portal` | Customer document access, PDF presentation, repeat requests, private evidence |

Django templates render the interfaces. `static/css/site.css` styles public pages; `static/css/crew.css` styles operations. Small JavaScript modules provide navigation, galleries, and the offline outbox. There is no separate frontend build.

## Data and business rules

Operations views validate forms and call explicit functions in `operations/services.py`. Domain functions check authorization, reload affected rows, and wrap state transitions in atomic transactions. Accepted estimate/offer snapshots and issued invoice snapshots protect historical terms. Database constraints supplement service validation.

PostgreSQL is the intended production database. The development database is SQLite; `select_for_update` does not provide production concurrency guarantees there. A singleton scheduling lock serializes schedule reservations in PostgreSQL. Production also requires shared Redis for rate limiting and Celery work.

## Delivery and storage

Notifications are database records. Optional Web Push sends generic notifications through configured VAPID settings. Estimate/invoice emails use the persistent `OutboundMessage` outbox, with attempt counts and delivery timestamps. Local email delivery writes files.

Public image derivatives use Django's configured storage; private originals and job evidence use private filesystem roots. Production private storage, backup, and authenticated retrieval must be verified independently of public media storage.

The crew service worker caches a limited shell. Sensitive authenticated HTML is not intended for general offline caching. Per-user device storage retains a small summary and an outbox; the server verifies the user and records an idempotency receipt for each synchronized update.
