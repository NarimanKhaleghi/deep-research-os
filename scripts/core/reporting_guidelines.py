"""Reporting-guideline checklists for manuscript QA.

These are structural prompts, not a substitute for the official checklist.
"""

from __future__ import annotations

import re
from typing import Iterable

GUIDELINES = {
    "consort": {
        "name": "CONSORT 2010 (randomised trials)",
        "required": {
            "title": ("randomi", "trial", "کارآزمایی"),
            "abstract": ("abstract", "چکیده"),
            "trial design": ("trial design", "parallel", "crossover", "طرح"),
            "participants": ("eligib", "participant", "inclusion", "شرکت‌کننده"),
            "interventions": ("intervention", "مداخله"),
            "outcomes": ("outcome", "پیامد"),
            "sample size": ("sample size", "power", "حجم نمونه"),
            "randomisation": ("random", "allocation", "تصادفی"),
            "blinding": ("blind", "mask", "کورسازی"),
            "statistical methods": ("statistical", "analysis", "آماری"),
            "participant flow": ("flow", "enrol", "assigned", "نمودار"),
            "numbers analysed": ("analysed", "analyzed", "تحلیل"),
            "harms": ("adverse", "harm", "عوارض"),
            "limitations": ("limitation", "محدودیت"),
            "registration": ("regist", "trial number", "ثبت"),
            "funding": ("fund", "grant", "تامین مالی"),
        },
    },
    "prisma": {
        "name": "PRISMA 2020 (systematic reviews)",
        "required": {
            "rationale": ("rationale", "background", "دلیل"),
            "objectives": ("objective", "aim", "هدف"),
            "eligibility": ("eligib", "inclusion", "معیار"),
            "information sources": ("database", "search", "پایگاه"),
            "search strategy": ("search strategy", "query", "راهبرد جستجو"),
            "selection process": ("screening", "selection", "غربال"),
            "data collection": ("data extraction", "data collection", "استخراج"),
            "risk of bias": ("risk of bias", "quality assessment", "سوگیری"),
            "effect measures": ("effect measure", "odds ratio", "relative risk", "اندازه اثر"),
            "synthesis": ("synthesis", "meta-analysis", "heterogeneity", "ترکیب"),
            "reporting bias": ("publication bias", "funnel", "سوگیری انتشار"),
            "certainty": ("certainty", "grade", "اطمینان"),
            "limitations": ("limitation", "محدودیت"),
            "registration": ("regist", "protocol", "ثبت"),
            "funding": ("fund", "grant", "تامین مالی"),
        },
    },
    "strobe": {
        "name": "STROBE (observational studies)",
        "required": {
            "design": ("cohort", "case-control", "cross-sectional", "مقطعی", "همگروه"),
            "setting": ("setting", "site", "محیط"),
            "participants": ("participant", "eligib", "شرکت‌کننده"),
            "variables": ("variable", "exposure", "outcome", "متغیر"),
            "data sources": ("data source", "measurement", "داده"),
            "bias": ("bias", "سوگیری"),
            "sample size": ("sample size", "حجم نمونه"),
            "statistical methods": ("statistical", "regression", "آماری"),
            "descriptive data": ("descriptive", "baseline", "توصیفی"),
            "main results": ("main result", "estimate", "نتیجه"),
            "limitations": ("limitation", "محدودیت"),
            "funding": ("fund", "grant", "تامین مالی"),
        },
    },
    "coreq": {
        "name": "COREQ (qualitative interviews/focus groups)",
        "required": {
            "research team": ("research team", "interviewer", "تیم پژوهش"),
            "reflexivity": ("reflexiv", "positionality", "بازتاب"),
            "study design": ("qualitative", "interview", "focus group", "کیفی"),
            "participants": ("participant", "sampling", "شرکت‌کننده"),
            "setting": ("setting", "محیط"),
            "data collection": ("interview guide", "data collection", "مصاحبه"),
            "analysis": ("thematic", "coding", "تحلیل"),
            "trustworthiness": ("trustworthiness", "credibility", "اعتبار"),
            "participant quotes": ("quote", "نقل قول"),
            "limitations": ("limitation", "محدودیت"),
        },
    },
    "care": {
        "name": "CARE (case reports)",
        "required": {
            "patient information": ("patient", "history", "بیمار"),
            "clinical findings": ("clinical finding", "examination", "معاینه"),
            "timeline": ("timeline", "course", "روند"),
            "diagnostic assessment": ("diagnos", "test", "تشخیص"),
            "therapeutic intervention": ("treatment", "intervention", "درمان"),
            "follow-up": ("follow-up", "outcome", "پیگیری"),
            "informed consent": ("consent", "رضایت"),
            "limitations": ("limitation", "محدودیت"),
        },
    },
    "tripod": {
        "name": "TRIPOD (prediction models)",
        "required": {
            "source of data": ("data source", "cohort", "داده"),
            "participants": ("participant", "eligib", "شرکت‌کننده"),
            "outcome": ("outcome", "پیامد"),
            "predictors": ("predictor", "variable", "پیش‌بین"),
            "sample size": ("sample size", "events per variable", "حجم نمونه"),
            "model development": ("model development", "regression", "مدل"),
            "performance": ("discrimination", "calibration", "auc", "عملکرد"),
            "validation": ("validation", "bootstrap", "اعتبارسنجی"),
            "limitations": ("limitation", "محدودیت"),
        },
    },
    "arrive": {
        "name": "ARRIVE (animal research)",
        "required": {
            "study design": ("study design", "random", "طرح"),
            "sample size": ("sample size", "power", "حجم نمونه"),
            "housing": ("housing", "husbandry", "نگهداری"),
            "ethics": ("ethic", "approval", "اخلاق"),
            "experimental procedures": ("procedure", "intervention", "روش"),
            "results": ("result", "outcome", "نتیجه"),
            "limitations": ("limitation", "محدودیت"),
        },
    },
}

ALIASES = {
    "randomized controlled trial": "consort", "rct": "consort",
    "systematic review": "prisma", "meta-analysis": "prisma",
    "observational": "strobe", "cohort": "strobe", "case-control": "strobe",
    "qualitative": "coreq", "interview": "coreq",
    "case report": "care", "prediction model": "tripod",
    "animal": "arrive",
}


def detect(text: str, declared: str | None = None) -> str | None:
    if declared and declared.lower() in GUIDELINES:
        return declared.lower()
    low = (text or "").lower()
    for label, key in ALIASES.items():
        if label in low:
            return key
    return None


def check(text: str, guideline: str) -> dict:
    key = (guideline or "").lower()
    spec = GUIDELINES.get(key)
    if not spec:
        return {"guideline": guideline, "known": False, "ok": False,
                "missing": ["unknown guideline"], "present": []}
    low = re.sub(r"\s+", " ", text or "").lower()
    present, missing = [], []
    for item, markers in spec["required"].items():
        if any(m in low for m in markers):
            present.append(item)
        else:
            missing.append(item)
    return {"guideline": key, "name": spec["name"], "known": True,
            "ok": not missing, "present": present, "missing": missing,
            "coverage": round(len(present) / max(1, len(present) + len(missing)), 2)}


def check_all(text: str, guidelines: Iterable[str]) -> dict:
    results = [check(text, g) for g in guidelines]
    return {"ok": all(r["ok"] for r in results), "results": results}
