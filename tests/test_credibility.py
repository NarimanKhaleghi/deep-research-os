"""Credibility scorer — band behavior, retraction caps, recency."""

from __future__ import annotations

import pytest

from core import credibility


def base_source(**kw):
    rec = {
        "id": "SRC-0001", "url": "https://example.org/a", "doi": None,
        "title": "A study", "authors": [], "publisher": "Example",
        "published": "2025-01-01", "service": "web", "type": "webpage",
        "extra": {},
    }
    rec.update(kw)
    return rec


def test_band_thresholds():
    assert credibility.band_for(90) == "A"
    assert credibility.band_for(85) == "A"
    assert credibility.band_for(84) == "B"
    assert credibility.band_for(70) == "B"
    assert credibility.band_for(69) == "C"
    assert credibility.band_for(55) == "C"
    assert credibility.band_for(54) == "D"


def test_retracted_is_capped_and_flagged():
    s = base_source(type="journal-article", doi="10.1/retracted",
                    url="https://journal.example/retracted",
                    extra={"is_retracted": True})
    cred = credibility.score_source(s)
    assert cred["band"] == "D"
    assert cred["score"] <= 40
    assert cred["dimensions"]["integrity"] == 0
    assert "RETRACTED" in cred["rationale"]


def test_gov_statistics_scores_high():
    s = base_source(url="https://www.census.gov/data/x", type="statistics",
                    service="census", published="2026-01-01")
    cred = credibility.score_source(s)
    assert cred["band"] in ("A", "B")
    assert cred["score"] >= 70


def test_recency_dimension_decays():
    fresh = credibility.score_source(base_source(type="news", published="2026-10-01",
                                                 url="https://reuters.com/x"))
    stale = credibility.score_source(base_source(type="news", published="2018-01-01",
                                                 url="https://reuters.com/y"))
    assert fresh["dimensions"]["recency"] > stale["dimensions"]["recency"]


def test_peer_venue_bonus_beats_aggregator():
    venue = credibility.score_source(base_source(
        type="journal-article", doi="10.1/x", url="https://nature.com/articles/x"))
    blog = credibility.score_source(base_source(
        type="webpage", url="https://medium.com/@someone/post"))
    assert venue["score"] > blog["score"]


def test_overrides_are_applied():
    s = base_source(type="journal-article", doi="10.1/ov")
    first = credibility.score_source(s)
    s["credibility"] = {"overrides": [{"dimension": "recency", "delta": -10,
                                       "by": "human", "reason": "stale market data"}]}
    second = credibility.score_source(s)
    assert second["score"] < first["score"]
    assert second["overrides"][0]["dimension"] == "recency"
