# One Active Event per User, with Review State scoped to the Event

A User has at most one Active Event at a time, and Review State is keyed by (Event, Vocab Item), not by (User, Vocab Item). Deadline compression and the Final Window guarantee are only well-defined against a single Event Day. If Review State were shared across concurrent or successive Events, two deadlines would compete for the same item, and a history built for an earlier deadline would skew the schedule. The cost is that no progress carries over between Events. For a cram app built around one real event, that's acceptable.

## Considered Options

- **Several independent Active Events:** possible later. Each would need its own "today", countdown and Review Queue, which complicates the main UI for little MVP value.
- **Review State shared across a User's Events:** rejected, because it breaks the Final Window guarantee whenever two Events overlap or follow closely.
