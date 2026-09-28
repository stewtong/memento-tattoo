"""A4: a local embedding baseline, for the evaluation only.

Needs the optional ``fastembed`` dependency. The package never imports this
module; it exists so the package's choice of lexical ranking without a vector
database is tested against a real embedding arm.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

DEFAULT_MODEL = "BAAI/bge-base-en-v1.5"


def note_text(note: dict) -> str:
    parts = [f"Situation: {note.get('situation') or ''}", f"Note: {note.get('note') or ''}"]
    if note.get("why"):
        parts.append(f"Why: {note['why']}")
    if note.get("aliases"):
        parts.append("aliases: " + ", ".join(note["aliases"]))
    return "\n".join(parts)


class EmbeddingArm:
    """Cosine ranking with vectors cached on disk by text hash."""

    def __init__(self, cache_dir: Path, model: str = DEFAULT_MODEL, model_cache: Path | None = None):
        from fastembed import TextEmbedding

        self.model_name = model
        self.model = TextEmbedding(model_name=model, cache_dir=str(model_cache) if model_cache else None)
        self.cache_path = cache_dir / f"vectors-{model.replace('/', '_')}.json"
        self.cache: dict[str, list[float]] = json.loads(self.cache_path.read_text()) if self.cache_path.exists() else {}

    @staticmethod
    def _key(kind: str, text: str) -> str:
        return kind + ":" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:24]

    def _ensure(self, kind: str, texts: list[str]) -> None:
        todo = [t for t in dict.fromkeys(texts) if self._key(kind, t) not in self.cache]
        if not todo:
            return
        embed = self.model.query_embed if kind == "q" else self.model.passage_embed
        for text, vec in zip(todo, embed(todo)):
            norm = float(sum(float(x) * float(x) for x in vec)) ** 0.5 or 1.0
            self.cache[self._key(kind, text)] = [float(x) / norm for x in vec]

    def save(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps(self.cache))

    def rank(self, query: str, corpus: list[dict], limit: int = 50) -> list[str]:
        texts = [note_text(n) for n in corpus]
        self._ensure("p", texts)
        self._ensure("q", [query])
        import numpy as np  # installed with fastembed

        qv = np.asarray(self.cache[self._key("q", query)])
        docs = np.asarray([self.cache[self._key("p", t)] for t in texts])
        sims = docs @ qv
        order = sorted(range(len(corpus)), key=lambda i: (-float(sims[i]), corpus[i]["note_id"]))
        return [corpus[i]["note_id"] for i in order[:limit]]
