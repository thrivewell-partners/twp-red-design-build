from odoo import api, fields, models

STEPS = [("survey", "Building survey"), ("design", "Design"), ("layout", "Layout")]


class TwpDesignLine(models.Model):
    """A line the firm designs, such as infrared heating or HVLS fans. Its kind decides the steps."""

    _name = "twp.design.line"
    _description = "Design line"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    # Line modules add their kinds with selection_add, and their steps in _twp_steps_by_kind.
    kind = fields.Selection(
        [("general", "General")], required=True, default="general",
        help="What kind of design the line needs. It decides which steps a lead must finish.")

    _name_unique = models.Constraint("UNIQUE(name)", "A design line with this name already exists.")

    @api.model
    def _twp_steps_by_kind(self):
        """The steps each kind needs. A kind left out needs none."""
        return {"general": {"survey", "design", "layout"}}

    def _twp_steps(self):
        self.ensure_one()
        return self._twp_steps_by_kind().get(self.kind, set())
