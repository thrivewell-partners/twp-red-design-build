{
    "name": "Design / Build",
    "summary": "Choose the lines a lead is designed for, a design job per line, and a building survey shared by all",
    "description": """
For a firm that designs what it sells. On a pipeline ticked Design / Build, a lead says which lines
it is being designed for. Each line gets a design job, and the buildings are surveyed once for
every line. Each line's kind says which steps it needs: the survey, the design, the layout. Three
flags on the lead follow the lines chosen, so stage checks ask only for the steps a lead needs.
Line modules add their own kinds, and the wizards that do the design.
""",
    "version": "19.0.1.0.0",
    "category": "Sales/CRM",
    "license": "LGPL-3",
    "author": "ThriveWell Partners",
    "depends": ["crm", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "views/twp_design_line_views.xml",
        "views/twp_design_building_views.xml",
        "views/twp_design_job_views.xml",
        "views/crm_team_views.xml",
        "views/crm_lead_views.xml",
        "views/menus.xml",
    ],
    "installable": True,
    "application": False,
}
