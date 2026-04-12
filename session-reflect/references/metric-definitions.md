# session-reflect Metric Definitions

## Baseline Metrics

- **correction_rate** = `SUM(plugin_events.post_dispatch_signals.user_correction_within_3_turns=1) / COUNT(plugin_events)` for `(plugin, component, window)`
- **abandonment_rate** = `SUM(plugin_events.post_dispatch_signals.user_abandoned_topic=1) / COUNT(plugin_events)` for `(plugin, component, window)`
- **agent_efficiency_avg** = `AVG(plugin_events.agent_turns_used / plugin_events.agent_max_turns)` filtered to `component_type='agent'` for `(plugin, component, window)` (NULL agent_max_turns excluded)
- **adoption_rate** = `SUM(plugin_events.post_dispatch_signals.result_adopted=1) / SUM(plugin_events.result_ok=1)` for `(plugin, component, window)` (denominator: only successful invocations)
