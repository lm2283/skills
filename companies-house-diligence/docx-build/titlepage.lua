-- titlepage.lua — opt-in cover page + table of contents for the docx build.
--
-- Behaviour is driven entirely by YAML frontmatter, so whether a given
-- document gets a title page / TOC is a property of the *source*, not the
-- build tool:
--
--   ---
--   subtitle: "IKEM Ambient AI Proof of Concept"   # optional
--   author:   "InterSystems"                       # optional
--   date:     "June 2026"                          # optional
--   titlepage: true        # render a branded cover page
--   toc: true              # insert a Table of Contents after the cover
--   ---
--   # Scope of Work (SOW)   <- becomes the cover title automatically
--   ## Background           <- promoted to Heading 1 in the body
--
-- When `titlepage: true`:
--   * The document's leading level-1 heading is lifted out and used as the
--     cover title (unless an explicit `title:` is set in frontmatter), and
--     every remaining heading is promoted one level (## -> #, ### -> ## ...).
--     This means the same Markdown reads naturally with or without a cover:
--     drop the flag and the H1 simply stays as the top section heading.
--   * A cover page is prepended: brand logo, title, optional subtitle, and
--     optional author/date line, sitting in their own Word section so a
--     teal brand rail can run down the page edge (see patch-reference.py).
--
-- `toc: true` injects a Word TOC field (levels 1-3). Word populates it on
-- open / when fields are updated (it will offer, or press F9 / right-click ->
-- Update Field). Works independently of `titlepage`.

local LOGO = "assets/intersystems-logo-color.png"

-- Coerce a metadata value that may be a MetaBool or a string ("true"/"yes")
-- into a Lua boolean.
local function meta_true(v)
  if v == nil then return false end
  if type(v) == "boolean" then return v end
  local s = pandoc.utils.stringify(v):lower()
  return s == "true" or s == "yes" or s == "1"
end

-- A bare page break paragraph.
local function page_break()
  return pandoc.RawBlock("openxml",
    '<w:p><w:r><w:br w:type="page"/></w:r></w:p>')
end

-- A "next page" section break carrying the cover section's page geometry
-- (A4, 2.54cm margins). The brand rail itself is drawn as a page-anchored
-- floating shape (see brand_rail) rather than a page border, so it can carry
-- the teal->indigo gradient of the Marp lead slide.
local function cover_section_break()
  return pandoc.RawBlock("openxml", table.concat({
    '<w:p><w:pPr><w:sectPr>',
      '<w:pgSz w:w="11906" w:h="16838"/>',
      '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"',
      ' w:header="720" w:footer="720" w:gutter="0"/>',
    '</w:sectPr></w:pPr></w:p>',
  }))
end

-- Brand rail: a full-height ~5pt vertical bar at the left page edge with a
-- teal->indigo vertical gradient, mirroring section::before in the Marp
-- intersystems-light theme. Implemented as a VML rectangle anchored to the
-- page (z-index behind text). Because a floating shape renders on the page
-- where its anchor paragraph is laid out, this appears only on the cover.
-- The anchor paragraph is made effectively zero-height so it adds no visible
-- space above the logo.
local function brand_rail()
  return pandoc.RawBlock("openxml", table.concat({
    '<w:p><w:pPr>',
      '<w:spacing w:before="0" w:after="0" w:line="20" w:lineRule="exact"/>',
      '<w:rPr><w:sz w:val="2"/></w:rPr>',
    '</w:pPr>',
    '<w:r><w:rPr><w:noProof/><w:sz w:val="2"/></w:rPr><w:pict>',
      '<v:rect id="brand-rail" o:spid="_x0000_s1026"',
      ' style="position:absolute;left:0;margin-top:0;width:5pt;',
      'height:11.7in;',
      'mso-position-horizontal-relative:page;mso-position-vertical:top;',
      'mso-position-vertical-relative:page;z-index:-251658240"',
      ' fillcolor="#00B2A9" stroked="f">',
        '<v:fill type="gradient" angle="180" color="#00B2A9" color2="#2F2A95"/>',
      '</v:rect>',
    '</w:pict></w:r></w:p>',
  }))
end

-- Word TOC field (levels 1-3, hyperlinked). `w:dirty` asks Word to refresh
-- it. The visible placeholder shows until the field is updated.
local function toc_field()
  return pandoc.RawBlock("openxml", table.concat({
    '<w:p><w:pPr><w:rPr><w:noProof/></w:rPr></w:pPr>',
    '<w:r><w:fldChar w:fldCharType="begin" w:dirty="true"/></w:r>',
    '<w:r><w:instrText xml:space="preserve"> TOC \\o "1-3" \\h \\z \\u </w:instrText></w:r>',
    '<w:r><w:fldChar w:fldCharType="separate"/></w:r>',
    '<w:r><w:t xml:space="preserve">Update this field to generate the table of contents (right-click &gt; Update Field, or press F9).</w:t></w:r>',
    '<w:r><w:fldChar w:fldCharType="end"/></w:r>',
    '</w:p>',
  }))
end

local function styled(style, blocks)
  -- NOTE: pandoc resolves custom-style by the style's *name* (w:name), not its
  -- styleId. The value passed here must therefore match the w:name set in
  -- patch-reference.py, otherwise pandoc fabricates an empty duplicate style
  -- (which Word then applies instead of the branded one).
  return pandoc.Div(blocks, pandoc.Attr("", {}, { ["custom-style"] = style }))
end

function Pandoc(doc)
  local meta = doc.meta
  local want_cover = meta_true(meta.titlepage)
  local want_toc   = meta_true(meta.toc)

  if not want_cover and not want_toc then
    return nil
  end

  local body = doc.blocks
  local cover = {}

  if want_cover then
    -- Lift the leading H1 into the title (unless one is already set) and
    -- promote every remaining heading by one level.
    local title_inlines = nil
    if body[1] and body[1].t == "Header" and body[1].level == 1 then
      if meta.title == nil then
        title_inlines = body[1].content
      end
      table.remove(body, 1)
    end
    body = pandoc.walk_block(pandoc.Div(body), {
      Header = function(h)
        if h.level > 1 then
          h.level = h.level - 1
          return h
        end
      end,
    }).content

    if title_inlines == nil and meta.title ~= nil then
      title_inlines = { pandoc.Str(pandoc.utils.stringify(meta.title)) }
    end
    title_inlines = title_inlines or {}

    -- Cover blocks: rail, logo, title, optional subtitle, optional author/date.
    table.insert(cover, brand_rail())
    table.insert(cover, styled("Title Page Logo", {
      pandoc.Para({ pandoc.Image("InterSystems", LOGO, "",
        pandoc.Attr("", {}, { width = "2.6in" })) }),
    }))
    table.insert(cover, styled("Title Page Title", {
      pandoc.Para(title_inlines),
    }))
    if meta.subtitle ~= nil then
      table.insert(cover, styled("Title Page Subtitle", {
        pandoc.Para({ pandoc.Str(pandoc.utils.stringify(meta.subtitle)) }),
      }))
    end

    -- author / date line (author may be a single value or a list)
    local meta_bits = {}
    if meta.author ~= nil then
      local a = meta.author
      if a.t == "MetaList" then
        local names = {}
        for _, item in ipairs(a) do names[#names + 1] = pandoc.utils.stringify(item) end
        table.insert(meta_bits, table.concat(names, ", "))
      else
        table.insert(meta_bits, pandoc.utils.stringify(a))
      end
    end
    if meta.date ~= nil then
      table.insert(meta_bits, pandoc.utils.stringify(meta.date))
    end
    if #meta_bits > 0 then
      table.insert(cover, styled("Title Page Meta", {
        pandoc.Para({ pandoc.Str(table.concat(meta_bits, "  \u{2022}  ")) }),
      }))
    end

    table.insert(cover, cover_section_break())
  end

  if want_toc then
    table.insert(cover, styled("TOC Heading", { pandoc.Para({ pandoc.Str("Contents") }) }))
    table.insert(cover, toc_field())
    table.insert(cover, page_break())
  end

  local out = {}
  for _, b in ipairs(cover) do table.insert(out, b) end
  for _, b in ipairs(body)  do table.insert(out, b) end

  -- Suppress pandoc's own writer-injected title block and auto-TOC: we have
  -- consumed these into the cover / injected our own field, so clear the
  -- metadata keys the docx writer would otherwise render at the top.
  meta.toc = nil
  if want_cover then
    meta.title = nil
    meta.subtitle = nil
    meta.author = nil
    meta.date = nil
  end

  return pandoc.Pandoc(out, meta)
end
