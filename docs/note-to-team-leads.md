# What you can ask the assistant about usage

You can ask, in the assistant, how much your own team used it and what that cost. You do not get a view of any other team, and you cannot change what your team is allowed to do from the chat. That is deliberate.

## What you can ask

Talk about your own team, and name a period. These all work:

- "How much did my team use the assistant in the last 7 days?"
- "What did we spend in September?"
- "Who on my team used it most in the week of 31 August?" (that week is `2026-W36`)
- "Is web search turned on for us? What about code execution?"

"Last 7 days" and "last 30 days" are counted back from 28 September 2026, which is the end of the usage export we have loaded. They are not counted from today. If you want a specific week or month, name it: a week like `2026-W36`, or a month like `2026-09`.

The answer splits Claude and Gemini, then gives a total. Gemini does not report a request count, so you will see tokens and cost for Gemini, and tokens, cost, and requests for Claude. Cost is in US dollars. Claude's export arrives in cents; we convert it before you see it.

## What you cannot ask, and why

You only see your own team. If you ask about Finance, or about "the company", the assistant is refused and it is not given the numbers to summarise. A platform admin can see every team. A team lead cannot. An ordinary member of the team cannot see usage at all in production.

You also cannot turn capabilities on or off from the chat. That includes web search, code execution, and this usage connector itself. In production only the two platform admins, Chloe Dubois and Arjun Mehta, can change those controls. They do it on the usage admin page, and the assistant then follows the new setting. If a team lead could flip a control by asking nicely, the control would not be a control.

One more limit. In production this usage connector is switched on only for Clinical Operations and IT Platform. The other four teams will get a refusal even for their own numbers, until IT Platform enables `usage-connector` for that team. Web search stays on for every team. Code execution stays off for every team. Those are the current defaults, not a bug in the assistant.

## How to ask for more

Email IT Platform, or ask Chloe or Arjun directly. Say which team, which capability (`usage-connector`, `web-search`, or `code-execution`), and whether you want it on or off. They change it on the admin page. You do not need a new assistant, and you do not need to be given another team's login.

If you need a period we do not have, say so. The export we loaded runs from 3 August 2026 through 27 September 2026. Anything outside that window will come back empty, which is not the same thing as a refusal.
