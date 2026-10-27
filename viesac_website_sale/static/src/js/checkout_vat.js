/** @odoo-module **/
import publicWidget from '@web/legacy/js/public/public_widget';
import { jsonrpc } from '@web/core/network/rpc_service';
import { _t } from '@web/core/l10n/translation';

publicWidget.registry.ViesacCheckoutVat = publicWidget.Widget.extend({
    selector: 'form.checkout_autoformat',
    events: {
        'input #viesac_checkout_vat_input': '_onVatInput',
        'change select[name="country_id"]': '_onVatInput',
    },
    start() {
        this.typingTimer = null;
        this.requestVersion = 0;
        return this._super(...arguments);
    },
    destroy() {
        clearTimeout(this.typingTimer);
        this.requestVersion++;
        return this._super(...arguments);
    },
    _onVatInput() {
        clearTimeout(this.typingTimer);
        const version = ++this.requestVersion;
        const $input = this.$('#viesac_checkout_vat_input');
        if (!$input.length) return;
        const vat = ($input.val() || '').trim();
        this.$('#viesac_vat_status_indicator').addClass('d-none');
        if (vat.length >= 4) {
            this.typingTimer = setTimeout(() => this._performVatValidation(vat, version), 800);
        }
    },
    async _performVatValidation(vat, version) {
        const $indicator = this.$('#viesac_vat_status_indicator');
        const $spinner = this.$('#viesac_vat_spinner');
        const $text = this.$('#viesac_vat_status_text');
        $indicator.removeClass('d-none bg-success bg-danger bg-warning text-white text-dark');
        $spinner.removeClass('d-none');
        $text.text(_t('Checking...'));
        try {
            const data = await jsonrpc('/viesac/checkout/validate_vat', { vat });
            if (version !== this.requestVersion || this.isDestroyed()) return;
            $spinner.addClass('d-none');
            if (data.valid) {
                $indicator.addClass('bg-success text-white');
                $text.text(_t('VALID'));
            } else if (data.status === 'invalid') {
                $indicator.addClass('bg-danger text-white');
                $text.text(_t('INVALID'));
            } else {
                $indicator.addClass('bg-warning text-dark');
                $text.text(data.status === 'pending' ? _t('PENDING') : _t('UNVERIFIED'));
            }
        } catch {
            if (version === this.requestVersion && !this.isDestroyed()) $indicator.addClass('d-none');
        }
    },
});
