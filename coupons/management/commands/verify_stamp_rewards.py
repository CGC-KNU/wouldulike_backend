"""
import_stamp_rewards_from_csv의 STAMP_DATA와 현재 DB 상태를 비교합니다.
차이가 있으면 import 시 내용이 변경되었음을 의미합니다.
"""
import json
from django.core.management.base import BaseCommand
from django.db import router

from coupons.models import StampRewardRule, RestaurantCouponBenefit
from coupons.service import STAMP_DB_ALIAS

# import_stamp_rewards_from_csv와 동일한 데이터/상수
from coupons.management.commands.import_stamp_rewards_from_csv import (
    STAMP_DATA,
    VISIT_COUPON_TYPES,
    THRESHOLD_COUPON_TYPES,
)


def _build_expected_rule(restaurant_id: int, data: dict) -> dict | None:
    """STAMP_DATA에서 expected config_json 생성."""
    rule_type = data["rule_type"]
    config = data["config"]
    stamp_notes = config.get("notes", "")

    if rule_type == "VISIT":
        range_keys = [
            f"{min_v}_{max_v}" if min_v != max_v else str(min_v)
            for min_v, max_v, _, _ in config["ranges"]
        ]
        return {
            "rule_type": rule_type,
            "config_json": {
                "ranges": [
                    {
                        "min_visit": config["ranges"][i][0],
                        "max_visit": config["ranges"][i][1],
                        "coupon_type_code": VISIT_COUPON_TYPES[range_keys[i]],
                    }
                    for i in range(len(config["ranges"]))
                ],
                "cycle_target": config.get("cycle_target", 10),
                "notes": stamp_notes,
            },
        }
    else:
        return {
            "rule_type": rule_type,
            "config_json": {
                "thresholds": [
                    {"stamps": t[0], "coupon_type_code": THRESHOLD_COUPON_TYPES[t[0]]}
                    for t in config["thresholds"]
                ],
                "cycle_target": config.get("cycle_target", 10),
                "notes": stamp_notes,
            },
        }


def _build_expected_benefits(restaurant_id: int, data: dict) -> dict:
    """STAMP_DATA에서 expected benefits per coupon_type_code."""
    rule_type = data["rule_type"]
    config = data["config"]
    result = {}

    if rule_type == "VISIT":
        for i, (min_v, max_v, title, notes) in enumerate(config["ranges"]):
            key = f"{min_v}_{max_v}" if min_v != max_v else str(min_v)
            code = VISIT_COUPON_TYPES[key]
            result[code] = {"title": title[:120], "notes": notes[:500] if notes else ""}
    else:
        for stamps, title, notes in config["thresholds"]:
            code = THRESHOLD_COUPON_TYPES[stamps]
            result[code] = {"title": title[:120], "notes": notes[:500] if notes else ""}
    return result


class Command(BaseCommand):
    help = "STAMP_DATA와 DB 상태 비교 (차이 있으면 import 시 변경됨)"

    def handle(self, *args, **options):
        rule_alias = STAMP_DB_ALIAS
        benefit_alias = router.db_for_read(RestaurantCouponBenefit)

        rule_diffs = []
        benefit_diffs = []

        for restaurant_id, data in STAMP_DATA.items():
            expected = _build_expected_rule(restaurant_id, data)
            if not expected:
                continue

            # StampRewardRule 비교
            try:
                rule = StampRewardRule.objects.using(rule_alias).get(
                    restaurant_id=restaurant_id
                )
                db_config = rule.config_json
                exp_config = expected["config_json"]

                # config_json 비교 (순서 무시)
                if not _config_equal(db_config, exp_config):
                    rule_diffs.append(
                        {
                            "restaurant_id": restaurant_id,
                            "field": "config_json",
                            "db": db_config,
                            "expected": exp_config,
                        }
                    )
            except StampRewardRule.DoesNotExist:
                rule_diffs.append(
                    {
                        "restaurant_id": restaurant_id,
                        "field": "rule",
                        "db": None,
                        "expected": expected,
                    }
                )

            # RestaurantCouponBenefit 비교
            expected_benefits = _build_expected_benefits(restaurant_id, data)
            for code, exp in expected_benefits.items():
                try:
                    b = RestaurantCouponBenefit.objects.using(benefit_alias).get(
                        restaurant_id=restaurant_id,
                        coupon_type__code=code,
                        active=True,
                    )
                    db_title = (b.title or "").strip()
                    db_notes = (b.notes or "").strip()
                    if db_title != exp["title"] or db_notes != exp["notes"]:
                        benefit_diffs.append(
                            {
                                "restaurant_id": restaurant_id,
                                "code": code,
                                "db_title": db_title,
                                "db_notes": db_notes,
                                "expected_title": exp["title"],
                                "expected_notes": exp["notes"],
                            }
                        )
                except RestaurantCouponBenefit.DoesNotExist:
                    benefit_diffs.append(
                        {
                            "restaurant_id": restaurant_id,
                            "code": code,
                            "db_title": None,
                            "db_notes": None,
                            "expected_title": exp["title"],
                            "expected_notes": exp["notes"],
                        }
                    )

        # 결과 출력
        if not rule_diffs and not benefit_diffs:
            self.stdout.write(
                self.style.SUCCESS(
                    "모든 식당의 DB가 STAMP_DATA와 일치합니다. "
                    "import 시 내용 변경 없음(동일 데이터 덮어쓰기)."
                )
            )
            return

        self.stdout.write(self.style.WARNING("차이 발견 (import 시 아래 내용으로 변경됨):"))
        if rule_diffs:
            self.stdout.write("\n[StampRewardRule 차이]")
            for d in rule_diffs:
                self.stdout.write(f"  restaurant_id={d['restaurant_id']}")
                if d.get("expected"):
                    self.stdout.write(
                        f"    expected: {json.dumps(d['expected'], ensure_ascii=False)}"
                    )
                if d.get("db") is not None:
                    self.stdout.write(
                        f"    db:      {json.dumps(d['db'], ensure_ascii=False)}"
                    )
        if benefit_diffs:
            self.stdout.write("\n[RestaurantCouponBenefit 차이]")
            for d in benefit_diffs:
                self.stdout.write(
                    f"  restaurant_id={d['restaurant_id']} {d['code']}"
                )
                self.stdout.write(
                    f"    db:      title={d['db_title']!r} notes={d['db_notes']!r}"
                )
                self.stdout.write(
                    f"    expected: title={d['expected_title']!r} notes={d['expected_notes']!r}"
                )


def _config_equal(a: dict, b: dict) -> bool:
    """config_json 비교 (순서 무시)."""
    return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
