#!/usr/bin/env python3
"""Patch documents/docx-build/reference.docx into an InterSystems-branded
light template, so pandoc-generated Word documents share the visual language
of the Marp `intersystems-light` slide theme.

It applies:
  - Brand colour scheme (indigo #2F2A95, teal #00B2A9, deep blue #006990,
    sky #92C0E9, lilac #C5B4E2, coral #FFA489) as the document theme.
  - Arial as both major (heading) and minor (body) theme fonts.
    (Arial is metric-identical to the open Liberation Sans that LibreOffice
    substitutes on Linux, so line breaking matches between Word and the
    LibreOffice-based PDF previews. Verdana — the Marp deck font — has no
    widely shipped open metric clone, so it drifts between the two.)
  - Body text at 11pt in near-black ink (#1C1B3A).
  - Title / Subtitle and Heading 1-4 styled in the brand palette, with a
    teal rule beneath Heading 1.
  - Brand-coloured hyperlinks (deep blue, underlined).
  - A branded default table style: indigo header row with white bold text
    and light horizontal rules.
  - Centred Figure and Caption paragraph styles (as before).

Run:  python3 documents/docx-build/patch-reference.py
Then rebuild:  ./documents/docx-build/build.sh
"""
import re
import shutil
import subprocess
import zipfile
from pathlib import Path

# ---- brand palette (matches presentations/marp-build/themes/intersystems-light.css)
INDIGO = "2F2A95"   # accent1 / headings
TEAL   = "00B2A9"   # accent2 / rules + accents
DEEP   = "006990"   # accent3 / sub-headings + links
SKY    = "92C0E9"   # accent4
LILAC  = "C5B4E2"   # accent5
CORAL  = "FFA489"   # accent6
INK    = "1C1B3A"   # body text
RULE   = "D9D7EC"   # table borders
RULE_LT = "EDEBF6"  # inside-row rules
FONT   = "Arial"

HERE = Path(__file__).resolve().parent
REF = HERE / "reference.docx"
WORK = HERE / ".ref-tmp"

# ---- brand logo for opt-in title pages ----------------------------------
# titlepage.lua embeds documents/docx-build/assets/intersystems-logo-color.png.
# It is rasterised once from the Marp theme's vector logo via LibreOffice so
# the Word cover shares the exact same wordmark as the slide deck. We only
# (re)generate it when missing, keeping this script fast and offline-friendly;
# delete the PNG to force a refresh.
LOGO_SVG = (HERE / ".." / ".." / "presentations" / "marp-build" / "themes"
            / "assets" / "intersystems-logo-color.svg").resolve()
LOGO_PNG = HERE / "assets" / "intersystems-logo-color.png"

def ensure_logo():
    if LOGO_PNG.exists():
        return
    if not LOGO_SVG.exists():
        print(f"WARNING: logo source not found ({LOGO_SVG}); title pages will"
              " have no logo until assets/intersystems-logo-color.png exists.")
        return
    soffice = shutil.which("libreoffice") or shutil.which("soffice")
    if not soffice:
        print("WARNING: LibreOffice not found; cannot rasterise the logo."
              " Provide assets/intersystems-logo-color.png manually.")
        return
    LOGO_PNG.parent.mkdir(exist_ok=True)
    # Scale the SVG up (it caps ~2048px wide) for a crisp print logo.
    svg = LOGO_SVG.read_text()
    svg = svg.replace('width="600" height="160.3"', 'width="2400" height="641.2"')
    tmp_svg = HERE / "assets" / "_logo-src.svg"
    tmp_svg.write_text(svg)
    subprocess.run([soffice, "--headless", "--convert-to", "png",
                    "--outdir", str(LOGO_PNG.parent), str(tmp_svg)], check=True)
    (LOGO_PNG.parent / "_logo-src.png").rename(LOGO_PNG)
    tmp_svg.unlink()
    print(f"Generated: {LOGO_PNG}")

ensure_logo()

# Regenerate a clean default reference doc each time so this script is idempotent.
subprocess.run(
    ["pandoc", "-o", str(REF), "--print-default-data-file", "reference.docx"],
    check=True,
)

if WORK.exists():
    shutil.rmtree(WORK)
WORK.mkdir()
with zipfile.ZipFile(REF) as z:
    z.extractall(WORK)

styles_path = WORK / "word" / "styles.xml"
theme_path  = WORK / "word" / "theme" / "theme1.xml"
document_path = WORK / "word" / "document.xml"

# --- 0. Page geometry: explicit A4 + 2.54cm margins (~6.27" usable width) ---
# The pandoc default reference.docx ships an empty <w:sectPr/>, which makes
# pandoc's docx writer fall back to a default image-width cap that may not
# match the real text column, so wide images (e.g. width="100%") can render
# smaller than requested while narrower ones render exactly, producing
# inconsistent figure sizes. Pin the section geometry to A4 (11906 x 16838
# twips) with 2.54cm (1440-twip = 1") margins so the usable width is a known
# ~6.27" and matches the PAGE_WIDTH_IN assumption in figure-img.lua.
document_xml = document_path.read_text()
sect_pr = (
    "<w:sectPr>"
    '<w:pgSz w:w="11906" w:h="16838" />'
    '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"'
    ' w:header="720" w:footer="720" w:gutter="0" />'
    "</w:sectPr>"
)
document_xml, n_sect = re.subn(r'<w:sectPr\s*/>|<w:sectPr>.*?</w:sectPr>',
                              lambda _m: sect_pr, document_xml, count=1, flags=re.S)
if n_sect != 1:
    raise SystemExit("sectPr not found / not unique in document.xml")
document_path.write_text(document_xml)

# --- 1. Theme: brand colour scheme + Arial fonts ------------------------
theme_xml = theme_path.read_text()

brand_scheme = (
    '<a:clrScheme name="InterSystems">'
    '<a:dk1><a:sysClr val="windowText" lastClr="000000" /></a:dk1>'
    '<a:lt1><a:sysClr val="window" lastClr="FFFFFF" /></a:lt1>'
    f'<a:dk2><a:srgbClr val="{INDIGO}" /></a:dk2>'
    '<a:lt2><a:srgbClr val="F2F2F2" /></a:lt2>'
    f'<a:accent1><a:srgbClr val="{INDIGO}" /></a:accent1>'
    f'<a:accent2><a:srgbClr val="{TEAL}" /></a:accent2>'
    f'<a:accent3><a:srgbClr val="{DEEP}" /></a:accent3>'
    f'<a:accent4><a:srgbClr val="{SKY}" /></a:accent4>'
    f'<a:accent5><a:srgbClr val="{LILAC}" /></a:accent5>'
    f'<a:accent6><a:srgbClr val="{CORAL}" /></a:accent6>'
    f'<a:hlink><a:srgbClr val="{DEEP}" /></a:hlink>'
    f'<a:folHlink><a:srgbClr val="{INDIGO}" /></a:folHlink>'
    '</a:clrScheme>'
)
theme_xml = re.sub(r'<a:clrScheme .*?</a:clrScheme>', brand_scheme, theme_xml, count=1, flags=re.S)

def set_latin(xml, scheme_tag, typeface):
    pattern = rf'(<a:{scheme_tag}>.*?<a:latin\s+typeface=")[^"]*(")'
    return re.sub(pattern, rf'\g<1>{typeface}\g<2>', xml, count=1, flags=re.S)

theme_xml = set_latin(theme_xml, "majorFont", FONT)
theme_xml = set_latin(theme_xml, "minorFont", FONT)
theme_path.write_text(theme_xml)

# --- 2. Patch styles.xml -------------------------------------------------
styles_xml = styles_path.read_text()

def replace_style(xml, style_id, new_block):
    pattern = rf'<w:style [^>]*w:styleId="{style_id}"[^>]*>.*?</w:style>'
    out, n = re.subn(pattern, lambda _m: new_block, xml, count=1, flags=re.S)
    if n != 1:
        raise SystemExit(f"Style not found / not unique: {style_id}")
    return out

def add_style(xml, new_block):
    """Insert a brand-new style definition just before </w:styles>."""
    out, n = re.subn(r'</w:styles>', new_block + "\n</w:styles>", xml, count=1)
    if n != 1:
        raise SystemExit("</w:styles> not found")
    return out

# Normal: Arial 11pt (sz is half-points), near-black ink.
styles_xml = replace_style(styles_xml, "Normal", f'''<w:style w:type="paragraph" w:default="1" w:styleId="Normal">
    <w:name w:val="Normal" />
    <w:qFormat />
    <w:rPr>
      <w:rFonts w:asciiTheme="minorHAnsi" w:hAnsiTheme="minorHAnsi" w:cstheme="minorBidi" />
      <w:color w:val="{INK}" />
      <w:sz w:val="22" />
      <w:szCs w:val="22" />
    </w:rPr>
  </w:style>''')

# Title: indigo, bold, left-aligned, with a teal rule beneath.
styles_xml = replace_style(styles_xml, "Title", f'''<w:style w:type="paragraph" w:styleId="Title">
    <w:name w:val="Title" />
    <w:basedOn w:val="Normal" />
    <w:next w:val="BodyText" />
    <w:qFormat />
    <w:pPr>
      <w:keepNext />
      <w:keepLines />
      <w:spacing w:before="240" w:after="120" />
    </w:pPr>
    <w:rPr>
      <w:rFonts w:asciiTheme="majorHAnsi" w:eastAsiaTheme="majorEastAsia" w:hAnsiTheme="majorHAnsi" w:cstheme="majorBidi" />
      <w:b />
      <w:bCs />
      <w:color w:val="{INDIGO}" />
      <w:sz w:val="52" />
      <w:szCs w:val="52" />
    </w:rPr>
  </w:style>''')

# Subtitle: deep blue, left-aligned.
styles_xml = replace_style(styles_xml, "Subtitle", f'''<w:style w:type="paragraph" w:styleId="Subtitle">
    <w:name w:val="Subtitle" />
    <w:basedOn w:val="Title" />
    <w:next w:val="BodyText" />
    <w:qFormat />
    <w:pPr>
      <w:keepNext />
      <w:keepLines />
      <w:spacing w:before="120" w:after="240" />
      <w:pBdr>
        <w:bottom w:val="none" w:sz="0" w:space="0" w:color="auto" />
      </w:pBdr>
    </w:pPr>
    <w:rPr>
      <w:b w:val="0" />
      <w:color w:val="{DEEP}" />
      <w:sz w:val="30" />
      <w:szCs w:val="30" />
    </w:rPr>
 </w:style>''')

# Heading 1: indigo, bold, 18pt, teal rule beneath.
styles_xml = replace_style(styles_xml, "Heading1", f'''<w:style w:type="paragraph" w:styleId="Heading1">
    <w:name w:val="Heading 1" />
    <w:basedOn w:val="Normal" />
    <w:next w:val="BodyText" />
    <w:uiPriority w:val="9" />
    <w:qFormat />
    <w:pPr>
      <w:keepNext />
      <w:keepLines />
      <w:spacing w:before="400" w:after="120" />
      <w:outlineLvl w:val="0" />
    </w:pPr>
    <w:rPr>
      <w:rFonts w:asciiTheme="majorHAnsi" w:eastAsiaTheme="majorEastAsia" w:hAnsiTheme="majorHAnsi" w:cstheme="majorBidi" />
      <w:b />
      <w:bCs />
      <w:color w:val="{INDIGO}" />
      <w:sz w:val="36" />
      <w:szCs w:val="36" />
    </w:rPr>
  </w:style>''')

# Heading 2: indigo, bold, 15pt.
styles_xml = replace_style(styles_xml, "Heading2", f'''<w:style w:type="paragraph" w:styleId="Heading2">
    <w:name w:val="Heading 2" />
    <w:basedOn w:val="Normal" />
    <w:next w:val="BodyText" />
    <w:uiPriority w:val="9" />
    <w:unhideWhenUsed />
    <w:qFormat />
    <w:pPr>
      <w:keepNext />
      <w:keepLines />
      <w:spacing w:before="280" w:after="80" />
      <w:outlineLvl w:val="1" />
    </w:pPr>
    <w:rPr>
      <w:rFonts w:asciiTheme="majorHAnsi" w:eastAsiaTheme="majorEastAsia" w:hAnsiTheme="majorHAnsi" w:cstheme="majorBidi" />
      <w:b />
      <w:bCs />
      <w:color w:val="{INDIGO}" />
      <w:sz w:val="30" />
      <w:szCs w:val="30" />
    </w:rPr>
  </w:style>''')

# Heading 3: deep blue, bold, 13pt.
styles_xml = replace_style(styles_xml, "Heading3", f'''<w:style w:type="paragraph" w:styleId="Heading3">
    <w:name w:val="Heading 3" />
    <w:basedOn w:val="Normal" />
    <w:next w:val="BodyText" />
    <w:uiPriority w:val="9" />
    <w:unhideWhenUsed />
    <w:qFormat />
    <w:pPr>
      <w:keepNext />
      <w:keepLines />
      <w:spacing w:before="240" w:after="80" />
      <w:outlineLvl w:val="2" />
    </w:pPr>
    <w:rPr>
      <w:rFonts w:asciiTheme="majorHAnsi" w:eastAsiaTheme="majorEastAsia" w:hAnsiTheme="majorHAnsi" w:cstheme="majorBidi" />
      <w:b />
      <w:bCs />
      <w:color w:val="{DEEP}" />
      <w:sz w:val="26" />
      <w:szCs w:val="26" />
    </w:rPr>
  </w:style>''')

# Heading 4: teal, bold, 12pt.
styles_xml = replace_style(styles_xml, "Heading4", f'''<w:style w:type="paragraph" w:styleId="Heading4">
    <w:name w:val="Heading 4" />
    <w:basedOn w:val="Normal" />
    <w:next w:val="BodyText" />
    <w:uiPriority w:val="9" />
    <w:unhideWhenUsed />
    <w:qFormat />
    <w:pPr>
      <w:keepNext />
      <w:keepLines />
      <w:spacing w:before="240" w:after="80" />
      <w:outlineLvl w:val="3" />
    </w:pPr>
    <w:rPr>
      <w:rFonts w:asciiTheme="majorHAnsi" w:eastAsiaTheme="majorEastAsia" w:hAnsiTheme="majorHAnsi" w:cstheme="majorBidi" />
      <w:b />
      <w:bCs />
      <w:color w:val="{TEAL}" />
      <w:sz w:val="24" />
      <w:szCs w:val="24" />
    </w:rPr>
  </w:style>''')

# Hyperlink: deep blue, underlined.
styles_xml = replace_style(styles_xml, "Hyperlink", f'''<w:style w:type="character" w:styleId="Hyperlink">
    <w:name w:val="Hyperlink" />
    <w:basedOn w:val="BodyTextChar" />
    <w:rPr>
      <w:color w:val="{DEEP}" />
      <w:u w:val="single" />
    </w:rPr>
  </w:style>''')

# Figure: centered.
styles_xml = replace_style(styles_xml, "Figure", '''<w:style w:type="paragraph" w:customStyle="1" w:styleId="Figure">
    <w:name w:val="Figure" />
    <w:basedOn w:val="Normal" />
    <w:pPr>
      <w:jc w:val="center" />
    </w:pPr>
  </w:style>''')

# Caption: centered, italic, muted.
styles_xml = replace_style(styles_xml, "Caption", f'''<w:style w:type="paragraph" w:styleId="Caption">
    <w:name w:val="Caption" />
    <w:basedOn w:val="Normal" />
    <w:link w:val="BodyTextChar" />
    <w:pPr>
      <w:spacing w:before="0" w:after="160" />
      <w:jc w:val="center" />
    </w:pPr>
    <w:rPr>
      <w:i />
      <w:color w:val="{DEEP}" />
      <w:sz w:val="20" />
      <w:szCs w:val="20" />
    </w:rPr>
  </w:style>''')

# TOC heading ("Contents"): indigo, like Heading 1 but never numbered and
# kept out of the TOC itself.
styles_xml = replace_style(styles_xml, "TOCHeading", f'''<w:style w:type="paragraph" w:styleId="TOCHeading">
    <w:name w:val="TOC Heading" />
    <w:basedOn w:val="Heading1" />
    <w:next w:val="Normal" />
    <w:uiPriority w:val="39" />
    <w:unhideWhenUsed />
    <w:qFormat />
    <w:pPr>
      <w:spacing w:before="0" w:after="160" />
      <w:outlineLvl w:val="9" />
    </w:pPr>
  </w:style>''')

# ---- Title-page styles (used by titlepage.lua for opt-in cover pages) ----
# These are custom styles addressed via pandoc's custom-style Divs, so they
# are independent of pandoc's own Title/Subtitle block styling.

# Logo paragraph: left aligned, with generous space beneath before the title.
styles_xml = add_style(styles_xml, f'''<w:style w:type="paragraph" w:customStyle="1" w:styleId="TitlePageLogo">
    <w:name w:val="Title Page Logo" />
    <w:basedOn w:val="Normal" />
    <w:next w:val="TitlePageTitle" />
    <w:qFormat />
    <w:pPr>
      <w:spacing w:before="720" w:after="0" />
      <w:jc w:val="left" />
    </w:pPr>
  </w:style>''')

# Cover title: large indigo, pushed down the page, teal rule beneath.
styles_xml = add_style(styles_xml, f'''<w:style w:type="paragraph" w:customStyle="1" w:styleId="TitlePageTitle">
    <w:name w:val="Title Page Title" />
    <w:basedOn w:val="Normal" />
    <w:next w:val="TitlePageSubtitle" />
    <w:qFormat />
    <w:pPr>
      <w:keepNext />
      <w:keepLines />
      <w:spacing w:before="3200" w:after="160" w:line="264" w:lineRule="auto" />
    </w:pPr>
    <w:rPr>
      <w:rFonts w:asciiTheme="majorHAnsi" w:hAnsiTheme="majorHAnsi" w:cstheme="majorBidi" />
      <w:b />
      <w:bCs />
      <w:color w:val="{INDIGO}" />
      <w:sz w:val="64" />
      <w:szCs w:val="64" />
    </w:rPr>
  </w:style>''')

# Cover subtitle: deep blue, lighter weight.
styles_xml = add_style(styles_xml, f'''<w:style w:type="paragraph" w:customStyle="1" w:styleId="TitlePageSubtitle">
    <w:name w:val="Title Page Subtitle" />
    <w:basedOn w:val="Normal" />
    <w:next w:val="TitlePageMeta" />
    <w:qFormat />
    <w:pPr>
      <w:keepLines />
      <w:spacing w:before="40" w:after="120" />
    </w:pPr>
    <w:rPr>
      <w:rFonts w:asciiTheme="majorHAnsi" w:hAnsiTheme="majorHAnsi" w:cstheme="majorBidi" />
      <w:color w:val="{DEEP}" />
      <w:sz w:val="30" />
      <w:szCs w:val="30" />
    </w:rPr>
  </w:style>''')

# Cover author / date line: small, uppercase, muted.
styles_xml = add_style(styles_xml, f'''<w:style w:type="paragraph" w:customStyle="1" w:styleId="TitlePageMeta">
    <w:name w:val="Title Page Meta" />
    <w:basedOn w:val="Normal" />
    <w:next w:val="Normal" />
    <w:qFormat />
    <w:pPr>
      <w:spacing w:before="0" w:after="0" />
    </w:pPr>
    <w:rPr>
      <w:caps />
      <w:color w:val="6C6C8C" />
      <w:spacing w:val="12" />
      <w:sz w:val="18" />
      <w:szCs w:val="18" />
    </w:rPr>
  </w:style>''')

# Default Table style: light horizontal rules, bold (uncoloured) header row.
styles_xml = replace_style(styles_xml, "Table", f'''<w:style w:type="table" w:default="1" w:styleId="Table">
    <w:name w:val="Table" />
    <w:basedOn w:val="TableNormal" />
    <w:qFormat />
    <w:tblPr>
      <w:tblInd w:w="0" w:type="dxa" />
      <w:tblBorders>
        <w:top w:val="single" w:sz="4" w:space="0" w:color="{RULE}" />
        <w:bottom w:val="single" w:sz="4" w:space="0" w:color="{RULE}" />
        <w:insideH w:val="single" w:sz="4" w:space="0" w:color="{RULE_LT}" />
      </w:tblBorders>
      <w:tblCellMar>
        <w:top w:w="40" w:type="dxa" />
        <w:left w:w="108" w:type="dxa" />
        <w:bottom w:w="40" w:type="dxa" />
        <w:right w:w="108" w:type="dxa" />
      </w:tblCellMar>
    </w:tblPr>
    <w:tblStylePr w:type="firstRow">
      <w:rPr>
        <w:b />
      </w:rPr>
    </w:tblStylePr>
  </w:style>''')

# Heading rule: a thin teal hairline used by sections.lua to draw an optional
# rule under headings (frontmatter `heading-rules: true`). It is its own near
# zero-height paragraph placed immediately after a heading.
styles_xml = add_style(styles_xml, f'''<w:style w:type="paragraph" w:customStyle="1" w:styleId="HeadingRule">
    <w:name w:val="Heading Rule" />
    <w:basedOn w:val="Normal" />
    <w:next w:val="BodyText" />
    <w:pPr>
      <w:spacing w:before="40" w:after="120" w:line="40" w:lineRule="exact" />
      <w:pBdr>
        <w:bottom w:val="single" w:sz="12" w:space="1" w:color="{TEAL}" />
      </w:pBdr>
    </w:pPr>
    <w:rPr>
      <w:sz w:val="4" />
      <w:szCs w:val="4" />
    </w:rPr>
  </w:style>''')

styles_path.write_text(styles_xml)

# --- 3. Repack ------------------------------------------------------------
REF.unlink()
with zipfile.ZipFile(REF, "w", zipfile.ZIP_DEFLATED) as z:
    for p in sorted(WORK.rglob("*")):
        if p.is_file():
            z.write(p, p.relative_to(WORK))

shutil.rmtree(WORK)
print(f"Patched: {REF}")
