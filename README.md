# VIESAC for Odoo 17 — local integration

Local URL: http://localhost:8069. Database: `viesac_test`.

## Modules and architecture

- `viesac_vat_compliance`: contacts, sales, purchases, invoices, stock delivery holds, audit archive, rates catalog and settings. Uses the existing VIESAC REST API; national validation logic stays in VIESAC.
- `viesac_website_sale`: optional checkout VAT status indicator. Checks active carts, caches recent results in the session and limits requests. Does not change fiscal positions, return company names or grant tax exemptions. EORI is handled in the back office.
- API credentials are standard Odoo configuration parameters, restricted to system administrators. One VIESAC account is shared by the database. Audit records have company access rules; shared contacts retain a shared verification status.
- Document audit requests use stable idempotency keys to tolerate retries. Manual contact audits intentionally create new checks. Audit creation consumes VIESAC credits; PDF/XML downloads depend on the account plan.
- Invoices display their own audit evidence rather than the contact's current status. Changing a VAT/EORI identifier resets the corresponding contact result.
- Pending audits refresh every 10 minutes. Rates synchronize daily. Odoo's built-in scheduler starts these jobs automatically while the container runs; no host cron setup is required.
- Webhooks are optional. Configure `/viesac/webhook` on a publicly reachable HTTPS endpoint and use the same secret in Odoo and the VIESAC portal. Requests require the VIESAC timestamped HMAC signature and a timestamp within five minutes. Notifications trigger an authoritative API refresh. Without a secret, requests return HTTP 401; polling still works.

## Start and update locally

From `C:\viesac`:

```powershell
docker compose -f docker-compose.odoo.yml up -d
```

The addon folders are mounted into Odoo at `/mnt/extra-addons`. After editing Python or XML, update the installed modules and restart the local Odoo service so its registry and views use the new code. Back up the database first when changing stored fields.

Open Accounting → Configuration → Settings → VIESAC to save the API key, test the connection, choose certificate language, supplier policy and attachment/delivery options. The API language codes for Czech and Greek are `cz` and `gr`.

## Verification

The review used a separate database, `viesac_review_20261027`, installed without demo data. Repeat the module checks with:

```powershell
docker exec viesac_odoo odoo --db_host=viesac_odoo_db --db_user=odoo --db_password=odoo -d viesac_review_20261027 -u viesac_vat_compliance,viesac_website_sale --test-enable --test-tags=/viesac_vat_compliance,/viesac_website_sale --stop-after-init --http-port=8079 --max-cron-threads=0
```

The test process disables its own cron threads; this does not disable the scheduler in the running Odoo service. Tests mock paid API operations and government checks. HTTP tests exercise the real Odoo webhook route.

## Scope and remaining limitations

- This version is verified on Odoo 17, not other major releases.
- Tax exemptions, OSS mappings/reporting, product defaults and rate changes require the appropriate Odoo accounting localization. The assistant can create a standard company tax or open rate/tax lists for review. It does not archive arbitrary taxes or claim OSS configuration is complete.
- Bulk checks are synchronous. Use small selections; a durable background queue is a separate improvement for large batches.
- Certificate selection covers the 23 VIESAC API locales. Existing Odoo translation files cover seven languages and do not yet translate every revised label; English fallback remains possible.
- A certificate download can fail independently of a successful audit, including on a plan without download access. The audit remains available; “Refresh from VIESAC” can retry missing attachments. A SHA-256 hash is not a digital signature.
- The Compose passwords are development values, and HTTP is bound to the local loopback interface. This file is for local use.
