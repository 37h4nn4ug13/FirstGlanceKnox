# Production release gates

No deployment has been performed. The current Django application is a local project and is not configured as a hosted Sites/Cloudflare Worker application.

## Required infrastructure and configuration

- PostgreSQL `DATABASE_URL`, shared Redis `REDIS_URL`, an independently generated `SECRET_KEY`, and `DEBUG=false`.
- Exact `ALLOWED_HOSTS`, HTTPS `SITE_URL`, and trusted CSRF origins. Enable the proxy HTTPS setting only when the trusted proxy strips untrusted forwarding headers.
- A Python WSGI host, Celery worker, and one Celery Beat scheduler for maintenance. Production worker topology must be validated on the chosen host.
- `collectstatic`, database migrations, durable private/public media storage, backups, and a tested restore procedure.
- Explicit production email configuration and sender verification; enable task dispatch only after provider authorization and delivery checks.
- Optional VAPID keys/subject and push configuration, with real-device tests. Keep private keys and account data out of source control.

## Verification before launch

1. Validate simultaneous booking, offer acceptance/withdrawal, invoice numbering, payment retries/reversals, and recurring visit generation against PostgreSQL. SQLite tests do not prove lock behavior.
2. Run `manage.py check --deploy` using the real production configuration. Verify secure cookies, HTTPS redirects, trusted hosts/proxy behavior, shared throttling, and private-file isolation.
3. Verify outbox retries, token revocation, attachment rendering, and provider failures. Delivery cannot promise exactly-once behavior across a crash after provider acceptance but before a database commit.
4. Test customer/staff invitation and recovery journeys, full permission boundaries, and customer-safe PDF content/layout.
5. Test PWA installation, logout/account switching, offline duplicate/conflict recovery, and push on supported real devices and browsers. Current browser checks use Chromium only.
6. Replace temporary imagery and demo prices; supply verified contact details, approved testimonials, service coverage, privacy policy, and terms.
7. Complete the remaining workflow scope in [checklist.md](checklist.md), including draft/revision editing and recurring-plan administration.

Use synthetic data for staging and never expose the local demo database or `.local/demo-access.txt`. Deployment, real customer messaging, and payment integrations require explicit user authorization under the project brief.
