# An Event's status is derived, not stored

An Event stores only `abandoned_at`. Whether it's Active or Past is worked out at read time from `abandoned_at`, the Event Day and the User's timezone. An Event Day passes in each User's local midnight without any write, so a stored status would be stale until a job caught up with it. The cost is that Postgres can't enforce "at most one Active Event" with a partial unique index, since the index can't depend on "today". The Event service enforces it instead: it locks the User's row (`SELECT … FOR UPDATE`) while checking for an Active Event and creating a new one.

## Considered Options

- **A stored `status` column plus a nightly job that marks Events as Past:** simpler queries and a database constraint, but wrong for hours around each timezone's midnight, and it needs a scheduler that doesn't exist until Week 7.
