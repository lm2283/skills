-- table-width.lua
--
-- Pandoc emits Markdown pipe tables with no column widths, which become a
-- zero-width DOCX table that LibreOffice/Word collapse to a single visible
-- column. This filter gives any table whose columns have no explicit width an
-- even split across the full page width, so the DOCX gets a proper column grid
-- and renders at 100% width. Tables that already specify relative widths are
-- left untouched.
--
-- Handles both the pandoc >= 2.10 Table API (colspecs) and the pandoc < 2.10
-- API (aligns/widths).

local function all_zero(widths)
  for _, w in ipairs(widths) do
    if type(w) == "number" and w > 0 then
      return false
    end
  end
  return true
end

function Table(tbl)
  -- Newer API: tbl.colspecs = list of { alignment, width }
  if tbl.colspecs ~= nil then
    local specs = tbl.colspecs
    local n = #specs
    if n == 0 then return nil end
    local widths = {}
    for i = 1, n do widths[i] = specs[i][2] end
    if not all_zero(widths) then return nil end
    local even = 1.0 / n
    for i = 1, n do specs[i] = { specs[i][1], even } end
    tbl.colspecs = specs
    return tbl
  end

  -- Older API: tbl.widths = list of numbers
  if tbl.widths ~= nil then
    local n = #tbl.widths
    if n == 0 then return nil end
    if not all_zero(tbl.widths) then return nil end
    local even, w = 1.0 / n, {}
    for i = 1, n do w[i] = even end
    tbl.widths = w
    return tbl
  end

  return nil
end
