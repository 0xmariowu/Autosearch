"""autosearch:model-routing meta skill package marker.

Advisory-only skill: provides a Fast / Standard / Best tier catalog for all
autosearch leaf skills. The runtime AI reads this, consults the `model_tier`
frontmatter on each leaf skill, and routes to the cheapest model that clears
the task's quality bar. Autosearch does not itself switch models — the runtime
AI is the decision-maker.
"""
