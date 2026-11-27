# Generated content is stored in Postgres; Redis only stops duplicate generation

Generated content (Listen Dialogues now, and Vocab Items, which Review States already point to) is written to Postgres, in shared tables keyed by (language, Scenario, Level). The table is the cache: before calling the LLM, generation checks whether the key is already filled and skips it if so. Redis does not hold a copy of the content. Its only job here is to make sure one key is never generated twice at the same time: arq's job ID, derived from the Event, stops one Event's job being queued twice, and a short per-key lock stops two Events' jobs filling the same key at once. Generated content is never regenerated or edited in place. A bad item is retired instead, so a Listen Task or Review that already refers to it keeps working.

## Considered Options

- **Cache LLM responses in Redis under (language, Scenario, Level), as CLAUDE.md first said:** content that Users have already seen would sit in a store that can be evicted or flushed, and it would also be needed in Postgres for foreign keys. That's two copies with nothing to keep them in sync.
- **Redis as a cache in front of the Postgres tables:** saves a few indexed reads per Event creation, which is not worth a second copy that can go stale.

## Consequences

- Flushing Redis never loses content or changes what a User sees.
- Filled keys cost nothing to generate again, so a Re-plan or a retried job can run the same per-Event job again safely.
