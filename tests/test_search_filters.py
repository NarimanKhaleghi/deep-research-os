"""Connector normalization, search filters and export privacy defaults."""

from __future__ import annotations

from pathlib import Path

from conftest import add_source, run_cli, seed_project

from connectors import doaj, europepmc, hal, openaire, semanticscholar, zenodo
from connectors import registry
from core import fulltext, fulltext_store
from core.evidence_store import Ledger


def _rec(**kw):
    base = {"service": "x", "title": "t", "url": "https://example.org/x", "type": "journal-article",
            "published": "2024-01-01", "extra": {}}
    base.update(kw)
    return base


def test_apply_filters_year_oa_type():
    records = [
        _rec(title="old", published="2019", extra={"is_oa": True}),
        _rec(title="closed", published="2024", extra={"is_oa": False}),
        _rec(title="recent-oa", published="2023", extra={"is_oa": True}),
        _rec(title="preprint", published="2025", type="preprint", extra={"is_oa": True}),
        _rec(title="nodate", published=None, extra={"is_oa": True}),
    ]
    out = registry.apply_filters(records, year_from=2020, year_to=2024, oa_only=True)
    assert [r["title"] for r in out] == ["recent-oa"]
    out = registry.apply_filters(records, types=["preprint"])
    assert [r["title"] for r in out] == ["preprint"]
    assert [r["title"] for r in registry.sort_records(records, "date")] == [
        "preprint", "closed", "recent-oa", "old", "nodate"]


def test_europepmc_parse():
    payload = {"resultList": {"result": [{
        "source": "MED", "pmid": "123", "pmcid": "PMC123", "doi": "10.1/x",
        "title": "A trial", "authorString": "Smith J, Doe A.", "pubYear": "2024",
        "journalTitle": "Journal", "abstractText": "Abstract", "isOpenAccess": "Y",
        "inEPMC": "Y", "hasPDF": "Y", "citedByCount": 4,
    }]}}
    rec = europepmc.parse_results(payload)[0]
    assert rec["doi"] == "10.1/x"
    assert rec["extra"]["pmcid"] == "PMC123"
    assert rec["extra"]["is_oa"] is True


def test_doaj_parse():
    payload = {"results": [{"id": "abc", "bibjson": {
        "title": "OA paper", "year": "2023", "abstract": "A",
        "author": [{"name": "Smith, J."}], "identifier": [{"type": "doi", "id": "10.1/y"}],
        "journal": {"title": "OA Journal", "license": [{"type": "CC-BY"}]},
        "link": [{"type": "fulltext", "url": "https://example.org/pdf"}],
    }}]}
    rec = doaj.parse_results(payload)[0]
    assert rec["doi"] == "10.1/y"
    assert rec["extra"]["is_oa"] is True
    assert rec["url"] == "https://example.org/pdf"


def test_semanticscholar_parse():
    payload = {"data": [{
        "paperId": "p1", "title": "Paper", "abstract": "A", "year": 2022,
        "authors": [{"name": "Jane Smith"}], "externalIds": {"DOI": "10.1/z"},
        "openAccessPdf": {"url": "https://example.org/p.pdf"}, "venue": "Venue",
        "publicationTypes": ["JournalArticle"], "citationCount": 7,
    }]}
    rec = semanticscholar.parse_results(payload)[0]
    assert rec["doi"] == "10.1/z"
    assert rec["extra"]["is_oa"] is True
    assert rec["extra"]["cited_by"] == 7


def test_openaire_parse():
    payload = {"results": [{
        "id": "oa1", "mainTitle": "Open paper", "description": "A",
        "publicationDate": "2024-02-01", "type": "publication",
        "pid": [{"scheme": "doi", "value": "10.1/o"}],
        "authors": [{"fullName": "Jane Smith"}],
        "bestAccessRight": {"label": "OPEN"},
        "instances": [{"urls": ["https://example.org/o"]}],
    }]}
    rec = openaire.parse_results(payload)[0]
    assert rec["doi"] == "10.1/o"
    assert rec["extra"]["is_oa"] is True


def test_zenodo_parse():
    payload = {"hits": {"hits": [{
        "id": 1, "metadata": {"title": "Dataset", "doi": "10.1/d",
                              "creators": [{"name": "Smith, J."}],
                              "publication_date": "2024-03-01",
                              "resource_type": {"type": "dataset"}, "description": "A"},
        "links": {"self_html": "https://zenodo.org/records/1"},
    }]}}
    rec = zenodo.parse_results(payload)[0]
    assert rec["type"] == "dataset"
    assert rec["extra"]["is_oa"] is True


def test_hal_parse():
    payload = {"response": {"docs": [{
        "uri_s": "https://hal.example/1", "doiId_s": "10.1/h",
        "title_s": ["HAL paper"], "authFullName_s": ["Jane Smith"],
        "producedDateY_i": 2021, "abstract_s": ["A"], "docType_s": "ART",
        "openAccess_bool": True, "journalTitle_s": ["Journal"],
    }]}}
    rec = hal.parse_results(payload)[0]
    assert rec["doi"] == "10.1/h"
    assert rec["extra"]["is_oa"] is True


def test_export_excludes_fulltext_by_default(env):
    project = seed_project(env)
    sid, _ = add_source(project, text="snapshot", title="Paper", url="https://example.org/p",
                        doi="10.1/export")
    ledger = Ledger(project)
    artifact = fulltext.extract_artifact(b"<article><body><p>" + b"word " * 400 + b"</p></body></article>",
                                         filename="paper.xml")
    fulltext_store.store_artifact(project, ledger, ledger.source(sid), b"<article/>", artifact,
                                  {"url": "https://example.org/p.xml"})
    out = project / "exports" / "test"
    _, data, _ = run_cli("export", "--project", str(project), "--out", str(out), expect=0)
    assert data["fulltext_artifacts_excluded"] == 1
    assert not (out / "sources" / f"{sid}.xml").exists()
    assert (out / "sources" / f"{sid}.json").exists()
    _, data2, _ = run_cli("export", "--project", str(project), "--out", str(out / "all"),
                          "--include-fulltext", expect=0)
    assert (out / "all" / "sources" / f"{sid}.xml").exists()
    assert data2["fulltext_artifacts_excluded"] == 0
