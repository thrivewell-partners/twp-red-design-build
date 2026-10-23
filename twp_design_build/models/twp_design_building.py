from odoo import api, fields, models

INSULATED = [("insulated", "Insulated"), ("uninsulated", "Un-insulated")]
# Line modules add steps of their own with selection_add, e.g. the heat loss before Review.
SURVEY_STEPS = [
    ("size", "Size and roof"),
    ("envelope", "Walls and roof"),
    ("doors", "Doors and windows"),
    ("use", "Use"),
    ("drawings", "Drawings"),
    ("review", "Review"),
]


class TwpDesignBuilding(models.Model):
    """One building on a lead, surveyed once for every line. The fields follow DRP's Building Survey Form."""

    _name = "twp.design.building"
    _description = "Building survey"
    _order = "lead_id, sequence, id"

    lead_id = fields.Many2one("crm.lead", string="Lead", required=True, index=True, ondelete="cascade")
    sequence = fields.Integer(default=10)
    name = fields.Char(required=True, default=lambda self: self._default_name())
    company_id = fields.Many2one(related="lead_id.company_id", store=True)

    length = fields.Float("Length (ft)")
    width = fields.Float("Width (ft)")
    eave_height = fields.Float("Eave height (ft)")
    area = fields.Float("Area (sq ft)", compute="_compute_size", store=True)
    volume = fields.Float("Volume (cu ft)", compute="_compute_size", store=True)
    is_measured = fields.Boolean(
        "Measured", compute="_compute_size", store=True, help="Length, width and eave height are all filled in.")
    roof_shape = fields.Selection([("flat", "Flat"), ("dome", "Dome"), ("pitched", "Pitched")])
    ridge_height = fields.Float(
        "Ridge height (ft)", help="Floor to the ridge, or to the top of a dome. Recorded only: like the "
                                  "heat-loss template, the sizes below take the roof as flat at the eave height.")
    # The envelope as the heat-loss template sizes it: gross walls, a flat roof, the full slab perimeter.
    wall_area = fields.Float("Wall area (sq ft)", compute="_compute_size", store=True)
    roof_area = fields.Float("Roof area (sq ft)", compute="_compute_size", store=True)
    slab_perimeter = fields.Float("Slab edge (lin ft)", compute="_compute_size", store=True)

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
    opening_ids = fields.One2many("twp.design.building.opening", "building_id", string="Doors and windows")
    door_count = fields.Integer("Doors", compute="_compute_openings", store=True)
    door_area = fields.Float("Door area (sq ft)", compute="_compute_openings", store=True)
    window_area = fields.Float("Window area (sq ft)", compute="_compute_openings", store=True)
    skylight_area = fields.Float("Skylight area (sq ft)", compute="_compute_openings", store=True)
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
    # Where the survey wizard is. Stored, so a survey left half done reopens where it stopped.
    survey_step = fields.Selection(SURVEY_STEPS, default="size", required=True)

    @api.depends("length", "width", "eave_height")
    def _compute_size(self):
        for building in self:
            # The heat-loss template's own arithmetic, cell for cell (K9, I9, C15 + C16, C18, C22).
            length, width, height = building.length, building.width, building.eave_height
            building.area = length * width
            building.volume = length * width * height
            building.is_measured = length > 0 and width > 0 and height > 0
            building.wall_area = (length + width) * 2 * height
            building.roof_area = length * width
            building.slab_perimeter = (length + width) * 2

    @api.depends("opening_ids.kind", "opening_ids.count", "opening_ids.area")
    def _compute_openings(self):
        for building in self:
            openings = building.opening_ids
            doors = openings.filtered(lambda o: o.kind == "door")
            building.door_count = sum(doors.mapped("count"))
            building.door_area = sum(doors.mapped("area"))
            building.window_area = sum(openings.filtered(lambda o: o.kind == "window").mapped("area"))
            building.skylight_area = sum(openings.filtered(lambda o: o.kind == "skylight").mapped("area"))

    def _default_name(self):
        lead_id = self.env.context.get("default_lead_id")
        if not lead_id:
            return False
        return f"Bldg {self.search_count([('lead_id', '=', lead_id)]) + 1}"

    def action_open_survey(self):
        """The survey wizard: this building, one step at a time, in a dialog. Empty, a new building."""
        return {
            "type": "ir.actions.act_window",
            "name": self.name or self.env._("Building survey"),
            "res_model": self._name,
            "res_id": self[:1].id,
            "view_mode": "form",
            "views": [(self.env.ref("twp_design_build.twp_design_building_view_form_survey").id, "form")],
            "target": "new",
        }

    def _survey_move(self, offset):
        self.ensure_one()
        keys = self._fields["survey_step"].get_values(self.env)
        index = keys.index(self.survey_step) + offset
        self.survey_step = keys[max(0, min(index, len(keys) - 1))]
        return self.action_open_survey()

    def action_survey_next(self):
        return self._survey_move(1)

    def action_survey_back(self):
        return self._survey_move(-1)

    def action_survey_done(self):
        # Opened again, the survey starts from the top.
        self.survey_step = "size"
        return {"type": "ir.actions.act_window_close"}

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
