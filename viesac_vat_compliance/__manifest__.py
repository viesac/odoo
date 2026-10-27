# -*- coding: utf-8 -*-
{
    'name': 'VIESAC: EU VIES VAT, GST & EORI Compliance',
    'version': '17.0.1.0.3',
    'category': 'Accounting/Accounting',
    'summary': 'EU VIES VAT validation, Global Tax Checks, EORI, Audit Certificates & Rates',
    'description': """
VIESAC EU VIES VAT, GST & EORI Connector for Odoo
=================================================

Automated VAT validation and compliance for the European Union (VIES) and global tax authorities.

Key Features
------------
* Real-time EU VIES (VAT Information Exchange System) validation with official consultation numbers.
* Multi-registry verification across the EU, UK, Norway, Switzerland, Australia, Turkey, Serbia, UAE and more.
* Back-office EORI number verification for cross-border logistics and customs declarations.
* Automated audit logs linked to Contacts (res.partner), Sales Orders (sale.order), Purchase Orders (purchase.order) and Invoices (account.move).
* Downloadable official PDF Audit Certificates in 23 languages and tamper-evident SHA-256 XML evidence records.
* Flexible compliance policies: delivery holds on pending audits, vendor bill warnings or strict blocking of invalid suppliers.
* Automated daily rates catalog covering 115+ countries and EU destination VAT rate review.
* Background scheduled polling and HMAC-SHA256 signed webhook synchronization.

Supported Countries & Tax Authorities
-------------------------------------
* European Commission VIES (All 27 EU Member States):
  Austria (AT), Belgium (BE), Bulgaria (BG), Croatia (HR), Cyprus (CY), Czech Republic (CZ),
  Denmark (DK), Estonia (EE), Finland (FI), France (FR - DGFiP / VIES), Germany (DE - BZSt / VIES),
  Greece (EL / GR), Hungary (HU - NAV), Ireland (IE), Italy (IT - Agenzia delle Entrate),
  Latvia (LV), Lithuania (LT), Luxembourg (LU), Malta (MT), Netherlands (NL), Poland (PL),
  Portugal (PT), Romania (RO - ANAF), Slovakia (SK), Slovenia (SI), Spain (ES - AEAT), Sweden (SE),
  plus Northern Ireland (XI).
* United Kingdom (GB) - HM Revenue & Customs (HMRC)
* Norway (NO) - Brønnøysundregistrene (BRREG) & Skatteetaten (MVA)
* Switzerland & Liechtenstein (CH, LI) - Federal Tax Administration (ESTV / UID)
* Australia (AU) - Australian Business Register (ABR / ATO - ABN / GST)
* Turkey (TR) - Gelir İdaresi Başkanlığı (GİB)
* Serbia (RS) - Poreska uprava (PURS / PIB)
* United Arab Emirates (AE) - Federal Tax Authority (FTA / TRN)
* Worldwide: Offline statutory format and checksum validation for 115+ jurisdictions.

Supported National Tax Identifiers & Local Terms
------------------------------------------------
* Germany & Austria: USt-IdNr (Umsatzsteuer-Identifikationsnummer), UID, MwSt
* France, Belgium, Luxembourg: Numéro de TVA, TVA intracommunautaire
* Italy: Partita IVA (P.IVA), Codice Fiscale
* Spain: NIF, CIF, Número de Identificación Fiscal, IVA
* Poland: NIP (Numer Identyfikacji Podatkowej)
* Netherlands & Belgium: Btw-nummer, Btw-identificatienummer
* Sweden & Denmark: Momsnummer, CVR
* Norway: MVA (Merverdiavgift), Foretaksregisteret, Organisasjonsnummer
* Switzerland: UID (Unternehmens-Identifikationsnummer), MWST / TVA / IVA
* Czech Republic & Slovakia: DIČ, IČ DPH
* Romania: CUI, CIF (Cod de Înregistrare Fiscală)
* Hungary: Adószám, Közösségi adószám
* United Kingdom: UK VAT Registration Number (HMRC)
* Australia: ABN (Australian Business Number), GST
* United Arab Emirates: TRN (Tax Registration Number)
* Turkey: VKN (Vergi Kimlik Numarası)
* Serbia: PIB (Poreski identifikacioni broj)
* Customs: EORI (Economic Operators Registration and Identification)

Keywords: VIES, VAT, EORI, GST, Tax, VAT check, VIES validator, VAT validation,
Reverse charge, Intra-community, Tax exemption, One Stop Shop, OSS, Audit certificate,
Tax compliance, Delivery hold, Vendor bill validation, HMRC, BRREG, ESTV, UID, ABN, FTA.

Requires a VIESAC API key for live checks and audits. Audit creation consumes
VIESAC account credits. Certificate languages are selected from the 23 API locales.
One API account is shared by the Odoo database; audit access is restricted by company.
Tax exemptions and OSS reporting require Odoo accounting localization configuration.
The module does not determine legal eligibility for a tax exemption or guarantee audit outcomes.
Uses the requests library included with Odoo.
    """,
    'author': 'VIESAC',
    'website': 'https://viesac.eu',
    'license': 'LGPL-3',
    'price': 0.0,
    'currency': 'EUR',
    'images': [
        'static/description/banner.png',
        'static/description/screenshot_customers.jpg',
        'static/description/screenshot_audit.jpg',
        'static/description/screenshot_invoices.jpg',
        'static/description/screenshot_orders.jpg',
    ],
    'depends': [
        'base',
        'mail',
        'contacts',
        'account',
        'base_vat',
        'sale_management',
        'purchase',
        'sale_stock',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/company_rules.xml',
        'data/ir_cron_data.xml',
        'views/res_config_settings_views.xml',
        'views/res_partner_views.xml',
        'views/sale_order_views.xml',
        'views/purchase_order_views.xml',
        'views/account_move_views.xml',
        'views/viesac_audit_log_views.xml',
        'views/viesac_vat_rate_views.xml',
        'views/report_invoice.xml',
        'wizards/viesac_bulk_check_wizard_views.xml',
        'wizards/viesac_tax_sync_wizard_views.xml',
    ],
    'external_dependencies': {'python': ['requests']},
    'installable': True,
    'application': True,
    'auto_install': False,
    'post_init_hook': 'post_init_hook',
}
