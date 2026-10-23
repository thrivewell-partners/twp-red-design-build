from unittest.mock import patch

from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestDesignBuild(TransactionCase):
    """Lines chosen on a lead make its jobs, and the flags ask only for the steps those lines need."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.team = cls.env["crm.team"].create({"name": "TWP Design / Build", "twp_db_enabled": True})
        Line = cls.env["twp.design.line"]
        cls.infrared = Line.create({"name": "TWP Infrared Heating"})
        cls.hvls = Line.create({"name": "TWP HVLS Fans"})
        cls.attachment = cls.env["ir.attachment"].create({"name": "TWP layout.pdf", "raw": b"%PDF-1.4"})

    def _lead(self, lines=(), **vals):
        return self.env["crm.lead"].create({
            "name": "TWP 90x30 pole barn",
            "type": "opportunity",
            "team_id": self.team.id,
            "twp_db_line_ids": [Command.set([line.id for line in lines])],
            **vals,
        })

    def _building(self, lead, **vals):
        return self.env["twp.design.building"].create({"lead_id": lead.id, **vals})

    def test_a_pipeline_is_design_build_by_its_tick(self):
        self.assertTrue(self._lead().twp_db_is_design_build)
        other = self.env["crm.team"].create({"name": "TWP Other"})
        lead = self.env["crm.lead"].create({"name": "TWP Plain", "type": "opportunity", "team_id": other.id})
        self.assertFalse(lead.twp_db_is_design_build)
        other.twp_db_enabled = True
        self.assertTrue(lead.twp_db_is_design_build)

    def test_choosing_a_line_makes_its_job(self):
        lead = self._lead([self.infrared])
        self.assertEqual(lead.twp_db_job_ids.line_id, self.infrared)
        lead.twp_db_line_ids = [Command.link(self.hvls.id)]
        self.assertEqual(lead.twp_db_job_ids.line_id, self.infrared | self.hvls)

    def test_removing_a_line_archives_its_job_and_choosing_it_again_restores_it(self):
        lead = self._lead([self.infrared, self.hvls])
        job = lead.twp_db_job_ids.filtered(lambda j: j.line_id == self.hvls)
        job.equipment = "TWP two 24' fans"
        lead.twp_db_line_ids = [Command.unlink(self.hvls.id)]
        self.assertFalse(job.active)
        self.assertEqual(lead.twp_db_job_ids.line_id, self.infrared)
        lead.twp_db_line_ids = [Command.link(self.hvls.id)]
        self.assertTrue(job.active, "The same job comes back, with what was written on it")
        self.assertEqual(job.equipment, "TWP two 24' fans")
        jobs = self.env["twp.design.job"].with_context(active_test=False).search([("lead_id", "=", lead.id)])
        self.assertEqual(len(jobs), 2)

    def test_a_building_is_sized_and_numbered(self):
        lead = self._lead([self.infrared])
        first = self._building(lead, length=90, width=30, eave_height=14)
        self.assertEqual(first.name, "Bldg 1")
        self.assertEqual(first.area, 2700)
        self.assertEqual(first.volume, 37800)
        self.assertTrue(first.is_measured)
        second = self._building(lead, length=40)
        self.assertEqual(second.name, "Bldg 2")
        self.assertFalse(second.is_measured)
        self.assertEqual(self._building(lead, name="TWP Shop").name, "TWP Shop")

    def test_no_lines_means_nothing_is_owed(self):
        lead = self._lead()
        self.assertTrue(lead.twp_db_survey_done)
        self.assertTrue(lead.twp_db_design_done)
        self.assertTrue(lead.twp_db_layout_done)

    def test_the_flags_follow_the_work(self):
        lead = self._lead([self.infrared])
        job = lead.twp_db_job_ids
        self.assertFalse(lead.twp_db_survey_done)
        self.assertFalse(lead.twp_db_design_done)
        self.assertFalse(lead.twp_db_layout_done)

        building = self._building(lead, length=90, width=30)
        self.assertFalse(lead.twp_db_survey_done, "A building without its eave height is not measured")
        building.eave_height = 14
        self.assertTrue(lead.twp_db_survey_done)
        self._building(lead)
        self.assertFalse(lead.twp_db_survey_done, "Every building has to be measured")

        job.equipment = "   "
        self.assertFalse(lead.twp_db_design_done, "Blank equipment is not a design")
        job.equipment = "TWP 6 tube heaters"
        self.assertTrue(lead.twp_db_design_done)
        job.layout_attachment_ids = [Command.link(self.attachment.id)]
        self.assertTrue(lead.twp_db_layout_done)

    def test_a_removed_line_owes_nothing(self):
        lead = self._lead([self.infrared, self.hvls])
        lead.twp_db_job_ids.filtered(lambda j: j.line_id == self.infrared).equipment = "TWP 6 tube heaters"
        self.assertFalse(lead.twp_db_design_done)
        lead.twp_db_line_ids = [Command.unlink(self.hvls.id)]
        self.assertTrue(lead.twp_db_design_done)

    def test_the_flags_ask_only_for_the_steps_a_kind_needs(self):
        # As a line module would: a kind that needs only the survey and a design.
        Line = self.registry["twp.design.line"]
        with patch.object(Line, "_twp_steps_by_kind", lambda self: {"general": {"survey", "design"}}):
            lead = self._lead([self.hvls])
            self.assertFalse(lead.twp_db_design_done)
            self.assertTrue(lead.twp_db_layout_done, "No layout is owed for a kind that needs none")
        with patch.object(Line, "_twp_steps_by_kind", lambda self: {}):
            lead = self._lead([self.hvls])
            self.assertTrue(lead.twp_db_survey_done)
            self.assertTrue(lead.twp_db_design_done)
            self.assertTrue(lead.twp_db_layout_done)

    def test_the_survey_wizard_steps_through_the_building(self):
        lead = self._lead([self.infrared])
        action = lead.action_twp_db_survey_building()
        self.assertEqual(action["target"], "new")
        self.assertFalse(action["res_id"], "A new building")
        Building = self.env["twp.design.building"].with_context(action["context"])
        building = Building.create({"length": 90, "width": 30, "eave_height": 14})
        self.assertEqual(building.lead_id, lead)
        self.assertEqual(building.name, "Bldg 1")
        self.assertEqual(building.survey_step, "size")

        self.assertEqual(building.action_survey_back()["res_id"], building.id)
        self.assertEqual(building.survey_step, "size", "Back stops at the first step")
        # Line modules may add steps, so walk whatever the field holds; Next stops at the last.
        steps = building._fields["survey_step"].get_values(self.env)
        self.assertEqual(steps[:5], ["size", "envelope", "doors", "use", "drawings"])
        self.assertEqual(steps[-1], "review")
        for step in steps[1:] + steps[-1:]:
            building.action_survey_next()
            self.assertEqual(building.survey_step, step)
        building.action_survey_back()
        self.assertEqual(building.survey_step, steps[-2])
        self.assertEqual(building.action_survey_done()["type"], "ir.actions.act_window_close")
        self.assertEqual(building.survey_step, "size", "Opened again, the survey starts from the top")
        self.assertTrue(lead.twp_db_survey_done)

    def test_the_envelope_is_sized_like_the_template(self):
        building = self._building(self._lead(), length=90, width=30, eave_height=14)
        self.assertEqual(building.wall_area, 3360, "Gross walls: (90 + 30) x 2 x 14")
        self.assertEqual(building.roof_area, 2700, "A flat roof")
        self.assertEqual(building.slab_perimeter, 240)

    def test_a_ridge_adds_the_gables_the_slope_and_the_space_under_it(self):
        building = self._building(self._lead(), length=90, width=30, eave_height=14, ridge_height=19)
        self.assertEqual(building.volume, 37800, "Only a pitched roof uses the ridge")
        building.roof_shape = "pitched"
        # A 5 ft rise over a 30 ft span: two gables of 15 x 5 on the end walls.
        self.assertEqual(building.end_wall_area, 30 * 14 * 2 + 30 * 5)
        self.assertEqual(building.long_wall_area, 90 * 14 * 2)
        self.assertEqual(building.volume, 37800 + 90 * 30 * 5 / 2)
        self.assertAlmostEqual(building.roof_area, 90 * 2 * (15 ** 2 + 5 ** 2) ** .5)
        self.assertEqual(building.area, 2700, "The floor is the floor")
        building.ridge_along = "width"
        self.assertEqual(building.long_wall_area, 90 * 14 * 2 + 90 * 5)
        self.assertEqual(building.end_wall_area, 30 * 14 * 2)
        self.assertAlmostEqual(building.roof_area, 30 * 2 * (45 ** 2 + 5 ** 2) ** .5)
        building.roof_shape = "flat"
        self.assertEqual(building.roof_area, 2700)

    def test_doors_and_windows_add_up_by_kind(self):
        building = self._building(self._lead(), length=90, width=30, eave_height=14)
        building.opening_ids = [
            Command.create({"kind": "door", "door_style": "overhead", "count": 2, "width": 12, "height": 12,
                            "insulated": True}),
            Command.create({"kind": "door", "door_style": "man", "count": 3, "width": 3, "height": 7}),
            Command.create({"kind": "window", "count": 4, "width": 3, "height": 4}),
            Command.create({"kind": "skylight", "width": 4, "height": 8}),
        ]
        self.assertEqual(building.door_count, 5)
        self.assertEqual(building.door_area, 2 * 144 + 3 * 21)
        self.assertEqual(building.window_area, 48)
        self.assertEqual(building.skylight_area, 32)
