# CramPlan

CramPlan prepares one learner, in a foreign language, for one real-world event on a fixed date. It does this by working backward from that date.

## Language

### Learner and event

**User**:
A person preparing for an Event.
_Avoid_: Learner, student, account

**Event**:
The real-world occasion a User is preparing for, held on one local date, in one target language. Examples: a job interview, a relocation, a speech.
_Avoid_: Goal, deadline, trip, occasion

**Active Event**:
The one Event a User is currently preparing for. A User has at most one Active Event; any others are past and read-only.
_Avoid_: Current event, open event

**Past Event**:
An Event that is over, either because its Event Day has ended or because it was abandoned. It's read-only.
_Avoid_: Archived event, finished event, closed event

**Abandoned Event**:
A Past Event the User ended early, before its Event Day, to start a different Event.
_Avoid_: Cancelled event, deleted event

**Daily Budget**:
The minutes per day a User commits to an Event: 15, 30 or 45. Reviews and Tasks together must fit inside it.
_Avoid_: Time budget, study time, daily goal

**Event Type**:
The kind of Event: interview, relocation or speech. It decides which Scenarios are available.
_Avoid_: Template, category

**Event Day**:
The local calendar date of the Event, in the User's timezone. Nothing is scheduled on or after it.
_Avoid_: Deadline, due date

**Level**:
The User's proficiency in the target language, on a trimmed CEFR scale: A1, A2, B1, B2, C1.
_Avoid_: Skill, proficiency score

**Native Language**:
The User's own language, which every Vocab Item translation is in. Only English is supported for now.
_Avoid_: Source language, first language

**Placement Quiz**:
An optional short quiz during onboarding that sets the User's Level instead of a self-rating.

### Situations

**Scenario**:
A reusable real-world situation within an Event Type, such as "Apartment check-in" or "Salary negotiation". It has a fixed difficulty and is the same in every language. Vocab Items and roleplay prompts belong to a Scenario, and progress is measured per Scenario.
_Avoid_: Topic, situation, unit

**Scenario Catalog**:
The fixed, hand-written set of Scenarios for each Event Type. Plans choose and order Scenarios from it; they never make up new ones.
_Avoid_: Scenario library, templates

**Milestone**:
A Scenario scheduled within one Plan version, with a target date and a position in the order.
_Avoid_: Checkpoint, stage, chapter

### Planning

**Plan**:
One version of the day-by-day schedule of Milestones and Tasks that leads up to the Event Day. An Event has a sequence of Plan versions.
_Avoid_: Schedule, curriculum, course

**Current Plan**:
The latest Plan version of an Event. Every earlier version is a Superseded Plan.

**Superseded Plan**:
A Plan version that a later one replaced. It keeps its completed and Missed Tasks unchanged, as a record.

**Re-plan**:
Generating a new Plan version that schedules only Plan Days from today onward. It's triggered by Missed Tasks, a change to the Event Day or Level, or the User's request.
_Avoid_: Rebalance, regenerate, reschedule

**Plan Day**:
One calendar day of a Plan, in the User's timezone.
_Avoid_: Session, slot

**Final Window**:
The two Plan Days just before the Event Day. Every Introduced Vocab Item must be reviewed at least once in it, and no new Vocab Items are introduced in it.
_Avoid_: Last 48 hours, cram window

**Task**:
One unit of planned practice on a Plan Day, for one Milestone. A Plan Day has 3–4 Tasks. Its kind is vocab, listen or speak.
_Avoid_: Exercise, activity, lesson

**Vocab Task**:
A Task that introduces a batch of new Vocab Items from its Milestone's Scenario.

**Listen Task**:
A Task in which the User hears a short dialogue set in its Milestone's Scenario and answers three comprehension questions. It's complete once all three are answered.

**Speak Task**:
A Task that the User completes by doing a Roleplay Session for its Milestone.

**Missed Task**:
A Task left incomplete after its Plan Day has ended. It's never completed afterwards.
_Avoid_: Skipped task, overdue task

### Practice

**Vocab Item**:
A phrase in a target language, with its translation, belonging to a Scenario. Shared across Users.
_Avoid_: Word, card, flashcard, term

**Introduced Vocab Item**:
A Vocab Item that a Vocab Task has presented to the User for the Active Event. Only Introduced Vocab Items get Reviews.

**Review State**:
The spaced-repetition progress of one Introduced Vocab Item within one Event. Each Event starts fresh; nothing carries over between Events.
_Avoid_: Card state, memory, progress

**Review**:
One recall of a Vocab Item that the User grades themselves, from 0 to 5. Reviews are scheduled by spaced repetition and are not Tasks.
_Avoid_: Drill, quiz, practice

**Grade**:
The 0–5 recall rating on a Review. The User chooses one of Again, Hard, Good or Easy.
_Avoid_: Score, rating

**Review Queue**:
The Vocab Items due for Review now. It runs alongside a Plan Day's Tasks and doesn't count toward them.
_Avoid_: Due list, backlog

**Roleplay Session**:
A spoken conversation in which the AI plays the other party in a Milestone's Scenario, producing a transcript and feedback. A session that's too short goes unscored and doesn't complete a Speak Task.
_Avoid_: Conversation, call, dialogue, rehearsal

**Roleplay Score**:
A Roleplay Session's 0–100 result, the mean of four rubric criteria each rated 0–5: goal achieved, comprehensibility, accuracy and fluency.
_Avoid_: Grade, rating, mark

### Readiness

**Readiness**:
How far a User has progressed toward being ready for the Event Day, from 0 to 100. It starts near 0 and gets close to 100 only once the whole Plan is completed and performed well.
_Avoid_: Score, progress, confidence

**Scenario Readiness**:
The Readiness for one Scenario of the Current Plan. It combines Retention, Roleplay performance and Completion.

**Overall Readiness**:
The difficulty-weighted average of an Event's Scenario Readiness values.
_Avoid_: Total score, readiness score

**Retention**:
How well the User currently recalls a Scenario's planned Vocab Items, counting items not yet introduced as not recalled.
_Avoid_: Memory, recall rate

**Completion**:
The share of a Scenario's planned Tasks the User has completed, across all Plan versions.
_Avoid_: Adherence, progress

**Readiness Snapshot**:
The Scenario Readiness and Overall Readiness recorded at the end of one Plan Day. It's never recalculated afterwards.
_Avoid_: Daily score, report
