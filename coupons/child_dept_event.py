"""
아동학부 쿠폰팩 일괄 발급 — 성년의날(GAEHWALIKE) 풀 + subtitle [아동학부 쿠폰팩 🐣].
"""
from __future__ import annotations

CHILD_DEPT_COUPON_TYPE_CODE = "CHILD_DEPT_COUPON_PACK"  # 구(주점) 발급 복구용
CHILD_DEPT_CAMPAIGN_CODE = "CHILD_DEPT_COUPON_PACK_202605"
CHILD_DEPT_SUBTITLE = "[아동학부 쿠폰팩 🐣]"
CHILD_DEPT_ISSUE_KEY_NAMESPACE = "CHILD_DEPT_PACK"

# 5월 아동학부 신청폼(17명) + 추가
CHILD_DEPT_DEFAULT_NICKNAMES: tuple[str, ...] = (
    "맛집만간다",
    "노란포스트잇",
    "디니",
    "sysy0612",
    "이지은",
    "chan",
    "김주연",
    "라라미",
    "dawon1028",
    "haiiiigo",
    "hk",
    "tying2014",
    "쪼롱",
    "박세은",
    "하하루",
    "아료니",
    "죵재",
    "딸기잼잼",
    "딸기잼",
)


def load_nicknames_from_excel(path: str) -> list[str]:
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True)
    ws = wb.active
    nicknames: list[str] = []
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            continue
        if not row or len(row) < 6:
            continue
        fee = (row[4] or "").strip() if row[4] is not None else ""
        if fee and fee.upper() not in ("O", "Y", "YES", "예"):
            continue
        nick = (row[5] or "").strip() if row[5] is not None else ""
        if nick:
            nicknames.append(nick)
    wb.close()
    return nicknames


def ensure_child_dept_event_data(*, db_alias: str | None = None) -> str:
    """마이그레이션 호환 no-op (실제 발급은 GAEHWALIKE 풀 + issue_child_dept_coupon_pack)."""
    from coupons.festival_jungdunbam import resolve_cloudsql_alias

    return db_alias or resolve_cloudsql_alias()


def merge_nickname_lists(*lists: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in lists:
        for nick in raw:
            key = nick.strip()
            if not key:
                continue
            fold = key.casefold()
            if fold in seen:
                continue
            seen.add(fold)
            out.append(key)
    return out
