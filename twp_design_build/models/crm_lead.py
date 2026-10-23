from odoo import api, fields, models


class CrmLead(models.Model):
    """On a Design / Build pipeline, a lead says which lines it is designed for, and tracks each one's job."""

    _inherit = "crm.lead"

    twp_db_is_design_build = fields.Boolean(
        related="team_id.twp_db_enabled", string="Is Design / Build", store=True, index=True)
    twp_db_line_ids = fields.Many2many(
        "twp.design.line", "crm_lead_twp_design_line_rel", "lead_id", "line_id", string="Designing for",
        help="The lines this lead is designed for. Each one gets a design job.")
    twp_db_job_ids = fields.One2many("twp.design.job", "lead_id", string="Design jobs")
    twp_db_building_ids = fields.One2many("twp.design.building", "lead_id", string="Buildings")

    # Each is True when no chosen line needs the step, so a stage check on one asks only for what
    # the lead's lines need.
    twp_db_survey_done = fields.Boolean(
        "Survey done", compute="_compute_twp_db_done", store=True,
        help="Every building is measured, or no line chosen needs a survey.")
    twp_db_design_done = fields.Boolean(
        "Design done", compute="_compute_twp_db_done", store=True,
        help="Every job that needs a design has one, or no line chosen needs a design.")
    twp_db_layout_done = fields.Boolean(
        "Layout done", compute="_compute_twp_db_done", store=True,
        help="Every job that needs a layout has one, or no line chosen needs a layout.")

    @api.depends("twp_db_job_ids.line_id.kind", "twp_db_job_ids.active", "twp_db_job_ids.design_done",
                 "twp_db_job_ids.layout_done", "twp_db_building_ids.is_measured")
    def _compute_twp_db_done(self):
        for lead in self:
            jobs = lead.twp_db_job_ids.filtered("active")
            steps = {job: job.line_id._twp_steps() for job in jobs}
            buildings = lead.twp_db_building_ids
            lead.twp_db_survey_done = not any("survey" in s for s in steps.values()) or (
                bool(buildings) and all(buildings.mapped("is_measured")))
            lead.twp_db_design_done = all(job.design_done for job, s in steps.items() if "design" in s)
            lead.twp_db_layout_done = all(job.layout_done for job, s in steps.items() if "layout" in s)

    @api.model_create_multi
    def create(self, vals_list):
        leads = super().create(vals_list)
        leads.filtered("twp_db_line_ids")._twp_db_sync_jobs()
        return leads

    def write(self, vals):
        res = super().write(vals)
        if "twp_db_line_ids" in vals:
            self._twp_db_sync_jobs()
        return res

    def _twp_db_sync_jobs(self):
        """A job for every line chosen. A line removed archives its job, and choosing it again restores it."""
        Job = self.env["twp.design.job"].with_context(active_test=False)
        jobs = Job.search([("lead_id", "in", self.ids)])
        to_create = []
        for lead in self:
            mine = jobs.filtered(lambda j: j.lead_id == lead)
            for line in lead.twp_db_line_ids - mine.line_id:
                to_create.append({"lead_id": lead.id, "line_id": line.id})
            mine.filtered(lambda j: not j.active and j.line_id in lead.twp_db_line_ids).active = True
            mine.filtered(lambda j: j.active and j.line_id not in lead.twp_db_line_ids).active = False
        if to_create:
            Job.create(to_create)
