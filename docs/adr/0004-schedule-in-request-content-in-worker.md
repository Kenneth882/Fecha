# The Plan's schedule is built in the request; its content is generated in the worker

`POST /events` builds the Plan synchronously, in the same transaction as the Event, by calling the pure planner over the Scenario Catalog. The Event therefore never exists without a Current Plan, and onboarding never waits on a job to see its Milestones and Tasks. Generating content for a Plan that already exists (Vocab Items, Listen Task dialogues, roleplay prompts) is slow and costs money, so it's done by an arq job. The worker fills that content in. It never decides the schedule.

## Considered Options

- **Enqueue the whole Plan generation on `POST /events`** (the original CLAUDE.md wording): every client would have to handle an Event with no Plan yet and poll for it, even though the schedule needs no I/O at all.
