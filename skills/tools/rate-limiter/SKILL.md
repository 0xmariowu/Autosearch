<!-- Self-written, plan autosearch-0418-channels-and-skills.md § F002a -->
---
name: rate-limiter
description: Enforce per-channel request budgets across methods with async token buckets.
version: 1
methods:
  - id: acquire
    impl: impl.py
    requires: []
---

This tool skill coordinates request pacing for channel methods.
It provides a per-channel and per-method token bucket guard.
Each method can declare short and long budget limits.
The most common inputs are `per_min` and `per_hour`.
Minute limits protect against sharp bursts.
Hour limits protect against sustained scraping patterns.
When both are present, both buckets must have capacity.
The tighter bucket determines the wait time.
Usage is intentionally lightweight for channel implementations.
Call it with `async with limiter.acquire(channel, method, ...)`.
Enter the context immediately before the outbound request.
Exit happens automatically after the request block completes.
The context manager does not wrap retries or circuit breaking.
Those concerns stay with the calling channel code.
Buckets are independent per `(channel, method)` pair.
Different methods on the same channel do not share burst state.
Different channels also do not interfere with each other.
The bucket capacity matches the configured limit.
That means a method can consume a full short burst immediately.
Tokens then refill gradually over time.
The refill clock is monotonic and injectable for tests.
Sleep is also injectable so tests can verify blocking without waiting in real time.
If the required wait would exceed the configured ceiling, the tool raises `RateLimited`.
This makes backpressure explicit instead of silently stalling forever.
Callers can catch that exception and fall back to another method or channel.
The limiter itself does not decide fallback policy.
It only enforces the declared pacing contract.
Use this tool anywhere a channel method has known API quotas or anti-abuse thresholds.
Keep the limit values with the method metadata or method implementation.
Do not hardcode channel-wide sleeps in unrelated code.
Centralizing pacing here keeps behavior testable and consistent.
This tool is designed as a shared primitive, not a routed search skill.
