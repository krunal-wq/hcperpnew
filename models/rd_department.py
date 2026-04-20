"""
models/rd_department.py
───────────────────────
R&D department ko identify karne ke liye central helper.

Real-world me users department ko alag-alag tarikon se naam dete hain:
  'R&D', 'R & D', 'RD', 'R&D', 'R & D',
  'Research and Development', 'Research & Development',
  'Research And Development', 'R and D', 'r_and_d', 'r-and-d',
  'R and D Dept', 'RND', 'R.N.D.', etc.

Ye module saare variations ko ek consistent way se match karta hai.
"""
import re
from .base import db


# Normalized keywords jo valid R&D department names ke baad bante hain
# "research and development" ke alag-alag permutations
_RD_NORMALIZED_SET = {
    'rd',
    'r and d',
    'rnd',
    'research development',
    'research and development',
    'r & d',          # ampersand to "and" wala case — hum normalize nahi karte taki yeh alag se match ho
}


def _normalize(s):
    """
    Normalize karo string ko — lowercase, saari punctuation remove,
    'and' / '&' ko consistent kar do, multiple spaces ek me.
    """
    if not s:
        return ''
    x = s.strip().lower()
    # & ko " and " me convert (word-boundary safety ke saath)
    x = x.replace('&', ' and ')
    # All non-alphanumeric → space (. , _ - / etc.)
    x = re.sub(r'[^a-z0-9]+', ' ', x)
    # Collapse multi-spaces
    x = re.sub(r'\s+', ' ', x).strip()
    return x


def is_rd_department(value):
    """
    Python-side check: string `value` R&D department ka hai ya nahi?
    Use this when you already have a department/designation string in
    Python memory.

    Examples of True:
        'R&D'                       → 'r and d' → matches
        'R & D'                     → 'r and d' → matches
        'Research and Development'  → 'research and development'
        'Research & Development'    → 'research and development'
        'RD'                        → 'rd'
        'R and D'                   → 'r and d'
        'R_and_D Dept'              → 'r and d dept' → contains 'r and d'
        'RND Team'                  → 'rnd team' → contains 'rnd'

    Examples of False:
        'HR', 'Sales', 'IT', 'Production', '' , None
    """
    if not value:
        return False
    n = _normalize(value)
    if not n:
        return False

    # Direct match
    if n in _RD_NORMALIZED_SET:
        return True

    # Token-based match — jab 'r and d' / 'rnd' / 'research development'
    # as substring aaye larger string me (e.g. "R&D Department", "RND Team")
    for kw in ('r and d', 'research and development', 'research development'):
        if kw in n:
            # Must be word-bounded — 'brand d' shouldn't match 'r and d'
            # n is space-delimited tokens, so check word boundary
            pattern = r'(^|\s)' + re.escape(kw) + r'(\s|$)'
            if re.search(pattern, n):
                return True

    # Standalone 'rd' or 'rnd' token (not part of another word like "rod")
    tokens = n.split()
    if 'rd' in tokens or 'rnd' in tokens:
        return True

    # Dotted variations like "R.N.D.", "R.D." — normalize se 'r n d' / 'r d' ban jaate hain
    if tokens == ['r', 'n', 'd'] or tokens == ['r', 'd']:
        return True
    # "R.N.D. Dept" → "r n d dept" → check prefix
    if tokens[:3] == ['r', 'n', 'd'] or tokens[:2] == ['r', 'd']:
        return True

    return False


def rd_department_filter(EmployeeModel, include_designation=False):
    """
    SQLAlchemy OR-clause return karta hai jo kisi bhi R&D department
    naming variation ko match kare. Use karo Employee.query.filter() me:

        from models.rd_department import rd_department_filter
        emps = Employee.query.filter(
            Employee.is_deleted == False,
            rd_department_filter(Employee),
        ).all()

    Args:
        EmployeeModel: Employee SQLAlchemy model class
        include_designation: bhi True ho to Employee.designation me bhi
                              R&D-ish keywords (formulation, scientist,
                              chemist) dhundhega

    Note: SQL-level ILIKE patterns use karta hai. Hamare paas exact
    `_normalize()` SQL me nahi hai, toh practical patterns cover karte hain:
      - 'r&d'           (with ampersand, any spacing)
      - 'r & d'         (with spaces around &)
      - 'r and d'       (with 'and')
      - 'research%development'  (full form with any middle)
      - 'r_and_d', 'r-and-d'    (underscored/hyphenated)
      - 'rnd', 'rd'     (standalone — care kiya gaya hai word boundaries ka)
    """
    patterns = [
        # Ampersand variations
        '%r&d%',
        '%r & d%',
        '%r &d%',
        '%r& d%',
        # "and" word variations
        '%r and d%',
        '%r_and_d%',
        '%r-and-d%',
        # Full form
        '%research%development%',
        # Short forms
        'rnd',           # exact
        '%rnd %',        # prefix
        '% rnd%',        # suffix
        '%rnd',          # suffix at end
        'rd',            # exact standalone
        'r&d',           # exact
        'r & d',         # exact
    ]

    clauses = [EmployeeModel.department.ilike(p) for p in patterns]

    if include_designation and hasattr(EmployeeModel, 'designation'):
        desig_patterns = [
            '%r&d%',
            '%r & d%',
            '%research and development%',
            '%formulation%',
            '%scientist%',
            '%chemist%',
        ]
        clauses.extend([EmployeeModel.designation.ilike(p) for p in desig_patterns])

    return db.or_(*clauses)


# ── Quick self-test (run: python -m models.rd_department) ──
if __name__ == '__main__':
    print("is_rd_department() self-test:")
    test_cases = [
        # (input, expected)
        ('R&D',                         True),
        ('R & D',                       True),
        ('r&d',                         True),
        ('Research and Development',    True),
        ('Research & Development',      True),
        ('research_and_development',    True),
        ('R and D',                     True),
        ('RD',                          True),
        ('RND',                         True),
        ('R.N.D.',                      True),
        ('R&D Department',              True),
        ('R & D Team',                  True),
        ('r&d ',                        True),   # trailing space
        (' R&D',                        True),
        ('Sales',                       False),
        ('HR',                          False),
        ('IT',                          False),
        ('Production',                  False),
        ('Marketing',                   False),
        ('',                            False),
        (None,                          False),
        ('rod',                         False),  # not 'rd'
        ('brand',                       False),  # not 'r and d'
        ('Hard Goods',                  False),
    ]
    failed = 0
    for inp, expected in test_cases:
        got = is_rd_department(inp)
        mark = '✅' if got == expected else '❌'
        if got != expected: failed += 1
        print(f"  {mark} is_rd_department({inp!r:<40}) → {got}  (expected {expected})")
    print(f"\n  {'All passed!' if failed == 0 else f'{failed} failures'}")
