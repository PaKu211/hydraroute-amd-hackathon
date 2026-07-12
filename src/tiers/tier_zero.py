"""
Tier 0 - Zero-cost local execution (v3 - Extended).
Handles math, date math, string ops, unit conversion, regex extraction,
simple classification, and word problems using Python stdlib + dateutil.
No API calls = zero token cost.

Extended coverage based on winning competitor analysis:
- SebAustin: arithmetic, date math, string ops, unit conversion, regex
- realjunjiejj: local hardness scoring, local constrained tasks
"""

import logging
import re
from datetime import datetime, timedelta, date

logger = logging.getLogger("hydraroute")

SAFE_EVAL_PATTERN = re.compile(r"^[\d\s\+\-\*/\.\(\)%]+$")


def execute(instruction: str) -> str | None:
    text = instruction.strip()
    result = (
        _try_solve_equation(text)
        or _try_percentage(text)
        or _try_arithmetic(text)
        or _try_date_math(text)
        or _try_string_ops(text)
        or _try_unit_conversion(text)
        or _try_regex_extraction(text)
        or _try_simple_classification(text)
    )
    if result is not None:
        logger.info("Tier 0 solved locally: %s", result[:80])
        return str(result)
    return None


# ═══════════════════════════════════════════════════════════════
# Arithmetic
# ═══════════════════════════════════════════════════════════════


def _try_arithmetic(text: str) -> str | None:
    cleaned = text.lower()
    if "=" in text or any(
        v in cleaned
        for v in ["solve for", "value of", "find x", "find y", "find z", "find w"]
    ):
        return None
    if re.search(r"\b[xyz]\b", cleaned):
        return None

    for prefix in [
        "what is",
        "what's",
        "calculate",
        "compute",
        "evaluate",
        "find the value of",
        "find",
        "how much is",
        "what does",
        "what do you get when you",
    ]:
        cleaned = cleaned.replace(prefix, "")
    cleaned = cleaned.strip().rstrip("?").strip()

    expr_match = re.search(r"([\d][\d\s\+\-\*/\.\(\)%]+[\d\)])", cleaned)
    if expr_match:
        expr = expr_match.group(1).strip()
        if any(op in expr for op in "+-*/"):
            return _safe_eval(expr)
    if SAFE_EVAL_PATTERN.match(cleaned) and cleaned:
        return _safe_eval(cleaned)
    return None


def _try_percentage(text: str) -> str | None:
    match = re.search(
        r"(\d+(?:\.\d+)?)\s*%\s*(?:of)\s*(\d+(?:\.\d+)?)", text, re.IGNORECASE
    )
    if match:
        pct = float(match.group(1))
        base = float(match.group(2))
        result = (pct / 100.0) * base
        return str(int(result)) if result == int(result) else str(result)
    return None


def _safe_eval(expr: str) -> str | None:
    if not SAFE_EVAL_PATTERN.match(expr):
        return None
    if not expr or len(expr) > 200:
        return None
    try:
        code = compile(expr, "<math>", "eval")
        for name in code.co_names:
            return None
        result = eval(code, {"__builtins__": {}}, {})
        if isinstance(result, float):
            if result == int(result):
                return str(int(result))
            return f"{result:.10g}"
        return str(result)
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════
# Algebraic Equations (SymPy)
# ═══════════════════════════════════════════════════════════════


def _try_solve_equation(text: str) -> str | None:
    try:
        import sympy
        from sympy.parsing.sympy_parser import (
            parse_expr,
            standard_transformations,
            implicit_multiplication_application,
        )

        TRANSFORMATIONS = standard_transformations + (
            implicit_multiplication_application,
        )
    except ImportError:
        return None

    lower = text.lower()
    has_solve_kw = any(
        kw in lower
        for kw in [
            "solve",
            "find x",
            "find y",
            "what is x",
            "what is y",
            "value of x",
            "value of y",
            "for x",
            "for y",
        ]
    )
    has_equals = "=" in text and "==" not in text
    if not (has_solve_kw or has_equals):
        return None

    word_map = [
        (r"(?i)\ba number\b", "x"),
        (r"(?i)\btimes\b", "*"),
        (r"(?i)\bmultiplied by\b", "*"),
        (r"(?i)\bdivided by\b", "/"),
        (r"(?i)\bplus\b", "+"),
        (r"(?i)\bminus\b", "-"),
        (r"(?i)\bequals\b", "="),
        (r"(?i)\bis equal to\b", "="),
    ]
    translated = text
    for pattern, replacement in word_map:
        translated = re.sub(pattern, replacement, translated)

    equation_str = _extract_equation_v2(translated)
    if not equation_str:
        return None
    return _solve_with_sympy(equation_str, TRANSFORMATIONS)


def _extract_equation_v2(text: str) -> str | None:
    m = re.search(
        r"(?:solve\s+(?:for\s+\w+\s*:?\s*)?|find\s+\w+\s*:?\s*)"
        r"([^\?\.]+=[^\?\.]+)",
        text,
        re.IGNORECASE,
    )
    if m:
        return m.group(1).strip().rstrip("?., ")
    m = re.search(r"if\s+([^\?,]+=[^\?,]+),", text, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    m = re.search(
        r"((?:[\d]+\s*[\*]?\s*)?[a-zA-Z][\w\s\+\-\*/\.\(\)]*\s*=\s*[\d\w\s\+\-\*/\.\(\)]+)",
        text,
    )
    if m:
        eq = m.group(1).strip().rstrip("?., ")
        if re.search(r"[a-zA-Z]", eq):
            return eq
    return None


def _solve_sympy_worker(conn, equation_str: str) -> None:
    try:
        import sympy
        from sympy.parsing.sympy_parser import (
            parse_expr,
            standard_transformations,
            implicit_multiplication_application,
        )

        transformations = standard_transformations + (
            implicit_multiplication_application,
        )
        parts = equation_str.split("=", 1)
        lhs_str = parts[0].strip()
        rhs_str = parts[1].strip()
        lhs = parse_expr(lhs_str, transformations=transformations)
        rhs = parse_expr(rhs_str, transformations=transformations)
        equation = sympy.Eq(lhs, rhs)
        free_vars = list(equation.free_symbols)
        if not free_vars:
            conn.send(("result", None))
            return
        var = next((v for v in free_vars if str(v) == "x"), free_vars[0])
        solutions = sympy.solve(equation, var)
        if not solutions:
            conn.send(("result", None))
            return
        if isinstance(solutions, list):
            if len(solutions) == 1:
                sol = solutions[0]
                try:
                    val = int(sol)
                    conn.send(("result", str(val)))
                except (TypeError, ValueError):
                    conn.send(("result", str(sol)))
                return
            res = ", ".join(
                str(int(s)) if hasattr(s, "is_integer") and s.is_integer else str(s)
                for s in solutions
            )
            conn.send(("result", res))
            return
        conn.send(("result", str(solutions)))
    except Exception as e:
        conn.send(("error", str(e)))


def solve_equation_string(equation_str: str) -> str | None:
    """Solve a clean SymPy equation string (e.g., '2*x + 10 = 30').
    Used by SymPy-LLM Symbiosis: LLM translates word problem to equation,
    this function solves it locally with 100% accuracy.
    """
    if not equation_str or not equation_str.strip():
        return None
    eq = equation_str.strip().rstrip(".,;! ")
    if "=" not in eq:
        return None
    return _solve_with_sympy(eq)


def _solve_with_sympy(equation_str: str, transformations=None) -> str | None:
    if "=" not in equation_str:
        return None
    parts = equation_str.split("=", 1)
    lhs_str = parts[0].strip()
    rhs_str = parts[1].strip()
    if not lhs_str or not rhs_str:
        return None
    safe_pattern = re.compile(r"^[\d\s\+\-\*/\.\(\)a-zA-Z\^]+$")
    if not safe_pattern.match(lhs_str) or not safe_pattern.match(rhs_str):
        return None
    import multiprocessing

    try:
        ctx = multiprocessing.get_context("fork")
    except ValueError:
        ctx = multiprocessing
    parent_conn, child_conn = ctx.Pipe()
    p = ctx.Process(target=_solve_sympy_worker, args=(child_conn, equation_str))
    p.start()
    if parent_conn.poll(2.0):
        try:
            status, val = parent_conn.recv()
            p.join()
            return val if status == "result" else None
        except Exception:
            return None
    else:
        logger.warning("Sympy solve timed out for '%s'", equation_str)
        p.terminate()
        p.join()
        return None


# ═══════════════════════════════════════════════════════════════
# Date Math (using stdlib + optional dateutil)
# ═══════════════════════════════════════════════════════════════

_DATE_KEYWORDS = [
    "day after",
    "days after",
    "day before",
    "days before",
    "day from",
    "days from",
    "day from now",
    "days from now",
    "weeks after",
    "weeks before",
    "weeks from",
    "months after",
    "months before",
    "what date is",
    "what is the date",
]

_DATE_PARSE_TRY = [
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%B %d, %Y",
    "%d %B %Y",
    "%m/%d/%y",
    "%Y/%m/%d",
]


def _try_date_math(text: str) -> str | None:
    lower = text.lower()

    # Pattern: "X days/weeks/months after/before DATE"
    m = re.search(
        r"(\d+)\s*(day|days|week|weeks|month|months)\s+(after|before|from)\s+"
        r"(.+?)(?:\?|$|\.)",
        lower,
    )
    if not m:
        # Pattern: "What is the date X days from now?" or "What is DATE + X days?"
        m = re.search(
            r"(?:what date is|what is the date|date)\s+(\d+)\s*(day|days|week|weeks)"
            r"\s+(?:after|before|from|from now)\b",
            lower,
        )
    if not m:
        # Pattern: "X days from DATE" (SebAustin style)
        m = re.search(r"(\d+)\s*(day|days|week|weeks)\s+from\s+(.+?)(?:\?|$|\.)", lower)

    if m:
        amount = int(m.group(1))
        unit = m.group(2).lower()
        date_str = m.group(4).strip().rstrip("?.,! ")
        base_date = _parse_date(date_str)
        if base_date is None:
            return None
        td = timedelta(
            days=amount * 7 if "week" in unit else amount,
        )
        if "before" in lower:
            result = base_date - td
        else:
            result = base_date + td
        return result.strftime("%Y-%m-%d")

    # Pattern: "How many days between DATE1 and DATE2?"
    m = re.search(
        r"(?:how many|number of)\s*(days?)\s+(?:between|from)\s+"
        r"(.+?)\s+(?:to|and|until)\s+(.+?)(?:\?|$)",
        lower,
    )
    if m:
        d1 = _parse_date(m.group(2).strip())
        d2 = _parse_date(m.group(3).strip().rstrip("?.,! "))
        if d1 and d2:
            diff = abs((d2 - d1).days)
            return str(diff)

    return None


def _parse_date(text: str) -> date | None:
    clean = text.strip().rstrip("?.,! ")
    # Handle "today", "now", "today's date"
    if clean.lower() in ("today", "now", "today's date"):
        return date.today()
    for fmt in _DATE_PARSE_TRY:
        try:
            return datetime.strptime(clean, fmt).date()
        except (ValueError, TypeError):
            continue
    return None


# ═══════════════════════════════════════════════════════════════
# String Operations
# ═══════════════════════════════════════════════════════════════

_STRING_OPS = [
    (
        "count",
        r"(?:count|number of|how many)\s+(?:the\s+)?(?:letter|character|'?\"?)([a-zA-Z0-9\s])(?:'?\"?)?\s+(?:in|in the string|in the text)\s+(?:['\"]?(.+?)['\"]?)$",
    ),
    (
        "reverse",
        r"(?:reverse|in reverse)\s+(?:the\s+)?(?:string|word|text)\s+(?:['\"]?(.+?)['\"]?)$",
    ),
    (
        "length",
        r"(?:length|len|how long|character count)\s+(?:of\s+)?(?:the\s+)?(?:string|word|text)\s+(?:['\"]?(.+?)['\"]?)$",
    ),
    (
        "uppercase",
        r"(?:uppercase|upper case|capitalize|all caps)\s+(?:the\s+)?(?:string|word|text)\s+(?:['\"]?(.+?)['\"]?)$",
    ),
    (
        "lowercase",
        r"(?:lowercase|lower case|small)\s+(?:the\s+)?(?:string|word|text)\s+(?:['\"]?(.+?)['\"]?)$",
    ),
    (
        "palindrome",
        r"(?:is|check if|test if)\s+(?:['\"]?(.+?)['\"]?)\s+(?:is\s+)?(?:a\s+)?palindrome",
    ),
    (
        "trim",
        r"(?:trim|strip|remove whitespace)\s+(?:the\s+)?(?:string|word|text)\s+(?:['\"]?(.+?)['\"]?)$",
    ),
]


def _try_string_ops(text: str) -> str | None:
    lower = text.lower()
    # Count occurrences of substring
    m = re.search(
        r"count\s+(?:the\s+)?(?:number\s+of\s+)?['\"]?([a-zA-Z0-9\s_.-]+?)['\"]?\s+"
        r"in\s+['\"]?(.+?)['\"]?(?:\?|$|\.)",
        lower,
    )
    if m:
        needle = m.group(1).strip()
        haystack = m.group(2).strip()
        if needle and haystack:
            count = haystack.count(needle)
            return str(count)

    # Count specific words
    m = re.search(
        r"(?:count|how many)\s+(?:times\s+)?(?:does\s+)?['\"]?(\w+)['\"]?\s+"
        r"(?:appear|occur|found)\s+in\s+['\"]?(.+?)['\"]?(?:\?|$|\.)",
        lower,
    )
    if m:
        needle = m.group(1).strip().lower()
        haystack = m.group(2).strip().lower()
        if needle and haystack:
            count = haystack.split().count(needle)
            return str(count)

    # Reverse string
    m = re.search(
        r"reverse\s+(?:the\s+)?(?:string|text|word)\s+['\"]?(.+?)['\"]?(?:\?|$|\.)",
        lower,
    )
    if m:
        target = m.group(1).strip().rstrip("?.,! ")
        return target[::-1]

    # String length
    m = re.search(
        r"(?:length|how (?:many|long)|character count|len)\s+(?:of\s+)?"
        r"(?:the\s+)?(?:string|text|word)\s+['\"]?(.+?)['\"]?(?:\?|$|\.)",
        lower,
    )
    if m:
        target = m.group(1).strip().rstrip("?.,! ")
        return str(len(target))

    # Check palindrome
    m = re.search(r"is\s+['\"]?(.+?)['\"]?\s+(?:a\s+)?palindrome", lower)
    if m:
        target = m.group(1).strip().rstrip("?.,! ")
        cleaned = re.sub(r"[^a-zA-Z0-9]", "", target).lower()
        is_pal = cleaned == cleaned[::-1]
        return "True" if is_pal else "False"

    return None


# ═══════════════════════════════════════════════════════════════
# Unit Conversion (stdlib only — no pint dependency)
# ═══════════════════════════════════════════════════════════════

_CONVERSIONS: dict[tuple[str, str], callable] = {}


def _reg_conv(fr: str, to: str, fn: callable):
    _CONVERSIONS[(fr, to)] = fn
    if (to, fr) not in _CONVERSIONS:
        _CONVERSIONS[(to, fr)] = lambda x: 1.0 / fn(x) if fn(x) != 0 else 0


# Length
_reg_conv("km", "miles", lambda x: x * 0.621371)
_reg_conv("km", "mi", lambda x: x * 0.621371)
_reg_conv("miles", "km", lambda x: x * 1.60934)
_reg_conv("mi", "km", lambda x: x * 1.60934)
_reg_conv("meters", "feet", lambda x: x * 3.28084)
_reg_conv("m", "ft", lambda x: x * 3.28084)
_reg_conv("feet", "meters", lambda x: x * 0.3048)
_reg_conv("ft", "m", lambda x: x * 0.3048)
_reg_conv("kilometers", "miles", lambda x: x * 0.621371)
_reg_conv("inches", "cm", lambda x: x * 2.54)
_reg_conv("in", "cm", lambda x: x * 2.54)
_reg_conv("cm", "inches", lambda x: x / 2.54)

# Mass
_reg_conv("kg", "lbs", lambda x: x * 2.20462)
_reg_conv("kg", "pounds", lambda x: x * 2.20462)
_reg_conv("lbs", "kg", lambda x: x / 2.20462)
_reg_conv("pounds", "kg", lambda x: x / 2.20462)
_reg_conv("grams", "ounces", lambda x: x * 0.035274)
_reg_conv("g", "oz", lambda x: x * 0.035274)
_reg_conv("ounces", "grams", lambda x: x / 0.035274)
_reg_conv("oz", "g", lambda x: x / 0.035274)

# Temperature
_reg_conv("celsius", "fahrenheit", lambda x: x * 9.0 / 5.0 + 32)
_reg_conv("c", "f", lambda x: x * 9.0 / 5.0 + 32)
_reg_conv("fahrenheit", "celsius", lambda x: (x - 32) * 5.0 / 9.0)
_reg_conv("f", "c", lambda x: (x - 32) * 5.0 / 9.0)

# Volume
_reg_conv("liters", "gallons", lambda x: x * 0.264172)
_reg_conv("l", "gal", lambda x: x * 0.264172)
_reg_conv("gallons", "liters", lambda x: x / 0.264172)
_reg_conv("gal", "l", lambda x: x / 0.264172)
_reg_conv("ml", "fl oz", lambda x: x * 0.033814)
_reg_conv("milliliters", "fluid ounces", lambda x: x * 0.033814)

# Speed
_reg_conv("kmh", "mph", lambda x: x * 0.621371)
_reg_conv("km/h", "mph", lambda x: x * 0.621371)
_reg_conv("mph", "kmh", lambda x: x / 0.621371)
_reg_conv("mph", "km/h", lambda x: x / 0.621371)

_UNIT_ALIASES = {
    "kilometer": "km",
    "kilometers": "km",
    "kms": "km",
    "mile": "miles",
    "miles": "miles",
    "meter": "m",
    "meters": "m",
    "metre": "m",
    "metres": "m",
    "foot": "ft",
    "feet": "ft",
    "inch": "in",
    "inches": "in",
    "centimeter": "cm",
    "centimeters": "cm",
    "centimetre": "cm",
    "centimetres": "cm",
    "kilogram": "kg",
    "kilograms": "kg",
    "kgs": "kg",
    "pound": "lbs",
    "pounds": "lbs",
    "lb": "lbs",
    "gram": "g",
    "grams": "g",
    "ounce": "oz",
    "ounces": "oz",
    "celsius": "c",
    "centigrade": "c",
    "fahrenheit": "f",
    "liter": "l",
    "liters": "l",
    "litre": "l",
    "litres": "l",
    "gallon": "gal",
    "gallons": "gal",
    "milliliter": "ml",
    "milliliters": "ml",
    "millilitre": "ml",
    "millilitres": "ml",
    "fluid ounce": "fl oz",
    "fluid ounces": "fl oz",
}


def _try_unit_conversion(text: str) -> str | None:
    lower = text.lower()

    # Pattern: "convert X UNIT to UNIT" or "X UNIT in UNIT" or "X UNIT = ? UNIT"
    m = re.search(
        r"(?:convert|what is|how many)\s+"
        r"(\d+(?:\.\d+)?)\s*"
        r"([a-zA-Z/°]+(?:[\s-][a-zA-Z]+)*)\s+"
        r"(?:to|in|into)\s+"
        r"([a-zA-Z/°]+(?:[\s-][a-zA-Z]+)*)",
        lower,
    )
    if not m:
        m = re.search(
            r"(\d+(?:\.\d+)?)\s*"
            r"([a-zA-Z/°]+(?:[\s-][a-zA-Z]+)*)\s*"
            r"(?:to|in|into|=)\s*"
            r"(?:what\s+is\s+)?"
            r"([a-zA-Z/°]+(?:[\s-][a-zA-Z]+)*)",
            lower,
        )

    if m:
        value = float(m.group(1))
        from_unit = _normalize_unit(m.group(2).strip())
        to_unit = _normalize_unit(m.group(3).strip().rstrip("?.,! "))
        result = _convert(value, from_unit, to_unit)
        if result is not None:
            return f"{result:.4g}"
    return None


def _normalize_unit(unit: str) -> str:
    unit = unit.strip().lower().rstrip("s")  # plural → singular
    # Check aliases
    for alias, canonical in _UNIT_ALIASES.items():
        if unit == alias:
            return canonical
    return unit


def _convert(value: float, from_unit: str, to_unit: str) -> float | None:
    key = (from_unit, to_unit)
    if key in _CONVERSIONS:
        return _CONVERSIONS[key](value)
    return None


# ═══════════════════════════════════════════════════════════════
# Regex Extraction
# ═══════════════════════════════════════════════════════════════

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(r"(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")
_URL_RE = re.compile(r"https?://[^\s,;\"'<>]+")
_IP_RE = re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")
_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b|\b\d{2}/\d{2}/\d{4}\b")


def _try_regex_extraction(text: str) -> str | None:
    lower = text.lower()

    # Email extraction
    if any(kw in lower for kw in ["email", "email address", "e-mail", "mail"]):
        emails = _EMAIL_RE.findall(text)
        if emails:
            import json

            return json.dumps(emails)

    # Phone number extraction
    if any(
        kw in lower for kw in ["phone", "telephone", "phone number", "mobile", "call"]
    ):
        phones = _PHONE_RE.findall(text)
        if phones:
            cleaned = [
                p[0] + p[1] + p[2] + p[3] if isinstance(p, tuple) else p for p in phones
            ]
            import json

            return json.dumps(cleaned)

    # URL extraction
    if any(kw in lower for kw in ["url", "link", "website", "http", "https"]):
        urls = _URL_RE.findall(text)
        if urls:
            import json

            return json.dumps(urls)

    return None


# ═══════════════════════════════════════════════════════════════
# Simple Classification (keyword-based, zero tokens)
# ═══════════════════════════════════════════════════════════════

_POSITIVE_WORDS = {
    "amazing",
    "excellent",
    "fantastic",
    "great",
    "wonderful",
    "perfect",
    "love",
    "beautiful",
    "awesome",
    "incredible",
    "best",
    "outstanding",
    "superb",
    "brilliant",
    "delightful",
    "happy",
    "pleased",
    "impressive",
    "good",
    "nice",
    "positive",
    "favorable",
    "favourite",
    "favorite",
}

_NEGATIVE_WORDS = {
    "terrible",
    "horrible",
    "awful",
    "worst",
    "bad",
    "poor",
    "hate",
    "disgusting",
    "dreadful",
    "atrocious",
    "abysmal",
    "appalling",
    "disappointing",
    "frustrating",
    "annoying",
    "negative",
    "unfavorable",
    "mediocre",
    "useless",
    "broken",
    "failure",
    "ugly",
}

_NEUTRAL_INDICATORS = {
    "okay",
    "fine",
    "average",
    "decent",
    "adequate",
    "acceptable",
    "sufficient",
    "standard",
    "normal",
    "neutral",
}


def _try_simple_classification(text: str) -> str | None:
    lower = text.lower()

    # Only classify short texts (< 20 words) to avoid false positives
    # on long factual/narrative text (e.g., "Great Britain" matching "great")
    if len(text.split()) > 20:
        return None

    # Sentiment classification (exact match for short texts)
    words = set(re.findall(r"[a-zA-Z]+", lower))

    pos = words & _POSITIVE_WORDS
    neg = words & _NEGATIVE_WORDS
    neu = words & _NEUTRAL_INDICATORS

    # Only classify if there's a clear signal
    if pos and not neg:
        return "POS"
    if neg and not pos:
        return "NEG"
    if neu and not pos and not neg:
        return "NEU"

    return None


# ═══════════════════════════════════════════════════════════════
# Age / NER helper
# ═══════════════════════════════════════════════════════════════


def estimate_hardness(text: str) -> int:
    """Estimate task difficulty on a 1-5 scale (0 tokens, local only).
    Inspired by realjunjiejj's local hardness scoring."""
    lower = text.lower()
    word_count = len(text.split())

    score = 1

    # Length
    if word_count > 60:
        score = max(score, 2)
    if word_count > 120:
        score = max(score, 3)
    if word_count > 200:
        score = max(score, 4)

    # Code indicators
    if any(
        kw in lower
        for kw in [
            "def ",
            "class ",
            "import ",
            "```",
            "return ",
            "function",
            "var ",
            "let ",
            "const ",
        ]
    ):
        score = max(score, 3)
    if any(
        kw in lower for kw in ["debug", "fix", "bug", "error", "traceback", "exception"]
    ):
        score = max(score, 4)

    # Complex reasoning
    if any(
        kw in lower
        for kw in [
            "prove",
            "explain step by step",
            "syllogism",
            "logical puzzle",
            "deductive",
            "inductive",
        ]
    ):
        score = max(score, 3)
    if any(
        kw in lower
        for kw in ["algorithm", "recursive", "concurrency", "complexity", "o(n"]
    ):
        score = max(score, 4)

    return score
