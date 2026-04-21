"""autosearch:tikhub-fallback meta skill package marker.

Documentation-only skill. Codifies the decision tree for when the runtime AI
should escalate from autosearch's free native channel implementations to the
paid TikHub fallback on the 5 hardened Chinese anti-bot platforms. Autosearch
does not invoke TikHub automatically — the runtime AI consults this skill and
decides whether the cost is justified for the current task.
"""
