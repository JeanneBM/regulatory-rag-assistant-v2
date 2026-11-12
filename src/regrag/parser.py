"""Parse Official Journal XHTML into articles and citable units.

A citable unit is the smallest piece of text an answer may quote:

* a numbered paragraph without points, e.g. "Article 6(1)";
* the text introducing a list of points together with one point and all its sub-points,
  e.g. "Article 5(1), point (c)". Conditions in sub-points (i), (ii) therefore
  always travel with the point they qualify;
* text that follows a list of points inside the same paragraph.

The Official Journal lays points out as two-cell table rows (marker cell, text cell),
nested once per sub-level. The parser walks the DOM, keeps that table structure
and only falls back to plain text when a row has no marker.
"""
import itertools
import re
import textwrap
from dataclasses import dataclass, field

from bs4 import BeautifulSoup, NavigableString, Tag

from regrag.sources import Act
from regrag.text import squash

PARSER_VERSION = "2"
MAX_UNIT_CHARS = 4000
BLOCK_TAGS = {
    "address", "article", "aside", "blockquote", "caption", "dd", "div", "dl", "dt",
    "figcaption", "figure", "footer", "h1", "h2", "h3", "h4", "h5", "h6", "header",
    "li", "ol", "p", "pre", "section", "table", "tbody", "td", "tfoot", "th", "thead",
    "tr", "ul",
}
SKIP_TAGS = {"script", "style", "nav", "noscript", "template", "head", "title"}
ARTICLE_RE = re.compile(r"Article\s+(\d+)")
PARAGRAPH_RE = re.compile(r"(\d+)\.\s+\S")
MARKER_RE = re.compile(r"\((\d{1,3}[a-z]?|[a-z]{1,3}|[ivxlc]{1,6})\)")
END_RE = re.compile(r"^(ANNEX(?:\s|$)|Done at |This Regulation shall be binding in its entirety)")
STRUCTURE_RE = re.compile(r"^(CHAPTER|SECTION|TITLE|PART|Chapter|Section|Title|Part)\s+([IVXLC]+|\d+)$")


class ParseError(ValueError):
    """The source structure does not match what the importer can safely index."""


@dataclass(frozen=True)
class Block:
    """One line of visible text and the table cells that enclose it."""
    text: str
    cells: tuple[tuple[int, int, int], ...]  # (table, row, cell) per table level
    classes: frozenset[str]

    @property
    def depth(self) -> int:
        return len(self.cells)


def iter_blocks(root: Tag) -> list[Block]:
    """Return visible text as one whitespace-normalised line per block element.

    Inline markup (links, spans, footnote markers) stays inside its sentence, so a
    cross-reference such as <a>Article 6</a> can never become an article heading.
    Comments and other non-text nodes are dropped.
    """
    blocks: list[Block] = []
    tables = itertools.count()

    def walk(node: Tag, cells: tuple, classes: frozenset) -> None:
        buffer: list[str] = []

        def flush() -> None:
            text = squash("".join(buffer))
            buffer.clear()
            if text:
                blocks.append(Block(text, cells, classes))

        def visit(parent: Tag) -> None:
            for child in parent.children:
                if isinstance(child, NavigableString):
                    if type(child) is NavigableString:
                        buffer.append(str(child))
                    continue
                if not isinstance(child, Tag) or child.name in SKIP_TAGS:
                    continue
                if child.name in {"br", "hr"}:
                    flush()
                elif child.name == "table":
                    flush()
                    key = next(tables)
                    rows = [tr for tr in child.find_all("tr") if tr.find_parent("table") is child]
                    for row_index, row in enumerate(rows):
                        for cell_index, cell in enumerate(row.find_all(["td", "th"], recursive=False)):
                            walk(cell, (*cells, (key, row_index, cell_index)),
                                 frozenset(cell.get("class") or ()))
                elif child.name in BLOCK_TAGS:
                    flush()
                    walk(child, cells, frozenset(child.get("class") or ()) or classes)
                else:
                    visit(child)  # inline element: same line

        visit(node)
        flush()

    walk(root, (), frozenset())
    return blocks


@dataclass
class _Row:
    key: tuple[int, int]
    marker: str | None
    lines: list[str] = field(default_factory=list)
    pending: str | None = None  # sub-point marker waiting for its text cell

    def add(self, block: Block) -> None:
        inner_first_cell = block.cells[-1][2] == 0
        if block.depth >= 2 and inner_first_cell and MARKER_RE.fullmatch(block.text):
            self.pending = block.text
            return
        text = f"{self.pending} {block.text}" if self.pending else block.text
        self.pending = None
        self.lines.append(text)

    def render(self) -> list[str]:
        lines = [*self.lines] + ([self.pending] if self.pending else [])
        if self.marker and lines:
            lines[0] = f"({self.marker}) {lines[0]}"
        elif self.marker:
            lines = [f"({self.marker})"]
        return lines


@dataclass
class _Paragraph:
    number: str | None
    items: list = field(default_factory=list)  # str lines and _Row objects in order

    def add_text(self, text: str) -> None:
        self.items.append(text)

    def add_cell(self, block: Block) -> None:
        table, row, cell = block.cells[0]
        key = (table, row)
        if block.depth == 1 and cell == 0 and MARKER_RE.fullmatch(block.text):
            self.items.append(_Row(key, MARKER_RE.fullmatch(block.text).group(1)))
            return
        current = self.items[-1] if self.items and isinstance(self.items[-1], _Row) else None
        if current is None or current.key != key:
            current = _Row(key, None)
            self.items.append(current)
        current.add(block)


def _split(lines: list[str], limit: int = MAX_UNIT_CHARS) -> list[list[str]]:
    """Split a long unit between lines, or between words of an oversized line."""
    pieces = []
    for line in lines:
        pieces.extend(textwrap.wrap(line, limit, break_long_words=False, break_on_hyphens=False)
                      if len(line) > limit else [line])
    parts, current, size = [], [], 0
    for piece in pieces:
        if current and size + 1 + len(piece) > limit:
            parts.append(current)
            current, size = [], 0
        current.append(piece)
        size += len(piece) + 1
    if current:
        parts.append(current)
    return parts


def citation_label(article: str, paragraph: str | None = None, point: str | None = None) -> str:
    """EU drafting style: 'Article 5(1), point (c)'."""
    label = f"Article {article}"
    if paragraph:
        label += f"({paragraph})"
    if point:
        label += f", point ({point})"
    return label


def _is_title(block: Block) -> bool:
    if "oj-sti-art" in block.classes:
        return True
    text = block.text
    return (block.depth == 0 and len(text) < 250 and not PARAGRAPH_RE.match(text)
            and not text.endswith((".", ":", ";")))


def _is_structure_heading(block: Block) -> bool:
    return block.depth == 0 and (
        any(c.startswith("oj-ti-section") for c in block.classes)
        or bool(STRUCTURE_RE.match(block.text))
    )


def _article_units(act: Act, article: str, body: list[Block], url: str) -> list[dict]:
    title = ""
    if body and _is_title(body[0]):
        title, body = body[0].text, body[1:]
    paragraphs = [_Paragraph(None)]
    expected = 1
    for block in body:
        if block.depth == 0:
            match = PARAGRAPH_RE.match(block.text)
            if match and int(match.group(1)) == expected:
                if paragraphs[-1].items or paragraphs[-1].number:
                    paragraphs.append(_Paragraph(match.group(1)))
                else:
                    paragraphs[-1].number = match.group(1)
                expected += 1
            paragraphs[-1].add_text(block.text)
        else:
            paragraphs[-1].add_cell(block)

    units, seen = [], set()

    def emit(paragraph: str | None, point: str | None, lines: list[str], suffix: str) -> None:
        lines = [line for line in lines if line.strip()]
        if not lines:
            return
        base = f"{act.key}-art-{article}" + (f"-par-{paragraph}" if paragraph else "") + suffix
        parts = _split(lines)
        for index, part in enumerate(parts, 1):
            unit_id = base + (f"-part-{index}" if len(parts) > 1 else "")
            original, counter = unit_id, 2
            while unit_id in seen:
                unit_id, counter = f"{original}-dup{counter}", counter + 1
            seen.add(unit_id)
            units.append({
                "id": unit_id, "act": act.key, "celex": act.celex, "article": article,
                "article_title": title, "paragraph": paragraph, "point": point,
                "label": citation_label(article, paragraph, point),
                "text": "\n".join(part), "url": url,
            })

    for paragraph in paragraphs:
        if not any(isinstance(item, _Row) for item in paragraph.items):
            emit(paragraph.number, None, list(paragraph.items), "")
            continue
        # Each list of points is quoted with the text run directly above it, so a
        # quotation never joins lines that are not adjacent in the act.
        lead, run, tails = [], [], 0
        for row_index, item in enumerate(paragraph.items):
            if isinstance(item, _Row):
                if run:
                    lead, run = run, []
                marker = item.marker
                safe = re.sub(r"[^A-Za-z0-9]", "", marker) if marker else f"row{row_index}"
                emit(paragraph.number, marker, lead + item.render(), f"-pt-{safe}")
            else:
                run.append(item)
        if run:
            tails += 1
            emit(paragraph.number, None, run, f"-text-{tails}")
    return units


def parse_act(html: str, act: Act) -> list[dict]:
    """Return the citable units of every article of an act, in document order."""
    soup = BeautifulSoup(html, "html.parser")
    root = soup.find(id="document1") or soup.body or soup
    anchors = {tag.get("id") for tag in soup.find_all(id=True)}
    blocks = iter_blocks(root)
    starts, expected = [], 1
    for index, block in enumerate(blocks):
        match = ARTICLE_RE.fullmatch(block.text) if block.depth == 0 else None
        # Sequential numbering keeps quoted amendments ("Article 7a") and stray
        # headings from splitting an article.
        if match and int(match.group(1)) == expected:
            starts.append((index, str(expected)))
            expected += 1
    if not starts:
        raise ParseError(f"{act.key}: no articles parsed; source may be a bot challenge "
                         "or changed HTML")
    units = []
    for position, (start, article) in enumerate(starts):
        end = starts[position + 1][0] if position + 1 < len(starts) else len(blocks)
        body = blocks[start + 1:end]
        for index, block in enumerate(body):
            if block.depth == 0 and END_RE.match(block.text):
                body = body[:index]
                break
        # Chapter and section headings sit between the last paragraph of one
        # article and the next article heading.
        for index in range(max(0, len(body) - 4), len(body)):
            if _is_structure_heading(body[index]):
                body = body[:index]
                break
        anchor = f"art_{article}"
        url = act.eurlex_url + (f"#{anchor}" if anchor in anchors else "")
        units.extend(_article_units(act, article, body, url))
    for ordinal, unit in enumerate(units):
        unit["ordinal"] = ordinal
    return units


def require_coverage(units: list[dict], act: Act) -> None:
    """Fail closed when any article of the act is missing from the parsed text."""
    found = {unit["article"] for unit in units if unit["act"] == act.key and unit["text"].strip()}
    missing = [n for n in range(1, act.articles + 1) if str(n) not in found]
    extra = sorted(int(a) for a in found if int(a) > act.articles)
    if missing:
        raise ParseError(f"{act.key}: incomplete article coverage (missing {missing[:5]})")
    if extra:
        raise ParseError(f"{act.key}: unexpected articles beyond {act.articles}: {extra[:5]}")


def corpus_stats(units: list[dict]) -> dict:
    """Structural statistics used by the live-ingest workflow to spot parser drift."""
    stats = {}
    for unit in units:
        entry = stats.setdefault(unit["act"], {
            "articles": set(), "units": 0, "with_paragraph": 0, "with_point": 0,
            "with_title": 0, "max_chars": 0, "anchored": 0,
        })
        entry["articles"].add(unit["article"])
        entry["units"] += 1
        entry["with_paragraph"] += bool(unit["paragraph"])
        entry["with_point"] += bool(unit["point"])
        entry["with_title"] += bool(unit["article_title"])
        entry["anchored"] += "#" in unit["url"]
        entry["max_chars"] = max(entry["max_chars"], len(unit["text"]))
    for entry in stats.values():
        entry["articles"] = len(entry["articles"])
    return stats
