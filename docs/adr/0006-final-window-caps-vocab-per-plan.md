# The Final Window caps how many Vocab Items a Plan introduces

Every Introduced Vocab Item must be reviewed in the Final Window, and Reviews have to fit in the Review allowance of the Daily Budget. So a Plan introduces at most the number of items its two Final Window days of Review time can cover (60, 120 or 180 at 15, 30 or 45 minutes, at about 8 seconds per Review). The planner works out each Vocab Task's batch size as part of the schedule: it's sized to the Task's minutes and clamped so that the Plan's total stays under the cap. As a result, a 60-day Plan teaches no more phrases than a 20-day one, and spends its extra days on more practice instead. Content (hand-written or generated) only decides *which* items fill each batch, never how many (ADR 0004).

## Considered Options

- **Let the Final Window go over the Daily Budget:** keeps long Plans phrase-rich, but the last two days, when the User has the least time, would need 40+ minutes of Reviews.
- **Review only the most important items in the Final Window:** that's no longer a guarantee, and Retention would quietly decay for the rest.
