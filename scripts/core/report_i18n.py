"""Report localization — section headings, labels, and language detection.

The skill keeps a single canonical English pipeline (gates, anchors, IDs) while
report.md/report.html can be rendered in English or Persian. Language is
explicit (`--lang`) or auto-detected from the brief title/question.
"""

from __future__ import annotations

import re

LANGS = ("en", "fa")

# canonical section keys — order matters for REQUIRED_SECTIONS and the md/HTML TOC
SECTION_KEYS = ("summary", "requirements", "findings", "matrix", "contradictions",
                "methodology", "model", "limitations", "bibliography", "claims")

REQUIRED_SECTION_KEYS = ("summary", "findings", "methodology", "limitations", "bibliography")

ARABIC_RE = re.compile(r"[\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff\ufb50-\ufdff\ufe70-\ufeff]")

_STRINGS: dict[str, dict[str, str]] = {
    "en": {
        # document chrome
        "doc.question": "Question.",
        "doc.run": "Run",
        "doc.profile": "profile",
        "doc.generated": "generated",
        "doc.precision": "Citation precision",
        "doc.sources": "sources",
        "doc.evidence_records": "evidence records",
        "doc.verify": "verify",
        "doc.spend": "paid spend",
        "doc.version": "version",
        "doc.gates": "Gates",
        "doc.lang": "Language",
        "doc.toc": "Contents",
        "doc.print": "Print",
        "doc.top": "Top",
        "doc.theme": "Toggle theme",
        "doc.appendix_note": "Every claim in this run, with the verbatim evidence quotes "
                             "that support it.",
        "doc.claims_empty": "No claims recorded in the ledger.",
        # sections
        "sec.summary": "Executive Summary",
        "sec.requirements": "Requirement Coverage",
        "sec.findings": "Findings",
        "sec.matrix": "Literature Comparison Matrix",
        "sec.contradictions": "Contradictions & Resolutions",
        "sec.methodology": "Methodology",
        "sec.limitations": "Limitations",
        "sec.bibliography": "Bibliography",
        "sec.claims": "Claim & Evidence Index",
        "sec.model": "Model & Reproducibility",
        # tables
        "th.id": "ID", "th.requirement": "Requirement", "th.status": "Status",
        "th.mapped_to": "Mapped to", "th.waiver_reason": "Waiver reason",
        "th.study": "Study", "th.problem": "Problem", "th.framework": "Framework",
        "th.method": "Method", "th.context": "Context", "th.findings": "Findings",
        "th.limitations": "Limitations", "th.relevance": "Relevance",
        "th.kind": "Kind", "th.severity": "Severity", "th.conflict": "Conflict",
        "th.resolution": "Resolution",
        "th.angle": "Angle", "th.sources": "Sources", "th.evidence": "Evidence",
        "th.claims": "Claims", "th.bands": "Bands",
        "th.search": "Search log", "th.query": "Query", "th.engine": "Engine",
        "th.hits": "Hits", "th.kept": "Kept", "th.at": "At",
        "th.source": "Source", "th.title": "Title", "th.exclusion_reason": "Exclusion reason",
        "th.claim": "Claim", "th.type": "Type", "th.updated": "Last updated",
        "th.referenced_by": "Referenced by", "th.quotes": "Evidence quotes",
        "th.locator": "Locator",
        "th.symbol": "Symbol", "th.variable": "Variable", "th.role": "Role",
        "th.unit": "Unit", "th.baseline": "Baseline", "th.range": "Range",
        "th.grounding": "Grounding", "th.equation": "Equation",
        "th.expression": "Expression", "th.output": "Output", "th.case": "Case", "th.decision": "Decision",
        "th.early_warning": "Early warning", "th.parameter": "Parameter",
        "th.values": "Values", "th.breakpoint": "Breakpoint",
        "th.comparator": "Comparator", "th.cost_of_delay": "Cost of delay",
        "th.staging": "Staging", "th.learning": "Learning",
        "th.where_differs": "Where it differs", "th.as_of": "As of",
        "th.depth": "Read depth", "th.numeric_claim": "Numeric claim",
        "th.value": "Value",
        # inline bits
        "in.evidence": "Evidence",
        "in.sources": "Sources",
        "in.counterpoints": "Counterpoints",
        "in.gaps": "Gaps",
        "in.open": "open",
        "in.resolved": "resolved",
        "in.strength": "strength",
        "in.confidence": "confidence",
        "in.no_contradictions": "No contradictions detected among verified claims.",
        "in.no_evidence": "No linked evidence.",
        "in.legend": "Legend",
        "in.search_screening": "Search & screening",
        "in.excluded": "Excluded at screening (with reasons)",
        "in.engines": "Engines",
        "in.against": "Origin",
        "in.claim_of": "Claim",
        "in.status_reason": "Status reason",
        "in.citation_anchor": "Jump to citation",
        "in.link": "link",
        "in.skip": "Skip to content",
        "in.critical": "critical",
        # methodology bullets
        "me.profile_budget": "Profile & budget",
        "me.source_mix": "Source mix",
        "me.verification": "Verification",
        "me.coverage": "Coverage",
        "me.searches": "searches",
        "me.budget_sources": "sources",
        "me.budget_evidence": "evidence",
        "me.resolved": "citations resolved",
        "me.gaps": "corroboration gaps",
        "me.screen_outcomes": "screening outcomes",
        "me.engine_line": "Engine `{engine}`: {queries} queries, {hits} hits, {kept} kept.",
        "me.between": "between {a} and {b}",
        "me.logged": "{n} logged search(es)",
        "me.logged_between": "{n} logged search(es) between {a} and {b}",
        "me.evidence_depth": "Evidence depth",
        "me.depth_summary": "full-text: {full} · partial: {partial} · abstract-only: {abstract} · unrecorded: {unknown}",
        "me.provenance": "Numeric provenance",
        "me.provenance_note": "Every numeric claim is listed with its source date and locator; academic and decision-framework reports fail on undated numeric evidence.",
        "me.provenance_empty": "No numeric claims recorded.",
        # limitations
        "lim.waived": "Waived requirement {id} ({text}): {reason}",
        "lim.budget": "Budget exception: {counter} reached {actual} (ceiling {ceiling}) — {reason}",
        "lim.gate_waiver": "Gate waiver (phase {phase} · {check}): {reason}",
        "lim.health": "Source health: {source} failed {n}× (last error: {err})",
        "lim.health_plain": "Source health: {source} failed {n}×",
        "lim.retracted": "Retracted sources excluded from load-bearing claims: {ids}",
        "lim.open_cx": "Unresolved contradictions remain visible: {ids}",
        "lim.gaps": "Corroboration gaps: {n} critical claim(s) rest on a single origin ({ids}).",
        "lim.weak": "Weakly supported / contradicted claims are labeled inline: {n} claim(s).",
        "lim.unreachable": "Citations that could not be machine-verified: {ids}.",
        "lim.none": "No waivers, budget exceptions, or health failures were recorded for this run.",
        "lim.downgraded": "Gate downgrades via --allow-flagged: {names}",
        "lim.model.single_stage": "Model scope: the valuation is single-stage; it does not price staged learning, Bayesian updating, or value of information.",
        "lim.model.partial_stages": "Model scope: only {implemented} of {total} declared stages are implemented; later stage-gate learning is outside the model.",
        "lim.model.no_learning": "Model scope: no probability updating or value-of-information step is implemented.",
        "lim.model.heuristic": "Model scope: allocation uses {method} ranking, not constrained portfolio optimization; dependencies and indivisibilities are not priced.",
        "lim.model.missing": "No validated model card was supplied for a computational or decision-framework deliverable.",
        "model.scope": "Scope", "model.learning": "Learning", "model.selection": "Selection",
        "model.yes": "yes", "model.no": "no", "model.assumption": "assumption",
        "model.baseline": "Baseline comparator", "model.cases": "Reproducible cases",
        "model.variables": "Variables", "model.equations": "Equations",
        "model.comparators": "Comparator fidelity", "model.sensitivity": "Sensitivity",
        "model.reproduction": "Reproduce with",
        "model.note": "Every scenario input is printed in full and re-evaluated by `model check`.",
        "model.scope_note": "Scope disclosure",
        "model.implemented_stages": "Implemented stages",
        "model.case.baseline": "baseline", "model.case.scenario": "scenario",
        "model.case.sensitivity": "sensitivity",
        "model.role.input": "input", "model.role.parameter": "parameter",
        "model.role.probability": "probability", "model.role.state": "state",
        "model.role.constant": "constant",
        "model.structure.single-stage": "single-stage",
        "model.structure.multi-stage": "multi-stage",
        "model.structure.unspecified": "unspecified",
        "model.selection.none": "none", "model.selection.greedy": "greedy",
        "model.selection.ranking": "ranking", "model.selection.heuristic": "heuristic",
        "model.selection.optimization": "optimization", "model.selection.exact": "exact",
        "model.selection.unspecified": "unspecified",
        "model.dim.yes": "full", "model.dim.partial": "partial",
        "model.dim.no": "none", "model.dim.na": "n/a",
        "depth.full-text": "full text", "depth.partial": "partial",
        "depth.abstract": "abstract", "depth.unknown": "unrecorded",
        # footer
        "footer.generated_by": "Generated by",
        "footer.trace": "every claim above traces to a verbatim quote in a SHA-256-snapshotted "
                        "source.",
        "footer.gates": "Report gates",
        # gates summary
        "gates.pending": "pending — see `report check`",
        "gates.summary": "{p}/{n} hard checks passed",
        "gates.downgraded": "{k} downgraded via --allow-flagged: {names}",
        # strength / confidence / statuses
        "badge.established": "established", "badge.supported": "supported",
        "badge.tentative": "tentative",
        "badge.high": "high", "badge.medium": "medium", "badge.low": "low",
        "status.verified": "verified", "status.supported": "supported",
        "status.weakly_supported": "weakly supported", "status.unverified": "unverified",
        "status.unverifiable": "unverifiable", "status.contradicted": "contradicted",
        "status.outweighed": "outweighed",
        "st.mapped": "mapped", "st.unmet": "unmet", "st.waived": "waived",
        "st.open": "open", "st.adjudicated": "adjudicated",
        "kind.numeric": "numeric", "kind.polarity": "polarity",
        "type.statistic": "statistic", "type.empirical": "empirical",
        "type.methodological": "methodological", "type.qualitative": "qualitative",
        "type.theoretical": "theoretical", "type.factual": "factual",
        "type.causal": "causal", "type.comparative": "comparative",
        "src_band": "credibility",
        "src_snapshot": "snapshot",
    },
    "fa": {
        "doc.question": "پرسش",
        "doc.run": "اجرا",
        "doc.profile": "پروفایل",
        "doc.generated": "تولید",
        "doc.precision": "دقت استناد",
        "doc.sources": "منبع",
        "doc.evidence_records": "رکورد شواهد",
        "doc.verify": "راستی‌آزمایی",
        "doc.spend": "هزینهٔ پرداختی",
        "doc.version": "نسخه",
        "doc.gates": "گیت‌ها",
        "doc.lang": "زبان",
        "doc.toc": "فهرست",
        "doc.print": "چاپ",
        "doc.top": "بالا",
        "doc.theme": "تغییر پوسته",
        "doc.appendix_note": "همهٔ ادعاهای این اجرا، همراه با نقل‌قول‌های واژگانی پشتیبان.",
        "doc.claims_empty": "هیچ ادعایی در دفتر شواهد ثبت نشده است.",
        "sec.summary": "خلاصهٔ اجرایی",
        "sec.requirements": "پوشش الزامات",
        "sec.findings": "یافته‌ها",
        "sec.matrix": "ماتریس مقایسهٔ ادبیات",
        "sec.contradictions": "تناقض‌ها و داوری",
        "sec.methodology": "روش‌شناسی",
        "sec.limitations": "محدودیت‌ها",
        "sec.bibliography": "منابع",
        "sec.claims": "نمایهٔ ادعاها و شواهد",
        "sec.model": "مدل و بازتولیدپذیری",
        "th.id": "شناسه", "th.requirement": "الزام", "th.status": "وضعیت",
        "th.mapped_to": "اتصال", "th.waiver_reason": "دلیل واگذاری",
        "th.study": "پژوهش", "th.problem": "مسئله", "th.framework": "چارچوب",
        "th.method": "روش", "th.context": "بافت", "th.findings": "یافته‌ها",
        "th.limitations": "محدودیت‌ها", "th.relevance": "نسبت با پرسش",
        "th.kind": "نوع", "th.severity": "شدت", "th.conflict": "تعارض",
        "th.resolution": "داوری",
        "th.angle": "زاویه", "th.sources": "منابع", "th.evidence": "شواهد",
        "th.claims": "ادعاها", "th.bands": "طبقه‌ها",
        "th.search": "شناسهٔ جست‌وجو", "th.query": "عبارت", "th.engine": "موتور",
        "th.hits": "بازیافته", "th.kept": "نگه‌داشته", "th.at": "زمان",
        "th.source": "منبع", "th.title": "عنوان", "th.exclusion_reason": "دلیل حذف",
        "th.claim": "ادعا", "th.type": "نوع", "th.updated": "آخرین به‌روزرسانی",
        "th.referenced_by": "ارجاع‌داده‌شده از", "th.quotes": "نقل‌قول‌های شاهد",
        "th.locator": "نشانی در منبع",
        "th.symbol": "نماد", "th.variable": "متغیر", "th.role": "نقش",
        "th.unit": "واحد", "th.baseline": "مقدار پایه", "th.range": "دامنه",
        "th.grounding": "پشتوانه", "th.equation": "معادله",
        "th.expression": "عبارت", "th.output": "خروجی", "th.case": "حالت", "th.decision": "تصمیم",
        "th.early_warning": "هشدار پیش‌هنگام", "th.parameter": "پارامتر",
        "th.values": "مقادیر", "th.breakpoint": "نقطهٔ شکست",
        "th.comparator": "روش مقایسه", "th.cost_of_delay": "هزینهٔ تأخیر",
        "th.staging": "مرحله‌بندی", "th.learning": "یادگیری",
        "th.where_differs": "تفاوت اصلی", "th.as_of": "تا تاریخ",
        "th.depth": "عمق مطالعه", "th.numeric_claim": "ادعای عددی",
        "th.value": "مقدار",
        "in.evidence": "شواهد",
        "in.sources": "منابع",
        "in.counterpoints": "نکات مقابل",
        "in.gaps": "شکاف‌ها",
        "in.open": "باز",
        "in.resolved": "داوری‌شده",
        "in.strength": "قوت",
        "in.confidence": "اطمینان",
        "in.no_contradictions": "هیچ تناقضی میان ادعاهای راستی‌آزمایی‌شده یافت نشد.",
        "in.no_evidence": "شاهد پیوندی ثبت نشده است.",
        "in.legend": "راهنما",
        "in.search_screening": "جست‌وجو و غربالگری",
        "in.excluded": "حذف‌شده در غربالگری (با دلیل)",
        "in.engines": "موتورها",
        "in.against": "خاستگاه",
        "in.claim_of": "ادعا",
        "in.status_reason": "دلیل وضعیت",
        "in.citation_anchor": "پرش به استناد",
        "in.link": "پیوند",
        "in.skip": "پرش به محتوا",
        "in.critical": "حیاتی",
        "me.profile_budget": "پروفایل و بودجه",
        "me.source_mix": "ترکیب منابع",
        "me.verification": "راستی‌آزمایی",
        "me.coverage": "پوشش",
        "me.searches": "جست‌وجو",
        "me.budget_sources": "منبع",
        "me.budget_evidence": "شواهد",
        "me.resolved": "استناد تعیین‌شده",
        "me.gaps": "شکاف تأیید متقابل",
        "me.screen_outcomes": "پیامد غربالگری",
        "me.engine_line": "موتور «{engine}»: {queries} پرس‌وجو، {hits} بازیافته، {kept} نگه‌داشته.",
        "me.between": "میان {a} و {b}",
        "me.logged": "{n} جست‌وجوی ثبت‌شده",
        "me.logged_between": "{n} جست‌وجوی ثبت‌شده میان {a} و {b}",
        "me.evidence_depth": "عمق شواهد",
        "me.depth_summary": "متن کامل: {full} · بخشی: {partial} · فقط چکیده: {abstract} · ثبت‌نشده: {unknown}",
        "me.provenance": "پشتوانهٔ عددی",
        "me.provenance_note": "هر ادعای عددی همراه با تاریخ منبع و نشانی در منبع فهرست می‌شود؛ گزارش‌های دانشگاهی و چارچوب تصمیم در صورت نبود تاریخ شاهد عددی رد می‌شوند.",
        "me.provenance_empty": "هیچ ادعای عددی ثبت نشده است.",
        "lim.waived": "الزام {id} ({text}) واگذار شد: {reason}",
        "lim.budget": "استثنای بودجه: {counter} به {actual} رسید (سقف {ceiling}) — {reason}",
        "lim.gate_waiver": "واگذاری گیت (فاز {phase} · {check}): {reason}",
        "lim.health": "سلامت منبع: {source} {n} بار ناموفق بود (آخرین خطا: {err})",
        "lim.health_plain": "سلامت منبع: {source} {n} بار ناموفق بود",
        "lim.retracted": "منابع بازپس‌گرفته‌شده از ادعاهای باربر کنار گذاشته شدند: {ids}",
        "lim.open_cx": "تناقض‌های حل‌نشده در گزارش نمایان می‌مانند: {ids}",
        "lim.gaps": "شکاف تأیید متقابل: {n} ادعای حیاتی تنها بر یک خاستگاه تکیه دارد ({ids}).",
        "lim.weak": "ادعاهای با پشتیبانی ضعیف یا متناقض به‌صورت درون‌متنی برچسب خورده‌اند: {n} ادعا.",
        "lim.unreachable": "استنادهایی که راستی‌آزمایی ماشینی نشدند: {ids}.",
        "lim.none": "برای این اجرا هیچ واگذاری، استثنای بودجه یا خطای سلامتی ثبت نشده است.",
        "lim.downgraded": "تنزل گیت‌ها با --allow-flagged: {names}",
        "lim.model.single_stage": "دامنهٔ مدل: ارزش‌گذاری تک‌مرحله‌ای است و یادگیری مرحله‌ای، به‌روزرسانی بیزی یا ارزش اطلاعات را قیمت‌گذاری نمی‌کند.",
        "lim.model.partial_stages": "دامنهٔ مدل: فقط {implemented} از {total} مرحلهٔ اعلام‌شده پیاده‌سازی شده است؛ یادگیری مرحله‌های بعدی خارج از مدل است.",
        "lim.model.no_learning": "دامنهٔ مدل: هیچ گام به‌روزرسانی احتمال یا ارزش اطلاعات پیاده‌سازی نشده است.",
        "lim.model.heuristic": "دامنهٔ مدل: تخصیص منابع با رتبه‌بندی {method} انجام می‌شود، نه بهینه‌سازی سبدِ مقید؛ وابستگی‌ها و تفکیک‌ناپذیری قیمت‌گذاری نشده‌اند.",
        "lim.model.missing": "برای یک خروجی محاسباتی یا چارچوب تصمیم، کارت مدلِ معتبر ارائه نشده است.",
        "model.scope": "دامنه", "model.learning": "یادگیری", "model.selection": "انتخاب",
        "model.yes": "بله", "model.no": "خیر", "model.assumption": "فرض",
        "model.baseline": "مقایسهٔ پایه", "model.cases": "حالت‌های بازتولیدپذیر",
        "model.variables": "متغیرها", "model.equations": "معادلات",
        "model.comparators": "وفاداری مقایسه", "model.sensitivity": "حساسیت",
        "model.reproduction": "بازتولید با",
        "model.note": "همهٔ ورودی‌های سناریو کامل چاپ و با `model check` دوباره محاسبه می‌شوند.",
        "model.scope_note": "افشای دامنه",
        "model.implemented_stages": "مراحل پیاده‌سازی‌شده",
        "model.case.baseline": "پایه", "model.case.scenario": "سناریو",
        "model.case.sensitivity": "حساسیت",
        "model.role.input": "ورودی", "model.role.parameter": "پارامتر",
        "model.role.probability": "احتمال", "model.role.state": "وضعیت",
        "model.role.constant": "ثابت",
        "model.structure.single-stage": "تک‌مرحله‌ای",
        "model.structure.multi-stage": "چندمرحله‌ای",
        "model.structure.unspecified": "نامشخص",
        "model.selection.none": "بدون", "model.selection.greedy": "حریصانه",
        "model.selection.ranking": "رتبه‌بندی", "model.selection.heuristic": "ابتکاری",
        "model.selection.optimization": "بهینه‌سازی", "model.selection.exact": "بهینهٔ دقیق",
        "model.selection.unspecified": "نامشخص",
        "model.dim.yes": "کامل", "model.dim.partial": "جزئی",
        "model.dim.no": "ندارد", "model.dim.na": "بی‌ربط",
        "depth.full-text": "متن کامل", "depth.partial": "بخشی",
        "depth.abstract": "چکیده", "depth.unknown": "ثبت‌نشده",
        "footer.generated_by": "تولیدشده با",
        "footer.trace": "هر ادعا به نقل‌قول واژگانی از منبعی با هش SHA-256 متصل است.",
        "footer.gates": "گیت‌های گزارش",
        "gates.pending": "در انتظار — `report check` را ببینید",
        "gates.summary": "{p} از {n} بررسی سخت قبول شد",
        "gates.downgraded": "{k} مورد با --allow-flagged تنزل کرد: {names}",
        "badge.established": "استوار", "badge.supported": "پشتیبانی‌شده",
        "badge.tentative": "مقدماتی",
        "badge.high": "بالا", "badge.medium": "متوسط", "badge.low": "پایین",
        "status.verified": "تأییدشده", "status.supported": "پشتیبانی‌شده",
        "status.weakly_supported": "پشتیبانی ضعیف", "status.unverified": "راستی‌آزمایی‌نشده",
        "status.unverifiable": "غیرقابل راستی‌آزمایی", "status.contradicted": "متناقض",
        "status.outweighed": "کم‌وزن‌تر",
        "st.mapped": "پوشش‌داده‌شده", "st.unmet": "پوشش‌داده‌نشده", "st.waived": "واگذارشده",
        "st.open": "باز", "st.adjudicated": "داوری‌شده",
        "kind.numeric": "عددی", "kind.polarity": "قطبیت",
        "type.statistic": "آماری", "type.empirical": "تجربی",
        "type.methodological": "روش‌شناختی", "type.qualitative": "کیفی",
        "type.theoretical": "نظری", "type.factual": "واقعی",
        "type.causal": "علّی", "type.comparative": "مقایسه‌ای",
        "src_band": "اعتبار",
        "src_snapshot": "اسنپ‌شات",
    },
}


def normalize(value: str | None) -> str | None:
    """Return 'en'/'fa' for a user-supplied language, else None."""
    if not value:
        return None
    v = value.strip().lower()
    if v in ("fa", "farsi", "persian", "prs", "pes"):
        return "fa"
    if v in ("en", "english", "eng"):
        return "en"
    return None


def detect(text: str) -> str:
    """Dominant script heuristic: Persian when ≥15% of letters are Arabic-script."""
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return "en"
    arabic = sum(1 for ch in letters if ARABIC_RE.match(ch))
    return "fa" if arabic / len(letters) >= 0.15 else "en"


def resolve(explicit: str | None, *samples: str | None) -> str:
    """Explicit --lang wins; otherwise detect from title/question samples."""
    norm = normalize(explicit)
    if norm:
        return norm
    return detect(" ".join(s for s in samples if s))


def t(lang: str, key: str, default: str | None = None, **fmt) -> str:
    """Translate a key (English fallback) with optional format args."""
    table = _STRINGS.get(lang) or _STRINGS["en"]
    text = table.get(key) or _STRINGS["en"].get(key)
    if text is None:
        text = default if default is not None else key
    if fmt:
        try:
            return text.format(**fmt)
        except (KeyError, IndexError):
            return text
    return text


def heading(lang: str, key: str) -> str:
    return t(lang, f"sec.{key}")


def heading_variants(key: str) -> tuple[str, str]:
    """Both known spellings of a section heading (en, fa) for gate lookups."""
    return heading("en", key), heading("fa", key)


def labels(lang: str) -> dict[str, str]:
    """The full translated label table for a language (english fallback)."""
    table = _STRINGS.get(lang) or _STRINGS["en"]
    return {key: (table.get(key) or _STRINGS["en"].get(key, key)) for key in _STRINGS["en"]}


# Template-vocabulary aliases so requirement anchors recorded in one language
# still resolve against a report rendered in the other (legacy runs included).
_WORD_ALIASES = {
    "literature": "ادبیات", "comparison": "مقایسه", "matrix": "ماتریس",
    "screening": "غربالگری", "search": "جست‌وجو", "findings": "یافته‌ها",
    "finding": "یافته", "summary": "خلاصه", "methodology": "روش‌شناسی",
    "limitations": "محدودیت‌ها", "limitation": "محدودیت", "bibliography": "منابع",
    "requirement": "الزام", "requirements": "الزامات", "coverage": "پوشش",
    "contradiction": "تناقض", "contradictions": "تناقض‌ها", "claim": "ادعا",
    "claims": "ادعاها", "evidence": "شواهد", "sources": "منابع", "source": "منبع",
    "credibility": "اعتبار", "snapshot": "اسنپ‌شات", "excluded": "حذف‌شده",
    "counterpoints": "مقابل", "gaps": "شکاف‌ها", "index": "نمایه",
}


def anchor_aliases(anchor: str) -> str:
    """Token-level translation of an anchor (order-free matching downstream)."""
    words = re.findall(r"[\w\u0600-\u06ff]+", anchor)
    out = []
    for word in words:
        alt = _WORD_ALIASES.get(word.casefold())
        if alt:
            out.append(alt)
    return " ".join(out)
