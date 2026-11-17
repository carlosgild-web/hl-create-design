# 04 · Folder structure

*Hilda & Luna Beadworks · Electronics Engineering Design Manual · Edition 2026.1.
Fictional company; demo content.*

## Layout
<a id="layout"></a>

```text
<designs root>/
  HW/
    HL-HW-26-0042/
      A/
        HL-HW-26-0042_A.kicad_pro
        HL-HW-26-0042_A.kicad_sch
        hl_title_block.kicad_wks
        output/
          HL-HW-26-0042_A.pdf
      B/
        ...
  PWR/
  EMB/
  TFX/
```

One folder per department, one per design number, and one per revision.

## The designs root
<a id="designs-root"></a>

All designs live under one root folder: the engineering share in the company, and
`DESIGNS_ROOT` in Create Design. Nothing is saved outside it.

Create Design refuses any path that would leave the root: absolute paths, `..`, drive
letters such as `C:`, and links that point outside it.

*Why:* designs saved on desktops and personal drives were lost, and nobody could find
the latest revision.

## File names
<a id="file-names"></a>

Files are named `<DesignNumber>_<Rev>`, for example `HL-HW-26-0042_A.kicad_sch`. The design
name is never part of a file or folder name: names can change, numbers don't, and
names contain spaces.

## One folder per revision
<a id="revision-folders"></a>

Create Design creates a revision's folder once, from the company template. If the folder
already exists, it stops and changes nothing: it never overwrites files. Choose the next
free revision instead ([02-revisions](02-revisions.md#next-revision)).

To continue from the previous revision, open both projects in KiCad and copy the
schematic content into the new one. Don't copy the whole folder: the file names and the
title block would be those of the old revision.

## The output folder
<a id="output"></a>

`output/` holds the generated PDF and SVG. Generate them again after a change; don't edit
them.

## Don't
<a id="dont"></a>

- No spaces, accents, or words like `final`, `v2` or `copy` in folder names.
- Don't keep personal copies of a design outside the designs root.
- Don't rename or move design folders by hand.
