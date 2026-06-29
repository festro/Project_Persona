#!/usr/bin/env python3
"""RagStore -- backend-agnostic vector memory store (Chroma or embedded Qdrant).

The caller (server.py) computes embeddings (fastembed) and passes the vector in, so
the store stays embedding-agnostic. The backend is selected by RAG_BACKEND
(chroma|qdrant). Qdrant runs in EMBEDDED local mode (an on-disk path, or :memory:),
no server process -- mirroring Chroma's PersistentClient posture and keeping the
lean-node / portable story (Phase 2a). A daemon-supervised Qdrant server can come
later (Phase 3) without touching callers.

Both stores expose the same duck-typed surface:
    .backend / .ok / .error
    .add(collection, doc_id, text, vector, meta)
    .query(collection, vector, k, kind_filter=None) -> list[str]   # documents
    .count(collection) -> int
    .list_collections() -> list[str]
    .export_points(collection) -> iterator of {id, document, vector, meta}

export_points feeds the one-time chroma->qdrant migration. Everything here is unit-
tested offline (tests/test_ragstore.py) -- Chroma always, Qdrant when installed.
"""
from __future__ import annotations

from typing import Any, Dict, Iterator, List, Optional


def _kinds(kind_filter) -> List[str]:
    if not kind_filter:
        return []
    return sorted({str(x).strip().lower() for x in kind_filter if str(x).strip()})


class ChromaStore:
    """Wraps chromadb.PersistentClient. Mirrors the pre-Phase-2a behavior exactly."""

    backend = "chroma"

    def __init__(self, path: str, default_collection: str):
        self.ok = False
        self.error: Optional[str] = None
        self._path = path
        self._default = default_collection
        self._client = None
        self._collections: Dict[str, Any] = {}
        try:
            import chromadb
        except Exception as e:  # noqa: BLE001
            self.error = "chromadb_not_available: %r" % e
            return
        try:
            self._client = chromadb.PersistentClient(path=path)
            self._collections[default_collection] = \
                self._client.get_or_create_collection(default_collection)
            self.ok = True
        except Exception as e:  # noqa: BLE001
            self.error = "chroma_init_failed: %r" % e

    def _coll(self, collection: str):
        if not self.ok or self._client is None:
            return None
        c = self._collections.get(collection)
        if c is None:
            try:
                c = self._client.get_or_create_collection(collection)
                self._collections[collection] = c
            except Exception:  # noqa: BLE001
                return None
        return c

    def add(self, collection, doc_id, text, vector, meta):
        c = self._coll(collection)
        if c is None:
            return
        try:
            c.add(ids=[str(doc_id)], documents=[text],
                  embeddings=[list(vector)], metadatas=[meta or {}])
        except Exception:  # noqa: BLE001
            return

    def query(self, collection, vector, k, kind_filter=None) -> List[str]:
        c = self._coll(collection)
        if c is None or k <= 0:
            return []
        where = None
        ks = _kinds(kind_filter)
        if len(ks) == 1:
            where = {"kind": ks[0]}
        elif len(ks) > 1:
            where = {"$or": [{"kind": kk} for kk in ks]}
        try:
            res = c.query(query_embeddings=[list(vector)], n_results=k,
                          include=["documents"], where=where)
            return list((res.get("documents") or [[]])[0])[:k]
        except Exception:  # noqa: BLE001
            return []

    def count(self, collection) -> int:
        c = self._coll(collection)
        try:
            return int(c.count()) if c is not None else 0
        except Exception:  # noqa: BLE001
            return 0

    def list_collections(self) -> List[str]:
        if not self.ok or self._client is None:
            return []
        try:
            # chromadb >=0.6 returns names (str); older returns Collection objects.
            return [c if isinstance(c, str) else getattr(c, "name", str(c))
                    for c in self._client.list_collections()]
        except Exception:  # noqa: BLE001
            return []

    def export_points(self, collection) -> Iterator[Dict[str, Any]]:
        c = self._coll(collection)
        if c is None:
            return
        try:
            res = c.get(include=["documents", "embeddings", "metadatas"])
        except Exception:  # noqa: BLE001
            return
        # embeddings come back as numpy arrays -> avoid truthiness on arrays.
        def _arr(x):
            return x if x is not None else []
        ids = _arr(res.get("ids"))
        docs = _arr(res.get("documents"))
        embs = _arr(res.get("embeddings"))
        metas = _arr(res.get("metadatas"))
        for i, _id in enumerate(ids):
            yield {
                "id": _id,
                "document": docs[i] if i < len(docs) else "",
                "vector": list(embs[i]) if i < len(embs) and embs[i] is not None else None,
                "meta": metas[i] if i < len(metas) else {},
            }

    def delete(self, collection, ids) -> int:
        c = self._coll(collection)
        if c is None or not ids:
            return 0
        try:
            c.delete(ids=list(ids))
            return len(list(ids))
        except Exception:  # noqa: BLE001
            return 0

    def set_alias(self, alias, collection) -> bool:
        # Chroma has no native collection aliases; the Phase 6 alias chain falls back to
        # querying the mature collection name directly. Reported as unsupported.
        return False


class QdrantStore:
    """Wraps qdrant-client in EMBEDDED local mode (path=... on disk, or :memory:).
    Collections are created lazily at the embedding dimension with cosine distance.
    The 'kind' metadata is stored in the point payload alongside the document text."""

    backend = "qdrant"

    def __init__(self, path: str, dim: int, distance: str = "cosine"):
        self.ok = False
        self.error: Optional[str] = None
        self._dim = int(dim)
        self._client = None
        self._models = None
        self._ensured: set = set()
        try:
            from qdrant_client import QdrantClient, models
        except Exception as e:  # noqa: BLE001
            self.error = "qdrant_client_not_available: %r" % e
            return
        try:
            # location=":memory:" for ephemeral; else an on-disk embedded path.
            if path in (":memory:", "", None):
                self._client = QdrantClient(location=":memory:")
            else:
                self._client = QdrantClient(path=path)
            self._models = models
            self._distance = {
                "cosine": models.Distance.COSINE,
                "dot": models.Distance.DOT,
                "euclid": models.Distance.EUCLID,
            }.get(distance, models.Distance.COSINE)
            self.ok = True
        except Exception as e:  # noqa: BLE001
            self.error = "qdrant_init_failed: %r" % e

    def _ensure(self, collection: str) -> bool:
        if not self.ok or self._client is None:
            return False
        if collection in self._ensured:
            return True
        m = self._models
        try:
            if not self._client.collection_exists(collection):
                self._client.create_collection(
                    collection,
                    vectors_config=m.VectorParams(size=self._dim, distance=self._distance),
                )
            self._ensured.add(collection)
            return True
        except Exception:  # noqa: BLE001
            return False

    @staticmethod
    def _point_id(doc_id):
        # Qdrant point ids must be an unsigned int or a UUID string; pass UUIDs
        # through, else hash arbitrary ids into a stable 63-bit int.
        s = str(doc_id)
        if "-" in s and len(s) >= 32:
            return s
        import hashlib
        return int(hashlib.sha1(s.encode("utf-8")).hexdigest()[:15], 16)

    def add(self, collection, doc_id, text, vector, meta):
        if not self._ensure(collection):
            return
        m = self._models
        payload = dict(meta or {})
        payload["document"] = text
        try:
            self._client.upsert(collection, points=[m.PointStruct(
                id=self._point_id(doc_id), vector=list(vector), payload=payload)])
        except Exception:  # noqa: BLE001
            return

    def query(self, collection, vector, k, kind_filter=None) -> List[str]:
        if k <= 0 or not self._ensure(collection):
            return []
        m = self._models
        qfilter = None
        ks = _kinds(kind_filter)
        if ks:
            qfilter = m.Filter(should=[
                m.FieldCondition(key="kind", match=m.MatchValue(value=kk)) for kk in ks])
        try:
            res = self._client.query_points(
                collection, query=list(vector), limit=k,
                with_payload=True, query_filter=qfilter).points
            return [(p.payload or {}).get("document", "") for p in res][:k]
        except Exception:  # noqa: BLE001
            return []

    def count(self, collection) -> int:
        if not self._ensure(collection):
            return 0
        try:
            return int(self._client.count(collection).count)
        except Exception:  # noqa: BLE001
            return 0

    def list_collections(self) -> List[str]:
        if not self.ok or self._client is None:
            return []
        try:
            return [c.name for c in self._client.get_collections().collections]
        except Exception:  # noqa: BLE001
            return []

    def export_points(self, collection) -> Iterator[Dict[str, Any]]:
        if not self._ensure(collection):
            return
        offset = None
        while True:
            try:
                points, offset = self._client.scroll(
                    collection, with_payload=True, with_vectors=True,
                    limit=256, offset=offset)
            except Exception:  # noqa: BLE001
                return
            for p in points:
                payload = dict(p.payload or {})
                doc = payload.pop("document", "")
                yield {"id": p.id, "document": doc, "vector": p.vector, "meta": payload}
            if offset is None:
                break

    def delete(self, collection, ids) -> int:
        if not self._ensure(collection) or not ids:
            return 0
        m = self._models
        ids = list(ids)
        try:
            # Count how many of the requested ids actually exist, so the return value is the
            # real number deleted (not just the number requested) -- a silent mismatch (e.g. an
            # int point id passed as a string) otherwise reports a phantom success.
            present = len(self._client.retrieve(collection, ids=ids, with_payload=False, with_vectors=False))
            self._client.delete(collection, points_selector=m.PointIdsList(points=ids))
            return present
        except Exception:  # noqa: BLE001
            return 0

    def set_alias(self, alias, collection) -> bool:
        """Point a stable alias at `collection` (Phase 6 alias chain). Lets retrieval target
        the alias while the physical mature collection can be rebuilt underneath."""
        if not self._ensure(collection):
            return False
        m = self._models
        try:
            self._client.update_collection_aliases(change_aliases_operations=[
                m.CreateAliasOperation(create_alias=m.CreateAlias(
                    collection_name=collection, alias_name=alias))])
            return True
        except Exception:  # noqa: BLE001
            return False


def make_store(backend: str, *, chroma_path: str, default_collection: str,
               qdrant_path: str, dim: int):
    """Construct the configured store. Falls back to a disabled ChromaStore-shaped
    object's contract (ok=False) on an unknown backend so callers degrade gracefully."""
    b = (backend or "chroma").strip().lower()
    if b == "qdrant":
        return QdrantStore(qdrant_path, dim=dim)
    return ChromaStore(chroma_path, default_collection)
