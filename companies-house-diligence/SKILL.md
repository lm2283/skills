---
name: companies-house-diligence
description: >-
  Profile a UK company for lead generation and investment/sales due diligence,
  starting from its website. Mines the site for identifiers, anchors them on the
  Companies House APIs, untangles complex ownership (PE/holdco structures) into a
  graph, distinguishes real group members from same-name impostors, and produces
  a cited, plain-language company brief covering ownership, financials, leverage,
  risk and people.
  Use when the user gives a company website (ideally an /about, /contact or
  /legal page) and wants to understand who owns it, what the group looks like,
  and where the commercial or risk signals are.
compatibility: >-
  Cross-platform (Windows, macOS, Linux); pure Python, no admin rights or system
  binaries needed. Requires a Companies House API key in the COMPANIES_HOUSE_KEY
  environment variable or a .env file, and the skill virtualenv at .venv with the
  package installed editable (networkx, requests, matplotlib, scipy, pymupdf).
  PDF pages are rendered to images by pymupdf, so poppler is not needed. Network
  access to *.company-information.service.gov.uk and the target website is
  required. Read-only against Companies House. Optional: pandoc to also emit a
  Word .docx; when pandoc is absent the .docx is skipped and the Markdown
  profile is produced regardless.
---

# Companies House profile

Use this skill to turn a company's website into a structured **Companies House
profile**: a cited, plain-language briefing on a UK company built on the
Companies House Public Data API and Document API.

The work is **prescriptive and phased**. Do the phases in order; each one
feeds the next. Stop and surface a decision to the user at the marked
checkpoints rather than guessing.

The guiding principle throughout: **anchor on identifiers, then reason over a
graph — never trust a company name.** Name search returns impostors; only
ownership paths and shared people/addresses prove group membership.

## Setup

This skill is **self-contained**: it ships its own Python package
(`companies_house_diligence/`), API reference docs (`Documentation/`), and the
pandoc pipeline (`docx-build/`). Everything below runs from **the skill's own
directory** (the folder containing this `SKILL.md`), and all runtime artefacts
(`.venv`, `.env`, `.ch_cache`, `output/`) live there too. The bundled
`.gitignore` keeps those out of version control.

First-time setup, run **from this skill directory**:

```bash
# macOS / Linux
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install -e .            # registers the companies_house_diligence package
```

```powershell
# Windows (PowerShell). The interpreter is .venv\Scripts\python.exe
py -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\pip install -e .
```

The editable install makes `python -m companies_house_diligence...` importable
from this directory.

**Cross-platform notes.** The toolkit is pure Python and runs on Windows, macOS
and Linux with **no admin rights and no system binaries**: PDF pages are
rendered to images by PyMuPDF (a pip wheel, installed by `requirements.txt`),
so poppler / `pdftoppm` is not needed. All files are read and written as UTF-8.
The only optional external tool is **pandoc**, used solely to also emit a Word
`.docx`; when pandoc is absent the toolkit simply skips the `.docx` and the
Markdown profile (the primary artefact) is produced regardless. On Windows,
write `.venv\Scripts\python` wherever the examples below show `.venv/bin/python`.

**Output is plain ASCII by design.** To avoid Windows encoding problems, the
profile is written as ASCII (a pound sign becomes `GBP`, dashes become `-`, and
accented names are flattened, e.g. `Cafe`), and every command forces UTF-8 on
stdout so printing an accented company name never crashes. Keep your own edits
to `brief.md` ASCII too, and run the asciify step (Phase 8) as the last thing
before building the `.docx`. Pass `--no-ascii` to `brief` only if you know the
reader's environment handles UTF-8.

All commands in the phases below assume you are in this skill directory, so the
virtualenv interpreter and the `output/` paths resolve as written. Profiles are
written under `output/` here by default; pass `--out <absolute-path>` if you
want them somewhere else.

## Prerequisites

- API key in the `COMPANIES_HOUSE_KEY` environment variable (recommended):
  `export COMPANIES_HOUSE_KEY=...`. As a fallback the toolkit reads a `.env`
  file containing `COMPANIES_HOUSE_KEY=...`, searching upward from the current
  directory — so a `.env` in this skill directory works when you run from here.
  Get a free key at https://developer.company-information.service.gov.uk/ .
- Run everything with the skill virtualenv, `.venv/bin/python`, from this
  directory.
- API reference docs are in this skill's `Documentation/` directory — open the
  relevant Markdown files directly when you need exact endpoint parameters or
  response fields.

The toolkit is the `companies_house_diligence/` package inside this skill:

| Module | Role |
| --- | --- |
| `client.py` | API client: auth, 429 backoff, on-disk cache, document content |
| `scrape.py` | Phase 1: fetch a page's raw HTML (and likely legal pages); no parsing |
| `graph.py` | networkx schema (Company/External/Person/Address nodes), office occupancy |
| `discover.py` | Phases 2-4: anchor, walk up, discover members, classify |
| `accounts.py` | Phase 5: headline figures from iXBRL accounts; download + render group PDFs to images |
| `enrich.py` | Phases 5-7: financials/risk/people enrichment calls |
| `plain.py` | plain-language helpers: SIC lookup, money/trend formatting, size bands, ASCII transliteration |
| `brief.py` | Phase 8: render the profile (`brief.md`, plus `brief.docx` when pandoc is present) |
| `asciify.py` | rewrite text files (e.g. an edited `brief.md`) as plain ASCII |
| `cli.py` | orchestrates Phases 2-4; writes `output/` |
| `viz.py` | renders the ownership tree and evidence graphs (optional, not embedded) |

The `docx-build/` directory holds the pandoc assets (`reference.docx` and lua
filters); `brief.py` invokes `pandoc` directly (no shell), so the `.docx` build
works the same on Windows, macOS and Linux and is skipped cleanly when pandoc is
not installed.

All code is company-agnostic. Do not hard-code names, numbers or postcodes.

## Quick start (end to end)

```bash
export COMPANIES_HOUSE_KEY=...                       # or put it in .env here

# Phase 1 - fetch the page's raw HTML (and likely legal pages) to read by eye:
.venv/bin/python -m companies_house_diligence.scrape https://www.example.com/contact
#   writes output/_scrape/page_NN_*.html ; read them and find the company number

# Phases 2-4 - anchor, walk ownership up, discover members, classify:
.venv/bin/python -m companies_house_diligence.cli --number 01234567
#   writes a per-company subdir output/<number>_<name-slug>/ (printed as 'output dir')

# point the rest at that subdir:
D=output/01234567_example-limited        # use the dir the CLI printed

# Phases 5-8 - enrich + render the profile (writes $D/brief.md and, when pandoc
# is present, $D/brief.docx; --no-docx to skip):
.venv/bin/python -m companies_house_diligence.brief --out "$D"
```

Each company gets its own `output/<number>_<slug>/` directory, so several
companies can sit side by side. The profile is `$D/brief.md` (plus `$D/brief.docx`
when pandoc is available); supporting artefacts are alongside it. The ownership
tree graphic is **not** embedded in the profile (the text chain of control is
clear enough); render it separately only if you want it (see Visualising the
structure). The phase-by-phase detail below explains each step and how to
interpret it. (Pass `--out <root>` to the CLI to change the output root.)

---

## Phase 1 - Fetch the company's web page

Goal: get the raw HTML in front of you and **read it yourself** for the
high-signal identifiers. You read HTML far more reliably than any regex, so the
toolkit does no parsing; it only fetches.

```bash
.venv/bin/python -m companies_house_diligence.scrape https://www.example.com/contact
#   --no-follow      fetch only this page
#   --max-pages N    how many same-site legal/privacy/contact pages to also fetch (default 6)
#   --out DIR        where to write the .html files (default output/_scrape)
```

This fetches the page and, unless `--no-follow` is set, the top-ranked same-site
legal/privacy/contact links (privacy and legal pages first, because UK companies
must publish their registered number and office somewhere, usually the footer or
a legal page). It writes one `page_NN_<slug>.html` per page and prints the
paths. (You can equally fetch with `curl -sL <url>` if you prefer.)

Then **read those `.html` files** and pick out, by eye:

- **company registration number** - the killer identifier: 8 digits, or a
  2-letter prefix + 6 digits such as `SC`, `NI`, `OC`
- legal entity name(s) (anything ending Limited/Ltd/PLC/LLP)
- **registered-office address / postcode** (used to confirm a name match)
- VAT number, contact emails (supporting only)

Prefer `/about`, `/contact`, `/legal`, `/terms` and `/privacy` pages.

**Checkpoint:** if no company number appears anywhere, note it; Phase 2 can fall
back to name + postcode search, which is weaker.

---

## Phase 2 - Anchor on a single company

Resolve what you read to exactly one Companies House entity.

```bash
# preferred: you found the registration number on the page
.venv/bin/python -m companies_house_diligence.cli --number 01234567

# fallback: no number on the page, so match by name and the office postcode you saw
.venv/bin/python -m companies_house_diligence.cli --name "Example Ltd" --postcode "EC1N 8TE"
```

Anchoring confidence, in order:

1. **Verified company number** -> high confidence.
2. **Name + registered-office postcode match** -> high confidence.
3. **Name best-guess only** (no postcode match) -> low confidence; flag for the user.

The CLI prints the anchor and method, and creates the per-company output
subdirectory. **Checkpoint:** if confidence is low, confirm the entity with the
user before proceeding.

Read the anchor's profile critically. **Previous names are a strong tell**:
names like `... (BIDCO) LIMITED`, `... TOPCO`, `... MIDCO`, `... HOLDCO` signal a
private-equity buyout structure, which means you must trace ownership upward,
not stop at the first entity.

---

## Phase 3 - Walk the ownership chain upward

The CLI follows active corporate **PSC** (persons-with-significant-control)
edges from the anchor up to the ultimate UK-visible owner, resolving parents
by name when a PSC record omits its registration number.

It prints the chain, for example a PE stack:

```
^ OPERATING CO  →  ^ BIDCO  →  ^ DEBTCO  →  ^ MIDCO  →  ^ TOPCO
  →  ^ (newer acquisition layer)  →  ^ HOLDCO  ~ external controller [Jersey]
```

Interpretation:

- A chain ending in an **overseas holdco** (Jersey, Guernsey, Luxembourg,
  Cayman) controlled by a named **PE/fund manager** = private-equity ownership.
- **Newly created intermediate layers** (incorporated in the last 1–2 years)
  on top of an older stack indicate a **recent transaction / refinancing** —
  a material timing signal for sales and investment.
- The ultimate owner's *type* (PE fund / trade group / family / individual /
  overseas parent) frames everything downstream.

---

## Phase 4 - Discover group members and filter impostors

This runs as part of the same CLI command as Phases 2-3. It discovers candidate
group members two ways, then classifies each by graph topology, never by name:

1. **Name stem** — the top `--max-candidates` (default 40) relevance-ranked
   search hits for the anchor's distinctive name token.
2. **Shared registered office** — every company at the anchor's office
   postcode(s), but only when that address is **not a shared-service address**.
   The CLI probes each office's true occupancy (advanced-search `hits`); an
   address occupied by more than `OFFICE_SHARED_MAX` (200) companies is a
   formation agent or accountant, carries no group signal, and is skipped for
   candidate generation. Its true occupancy is still recorded so the classifier
   discounts it as a connector (see `graph.office_occupancy`). A separate,
   lower threshold (`discover.HIGH_FAN_OUT`, 25) governs classification: a
   shared office busier than this counts only as a weak/discounted connector,
   even when it was small enough to be crawled for candidates.

This is a deliberately bounded heuristic, not an exhaustive crawl (Companies
House has no list-subsidiaries endpoint). It will not find a member that shares
neither a name stem nor a non-shared registered office; state that limitation.

```bash
# --stem lets you set the name fragment to search (default: first token of the
# anchor's name). Pick a distinctive stem.
.venv/bin/python -m companies_house_diligence.cli --number 01234567 --stem ACME
```

Outputs (in the per-company subdir `output/<number>_<slug>/`, referred to as
`$D` below):

- `structure.json` — anchor, ownership chain, and every company with a label
- `structure.graphml` — the full graph (open in Gephi/yEd, or render below)

### How membership is decided (and how to explain it)

| Label | Meaning | Evidence |
| --- | --- | --- |
| **Confirmed** | Real group member | Active PSC ownership path connects it to the anchor / ultimate owner |
| **Probable** | Almost certainly in-group | No crawled ownership path, but ≥2 independent low-traffic connectors (shared officer **and** shared registered office) |
| **Possible** | Needs human review | Exactly one weak connector |
| **Excluded** | Same-name impostor | No ownership path and no low-traffic shared connector — a different component of the graph |

The key insight: the real group forms **one connected component** (shared PSC
edges, directors, registered office); a true namesake is disconnected or linked
only by a high-traffic shared-service address (a formation agent or
accountant), which is discounted.

**Always present Probable/Possible with their evidence, and never assert that a
Probable company is in-group without saying it is unconfirmed.**

---

## Visualising the structure (optional)

The profile does not embed any graphic; the text chain of control conveys the
structure. These renders are optional standalone diagnostics, useful when you
want to inspect ownership or justify a soft classification. Keep the two views
separate: a clean ownership story, and the evidence behind the soft
classifications.

```bash
# 1. Clean confirmed ownership tree (companies + ownership only):
.venv/bin/python -m companies_house_diligence.viz "$D/structure.graphml" \
    --classes "$D/structure.json" --mode confirmed --out "$D/confirmed_tree.png"
#   add --orient LR for a left-to-right tree

# 2. One focused 'why is X Probable?' evidence graph per Probable/Possible node:
.venv/bin/python -m companies_house_diligence.viz "$D/structure.graphml" \
    --classes "$D/structure.json" --mode probables --outdir "$D/probables"

# 3. (optional) full evidence hairball — companies + all shared people/addresses:
.venv/bin/python -m companies_house_diligence.viz "$D/structure.graphml" \
    --classes "$D/structure.json" --mode connectors --out "$D/connectors.png"
```

Conventions: green = Confirmed, amber = Probable, orange = Possible, red =
Excluded, grey = unexpanded stub. Solid dark arrows = ownership (controller →
controlled); blue squares = shared people; purple diamonds = shared addresses.

The `confirmed` tree and the per-Probable graphs are standalone diagnostics; the
profile itself stays text-only. Share a render with the user only if they ask.

---

## Phases 5-8 - Enrich and produce the profile

Phases 5-7 (financials, leverage/risk, people/triggers) and Phase 8 (the
Markdown profile) are run by a single command once discovery has written
`$D/structure.json`:

```bash
.venv/bin/python -m companies_house_diligence.brief --out "$D"
#   --no-financials / --no-risk    skip those enrichment calls
#   --download-accounts            download group-accounts PDFs and render them to images
#   --no-docx                      write Markdown only (skip the .docx)
```

This writes `$D/brief.md` and, when pandoc is available, `$D/brief.docx` (pandoc
is invoked directly, no shell; pass `--no-docx` to skip, and it is skipped
automatically when pandoc is not installed). The profile is text-only and embeds
no graphic. The sections below explain what each phase gathers and how to read
it; the underlying calls are documented in `Documentation/` (open the relevant
Markdown files directly).

### Phase 5 - financials (with real figures)

There are two places the numbers live, and the toolkit handles each differently:

**a) The company's own accounts (iXBRL — extracted automatically).** Most small
and micro UK companies file accounts as **iXBRL** (`application/xhtml+xml`):
machine-readable XML with every figure tagged by an FRS taxonomy concept.
`accounts.fetch_figures()` pulls the headline facts straight out
— net worth, cash, net current assets, headcount, and turnover/profit *when
disclosed* — for the current and prior year, and the brief prints them as a
plain table with year-on-year trends. No PDF reading needed. (Note: small
companies often elect **not** to file a profit & loss account, so turnover and
profit may simply be absent; balance-sheet items still come through.)

**b) Whole-group (consolidated) accounts (usually PDF - often scanned).** Real
group revenue/EBITDA sit in the **group accounts**, filed at one or two entities
in the chain. The tool flags every Confirmed company whose `accounts_type` is
`group`. These are frequently filed as **PDF only**, and large audited group
accounts are often **scanned images with no text layer**, so they cannot be
parsed. With `--download-accounts` the tool downloads each such PDF and renders
**every page to a high-quality image** (via PyMuPDF), into a self-contained
folder per document:

```
$D/group_accounts_<number>/
    accounts.pdf
    pages/
        page_001.png
        page_002.png
        ...
```

**Read the page images directly (you are multimodal).** Open the PNGs under
`$D/group_accounts_<number>/pages/` with the `read` tool and transcribe the
headline figures into the profile's Financial summary. There is no text
extraction step and no fallback: the images are the interface. The pages worth
reading, in order:

- **Contents** (page ~2) - gives the exact page numbers of each statement.
- **Strategic report** (early) - the plain-English story: what they do, any
  **acquisition / buyout** (date, buyer, enterprise value, new debt raised),
  and the growth strategy. This is usually the richest "why reach out now".
- **Consolidated income statement** - Revenue, gross profit, operating
  profit/loss, finance costs, profit/loss before tax, and any **management
  revenue / management EBITDA** (the non-GAAP numbers PE owners actually track).
- **Consolidated balance sheet** - total assets, cash, **borrowings**
  (the leveraged debt), net assets / total equity.
- The **subsidiary note** ("Investments"/"Group undertakings") - the definitive
  list of group members, including differently-named ones the Phase 4 search
  missed. Cross-check it against the Confirmed list and add any it names.

State in plain terms what the numbers mean - e.g. a heavily indebted PE-owned
group can be highly profitable at the EBITDA level yet report a pre-tax *loss*
purely because of interest on the buyout debt; that is a financing artefact, not
a failing business. Always cite the entity, statement and period you read from.

### Phase 6 - leverage and risk

For each Confirmed company the tool reports **charges** (outstanding vs
satisfied, `created_on`, and `persons_entitled` — the lenders / security
trustees) and any **insolvency** history. An outstanding charge with a security
trustee at a finance entity is the acquisition/leveraged debt — note its date
and holder; legacy bank debentures that are satisfied are historical.

For notable directors you can additionally screen disqualifications by hand:
`GET /search/disqualified-officers?q=<name>` — any hit is a serious flag.

### Phase 7 - people and timing triggers

The tool lists the anchor's **current directors**, **recent board changes**
(last ~18 months — a new CEO/CFO or a departing founder is a strong sales and
governance signal), **recently incorporated** group entities, and **rebrands**
(`former_names`, which often expose the whole acquisition history). New
`Newco/Bidco` layers from Phase 3 are the clearest "why reach out now" hook.

### Phase 8 - the profile

`brief.md` is titled "Companies House profile" and is written for a reader
without a finance background, in a measured, presentable register suitable for
forwarding to a sales director: plain headings, plain tables, minimal markdown
styling, no emoji, and no scattered editorialising.

Structure:

- **Summary** — a short prose paragraph (or two) at the top: what the company
  is, its size, ownership type, financial position and recent events. Keep the
  factual framing here; the explicit lead view lives in the next section.
- **Lead assessment** — a measured, sales-oriented read of how well-qualified
  the company looks *as a lead*, drawn only from Companies House signals (see
  the sales-lens pass below).
- **Registration details**, **Ownership and group structure**, **Financial
  summary**, **Borrowing and risk**, **Directors and recent changes**,
  **Glossary** (only the terms actually used), **References**, **Caveats**.

**Editorial passes, in this order.** After `brief.py` writes the draft, refine
it on `brief.md` in this sequence, then build the `.docx` last:

1. Rewrite the *Ownership and group structure* section (see below).
2. Fill in the *Financial summary* from the rendered group-account images
   (Phase 5), with citations.
3. The **sales-lens pass** on the Summary and Lead assessment (see below).
4. The **styling pass** that removes machine-written tics (see below).

**Presenting the group structure (do this deliberately; it is the part readers
remember).** `brief.py` emits a serviceable default for *Ownership and group
structure* — a bare chain of control, a flat list of external controllers, and
an alphabetical dump of every Confirmed member. Treat that as raw material and
**rewrite the section** into the opinionated style below. Do not lead with the
alphabetical member list.

- **Lead with a short transaction narrative, not the list.** Say in plain prose
  what the structure *is* and *how it came to be*: who ultimately controls it
  (named PE firm / founder / family / overseas parent), when the newest holding
  layer was incorporated, and — from the strategic report when you have read it
  — the buyout date, buyer(s), enterprise value and new debt raised. This is the
  "why reach out now" and belongs up front. A two-layer stack (a recent Newco
  layer sitting on an older one) is the clearest signal of a recent
  transaction; say so explicitly.
- **Keep the chain as an indented hierarchy, without inline labels.** Retain
  the default code-block chain exactly as `brief.py` renders it — each company
  on its own line, progressively indented so the nesting shows control at a
  glance — and do **not** append `-- role` comments to the lines. Convey roles
  (principal trading company, intermediate holdings, the Bidco/Finco that raised
  the debt, the ultimate parent that files the group accounts) in the
  surrounding prose instead, so the chain itself stays clean. Show the ultimate
  human / PE controllers in the narrative rather than as a detached list.
- **Name and source soft or non-obvious members.** Call out by name any
  Confirmed member that automated name/address search would miss (e.g. a
  differently-named subsidiary confirmed only by the parent's group-accounts
  subsidiary note), and state the authority: "on the authority of the filed
  group accounts, not guessed." Present Probable/Possible with their evidence as
  leads to verify, never as fact.
- **Keep, but demote, the full Confirmed list.** A large group's full member
  list is reference material: place it after the narrative (or summarise as
  "N confirmed members; full list below / in structure.json"). Lead with meaning.

**Sections are conditional.** The tool omits a section when it has nothing to
report (for example, no "Ownership and group structure" for a standalone
company, and no "Borrowing and risk" when there are no charges or insolvency).
You may trim further by judgement: drop anything that is not decision-relevant
for the company in front of you, and lead with whatever matters most for that
company.

**Citations.** Facts and figures carry numbered `[n]` markers tied to the exact
Companies House page or filing they came from (profile, PSC, charges, officers,
filing history). The markers resolve in a **References** list; the **Caveats**
section is separate and states the limitations. When you transcribe figures from
a group-account image (Phase 5), cite the source filing the same way.

Always present Probable/Possible as leads to verify, never as fact. Attach the
per-Probable evidence graphs from `$D/probables/` as an appendix if the user
wants the justification. Offer JSON alongside Markdown if useful
(`structure.json` already holds the structured data).

**Sales-lens pass (do this after the figures are in, before the styling pass).**
`brief.py` emits a measured *Lead assessment* by rule from Companies House
signals (size, growth, ownership/decision-making, timing triggers, risk) plus a
plain *Summary*. Refine both with a sales reader in mind, and keep them honest:

- **Qualify the lead, do not sell it.** State how well-qualified the company
  looks as a lead and why, in plain terms. Stay measured and free of hyperbole:
  no "exciting opportunity", no superlatives, no manufactured urgency.
- **Be honest when nothing stands out.** If the Companies House record shows
  nothing that clearly marks the company out, say so plainly ("nothing here
  strongly distinguishes it as a lead; prioritise only if other signals support
  it"). A lukewarm or negative read is more useful than false enthusiasm.
- **Lead with the "why now" and "why them".** Surface the genuine hooks a
  salesperson can act on: a recent buyout or refinancing, a new CEO/CFO, rapid
  growth, a new market, a newly incorporated entity. Tie the qualification to
  these, not to vague potential.
- **State the basis and its limits.** This judgement rests only on Companies
  House data, which carries no contact, product-fit, current-project or
  buying-intent information. Keep the line that says so; it is one input to lead
  qualification, not the whole picture.
- **Calibrate to size and ownership.** Budget capacity scales with size; a
  PE-owned group buys centrally and on ROI; a subsidiary may not hold the
  budget; an owner-managed company is a direct founder sell. Reflect this in the
  qualification rather than treating every company the same.

**Styling pass (do this last, on `brief.md`, before building the `.docx`).**
Re-read the finished brief and strip the tics that make text read as
machine-written, so it looks like a person wrote it:

- **Remove em dashes and en dashes.** `brief.py` writes ASCII, so its own dashes
  are already hyphens, but you may have typed `--` or pasted a dash while
  editing. Replace a dash standing in for punctuation with a comma, a colon, a
  full stop, or parentheses, whichever the sentence needs, and rephrase if a
  dash was papering over a weak join. Keep hyphens in genuine compounds
  (`asset-based`, `private-equity-backed`) and number ranges (`50-75%`, `3-9`).
- **Cut excessive bolding.** Bold is for table headers and at most the occasional
  genuinely key figure, not for emphasising whole phrases mid-sentence. Remove
  inline bold runs in prose; if a sentence only works because a phrase is
  bold, rewrite the sentence. Section headings already stand out, so do not bold
  text inside them.
- **Drop other LLM hallmarks:** no emoji, no decorative curly quotes where a
  plain one will do, no "In conclusion / Overall / It's worth noting that"
  filler, and no three-item parallel triads added for rhythm rather than fact.
- **Re-assert plain ASCII.** As the very last step, run
  `python -m companies_house_diligence.asciify "$D/brief.md"` so any non-ASCII
  you introduced while editing (a pasted pound sign, a smart quote, an accented
  name) is normalised. Money reads as `GBP` rather than a pound sign by design.
- Then rebuild the `.docx` from the cleaned Markdown so both outputs match.

The goal is plain, declarative prose a sales director would not clock as
AI-generated. Do not change any figure, name, citation marker or caveat while
doing this; it is a copy-edit, not a rewrite.

---

## Limitations and caveats (state these in the brief)

- Companies House has **no "list subsidiaries" endpoint**; downward discovery
  is a bounded heuristic (name stem + non-shared-service registered office), so
  the group list may be incomplete. Confirmed is reliable; Probable/Possible are
  not proof.
- **Person identity resolution is pragmatic** (`name + month/year of birth`);
  name variants, honorifics or missing DOBs can leave the same person as more
  than one node. Treat shared-person evidence as supporting, not decisive.
- **Overseas and branch entities** (Jersey holdcos, `BR`/`FC` registrations)
  carry no PSC/officer data and will appear as external nodes or fall out of
  classification — note them rather than treating them as excluded.
- **Financial figures** come from filed accounts: headline balance-sheet/P&L
  facts are extracted automatically from **iXBRL** for companies that file it
  (most small/micro entities), but small companies may omit a profit & loss
  account, and large **group accounts are usually PDF-only and often scanned
  images** — those are downloaded and rendered to page images for you to read
  directly (see Phase 5).
- Data reflects the latest filings, which can lag real-world events.
