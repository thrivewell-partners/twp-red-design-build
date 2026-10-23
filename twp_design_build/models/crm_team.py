from odoo import fields, models


class CrmTeam(models.Model):
    _inherit = "crm.team"

    twp_db_enabled = fields.Boolean(
        string="Design / Build",
        help="This pipeline designs what it sells: the lines a lead is designed for, a job per line, "
             "and the building survey.",
    )
