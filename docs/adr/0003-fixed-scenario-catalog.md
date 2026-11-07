# A fixed Scenario Catalog; the LLM never makes up Scenarios

Each Event Type has a hand-written Scenario Catalog (about 6–10 Scenarios, each with a fixed difficulty), and it's the same in every language. The User's goals and the LLM only choose and order Scenarios and generate content for them (Vocab Items, roleplay prompts, Listen Task dialogues). LLM-made Scenarios would make shared Vocab Items and the (language, Event Type, Level) cache key unstable. They would also leave the hand-written fallback templates with nothing concrete to cover, and would make difficulty-weighted planning and readiness impossible to compare across Users.

## Considered Options

- **LLM-generated Scenarios from the User's goals** (e.g. "nursing interview"): more personalised, but it rules out caching, fallbacks and shared content. Personalisation belongs in the generated content and roleplay prompts instead.
