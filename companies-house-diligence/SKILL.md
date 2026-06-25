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
  Requires a Companies House API key in the COMPANIES_HOUSE_KEY environment
  variable or a .env file, and the project virtualenv at .venv with the package
  installed editable (networkx, requests, matplotlib, scipy, pypdf). Network
  access to *.company-information.service.gov.uk and the target website is
  required. Read-only against Companies House. Optional: pandoc (with the
  bundled docx-build tool) to also emit a Word .docx, and the pdftoppm tool
  (poppler-utils) to rasterise scanned group-accounts PDFs for reading.
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

This is a project skill living in `.pi/skills/companies-house-diligence/`
(SKILL.md, the `companies_house_diligence/` package, `Documentation/`,
`docx-build/`, `requirements.txt`, `pyproject.toml`). Runtime artefacts
(`.venv`, `.env`, `.ch_cache`, `output/`) live at the **project root**, which is
also the working directory for every command below.

First-time setup, run from the project root:

```bash
python -m venv .venv
.venv/bin/pip install -r .pi/skills/companies-house-diligence/requirements.txt
.venv/bin/pip install -e .pi/skills/companies-house-diligence   # registers the package
```

The editable install makes `python -m companies_house_diligence...` importable
from the project root regardless of where the skill lives. To also produce Word
`.docx` profiles, install `pandoc` (the profile builds Markdown either way and
falls back gracefully when pandoc is absent).

## Prerequisites

- API key available as `COMPANIES_HOUSE_KEY` (the toolkit also reads `.env` at
  the project root).
- Run everything with the project virtualenv, `.venv/bin/python`, from the
  project root.
- API reference docs are in this skill's `Documentation/` directory — consult
  them with the `read-md` skill when you need exact endpoint parameters or
  response fields.

The toolkit is the `companies_house_diligence/` package inside this skill:

| Module | Role |
| --- | --- |
| `client.py` | API client: auth, 429 backoff, on-disk cache, document content |
| `scrape.py` | Phase 1: extract identifiers from a web page |
| `graph.py` | networkx schema (Company/External/Person/Address nodes), office occupancy |
| `discover.py` | Phases 2–3b: anchor, walk up, discover members, classify |
| `accounts.py` | Phase 4: pull headline figures from filed accounts (iXBRL) + fetch group PDFs |
| `enrich.py` | Phases 4–6: financials/risk/people enrichment calls |
| `plain.py` | plain-language helpers: SIC lookup, money/trend formatting, size bands |
| `brief.py` | Phase 7: render the Companies House profile (`brief.md`, and `brief.docx` via pandoc) |
| `cli.py` | orchestrates Phases 1–3b; writes `output/` |
| `viz.py` | renders the ownership tree and evidence graphs (optional, not embedded) |

The `docx-build/` directory holds the pandoc pipeline (`reference.docx` and lua
filters, driven by `build.sh`); `brief.py` calls `build.sh` to convert
`brief.md` into a styled Word document.

All code is company-agnostic. Do not hard-code names, numbers or postcodes.

## Quick start (end to end)

```bash
export COMPANIES_HOUSE_KEY=...                       # or rely on .env
# 1-3b: identify, anchor, ownership, members, classify.
# Writes to a per-company subdir: output/<number>_<name-slug>/ (printed as 'output dir').
.venv/bin/python -m companies_house_diligence.cli --url https://www.example.com/about/

# point the rest at that subdir:
D=output/01234567_example-limited        # use the dir the CLI printed

# 4-7: enrich + render the profile (writes $D/brief.md and, if pandoc is
# present, $D/brief.docx via the bundled docx-build tool; --no-docx to skip).
.venv/bin/python -m companies_house_diligence.brief --out "$D"
```

Each company gets its own `output/<number>_<slug>/` directory, so several
companies can sit side by side in the same repo. The profile is `$D/brief.md`
(plus `$D/brief.docx`); supporting artefacts are alongside it. The ownership
tree graphic is **not** embedded in the profile (the text chain of control is
clear enough); render it separately only if you want it (see Visualising the
structure). The phase-by-phase detail below explains each step and how to
interpret it. (Pass `--out <root>` to the CLI to change the output root.)

---

## Phase 1 — Identify the company from its website

Goal: extract high-signal identifiers, not marketing prose. The richest
sources are the **footer**, **structured data** (`<script type="application/
ld+json">`) and contact/legal pages.

You have two equivalent options:

1. **Let the toolkit scrape** (default): pass the URL to the CLI in Phase 2.
2. **Read the raw HTML yourself**: fetch the page (`curl -sL <url>`), read it,
   and pick out identifiers by eye. Viewing raw HTML is often enough — look for:
   - **company registration number** (the killer identifier: 8 digits, or a
     2-letter prefix + 6 digits such as `SC`, `NI`, `OC`)
   - VAT number, legal entity name(s) (anything ending Limited/Ltd/PLC/LLP)
   - **registered-office address / postcode** (used later to correlate)
   - contact emails and phone numbers

Prefer `/about`, `/contact`, `/legal`, `/terms` and `/privacy` pages — UK
companies must publish their registered number and office somewhere, usually
the footer or a legal page.

**Auto-following.** When the toolkit scrapes (option 1) and the page you give it
has no company number, the CLI automatically follows same-site
legal/privacy/contact links (ranked: privacy and legal pages first) and merges
their identifiers, stopping as soon as a number is found. So a bare `/contact`
URL whose number actually lives on `/privacy-policy` now anchors on its own. The
pages it read are printed and saved in `identifiers.json` (`pages_read`). Use
`--no-follow` to disable this, or `--max-pages N` to widen/narrow the crawl
(default 6, same host only). A saved `--html` file is never crawled.

**Checkpoint:** if no company number is found anywhere, note it; Phase 2 will
fall back to name + postcode search, which is weaker.

---

## Phase 2 — Anchor on a single company

Resolve the identifiers to exactly one Companies House entity.

```bash
# from a URL (toolkit scrapes the page):
.venv/bin/python -m companies_house_diligence.cli --url https://www.example.com/about/

# or anchor directly if you already know the number:
.venv/bin/python -m companies_house_diligence.cli --number 01234567

# or from a saved HTML file:
.venv/bin/python -m companies_house_diligence.cli --url https://example.com --html saved.html
```

Anchoring logic (in order of confidence):

1. **Company number on the page** → verify it resolves → high confidence.
2. **Name + registered-office postcode match** → high confidence.
3. **Name best-guess only** → low confidence; flag for the user.

The CLI prints the anchor and method. **Checkpoint:** if confidence is low,
confirm the entity with the user before proceeding.

Read the anchor's profile critically. **Previous names are a strong tell**:
names like `… (BIDCO) LIMITED`, `… TOPCO`, `… MIDCO`, `… HOLDCO` signal a
private-equity buyout structure — which means you must trace ownership upward,
not stop at the first entity.

---

## Phase 3 — Walk the ownership chain upward

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

## Phase 3b — Discover group members and filter impostors

This is where the graph earns its keep. The CLI discovers candidate group
members two ways, then classifies each by graph topology, never by name:

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
.venv/bin/python -m companies_house_diligence.cli --url https://www.example.com/about/ --stem ACME
```

Outputs (in the per-company subdir `output/<number>_<slug>/`, referred to as
`$D` below):

- `identifiers.json` — what Phase 1 extracted
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

## Phases 4–7 — Enrich and produce the brief

Phases 4–6 (financials, leverage/risk, people/triggers) and Phase 7 (the
Markdown brief) are run by a single command once discovery has written
`$D/structure.json`:

```bash
.venv/bin/python -m companies_house_diligence.brief --out "$D"
#   --no-financials / --no-risk    skip those enrichment calls
#   --download-accounts            download group-accounts PDFs that have no iXBRL
#   --no-docx                      write Markdown only (skip the .docx)
```

This writes `$D/brief.md` and, when pandoc is available, `$D/brief.docx` (via
the bundled `docx-build/` pipeline; pass `--no-docx` to skip). The profile is
text-only and embeds no graphic.
The sections below explain what each phase gathers and how to read it; the
underlying calls are documented in `Documentation/` (use the `read-md` skill).

### Phase 4 — financials (with real figures)

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

**b) Whole-group (consolidated) accounts (usually PDF — often scanned).** Real
group revenue/EBITDA sit in the **group accounts**, filed at one or two entities
in the chain. The tool flags every Confirmed company whose `accounts_type` is
`group`. These are frequently filed as **PDF only**, and large audited group
accounts are often **scanned images with no text layer** — so they cannot be
parsed automatically. With `--download-accounts` the tool downloads each such
PDF next to the brief and reports whether it has a readable text layer.

**When the group PDF is image-only, read it yourself (you are vision-capable).**
Rasterise the relevant pages and read them:

```bash
# find the statements via the Contents page, then render a few pages to PNG
pdftoppm -png -r 120 -f <first> -l <last> "$D/group_accounts_<number>.pdf" /tmp/pg
```

Then open the PNGs with the `read` tool and transcribe the headline figures into
the brief's Money section. The pages worth reading, in order:

- **Contents** (page ~2) — gives the exact page numbers of each statement.
- **Strategic report** (early) — the plain-English story: what they do, any
  **acquisition / buyout** (date, buyer, enterprise value, new debt raised),
  and the growth strategy. This is usually the richest "why reach out now".
- **Consolidated income statement** — Revenue, gross profit, operating
  profit/loss, finance costs, profit/loss before tax, and any **management
  revenue / management EBITDA** (the non-GAAP numbers PE owners actually track).
- **Consolidated balance sheet** — total assets, cash, **borrowings**
  (the leveraged debt), net assets / total equity.

State in plain terms what the numbers mean — e.g. a heavily indebted PE-owned
group can be highly profitable at the EBITDA level yet report a pre-tax *loss*
purely because of interest on the buyout debt; that is a financing artefact, not
a failing business. Always cite the entity, statement and period you read from.

### Phase 5 — leverage and risk

For each Confirmed company the tool reports **charges** (outstanding vs
satisfied, `created_on`, and `persons_entitled` — the lenders / security
trustees) and any **insolvency** history. An outstanding charge with a security
trustee at a finance entity is the acquisition/leveraged debt — note its date
and holder; legacy bank debentures that are satisfied are historical.

For notable directors you can additionally screen disqualifications by hand:
`GET /search/disqualified-officers?q=<name>` — any hit is a serious flag.

### Phase 6 — people and timing triggers

The tool lists the anchor's **current directors**, **recent board changes**
(last ~18 months — a new CEO/CFO or a departing founder is a strong sales and
governance signal), **recently incorporated** group entities, and **rebrands**
(`former_names`, which often expose the whole acquisition history). New
`Newco/Bidco` layers from Phase 3 are the clearest "why reach out now" hook.

### Phase 7 — the profile

`brief.md` is titled "Companies House profile" and is written for a reader
without a finance background, in a measured, presentable register suitable for
forwarding to a sales director: plain headings, plain tables, minimal markdown
styling, no emoji, and no scattered editorialising.

Structure:

- **Summary** — a short prose paragraph (or two) at the top: what the company
  is, its size, ownership type, financial position, recent events, and a single
  brief note on commercial relevance. All commercial framing lives here; the
  rest of the brief is factual.
- **Registration details**, **Ownership and group structure**, **Financial
  summary**, **Borrowing and risk**, **Directors and recent changes**,
  **Glossary** (only the terms actually used), **References**, **Caveats**.

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
a PDF by hand (Phase 4), cite the source filing the same way.

Always present Probable/Possible as leads to verify, never as fact. Attach the
per-Probable evidence graphs from `$D/probables/` as an appendix if the user
wants the justification. Offer JSON alongside Markdown if useful
(`structure.json` already holds the structured data).

**Final styling pass (do this last, on `brief.md`, before building the
`.docx`).** Re-read the finished brief and strip the tics that make text read as
machine-written, so it looks like a person wrote it:

- **Remove em dashes and en dashes.** Replace `—` / `–` with a comma, a colon,
  a full stop, or parentheses — whichever the sentence actually needs — and
  rephrase if a dash was papering over a weak join. Keep hyphens in genuine
  compounds (`asset-based`, `private-equity-backed`) and the number ranges in
  the chain/tables (e.g. `50-75%`, page `3-9`).
- **Cut excessive bolding.** Bold is for table headers and at most the occasional
  genuinely key figure, not for emphasising whole phrases mid-sentence. Remove
  inline `**…**` runs in prose; if a sentence only works because a phrase is
  bold, rewrite the sentence. Section headings already stand out, so do not bold
  text inside them.
- **Drop other LLM hallmarks:** no emoji, no “curly” decorative quotes where a
  plain one will do, no “In conclusion / Overall / It's worth noting that”
  filler, and no three-item parallel triads added for rhythm rather than fact.
- Then rebuild the `.docx` from the cleaned Markdown so both outputs match.

The goal is plain, declarative prose a sales director would not clock as
AI-generated. Do not change any figure, name, citation marker or caveat while
doing this — it is a copy-edit, not a rewrite.

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
  images** — those must be read by hand (rasterise + read; see Phase 4).
- Data reflects the latest filings, which can lag real-world events.
