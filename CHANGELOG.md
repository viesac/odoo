# Changelog

## 17.0.1.0.4

- Add explicit inline margins and text spacing between feature badges in both app descriptions, including wrapped rows.

## 17.0.1.0.3

- Restore and preserve the original feature covers for both modules.
- Update both app descriptions with VIESAC styling, inline CSS and explicit spacing between sections/cards.
- Replace illustrative interface images with real demo screenshots, centered and limited to 720 px.
- Remove the Official connector / Odoo 17 header line.
- Preserve standard local VAT syntax/checksum validation and prevent duplicate native VIES network calls when VIESAC is configured and enabled.
- Disable the native company online-check option on installation and provide an upgrade migration.
- Widen Verify VAT and keep the label on one line.
- Do not cache temporary checkout API errors; support delivery forms without a VAT field.
- Apply version-specific view, hook and checkout adapters.

## 17.0.1.0.2

- Preserve Odoo local VAT syntax/checksum validation and prevent duplicate native online VIES calls when VIESAC is configured and enabled.
- Disable the native company online-check option on installation, with an upgrade migration for existing installations.
- Add tests for native-validation handover, typo rejection, checksum rejection and fallback behavior.
- Replace illustrative interface images with five actual Odoo demo screenshots.
- Refresh both app descriptions with inline VIESAC styling, local outline icons and accurate feature copy.
- Widen Verify VAT and keep its label on one line; use a concise certificate link label.
- Do not cache temporary checkout API errors; handle delivery-address forms without a VAT field.
- Verify 37 connector tests on Odoo 17.
