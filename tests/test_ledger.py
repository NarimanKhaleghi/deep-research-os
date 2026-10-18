"""Ledger — ids, updates, origin keys."""

from __future__ import annotations

from core.evidence_store import Ledger


def test_ledger_ids_and_updates(tmp_path):
    ledger = Ledger(tmp_path)
    s1 = ledger.add_source({"url": "https://a.example/x", "title": "A", "type": "webpage",
                            "service": "web", "tier": 2, "angles_covered": ["x"],
                            "snapshot": {"path": "sources/SRC-0001.txt", "sha256": "abc"}})
    s2 = ledger.add_source({"url": "https://b.example/x", "title": "B", "type": "webpage",
                            "service": "web", "tier": 2, "angles_covered": ["x"],
                            "snapshot": {"path": "sources/SRC-0002.txt", "sha256": "def"}})
    assert (s1["id"], s2["id"]) == ("SRC-0001", "SRC-0002")

    e1 = ledger.add_evidence({"source_id": s1["id"], "quote": "hello world", "locator": "p.1",
                              "relevance": "supports", "angle": "x"})
    e2 = ledger.add_evidence({"source_id": s2["id"], "quote": "second quote", "locator": "p.2",
                              "relevance": "supports", "angle": "x"})
    assert (e1["id"], e2["id"]) == ("EV-0001", "EV-0002")

    c1 = ledger.add_claim({"text": "claim one", "type": "statistic", "evidence_ids": [e1["id"]]})
    assert c1["id"] == "CL-0001"
    assert c1["status"] == "unverified"

    updated = ledger.update_claim(c1["id"], status="supported")
    assert updated["status"] == "supported"
    assert ledger.claim("CL-0001")["status"] == "supported"

    cx = ledger.add_contradiction({"claim_ids": ["CL-0001"], "kind": "numeric",
                                   "severity": "medium", "detail": "x"})
    assert cx["id"] == "CX-0001"
    assert ledger.contradiction("CX-0001")["status"] == "open"

    assert ledger.counts() == {"sources": 2, "evidence": 2, "claims": 1, "contradictions": 1}


def test_origin_key_dedupes_syndication(tmp_path):
    ledger = Ledger(tmp_path)
    text = "hatch match quote here for verification purposes"
    s1 = ledger.add_source({"url": "https://news.example/a", "title": "A", "type": "news",
                            "service": "web", "tier": 2, "snapshot": {"path": f"sources/SRC-0001.txt",
                            "sha256": "x"}})
    s2 = ledger.add_source({"url": "https://news.example/b", "title": "B", "type": "news",
                            "service": "web", "tier": 2, "snapshot": {"path": f"sources/SRC-0002.txt",
                            "sha256": "y"}})
    e1 = ledger.add_evidence({"source_id": s1["id"], "quote": text, "locator": "1",
                              "relevance": "supports", "angle": "x"})
    e2 = ledger.add_evidence({"source_id": s2["id"], "quote": text, "locator": "2",
                              "relevance": "supports", "angle": "x"})
    c = ledger.add_claim({"text": "syndicated fact", "type": "statistic",
                          "evidence_ids": [e1["id"], e2["id"]], "critical": True})
    assert ledger.origin_keys_for_claim(c) == ["news.example"]
