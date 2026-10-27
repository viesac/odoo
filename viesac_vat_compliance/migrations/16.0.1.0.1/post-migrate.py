import re

from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    params = env['ir.config_parameter']
    locale = params.get_param('viesac.certificate_locale')
    if locale in ('cs', 'el'):
        params.set_param('viesac.certificate_locale', {'cs': 'cz', 'el': 'gr'}[locale])
    env['res.partner'].search([('viesac_official_source', '=', 'FORMAT_CHECK_ONLY')]).write({
        'viesac_vat_status': 'unverified', 'viesac_consultation_number': False,
        'viesac_last_reference': False,
    })
    for audit in env['viesac.audit.log'].search([]):
        document = audit.move_id or audit.sale_order_id or audit.purchase_order_id
        if document and audit.company_id != document.company_id:
            audit.company_id = document.company_id
    # Repair only the connector's legacy escaped notifications, preserving author,
    # timestamp and destination. Rebuild from audit fields instead of trusting HTML.
    messages = env['mail.message'].search([('body', 'ilike', 'VIESAC Tax')])
    for message in messages:
        if '&lt;div' not in message.body or 'Customs Verification Completed' not in message.body:
            continue
        reference = re.search(r'VAC-[A-Z0-9-]+', message.body)
        if reference:
            audit = env['viesac.audit.log'].search([('name', '=', reference.group())], limit=1)
            if audit:
                message.write({'body': audit._notification_body()})
