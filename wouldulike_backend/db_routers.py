class TypeDescriptionRouter:
    def db_for_read(self, model, **hints):
        """
        데이터 읽기 시 어떤 데이터베이스를 사용할지 결정
        """
        # 관계 접근 시 instance 힌트가 넘어오면 교차-DB 접근을 명시적으로 허용
        # 예) coupons 인스턴스에서 accounts.User를 읽는 경우 -> default
        instance = hints.get('instance')
        if instance is not None and getattr(instance._meta, 'app_label', None) == 'coupons' and getattr(model._meta, 'app_label', None) == 'accounts':
            return 'default'
        if model._meta.app_label in {'type_description', 'food_by_type'}:
            return 'rds'  # type_description, food_by_type은 rds에서 읽음
        if model._meta.app_label in {'coupons'}:
            return 'cloudsql'  # coupons는 cloudsql에서 읽음
        # elif model._meta.app_label == 'restaurants':
        #     return 'redshift'
        return 'default'  # 나머지는 기본 데이터베이스 사용

    def db_for_write(self, model, **hints):
        """
        데이터 쓰기 시 어떤 데이터베이스를 사용할지 결정
        """
        instance = hints.get('instance')
        if instance is not None and getattr(instance._meta, 'app_label', None) == 'coupons' and getattr(model._meta, 'app_label', None) == 'accounts':
            return 'default'
        if model._meta.app_label in {'type_description', 'food_by_type'}:
            return 'rds'  # type_description, food_by_type은 rds에 씀
        if model._meta.app_label in {'coupons'}:
            return 'cloudsql'  # coupons는 cloudsql에 씀
        # elif model._meta.app_label == 'restaurants':
        #     return 'redshift'
        return 'default'  # 나머지는 기본 데이터베이스 사용

    def allow_relation(self, obj1, obj2, **hints):
        """
        모든 데이터베이스 간의 관계를 허용
        """
        return True

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        마이그레이션이 가능한 데이터베이스를 결정
        """
        if app_label in {'type_description', 'food_by_type'}:
            return db == 'rds'  # type_description은 rds에만 마이그레이션
        if app_label in {'coupons'}:
            return db == 'cloudsql'  # coupons는 cloudsql에만 마이그레이션
        # elif app_label == 'restaurants':
        #     return db == 'redshift'
        return db == 'default'  # 나머지는 기본 데이터베이스에 마이그레이션
