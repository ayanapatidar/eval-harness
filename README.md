#  AI Agent Eval Harness

A lightweight evaluation harness for LLM-based document extraction agents, built overnight to try out some production based workflows.

## What This Is

A Python script that runs an LLM against a set of real-world title insurance document extraction* tasks, scores the outputs, and reports pass rates, latency, and failure modes, aggregating over a number of trials. 

Built to poke a little at a problem I'm interested in dealing with--- I wanted to visualize what could arise even in a sandbox environment like this, and how to start thinking about solving those problems. 

* Title insurance protects property buyers against defects in ownership history, which means accurate extraction of names, dates, and addresses from legal documents is core to the business.

## The Stack

- **Model**: llama3.2 via Ollama (local, no API cost)
- **Language**: Python
- **Tasks**: Property document extraction (address, buyer name, document type, missing fields, dates)

## Basic Workflow

Each test case defines:
- A **prompt** sent to the model
- **Expected keywords** that must appear in the response
- **Forbidden keywords** that must not appear (e.g. the seller's name when asking for the buyer)
- A **strict mode** flag that penalizes verbose responses--- this particular model likes to obfuscate by talking too much when it doesn't know what to do, even when explicitly asked to keep responses brief.

The harness runs each test case N times and computes mean accuracy, standard deviation, min/max, and per-test success rates. Future steps here (with some scaling) would probably involve confidence intervals--- I like knowing how much I don't know! 

### Scoring Outcomes
| Result | Meaning |
|---|---|
| PASS | Correct answer, clean response |
| SLOPPY | Correct answer present but response is verbose |
| BOOOOOOO | Wrong answer or refusal |

There's a CONTAMINATED flag in there too, because the model kept having trouble with ambiguity on Prompt 2 (more on that later). 

## Iteration Log

### v1 (Baseline)
Ran 5 test cases with simple prompts. Got 4/5.

The failure in question was TC002 (Extract buyer name): the model refused to extract "Johannes Makarov", treating it as a personal information disclosure rather than a business data extraction task. It had no problems with doing so for a name like Jane Smith, but a more "real" name confused it. 

### v2 (Prompt Engineering)

I thought it might be a good idea to add the business context into that one prompt, a la *"You are a document processing assistant for a title insurance company..."*. 

This still failed. The model's safety guardrail on personal names was strong enough that reframing the business context in the user prompt wasn't enough.

So: 

### v3 (System Prompt Fix)

Moved the business context into Ollama's dedicated system prompt field, which carries more weight than prepending context to the user message.

TC002 started responding--- but it now extracted the wrong name (seller instead of buyer), and added excessive explanation. Two new failure modes identified: wrong entity extraction and sloppy output.

My harness was still passing these most of the time, a consequence of the super basic keyword system I have set-up. As long as the model SAID "Johannes Makarov" it passed. Obviously, this needed a fix.

### v4 (Smarter Scoring)
Realized the scorer was too naive; added:

- **Strict mode** with a `max_extra_chars` threshold to catch correct-but-verbose responses
- **Forbidden keywords** to penalize responses that include the wrong entity even if the right one is also present
- **Three-way scoring**: PASS / SLOPPY / BOOOOOOO

As a consequence, expected keywords need to reflect the full correct answer, not just a substring — otherwise the strict threshold fires incorrectly on valid complete responses.

### v5 (Prompt Refinement (TC002))

This prompt was the one place where my model really struggled. The addition of two names is deliberate--- clearly we would like a model working in this to have a context window that can identify a buyer. 

Of course, a more complex model would have an easier time with this, but I wanted to see if I could get llama3.2 to behave in a way I liked by changing the prompt around. I saw higher accuracy rates after specificying *"The buyer is the person receiving the property transfer."*, and saw less SLOPPY results after specifying *"Respond with just the name, nothing else."*.

Still saw errors, though. The model has on average a 70-80% chance of getting this specific prompt right (an increase from a previous 40-60%). How do I know that? Well: 

### v6 (Statistical Stability Testing)

Calling it v6 is a bit misleading because I started doing this in parallel with v4. I love a little statistical analysis--- nothing too fancy. 

Added N_RUNS parameter to run each test case multiple times and compute:
- Mean accuracy across runs
- Standard deviation (how consistent is the model?)
- Min/max accuracy (what's the worst case?)
- Per-test success rates

Every prompt except for TC002 had a 100% success rate after adding the system context prompt. TC002 settled around 70-80% accuracy over multiple runs. 

This lead to mean accuracy settling at around 90%, with an STD of around 8-10%. About what I'd expect, when dealing with a problem prompt like this. 

## Failure Modes Encountered

| Failure Type | Description | Example |
|---|---|---|
| Safety refusal | Model refuses legitimate business task | "I cannot provide personal information..." |
| Wrong entity | Model extracts correct type but wrong instance | Extracts seller instead of buyer |
| Ambiguity deflection | Model asks a question instead of answering | "Would you like Mikhail's or Johannes' name?" |
| Sloppy output | Correct answer buried in excessive explanation | "Both parties are listed, however..." |


## What I'd Do Next

A lot. This is just for me to play with, and see how this one prewritten, small model functions in a very specific context. The natural next step is running this against a production-grade model via API, but right now I want to consider changes that could be made to the evaluation and harness. 

### Model Comparison
Run the same eval suite across llama3.2, qwen3.5, and a cloud model like Claude or GPT-4 to produce a side-by-side accuracy and latency table. I tried running this with qwen3.5 and received much better performance accuracy-wise, but the latency was through the roof, which is the kind of tradeoff I imagine seeing a lot of in this space. 

### JSON Extraction
Right now scoring is keyword matching on free text. I'm not thrilled about this, but this was a first pass, and the goal was to get something running and see what broke. A more robust approach would prompt the model to return structured JSON:
```json
{"buyer": "Johannes Makarov", "address": "842 Elm Street, Austin, TX 78701"}
```
Then validate the schema programmatically. Much easier to build reliable pipelines on top of, and catches a whole new class of failure modes (missing fields, wrong types, malformed output). 

### Richer Failure Analysis
Cluster failure modes across runs rather than just counting them. Categorize *why* things fail: refusal, wrong entity, ambiguity deflection, verbosity. Understanding the distribution of failure types would help figure out where to focus--- prompt engineering vs. model selection vs. architectural changes.

### Regression Testing in CI
Once we have a passing baseline, any prompt or model change should automatically be checked against it. Did the new prompt fix TC002 without breaking TC001-005? A CI eval pipeline catches regressions before they hit users. This is why the harness right now saves its output in a json--- of course, things would require a lot more scaling till we get to the CI stage, but it's nice to have the base set up. 

### Hallucination Detection
What if the model invents a name or date not present in the document? Current scoring only checks for correct answers--- it doesn't verify that the model isn't fabricating plausible-sounding but wrong information. A hallucination test would add documents with no extractable answer and check that the model says so rather than making something up.

## Takeaway

This was fun! A 100% pass rate on the first run would have been less interesting than this. The failure modes revealed real production concerns--- safety guardrails interfering with business tasks, entity disambiguation, ambiguity deflection, and output verbosity--- some of which I wouldn't have considered without trying this out. 

If I have a little more time to tinker with this, I hope I can hammer something nice out. Eventually the hope is to be able to pass in full pdfs and see how the models react. It'll be fun! 

