from odoo import api, SUPERUSER_ID
from odoo.addons.viesac_vat_compliance.hooks import disable_native_online_vies


def migrate(cr, version):
    # post_init_hook only runs on a fresh installation. Apply the same one-time
    # handover when an existing installation first upgrades to this version.
    disable_native_online_vies(api.Environment(cr, SUPERUSER_ID, {}))
