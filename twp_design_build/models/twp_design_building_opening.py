from odoo import api, fields, models


class TwpDesignBuildingOpening(models.Model):
    """A door, window or skylight on a building, or several alike: how many, and their size."""

    _name = "twp.design.building.opening"
    _description = "Door or window"
    _order = "building_id, sequence, id"

    building_id = fields.Many2one(
        "twp.design.building", string="Building", required=True, index=True, ondelete="cascade")
    sequence = fields.Integer(default=10)
    kind = fields.Selection(
        [("door", "Door"), ("window", "Window"), ("skylight", "Skylight")], required=True, default="door")
    door_style = fields.Selection([
        ("overhead", "Overhead"),
        ("roll_up", "Roll up"),
        ("track", "Track"),
        ("man", "Man door"),
        ("other", "Other"),
    ], string="Style")
    count = fields.Integer(default=1, required=True)
    width = fields.Float("Width (ft)")
    height = fields.Float("Height (ft)")
    insulated = fields.Boolean()
    area = fields.Float("Area (sq ft)", compute="_compute_area", store=True)
    note = fields.Char()

    _count_positive = models.Constraint("CHECK(count > 0)", "A door or window is counted at least once.")

    @api.depends("count", "width", "height")
    def _compute_area(self):
        for opening in self:
            opening.area = opening.count * opening.width * opening.height

    @api.onchange("kind")
    def _onchange_kind(self):
        if self.kind != "door":
            self.door_style = False
