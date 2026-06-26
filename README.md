# Skills

Personal agent skills. Each top-level folder is one skill (an open
[agent-skills](https://agentskills.io) `SKILL.md` plus its resources).

## companies-house-diligence

Turn a UK company's website into a cited, plain-language **Companies House
profile**: ownership graph, group members (filtering same-name impostors),
financials, leverage/risk, and people. See
[`companies-house-diligence/SKILL.md`](companies-house-diligence/SKILL.md).

### Install in Codex (works on Windows, macOS and Linux)

Codex discovers skills in `~/.agents/skills/` (user scope, available in every
repo) or `<repo>/.agents/skills/` (repo scope). Put the skill folder in one of
those. The clean way, so `git pull` keeps it updated, is to clone once and
symlink (Codex follows symlinked skill folders):

```bash
git clone https://github.com/lm2283/skills.git ~/src/lm-skills
mkdir -p ~/.agents/skills
ln -s ~/src/lm-skills/companies-house-diligence ~/.agents/skills/companies-house-diligence
```

(Or just copy it: `cp -r ~/src/lm-skills/companies-house-diligence ~/.agents/skills/`.
On Windows, copy the folder into `%USERPROFILE%\.agents\skills\`.)

### One-time setup of the skill

The skill is self-contained: its Python venv, API key and outputs all live
inside the skill folder, and it needs no admin rights or system binaries. Run
these **from inside the skill directory**:

```bash
# macOS / Linux
cd ~/.agents/skills/companies-house-diligence
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install -e .
```

```powershell
# Windows (PowerShell)
cd $env:USERPROFILE\.agents\skills\companies-house-diligence
py -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\pip install -e .
```

Then provide a Companies House API key (free, from
<https://developer.company-information.service.gov.uk/>). Either export it in
your shell (`export COMPANIES_HOUSE_KEY=...`, or `setx COMPANIES_HOUSE_KEY ...`
on Windows), or create a `.env` file in the skill folder containing:

```
COMPANIES_HOUSE_KEY=your_key_here
```

No other tools are required: PDF accounts are rendered to images by PyMuPDF (a
pip wheel, already in `requirements.txt`), so poppler is not needed.
**Optional:** install `pandoc` to also emit a styled Word `.docx`; without it
the skill just produces the Markdown profile and skips the `.docx`.

Restart Codex so it picks up the new skill. Then invoke it explicitly with
`$companies-house-diligence` (or `/skills`), or just give Codex a company
website and ask who owns it.

> Note: `.venv/`, `.env`, `.ch_cache/` and `output/` are git-ignored, so your
> key and generated profiles never get committed.
