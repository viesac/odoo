# -*- coding: utf-8 -*-
import base64
import json
import hashlib
import logging
import uuid
from markupsafe import Markup
from odoo import api, fields, models
from odoo.exceptions import UserError
from .viesac_api_client import ViesacApiClient, DEFAULT_BASE_URL

_logger = logging.getLogger(__name__)


class ViesacAuditLog(models.Model):
    _name = 'viesac.audit.log'
    _description = 'VIESAC Compliance Audit Proof'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'requested_at desc, id desc'

    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company, index=True)

    name = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        default='New',
        index=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Partner',
        required=True,
        ondelete='cascade',
        index=True,
    )
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Sales Order',
        ondelete='set null',
        index=True,
    )
    purchase_order_id = fields.Many2one(
        'purchase.order',
        string='Purchase Order',
        ondelete='set null',
        index=True,
    )
    move_id = fields.Many2one(
        'account.move',
        string='Invoice / Bill',
        ondelete='set null',
        index=True,
    )

    audit_type = fields.Selection(
        selection=[
            ('vat', 'VAT / GST Only'),
            ('eori', 'EORI Customs Only'),
            ('vat_eori', 'Hybrid (VAT + EORI)'),
        ],
        string='Audit Type',
        default='vat',
        required=True,
    )
    country_code = fields.Char(string='Country Code', size=2)
    vat_number = fields.Char(string='VAT Number')
    eori_country_code = fields.Char(string='EORI Country', size=2)
    eori_number = fields.Char(string='EORI Number')

    status = fields.Selection(
        selection=[
            ('valid', 'Valid'),
            ('limited_valid', 'Limited Valid'),
            ('pending', 'Pending Confirmation'),
            ('invalid', 'Invalid'),
            ('error', 'Error'),
            ('cancelled', 'Cancelled'),
        ],
        string='Overall Status',
        default='pending',
        index=True,
        tracking=True,
    )
    vat_status = fields.Selection(
        selection=[
            ('valid', 'Valid'),
            ('limited_valid', 'Limited Valid'),
            ('pending', 'Pending Confirmation'),
            ('invalid', 'Invalid'),
            ('error', 'Error'),
        ],
        string='VAT Status',
    )
    eori_status = fields.Selection(
        selection=[
            ('valid', 'Valid'),
            ('limited_valid', 'Limited Valid'),
            ('pending', 'Pending Confirmation'),
            ('invalid', 'Invalid'),
            ('error', 'Error'),
        ],
        string='EORI Status',
    )

    official_source = fields.Char(string='Registry Source')
    consultation_number = fields.Char(string='VIES Consultation #', index=True)
    company_name = fields.Char(string='Verified Name')
    company_address = fields.Char(string='Verified Address')
    order_number = fields.Char(string='Order Number')
    invoice_number = fields.Char(string='Invoice Number')
    customs_declaration_number = fields.Char(string='Customs Declaration № (MRN)')

    requested_at = fields.Datetime(string='Timestamp (UTC)')
    certificate_url = fields.Char(string='Certificate Portal URL')
    evidence_json = fields.Text(string='Raw Verification Evidence JSON')

    pdf_attachment_id = fields.Many2one(
        'ir.attachment',
        string='VAT Certificate PDF',
        ondelete='set null',
    )
    xml_attachment_id = fields.Many2one(
        'ir.attachment',
        string='VAT Evidence XML',
        ondelete='set null',
    )
    eori_pdf_attachment_id = fields.Many2one(
        'ir.attachment',
        string='EORI Certificate PDF',
        ondelete='set null',
    )
    eori_xml_attachment_id = fields.Many2one(
        'ir.attachment',
        string='EORI Evidence XML',
        ondelete='set null',
    )

    @api.model
    def create_or_run_audit(self, partner, order=None, purchase_order=None, invoice=None, audit_type='vat', customs_number=None):
        """Creates an official audit on VIESAC API and stores audit proof with attached certificates."""
        self.check_access_rights('create')
        partner.check_access_rights('write')
        partner.check_access_rule('write')
        document = order or purchase_order or invoice
        if document:
            document.check_access_rights('write')
            document.check_access_rule('write')
        company = document.company_id if document else self.env.company
        if company not in self.env.companies:
            raise UserError('This company is not available in the current session.')
        params = self.env['ir.config_parameter'].sudo()
        api_key = params.get_param('viesac.api_key', '')
        base_url = params.get_param('viesac.base_url', DEFAULT_BASE_URL)
        if not api_key:
            _logger.info("VIESAC audit skipped: no API key configured.")
            return False

        country_code = partner.country_id.code if partner.country_id else None
        vat = partner.vat or ''
        eori = partner.viesac_eori_number or ''

        payload = {
            'type': audit_type,
            'company_name': partner.name,
            'company_address': f"{partner.street or ''} {partner.city or ''} {partner.zip or ''}".strip() or None,
            'comment': f"Odoo audit for {partner.display_name}",
        }

        if audit_type in ('vat', 'vat_eori'):
            payload['vat_number'] = vat
            if country_code:
                payload['country_code'] = ViesacApiClient.identifier_country(vat, country_code)

        if audit_type in ('eori', 'vat_eori'):
            payload['eori_number'] = eori
            if country_code:
                payload['eori_country_code'] = ViesacApiClient.identifier_country(eori, country_code)

        if order:
            payload['order_number'] = order.name
        if purchase_order:
            payload['order_number'] = purchase_order.name
        if invoice:
            payload['invoice_number'] = invoice.name or invoice.ref or None

        if customs_number:
            payload['customs_declaration_number'] = customs_number

        # Stable per-document keys survive an Odoo transaction rollback or API timeout.
        # Manual contact audits intentionally create a fresh verification.
        key_data = [params.get_param('database.uuid'), company.id, audit_type,
                    partner.id, vat, eori,
                    [document._name, document.id] if document else str(uuid.uuid4())]
        idempotency_key = 'odoo-' + hashlib.sha256(json.dumps(key_data).encode()).hexdigest()
        result = ViesacApiClient.create_audit(api_key, payload, base_url=base_url, idempotency_key=idempotency_key)
        if ('error' in result or not result.get('reference_number') or
                result.get('status') not in dict(self._fields['status'].selection)):
            _logger.error("VIESAC audit creation failed: %s", result.get('error'))
            return False

        ref = result.get('reference_number', 'AUDIT')
        vals = {
            'company_id': company.id,
            'name': ref,
            'partner_id': partner.id,
            'sale_order_id': order.id if order else False,
            'purchase_order_id': purchase_order.id if purchase_order else False,
            'move_id': invoice.id if invoice else False,
            'audit_type': audit_type,
            'country_code': result.get('country_code') or country_code,
            'vat_number': result.get('vat_number') or vat,
            'eori_country_code': result.get('eori_country_code') or country_code,
            'eori_number': result.get('eori_number') or eori,
            'status': result.get('status', 'pending'),
            'vat_status': result.get('vat_status'),
            'eori_status': result.get('eori_status'),
            'official_source': result.get('official_source'),
            'consultation_number': result.get('consultation_number'),
            'company_name': result.get('company_name'),
            'company_address': result.get('company_address'),
            'order_number': result.get('order_number'),
            'invoice_number': result.get('invoice_number'),
            'customs_declaration_number': result.get('customs_declaration_number'),
            'certificate_url': result.get('certificate_url') or f"{base_url.rstrip('/')}/app/audits/{ref}",
            'evidence_json': json.dumps(result.get('verification_evidence') or {}, indent=2),
            'requested_at': fields.Datetime.now(),
        }

        existing = self.search([('name', '=', ref), ('company_id', '=', company.id)], limit=1)
        audit_record = existing or self.create(vals)

        # Update partner status
        partner_vals = {
            'viesac_last_reference': ref,
            'viesac_last_checked_at': fields.Datetime.now(),
        }
        if result.get('official_source'):
            partner_vals['viesac_official_source'] = result['official_source']
        if audit_type in ('vat', 'vat_eori'):
            partner_vals['viesac_consultation_number'] = result.get('consultation_number') or False
        if result.get('vat_status'):
            partner_vals['viesac_vat_status'] = result['vat_status']
        if result.get('eori_status'):
            partner_vals['viesac_eori_status'] = result['eori_status']
        partner.write(partner_vals)

        # Download & attach certificates if auto-attach is enabled
        auto_attach = params.get_param('viesac.auto_attach_certificates', 'True') == 'True'
        if auto_attach:
            audit_record._download_and_attach_certificates(order=order, purchase_order=purchase_order, invoice=invoice)

        return audit_record

    def _download_and_attach_certificates(self, order=None, purchase_order=None, invoice=None):
        """Downloads official PDF and XML certificates from VIESAC and attaches to documents."""
        self.ensure_one()
        params = self.env['ir.config_parameter'].sudo()
        api_key = params.get_param('viesac.api_key', '')
        base_url = params.get_param('viesac.base_url', DEFAULT_BASE_URL)
        locale = params.get_param('viesac.certificate_locale', 'en')
        if not api_key:
            return

        target_records = []
        if invoice:
            target_records.append(invoice)
        if order:
            target_records.append(order)
        if purchase_order:
            target_records.append(purchase_order)
        if not target_records:
            target_records.append(self)

        # 1. VAT Certificates (PDF & XML)
        if self.audit_type in ('vat', 'vat_eori') and self.vat_status == 'valid':
            pdf_data = ViesacApiClient.download_certificate(
                api_key, self.name, cert_format='pdf', cert_type='vat', locale=locale, base_url=base_url
            )
            if pdf_data.get('success'):
                pdf_att = self._create_attachment(
                    filename=f"{self.name}_viesac_certificate_{self.country_code or ''}_{self.vat_number or ''}.pdf",
                    data=pdf_data['content'],
                    mimetype='application/pdf',
                    target_records=target_records,
                )
                self.pdf_attachment_id = pdf_att.id

            xml_data = ViesacApiClient.download_certificate(
                api_key, self.name, cert_format='xml', cert_type='vat', base_url=base_url
            )
            if xml_data.get('success'):
                xml_att = self._create_attachment(
                    filename=f"{self.name}_viesac_verification_evidence_{self.country_code or ''}_{self.vat_number or ''}.xml",
                    data=xml_data['content'],
                    mimetype='application/xml',
                    target_records=target_records,
                )
                self.xml_attachment_id = xml_att.id

        # 2. EORI Certificates (PDF & XML)
        if self.audit_type in ('eori', 'vat_eori') and self.eori_status == 'valid':
            eori_pdf_data = ViesacApiClient.download_certificate(
                api_key, self.name, cert_format='pdf', cert_type='eori', locale=locale, base_url=base_url
            )
            if eori_pdf_data.get('success'):
                eori_pdf_att = self._create_attachment(
                    filename=f"{self.name}_viesac_eori_certificate_{self.eori_country_code or ''}_{self.eori_number or ''}.pdf",
                    data=eori_pdf_data['content'],
                    mimetype='application/pdf',
                    target_records=target_records,
                )
                self.eori_pdf_attachment_id = eori_pdf_att.id

            eori_xml_data = ViesacApiClient.download_certificate(
                api_key, self.name, cert_format='xml', cert_type='eori', base_url=base_url
            )
            if eori_xml_data.get('success'):
                eori_xml_att = self._create_attachment(
                    filename=f"{self.name}_viesac_eori_evidence_{self.eori_country_code or ''}_{self.eori_number or ''}.xml",
                    data=eori_xml_data['content'],
                    mimetype='application/xml',
                    target_records=target_records,
                )
                self.eori_xml_attachment_id = eori_xml_att.id

        # Post message in Chatter of target records
        self._post_chatter_notification(target_records)

    def _create_attachment(self, filename, data, mimetype, target_records):
        # Attach the archive copy to the audit so company access rules also protect it.
        att_model = self.env['ir.attachment']
        targets = [self] + [target for target in target_records if target != self]
        primary = False
        for target in targets:
            domain = [('name', '=', filename), ('res_model', '=', target._name), ('res_id', '=', target.id)]
            att = att_model.search(domain, limit=1)
            vals = {'name': filename, 'type': 'binary', 'datas': base64.b64encode(data),
                    'mimetype': mimetype, 'res_model': target._name, 'res_id': target.id}
            if att:
                att.write(vals)
            else:
                att = att_model.create(vals)
            primary = primary or att
        return primary

    def _notification_body(self):
        self.ensure_one()
        # Markup escapes values received from the external registry.
        body = Markup('<p><strong>VIESAC verification</strong><br/>Status: %s<br/>Registry: %s<br/>Reference: %s</p>') % (
            (self.status or 'pending').upper(), self.official_source or '', self.name)
        if self.consultation_number:
            body += Markup('<p>Consultation number: %s</p>') % self.consultation_number
        for label, country, number in [('VAT', self.country_code, self.vat_number),
                                       ('EORI', self.eori_country_code, self.eori_number)]:
            if number:
                identifier = number if number.upper().startswith((country or '').upper()) else (country or '') + number
                body += Markup('<p>%s: %s</p>') % (label, identifier)
        if self.certificate_url:
            body += Markup('<p>Audit record: <a href="%s" target="_blank">%s</a></p>') % (self.certificate_url, self.name)
        if self.pdf_attachment_id or self.eori_pdf_attachment_id:
            body += Markup('<p>PDF certificate archived.</p>')
        if self.xml_attachment_id or self.eori_xml_attachment_id:
            body += Markup('<p>SHA-256 XML evidence archived.</p>')
        return body

    def _post_chatter_notification(self, target_records):
        body = self._notification_body()
        for rec in target_records:
            if hasattr(rec, 'message_post'):
                rec.message_post(body=body, message_type='notification')

    def _finalize_documents(self):
        self.ensure_one()
        if self.move_id:
            self.move_id.viesac_compliance_verified = self.status == 'valid'
        if self.status == 'valid' and self.sale_order_id.viesac_delivery_held:
            self.sale_order_id.write({'viesac_delivery_held': False})
            self.sale_order_id.message_post(body='VIESAC verification completed. Delivery hold released.')
        params = self.env['ir.config_parameter'].sudo()
        if params.get_param('viesac.auto_attach_certificates', 'True') == 'True':
            missing_vat = self.vat_status == 'valid' and (not self.pdf_attachment_id or not self.xml_attachment_id)
            missing_eori = self.eori_status == 'valid' and (not self.eori_pdf_attachment_id or not self.eori_xml_attachment_id)
            if missing_vat or missing_eori:
                self._download_and_attach_certificates(order=self.sale_order_id,
                    purchase_order=self.purchase_order_id, invoice=self.move_id)

    def action_refresh_status(self):
        """Fetches latest audit status from VIESAC (e.g. for pending checks)."""
        self.ensure_one()
        self.check_access_rights('write')
        self.check_access_rule('write')
        params = self.env['ir.config_parameter'].sudo()
        api_key = params.get_param('viesac.api_key', '')
        base_url = params.get_param('viesac.base_url', DEFAULT_BASE_URL)
        if not api_key:
            raise UserError('VIESAC API Key is not configured.')

        data = ViesacApiClient.get_audit(api_key, self.name, base_url=base_url)
        if 'error' in data or data.get('status') not in dict(self._fields['status'].selection):
            raise UserError(f"Status refresh failed: {data.get('error')}")

        new_status = data.get('status')
        vals = {
            'status': new_status,
            'vat_status': data.get('vat_status'),
            'eori_status': data.get('eori_status'),
            'official_source': data.get('official_source'),
            'consultation_number': data.get('consultation_number'),
            'evidence_json': json.dumps(data.get('verification_evidence') or {}, indent=2),
        }
        self.write(vals)

        # An old audit must not replace the result for an edited Tax ID or a newer audit.
        partner = self.partner_id
        if partner.viesac_last_reference == self.name:
            changes = {}
            clean = ViesacApiClient.sanitize_vat
            if clean(partner.vat) in (clean(self.vat_number), clean((self.country_code or '') + (self.vat_number or ''))):
                changes.update(viesac_vat_status=data.get('vat_status') or partner.viesac_vat_status,
                               viesac_consultation_number=data.get('consultation_number') or False,
                               viesac_official_source=data.get('official_source') or False)
            if clean(partner.viesac_eori_number) in (clean(self.eori_number), clean((self.eori_country_code or '') + (self.eori_number or ''))):
                changes['viesac_eori_status'] = data.get('eori_status') or partner.viesac_eori_status
            if changes:
                partner.write(changes)
        self._finalize_documents()

        return True

    @api.model
    def cron_refresh_open_audits(self):
        """Scheduled cron job to finalize pending or limited_valid audits."""
        pending_audits = self.search([
            ('status', 'in', ('pending', 'limited_valid')),
            ('name', '!=', False),
        ], limit=30)
        for audit in pending_audits:
            try:
                with self.env.cr.savepoint():
                    audit.action_refresh_status()
            except Exception as e:
                _logger.warning("Cron refresh failed for audit %s: %s", audit.name, e)
        return True
