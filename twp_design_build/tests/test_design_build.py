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
        for step in ("use", "envelope", "doors", "drawings", "drawings"):
            building.action_survey_next()
            self.assertEqual(building.survey_step, step)
        building.action_survey_back()
        self.assertEqual(building.survey_step, "doors")
        self.assertEqual(building.action_survey_done()["type"], "ir.actions.act_window_close")
        self.assertEqual(building.survey_step, "size", "Opened again, the survey starts from the top")
        self.assertTrue(lead.twp_db_survey_done)
