def disable_native_online_vies(env):
    """Keep base_vat's local validation and disable the company online option."""
    env['res.company'].sudo().search([]).write({
        'vat_check_vies': False,
    })


def post_init_hook(env):
    disable_native_online_vies(env)
