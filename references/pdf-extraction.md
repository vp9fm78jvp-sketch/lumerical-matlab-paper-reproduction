# PDF extraction and coverage

`prepare` uses PyMuPDF to retain full-page PNGs/text, text line/block point coordinates, embedded image bytes and alpha masks, native vector paths, vector PDF figure crops, table cell candidates and equation anchors. Input content is preserved for an agent, rather than converted to guessed LaTeX. A source SHA-256 binds the inventory to the PDF.

Caption discovery matches caption-start “Fig./Figure N.” (including S-prefixed figures). Inline body references are independently inventoried; referenced figures without captions become visible missing-caption tasks. In identified supplements, explicitly main-text figure references are stored as external references, not invented local figure tasks. Document-hash-qualified figure/equation identities prevent main/supplement label collisions. Unreferenced captions can still be found. Captions without text/OCR anchors, floating captions split across blocks, numeric panel labels, complex multi-column geometry and scanned figure numbering require visual review. An unreferenced, unlabeled figure cannot be guaranteed detectable by text heuristics. Do not report exhaustive coverage from this parser alone.

The agent must inspect every page, append missed figure entries to paper.json with source page/caption, and correct all panels through review.json. Use a local persistent copy of the original PDF for later re-cropping. Exact panel bboxes are in PDF points (origin top-left), not PNG pixels. For a page rendered at DPI d, pixels = points*d/72. Crop conservatively enough to include ticks/units. If axes span panels, preserve parent and panel crops.

Example reviewed record:

```json
{"figures":{"Fig2":{"page":4,"panels":[
 {"label":"a","bbox":[305,36,570,250],"caption":"Microring self-pulsation",
  "class":"A","axes":[{"name":"time","unit":"us","scale":"linear"}],
  "legend":["input","output"],"annotations":["Pin=5mW"],"confidence":0.95}
]}},"coverage_reviewed":false,"evidence":"Visual check of page4 and caption; continue other pages"}
```

Never approve whole-paper coverage with only one figure reviewed. The program rejects a coverage flag when registered figures lack geometry review. It cannot detect a falsely asserted review; source review remains a scientific responsibility.

For scans, `--ocr` invokes PyMuPDF's local Tesseract integration. Missing OCR produces a warning and preserved page render, not invented text. Verify μ/n, τ/t, ν/v, 0/O, decimal exponents, signs, subscripts and italic species indices against zoomed page crops. Preserve raw OCR and corrected transcription side by side.

Retrieve supplemental PDFs/source data through primary publisher/author repositories when accessible. Store URL, version/date, DOI, checksum and access status. Do not assume preprint supplement parameters match a later journal article. Resolve material references selectively; retain unresolved citation tasks rather than silently importing familiar constants.

Keep copyrighted input PDFs and full-page extracts out of the public skill repository by default. Include source links and independently authored model/code; obtain redistribution permission for any input images included in a public release.
