# Changelog

## 17.0.1.0.2

- Preserve Odoo local VAT syntax/checksum validation and prevent duplicate native online VIES calls when VIESAC is configured and enabled.
- Disable the native company online-check option on installation, with an upgrade migration for existing installations.
- Add tests for native-validation handover, typo rejection, checksum rejection and fallback behavior.
- Replace illustrative interface images with five actual Odoo demo screenshots.
- Refresh both app descriptions with inline VIESAC styling, local outline icons and accurate feature copy.
- Widen Verify VAT and keep its label on one line; use a concise certificate link label.
- Do not cache temporary checkout API errors; handle delivery-address forms without a VAT field.
- Verify 37 connector tests on Odoo 17.
