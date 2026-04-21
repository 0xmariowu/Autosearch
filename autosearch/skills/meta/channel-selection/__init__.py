"""autosearch:channel-selection meta skill package marker.

Group-first channel selection for v2 tool-supplier architecture. Replaces
the legacy ``select-channels`` approach (which lived in the plugin
marketplace distribution and ranked flat across 41 channels) with a
two-stage pick: select 1-3 groups from the router index, then pick 3-8
leaf channels from within those groups. Runtime AI never needs to read all
41 channel SKILL.md bodies.
"""
