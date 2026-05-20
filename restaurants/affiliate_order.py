"""제휴 식당 목록·캐러셀 순서 (우주라이크 X 정든밤 축제 주막 우선)."""
from __future__ import annotations

import random

from django.db import connections

from coupons.festival_jungdunbam import (
    LEGACY_FESTIVAL_RESTAURANT_ID,
    RESTAURANT_ID as JUNGDUNBAM_FESTIVAL_RESTAURANT_ID,
)

# 맨 앞에 둘 식당 (현재 299)
PRIORITY_FIRST_RESTAURANT_IDS: tuple[int, ...] = (JUNGDUNBAM_FESTIVAL_RESTAURANT_ID,)
# 구 축제 ID(298)는 맨 뒤로 (DB에 제휴로 남아 있을 때)
DEMOTE_RESTAURANT_IDS: frozenset[int] = frozenset({LEGACY_FESTIVAL_RESTAURANT_ID})

_AFFILIATE_ROW_SQL = """
    SELECT
        restaurant_id,
        name,
        description,
        address,
        category,
        zone,
        phone_number,
        url,
        s3_image_urls
    FROM restaurants_affiliate
    WHERE restaurant_id = %s AND is_affiliate = TRUE
"""


def fetch_affiliate_row(
    restaurant_id: int,
    *,
    db_alias: str = "cloudsql",
) -> tuple | None:
    conn = connections[db_alias]
    with conn.cursor() as cursor:
        cursor.execute(_AFFILIATE_ROW_SQL, [restaurant_id])
        return cursor.fetchone()


def ensure_priority_affiliate_rows_included(
    rows,
    *,
    priority_ids: tuple[int, ...] = PRIORITY_FIRST_RESTAURANT_IDS,
    db_alias: str = "cloudsql",
) -> list:
    """목록에 없으면 DB에서 축제 주막 행을 붙인다 (마이그레이션·캐시 불일치 대비)."""
    rows = list(rows)
    present = {row[0] for row in rows}
    for rid in priority_ids:
        if rid in present:
            continue
        row = fetch_affiliate_row(rid, db_alias=db_alias)
        if row:
            rows.append(row)
            present.add(rid)
    return rows


def order_rows_priority_first(
    rows,
    *,
    priority_ids: tuple[int, ...] = PRIORITY_FIRST_RESTAURANT_IDS,
    demote_ids: frozenset[int] = DEMOTE_RESTAURANT_IDS,
) -> list:
    rows = list(rows)
    by_id = {row[0]: row for row in rows}
    ordered: list = []
    for rid in priority_ids:
        if rid in by_id:
            ordered.append(by_id[rid])
    demoted = [by_id[rid] for rid in demote_ids if rid in by_id and rid not in priority_ids]
    rest = [
        row
        for row in rows
        if row[0] not in set(priority_ids) and row[0] not in demote_ids
    ]
    return ordered + rest + demoted


def shuffle_rows_priority_first(
    rows,
    *,
    priority_ids: tuple[int, ...] = PRIORITY_FIRST_RESTAURANT_IDS,
    demote_ids: frozenset[int] = DEMOTE_RESTAURANT_IDS,
    db_alias: str = "cloudsql",
) -> list:
    rows = ensure_priority_affiliate_rows_included(
        rows, priority_ids=priority_ids, db_alias=db_alias
    )
    ordered = order_rows_priority_first(
        rows, priority_ids=priority_ids, demote_ids=demote_ids
    )
    priority_set = set(priority_ids) | demote_ids
    priority_rows = [row for row in ordered if row[0] in set(priority_ids)]
    demoted_rows = [row for row in ordered if row[0] in demote_ids]
    rest = [row for row in ordered if row[0] not in priority_set]
    random.shuffle(rest)
    return priority_rows + rest + demoted_rows


def prioritize_restaurant_id_list(
    ids,
    *,
    priority_ids: tuple[int, ...] = PRIORITY_FIRST_RESTAURANT_IDS,
    demote_ids: frozenset[int] = DEMOTE_RESTAURANT_IDS,
) -> list[int]:
    """스탬프 전체 조회 등 ID 목록 정렬."""
    id_list = list(ids)
    priority = [i for i in priority_ids if i in id_list]
    demoted = [i for i in demote_ids if i in id_list and i not in set(priority_ids)]
    rest = [i for i in id_list if i not in set(priority_ids) and i not in demote_ids]
    return priority + rest + demoted
