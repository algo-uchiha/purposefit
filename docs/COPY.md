# PurposeFit copy base (v1 submission)

Voice: a friend explaining it over coffee. Short words, concrete examples, no jargon on the main screens.
References studied: Vanta ("Get your compliance together": a casual command plus one plain line), Tonic ("real fake data": a small twist on familiar words), Skyflow (a short blunt headline, the explaining happens in the line below). We copy the pattern, not the words.

Rules
- Headline: 3 to 7 words, says one thing. Line under it: what it does, in words a non-technical person uses.
- No em dashes, no emoji, sentence case.
- Never use: unlock, seamless, leverage, empower, revolutionary, cutting-edge, next-generation, robust, holistic, AI-powered, game-changing.
- Every claim must be in docs/FACTS.md or come from the fixtures. "Nothing is leaked" is never promised; we say what was measured and on which data.
- Name meaning, if asked: the copy is fitted to the purpose. Purpose, fit.

## The idea in one breath (for the video and for judges)
Every time you share data, the other person only needs part of it. PurposeFit makes a copy with just that part, checks it, and only then lets it leave.

## Tagline options (pick one for the hero)
1. Send the data. Keep the details.   (recommended: plain, rhythmic, says exactly what it does)
2. Share the data, not the people.    (stronger emotion, slightly more abstract)
3. Give them what they need. Nothing more.
4. Hand over data, not secrets.
5. Only the data they need.   (shortest, good as the nav tagline or video end card)

Hero line under the tagline (use with option 1):
"Whenever you share data, the other side only needs part of it. PurposeFit makes a copy with just that part and checks it before it leaves."

Even simpler alternative:
"Sending data to someone? They don't need every detail. We make a copy with only what their job needs."

Pill above the headline: "Built for the TrustED PETs challenge, Since AI Hackathon 2026"
Buttons: "Try the demo" and "See what changes". Third link in the footer and the last panel: "Read the code".
Small note under the hero buttons: "Version 1 runs on prepared example data. Uploading your own files is next."

## Landing, five screens

### 1. Score
Headline options: "Safer. And still useful." / "Hide the details. Keep the value." (recommended: second)
Line: "Hiding everything makes data safe but useless. Hiding nothing makes it useful but risky. PurposeFit scores 0.98 out of 1 on the challenge data. The best standard method scores 0.58."
Caption under the chart: "Score on the challenge's customer service data. It counts how well people are protected and how useful the data stays."
Bar labels: "Shared as it is", "Best standard method", "PurposeFit".

### 2. What changes
Headline: "Everyone gets their own copy."
Line: "The analytics team doesn't need names. An outside vendor doesn't need ages. Each person gets only what their job needs."
Example card titles: "The original record", "Copy for the analytics team", "Copy for an outside vendor".
Footnote: "Made-up example."

### 3. How it works
Headline: "Four steps. No black box."
Line: "Open a file. We show what we found, what we changed and why."
1. "Spot the private bits": "Finds names, ID numbers, birth dates, places and health details, in tables and in what people said on calls."
2. "Ask what it's for": "Who gets the copy, and what will they do with it? That decides what stays."
3. "Hide what isn't needed": "Names become codes. Exact dates become ranges. Private words in call text are blacked out."
4. "Check before it leaves": "Runs the privacy checks and writes a short report anyone can read."

### 4. Safety
Headline: "Locked until it's safe."
Line: "The download button stays off until every check passes."
Stat captions (numbers from fixtures):
- "names or ID numbers left" (0)
- "Every person hides in a crowd of at least 5"
- "of identifying details left in call text" (0.9%)
- "health details left in call text, down from 95.6%" (0%)
Footnote: "Measured on the challenge's practice data."
Honest line: "Version 1 works on prepared files. Database connections and user accounts are not built yet."

### 5. Demo
Headline: "See it work on real data."
Line: "Open the demo. The customer service data is already loaded. Pick who the copy is for and watch it change."
Cards: "1. Look at the data", "2. Choose who it's for", "3. Check and download".
Buttons: "Try the demo", "Read the code".
Footer: "PurposeFit. Built at Since AI Hackathon 2026, Turku."

## Words on screen: say it this way
| Technical term | On screen |
|---|---|
| direct identifier | Points straight at a person |
| quasi identifier | Could point at someone when combined |
| pseudonymise | Replace with a code |
| generalise | Group into ranges |
| redact | Black out |
| k-anonymity (k at least 5) | Hidden in a crowd of at least 5 |
| utility | How useful the data stays |
| privacy risk | Chance someone can be found |
| scenario | Who the copy is for |
| policy card | Report |
| gate | Checks |
| export | Download |
Technical names live in the report page only.

## Workbench screens
Sidebar steps: "Your data", "Choose protection", "Check the proof", "Download".

Your data
- Title: "Start with an example."
- Line: "This is the data PurposeFit will protect. Look it over, then we find what's private."
- Caption: "Showing 25 of {n}"
- Note: "Uploading your own file is not built yet. This demo uses prepared example data."
- Button: "Find what's private"

Here is what we found
- Title: "Here's what we found."
- Line: "Red points straight at a person. Amber can point at someone when combined. Everything else is safe on its own."
- Chips: "Points at a person", "Could point at someone", "Safe on its own", "Free text"
- Button: "Choose who the copy is for"

Choose protection
- Title: "Who is this copy for?"
- Line: "We suggest what to do with each column. You can change any of them."
- Actions: "Replace with a code", "Group into ranges", "Remove", "Black out private words", "Keep as is"
- Why lines: "The team needs to link calls from the same person, not know who they are." / "Not needed for this job." / "An age range is enough." / "A region shows where demand is, not a street." / "Names, IDs and health details are removed. The topic stays." / "The team measures it."
- Button: "Protect this copy"; hint: "Takes a moment. The proof comes next."

Call text
- Title: "Private words, found and hidden."
- Line: "People say names, ID numbers and health problems out loud, even spelled out digit by digit. We find them and black them out. The topic of the call stays."
- Labels in the safe copy: NAME, ID NUMBER, HEALTH DETAIL (match the redactor's real labels)
- Button: "Continue to the proof"

Check the proof
- Title when all pass: "All checks passed."
- Title when one fails: "One check failed. This copy stays locked."
- Line: "Every check must pass before the download opens."
- Check names: "Names and IDs left", "Smallest crowd", "Private details in call text"
- Buttons: "Read the report", "Download safe copy"
- Locked button tooltip: "Locked until every check passes."

Download
- Title: "Your safe copy is ready."
- Line: "Same rows, same usefulness, nobody to point at."
- Summary heading: "What changed in this copy" with real counts: "{n} values replaced with codes", "{n} values grouped into ranges", "{n} values removed", "{n} private words blacked out"
- Buttons: "Download safe copy", "Read the report"

Empty and error states
- Loading: "Working on it. Large files take a moment."
- Server unreachable: "Can't reach the server. Is the demo running?"
- Gate refused (409): "This copy didn't pass the checks, so it can't be downloaded."

## Report (policy card) intro, for non-experts
"This report says what was removed, what was changed and what was kept in this copy, and why. It uses the terms from the European Data Protection Board's guidelines on pseudonymisation (01/2025)."

## Names and small copy
- Product: PurposeFit. Nav tagline: "Only the data they need."
- Meta description: "PurposeFit makes a safe copy of your data for each person you share it with, and checks it before it leaves."
- Repo one-liner: "Purpose-based privacy for shared data: detect, minimise, protect, prove."
