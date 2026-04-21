"""autosearch:router skill package marker.

Three-layer progressive-disclosure entry point:
  L0 router (this skill)
     ↓ picks 1-3 group indexes
  L1 group index (references/groups/*.md)
     ↓ picks 3-8 leaf skills
  L2 leaf skill (autosearch/skills/**)

Runtime AI reads only what is needed per task, not all 80+ leaf SKILL.md files.
"""
