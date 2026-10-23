from odoo import api, fields, models


class TwpDesignJob(models.Model):
    """One lead and one design line. Choosing the line on the lead makes it; removing the line archives it."""

    _name = "twp.design.job"
    _description = "Design job"
    _inherit = ["mail.thread"]
    _order = "lead_id, sequence, id"

    lead_id = fields.Many2one("crm.lead", string="Lead", required=True, index=True, ondelete="cascade")
    line_id = fields.Many2one("twp.design.line", string="Design line", required=True, ondelete="restrict")
    kind = fields.Selection(related="line_id.kind", store=True)
    sequence = fields.Integer(related="line_id.sequence", store=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(related="lead_id.company_id", store=True)

    sizing_basis = fields.Selection(
        [("whole", "Whole building"), ("spot", "Spot")], string="Sizing basis", default="whole", tracking=True)
    equipment = fields.Text(tracking=True, help="What the design calls for. The design is done once this is written.")
    layout_attachment_ids = fields.Many2many(
        "ir.attachment", "twp_design_job_layout_rel", "job_id", "attachment_id", string="Layout")
    notes = fields.Text()

    # Line modules extend the compute with what their own design needs.
    design_done = fields.Boolean("Design done", compute="_compute_design_done", store=True)
    layout_done = fields.Boolean("Layout done", compute="_compute_layout_done", store=True)

    _job_unique = models.Constraint("UNIQUE(lead_id, line_id)", "A lead has only one job per design line.")

    def action_open_record(self):
        """Open the full record from a list embedded in its lead, rather than the edit dialog."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }

    @api.depends("lead_id.name", "line_id.name")
    def _compute_display_name(self):
        for job in self:
            job.display_name = f"{job.lead_id.name or ''} - {job.line_id.name or ''}"

    @api.depends("equipment")
    def _compute_design_done(self):
        for job in self:
            job.design_done = bool((job.equipment or "").strip())

    @api.depends("layout_attachment_ids")
    def _compute_layout_done(self):
        for job in self:
            job.layout_done = bool(job.layout_attachment_ids)
