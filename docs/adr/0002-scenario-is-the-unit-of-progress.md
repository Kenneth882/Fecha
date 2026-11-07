# Scenario, not Milestone, is the unit of progress

Every Re-plan creates a new Plan version with new Milestones. Roleplay Sessions and Scenario Readiness therefore attach to (Event, Scenario), not to a Milestone. Completed and Missed Tasks stay on the Plan version they belonged to, and a Re-plan only schedules Plan Days from today onward. This way, progress on "Apartment check-in" survives any number of Re-plans, and no completed work is ever copied or overwritten. Completion is calculated across all Plan versions of the Event.

## Consequences

Anything that measures progress has to go through the Scenario. Code that walks the Current Plan's Milestones on their own will miss history from Superseded Plans.
