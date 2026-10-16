# Techniques from the TypeSafe cookbooks

Each row is a technique the [cookbooks](https://docs.typesafe.ai/cookbooks.md) show. Read the cookbook before copying its thresholds; they are examples to test on your data. `composition-patterns.md` holds the patterns we also built scripts for.

| Technique | Shape | Cookbook |
|---|---|---|
| Beam search over Choice probabilities | One Choice per tree level. Keep the best `K` paths by length-normalized score `prod(edge_p) ** (1 / decisions)`, so shallow and deep leaves compare fairly. Each beam path is one more question in the same request. Greedy search cannot undo an early mistake; a beam can. | hierarchical_classification |
| Report the parent when unsure | Classify into a fine label with one Choice. Below a confidence cutoff, report the broader parent label instead. No second call. In the cookbook, cutoff 0.9 split 60 filings in half: the confident half was right 90% of the time, the other half 40%, and 70% when reported one level up. | classification_using_confidence |
| Uncertain outcome for review | Treat a Choice whose top probability is under a cutoff (0.60 in the cookbook) as `uncertain` and send it to a person. Same for a Noul in a band (0.30 to 0.70). Label agreement across repeats rose from 90.8% to 99.2% with 74.2% of answers still automatic. Keep the raw probabilities visible. | consistency_choice, consistency_noul |
| Noul as a sort key | One Noul per query and candidate pair; sort candidates by the probability instead of thresholding. Top-1 accuracy 5% to 18% and top-10 38% to 62% over a BM25 shortlist. | rerank_typesafe |
| Rank ids, then check existence | One Choice over line or item ids ranks them by fit. Probabilities sum to 1, so something always ranks first. Add a Noul "does the document contain an answer at all?" in the same request. | semantic_find |
| Select, then copy | A regex over-finds candidate spans; a Choice picks one (plus `none`); code copies and normalizes it. Jev cannot invent or transpose a digit. Check that the right span is among the candidates. | pre_parsed_value_extraction |
| Closed-set arguments | Map a function name and each closed-set argument to a Choice; the weakest argument confidence gates the call. | function_calling |
| Dates as parts | Choice per part (kind, month, day, year, weekday) with a "not stated" option; code resolves and validates the date, and routes low confidence or impossible dates to review. | date_extraction |
| Verify a cheap extractor | A cheap model extracts; per-field Nouls ask "is this value absent from the source?" and "was it lifted from unrelated text?"; escalate to a reasoning model only when one fires. Same questions for every field, with the field spec in structured `instructions`. | sde_cascade |
| Check a citation | Plain string match for a missing quote; one Choice (`verified`, `unsupported`, `contradicted`) reads the quote's context. Confidence picks what a person looks at. | citation_check |
| Screen both directions | One request per message with a Noul battery of hazards plus a harm Score; named policies map the answers to pass, review, block, or route. Run on LLM inputs and outputs. | llm_guardrails |
| Classify retrieved passages | Per passage: relevant, usable, contradicts the query's premise, tries to instruct the model. Code routes each to evidence, conflict, or drop. | classifying_rag_passages |
| Memory gate | After a call, a Noul asks whether the request states a durable fact worth remembering (P at least 0.5 saves it); a wrapper adds saved facts to later states. | basic_memory |
| Pairwise structure recovery | One Noul per adjacent line pair ("did the break split a sentence?"); merge blocks in code; then one Choice per block. Code reads explicit markers and blank lines itself. | autoformat |
| Score with a middle outcome | A Score whose levels are the outcomes (different, related, same), rounded to the nearest level; companion Nouls name which fields disagree. The middle level goes to a curator. | entity_alignment |
| Rank, then re-read the top | One request ranks the whole roster against the turn and asks whether any item is needed; a second re-reads only the top three with full text and may reject all. | skill_suggestion |
| Rules in code, answers kept | Ask the questions once; a `decide()` function holds the rules. Change a rule and rerun it with no new request. | twitch_chat_filter |
| Judgments as features | Zero-label setting: an LLM proposes questions, Jev answers them per row, a classical model (CatBoost) trains on the answers. For a Score, use the expected level and the uncertainty as two columns; for a Noul, the probability. | autoresearch_feature_discovery |
| Batch, don't split | 13 questions in one request were 12.2x cheaper and 10x faster than 13 requests, with the same answers: each question is scored independently of the others. | parallel_questions |

## Repeatability

The consistency cookbooks add a fresh throwaway `uid` field to the state on each call to draw independent samples. They report Jev's per-question probability spread at about 0.01 and flips only on near-threshold questions. Two consequences: a repeat of an identical request is not a new sample, and a threshold sitting where answers cluster will flip. Keep thresholds away from the cluster. The cookbook notes the `uid` cannot separate sensitivity to the extra field from variation on identical requests.

## Smoothing noisy state

For a state that changes between observations (a game screen, a loading page), averaging a Choice's `probabilities` over about three observations steadies the pick. The docs do not describe this; it is our practice from a game agent. Average probabilities, not picks, and test it against a single read on labeled frames before you adopt it.

## Decide by argmax

Take `choice` (the argmax) as the action. Do not sample from `probabilities`: they are calibrated for deciding, and sampling adds noise a labeled run cannot explain. Use the distribution for the runner-up when an action had no effect (`composition-patterns.md`, History injection), for a beam, and for review bands. For multi-step play, `scripts/jev_search.py` (checkpoint beam search) applies the beam idea to states.

## State legend

Give the state descriptive field names and, when a field's meaning is not obvious, one line saying what it shows ("`hud.slots`: item counts in the toolbar, left to right"). The docs ask for named JSON fields and backticked paths; a legend is the same idea applied to opaque fields.
