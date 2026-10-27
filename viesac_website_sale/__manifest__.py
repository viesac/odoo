# -*- coding: utf-8 -*-
{
    'name': 'VIESAC: eCommerce EU VIES & VAT Checkout',
    'version': '18.0.1.0.1',
    'category': 'Website/Website',
    'summary': 'Real-time EU VIES and global VAT number validation on eCommerce checkout',
    'description': """
VIESAC eCommerce EU VIES & VAT Checkout for Odoo
================================================

Automated VAT validation on the customer billing address step in Odoo eCommerce.

Key Features
------------
* Real-time EU VIES (VAT Information Exchange System) registration check for B2B customers.
* Supports intra-community EU transactions, UK HMRC, Norway, Switzerland, Australia and worldwide VAT formats.
* Seamless integration with Odoo fiscal positions for zero-rated reverse charge tax treatment (0% VAT).
* Session rate-limiting and intelligent cart caching to prevent scraping and abuse.
* Secure and privacy-focused: offline format checks are explicitly marked unverified.
* Back-office access to complete audit records and EORI checks via VIESAC Compliance module.

Countries & Identifiers Supported
---------------------------------
* All 27 EU Member States: Austria (AT), Belgium (BE), Bulgaria (BG), Croatia (HR), Cyprus (CY),
  Czech Republic (CZ), Denmark (DK), Estonia (EE), Finland (FI), France (FR), Germany (DE),
  Greece (EL), Hungary (HU), Ireland (IE), Italy (IT), Latvia (LV), Lithuania (LT),
  Luxembourg (LU), Malta (MT), Netherlands (NL), Poland (PL), Portugal (PT), Romania (RO),
  Slovakia (SK), Slovenia (SI), Spain (ES), Sweden (SE), plus Northern Ireland (XI).
* Non-EU Registries: United Kingdom (GB HMRC), Norway (NO BRREG), Switzerland (CH UID),
  Australia (AU ABN), Turkey (TR GİB), Serbia (RS PURS), UAE (AE FTA).
* Local Terms: USt-IdNr, TVA intracommunautaire, Partita IVA, NIF, CIF, NIP, BTW, MVA, Moms, ABN.

Keywords: VIES, VAT, Checkout, eCommerce, B2B, Reverse Charge, 0% VAT, Intra-Community,
Web store, Tax exemption, Cart VAT check, B2B checkout, VAT validation, Fiscal position.
    """,
    'author': 'VIESAC',
    'website': 'https://viesac.eu',
    'license': 'LGPL-3',
    'price': 0.0,
    'currency': 'EUR',
    'images': [
        'static/description/banner.png',
        'static/description/screenshot_checkout.png',
    ],
    'depends': [
        'viesac_vat_compliance',
        'website_sale',
    ],
    'data': [
        'views/templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'viesac_website_sale/static/src/css/checkout_vat.css',
            'viesac_website_sale/static/src/js/checkout_vat.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
