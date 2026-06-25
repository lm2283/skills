# Skills

Personal agent skills. Each top-level folder is one skill (an open
[agent-skills](https://agentskills.io) `SKILL.md` plus its resources).

## companies-house-diligence

Turn a UK company's website into a cited, plain-language **Companies House
profile**: ownership graph, group members (filtering same-name impostors),
financials, leverage/risk, and people. See
[`companies-house-diligence/SKILL.md`](companies-house-diligence/SKILL.md).

### Install in Codex

Codex discovers skills in `~/.agents/skills/` (user scope, available in every
repo) or `<repo>/.agents/skills/` (repo scope). Put the skill folder in one of
those. The clean way, so `git pull` keeps it updated, is to clone once and
symlink (Codex follows symlinked skill folders):

```bash
git clone https://github.com/lm2283/skills.git ~/src/lm-skills
mkdir -p ~/.agents/skills
ln -s ~/src/lm-skills/companies-house-diligence ~/.agents/skills/companies-house-diligence
```

(Or just copy it: `cp -r ~/src/lm-skills/companies-house-diligence ~/.agents/skills/`.)

### One-time setup of the skill

The skill is self-contained — its Python venv, API key and outputs all live
inside the skill folder. Run these **from inside the skill directory**:

```bash
cd ~/.agents/skills/companies-house-diligence
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install -e .
```

Then provide a Companies House API key (free, from
<https://developer.company-information.service.gov.uk/>). Either export it in
your shell:

```bash
export COMPANIES_HOUSE_KEY=your_key_here
```

or create a `.env` file in the skill folder containing:

```
COMPANIES_HOUSE_KEY=your_key_here
```

Optional, for the full experience:

- `pandoc` — also emit a styled Word `.docx` profile (Markdown is produced
  either way).
- `poppler-utils` (`pdftoppm`, `pdftotext`) — read scanned group-accounts PDFs.

Restart Codex so it picks up the new skill. Then invoke it explicitly with
`$companies-house-diligence` (or `/skills`), or just give Codex a company
website and ask who owns it.

> Note: `.venv/`, `.env`, `.ch_cache/` and `output/` are git-ignored, so your
> key and generated profiles never get committed.
