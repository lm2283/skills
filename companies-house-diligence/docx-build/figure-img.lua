-- Convert raw <img> tags (inline or block) into native Pandoc Image
-- elements so the docx writer embeds them. Also strip surrounding
-- <figure>/<figcaption> wrapper tags that pandoc would otherwise drop
-- silently.

local function extract_attr(html, name)
  return html:match(name .. '%s*=%s*"([^"]*)"')
      or html:match(name .. "%s*=%s*'([^']*)'")
end

-- Usable page width on A4 with 2.54cm (1") margins (210mm - 2*25.4mm).
local PAGE_WIDTH_IN = 6.27

local function width_to_pandoc(w)
  if not w then return nil end
  -- Convert percentages to absolute inches; pandoc 2.9's docx writer
  -- doesn't reliably honour % widths and falls back to native PNG size.
  local pct = w:match("^([%d%.]+)%%$")
  if pct then
    return string.format("%.2fin", (tonumber(pct) / 100) * PAGE_WIDTH_IN)
  end
  if w:match("%a") then return w end
  return w .. "px"
end

local function img_from_html(html)
  local src = extract_attr(html, "src")
  if not src then return nil end
  local alt   = extract_attr(html, "alt") or ""
  local width = width_to_pandoc(extract_attr(html, "width"))
  local attrs = {}
  if width then attrs["width"] = width end
  return pandoc.Image(alt, src, "", pandoc.Attr("", {}, attrs))
end

-- Inline <img>: replace with native Image wrapped so the docx writer
-- applies the centered "Figure" paragraph style.
function RawInline(el)
  if el.format ~= "html" then return nil end
  local tag = el.text:match("<img[^>]*>")
  if not tag then
    -- Drop wrapper tags so they don't pollute output
    if el.text:match("^</?figure") or el.text:match("^</?figcaption") then
      return {}
    end
    return nil
  end
  return img_from_html(tag)
end

-- When a block contains only an image (optionally with whitespace),
-- wrap it in a Div carrying custom-style="Figure" so it's centered.
local function wrap_if_image_only(el)
  local has_image, only_image = false, true
  for _, inl in ipairs(el.content) do
    if inl.t == "Image" then
      has_image = true
    elseif inl.t ~= "Space" and inl.t ~= "SoftBreak" and inl.t ~= "LineBreak" then
      only_image = false
    end
  end
  if has_image and only_image then
    return pandoc.Div({ el }, pandoc.Attr("", {}, { ["custom-style"] = "Figure" }))
  end
end

-- A figcaption in the source is rendered as a Plain whose inlines start
-- with a raw <em> tag and end with a raw </em> tag. Detect that pattern,
-- replace the raw HTML wrappers with real Emph, and apply the centered
-- "Caption" Word style.
local function wrap_if_caption(el)
  local inls = el.content
  if #inls < 2 then return nil end
  local first, last = inls[1], inls[#inls]
  local is_em_open  = first.t == "RawInline" and first.format == "html"
                       and first.text:match("^<em[%s>]")
  local is_em_close = last.t  == "RawInline" and last.format  == "html"
                       and last.text:match("^</em%s*>$")
  if not (is_em_open and is_em_close) then return nil end

  local inner = {}
  for i = 2, #inls - 1 do table.insert(inner, inls[i]) end
  local para = pandoc.Para({ pandoc.Emph(inner) })
  return pandoc.Div({ para }, pandoc.Attr("", {}, { ["custom-style"] = "Caption" }))
end

function Para(el)  return wrap_if_image_only(el) or wrap_if_caption(el) end
function Plain(el) return wrap_if_image_only(el) or wrap_if_caption(el) end

-- Block-level raw HTML: strip <figure>/<figcaption> wrappers,
-- and convert any block <img> tags into Image paragraphs.
function RawBlock(el)
  if el.format ~= "html" then return nil end
  local txt = el.text

  if txt:match("^%s*</?figure[^>]*>%s*$")
     or txt:match("^%s*</?figcaption[^>]*>%s*$") then
    return {}
  end

  if txt:find("<img", 1, true) then
    local inlines = {}
    for tag in txt:gmatch("<img[^>]*>") do
      local img = img_from_html(tag)
      if img then table.insert(inlines, img) end
    end
    if #inlines > 0 then return pandoc.Para(inlines) end
  end

  return nil
end
