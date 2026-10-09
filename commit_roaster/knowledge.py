"""Retrieval for the RAG pipeline: chunk the knowledge base and rank chunks with BM25."""

import re
from dataclasses import dataclass
from pathlib import Path

from rank_bm25 import BM25Okapi

DEFAULT_KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "knowledge"
CHUNK_HEADING = re.compile(r"^## \[([A-Z]{2}-\d{2})\] (.+)$", re.MULTILINE)
CITATION = re.compile(r"\[([A-Z]{2}-\d{2})\]")
STOPWORDS = set("a an and are as at be by for from has have in is it its of on or that the this to was "
                "with what why how not no do does should".split())


@dataclass(frozen=True)
class Chunk:
    id: str
    title: str
    text: str
    source: str


def tokenize(text):
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in STOPWORDS]


def load_chunks(knowledge_dir=DEFAULT_KNOWLEDGE_DIR):
    """Split every Markdown file on '## [ID] Title' headings; each section becomes one chunk."""
    chunks = []
    for path in sorted(Path(knowledge_dir).glob("*.md")):
        content = path.read_text(encoding="utf-8")
        headings = list(CHUNK_HEADING.finditer(content))
        for i, match in enumerate(headings):
            end = headings[i + 1].start() if i + 1 < len(headings) else len(content)
            body = " ".join(content[match.end():end].split())
            chunks.append(Chunk(match.group(1), match.group(2).strip(), body, path.name))
    return chunks


class KnowledgeBase:
    def __init__(self, chunks):
        if not chunks:
            raise ValueError("knowledge base is empty")
        self.chunks = chunks
        self.by_id = {c.id: c for c in chunks}
        # Titles are repeated so a match on the topic outweighs a passing mention in the text.
        self._bm25 = BM25Okapi([tokenize(f"{c.title} {c.title} {c.text}") for c in chunks])

    @classmethod
    def load(cls, knowledge_dir=DEFAULT_KNOWLEDGE_DIR):
        return cls(load_chunks(knowledge_dir))

    def search(self, query, k=3):
        terms = tokenize(query)
        if not terms:
            return []
        scores = self._bm25.get_scores(terms)
        ranked = sorted(zip(scores, self.chunks), key=lambda pair: pair[0], reverse=True)
        return [chunk for score, chunk in ranked[:k] if score > 0]

    def format_results(self, chunks):
        if not chunks:
            return "No matching guidelines found. Try different keywords."
        return "\n\n".join(f"[{c.id}] {c.title} ({c.source})\n{c.text}" for c in chunks)
