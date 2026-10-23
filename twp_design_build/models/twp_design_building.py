from odoo import api, fields, models

INSULATED = [("insulated", "Insulated"), ("uninsulated", "Un-insulated")]


class TwpDesignBuilding(models.Model):
    """One building on a lead, surveyed once for every line. The fields follow DRP's Building Survey Form."""

    _name = "twp.design.building"
    _description = "Building survey"
    _order = "lead_id, sequence, id"

    lead_id = fields.Many2one("crm.lead", string="Lead", required=True, index=True, ondelete="cascade")
    sequence = fields.Integer(default=10)
    name = fields.Char(required=True)
    company_id = fields.Many2one(related="lead_id.company_id", store=True)

    length = fields.Float("Length (ft)")
    width = fields.Float("Width (ft)")
    eave_height = fields.Float("Eave height (ft)")
    area = fields.Float("Area (sq ft)", compute="_compute_size", store=True)
    volume = fields.Float("Volume (cu ft)", compute="_compute_size", store=True)
    is_measured = fields.Boolean(
        "Measured", compute="_compute_size", store=True, help="Length, width and eave height are all filled in.")

    roof_shape = fields.Selection([("flat", "Flat"), ("dome", "Dome"), ("pitched", "Pitched")])
    function = fields.Selection([
        ("manufacturing", "Manufacturing"),
        ("car_wash", "Car wash"),
        ("warehouse", "Warehouse"),
        ("fire_station", "Fire station"),
        ("other", "Other"),
    ], string="Building function")
    function_other = fields.Char("Other function")
    activity = fields.Char()
    wall_material = fields.Char("Wall materials")
    wall_insulation = fields.Char("Wall insulation")
    wall_r_value = fields.Float("Wall R value")
    roof_material = fields.Char("Roof materials")
    roof_insulation = fields.Char("Roof insulation")
    roof_r_value = fields.Float("Roof R value")
    door_type = fields.Selection([("roll_up", "Roll up"), ("track", "Track")], string="Doors")
    door_insulation = fields.Selection(INSULATED, string="Door insulation")
    slab_edge = fields.Selection(INSULATED)
    desired_temperature = fields.Float("Desired temp. (°F)")
    venting = fields.Selection([("sidewall", "Sidewall"), ("roof", "Roof")], string="Preferred venting")
    floor_plan_attachment_ids = fields.Many2many(
        "ir.attachment", "twp_design_building_floor_plan_rel", "building_id", "attachment_id",
        string="Floor plan", help="With dimensions, and where every door and window is.")
    elevation_attachment_ids = fields.Many2many(
        "ir.attachment", "twp_design_building_elevation_rel", "building_id", "attachment_id",
        string="Elevation", help="With dimensions and interior obstructions.")
    notes = fields.Text()

    @api.depends("length", "width", "eave_height")
    def _compute_size(self):
        for building in self:
            # The same arithmetic as the heat-loss template: length x width, times eave height.
            building.area = building.length * building.width
            building.volume = building.area * building.eave_height
            building.is_measured = building.length > 0 and building.width > 0 and building.eave_height > 0

    @api.model_create_multi
    def create(self, vals_list):
        # An unnamed building is numbered after the lead's others: Bldg 1, Bldg 2.
        counts = {}
        for vals in vals_list:
            if vals.get("name") or not vals.get("lead_id"):
                continue
            lead_id = vals["lead_id"]
            if lead_id not in counts:
                counts[lead_id] = self.search_count([("lead_id", "=", lead_id)])
            counts[lead_id] += 1
            vals["name"] = f"Bldg {counts[lead_id]}"
        return super().create(vals_list)
