-- sections.lua — per-document heading numbering and optional heading rules,
-- driven by YAML frontmatter so each source decides its own look:
--
--   ---
--   number-sections: true   # prefix headings with 1, 1.1, 1.1.1 ...
--   heading-rules: true     # draw a thin teal rule under H1 / H2
--   ---
--
-- Both default to off. A heading carrying the `.unnumbered` class (Pandoc's
-- `# Heading {-}`) is skipped by the numberer. Numbers are written as text
-- into the heading, so they render identically everywhere (Word, the PDF
-- preview, etc.) and regenerate from source on each build.
--
-- This runs after titlepage.lua, so heading levels reflect any title-page
-- promotion (## -> # ...) before they are counted.

local function meta_true(v)
  if v == nil then return false end
  if type(v) == "boolean" then return v end
  local s = pandoc.utils.stringify(v):lower()
  return s == "true" or s == "yes" or s == "1"
end

-- A standalone hairline paragraph (HeadingRule style, defined in
-- patch-reference.py) placed directly beneath a heading.
local function rule_para()
  return pandoc.RawBlock("openxml",
    '<w:p><w:pPr><w:pStyle w:val="HeadingRule"/></w:pPr></w:p>')
end

function Pandoc(doc)
  local number = meta_true(doc.meta["number-sections"])
  local rules  = meta_true(doc.meta["heading-rules"])
  if not number and not rules then
    return nil
  end

  local counters = { 0, 0, 0, 0, 0, 0, 0, 0, 0 }
  local out = {}

  for _, blk in ipairs(doc.blocks) do
    if blk.t == "Header" then
      local lvl = blk.level

      if number and not blk.classes:includes("unnumbered") then
        counters[lvl] = counters[lvl] + 1
        for i = lvl + 1, #counters do counters[i] = 0 end
        local parts = {}
        for i = 1, lvl do parts[#parts + 1] = tostring(counters[i]) end
        local label = table.concat(parts, ".")
        -- e.g. "1", "1.1", "1.1.1" followed by an em-space before the text.
        table.insert(blk.content, 1, pandoc.Str("\u{2003}"))
        table.insert(blk.content, 1, pandoc.Str(label))
      end

      table.insert(out, blk)

      if rules and (lvl == 1 or lvl == 2) then
        table.insert(out, rule_para())
      end
    else
      table.insert(out, blk)
    end
  end

  return pandoc.Pandoc(out, doc.meta)
end
