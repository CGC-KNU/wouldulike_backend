from django.db import models

class TypeDescription(models.Model):
    type_code = models.CharField(max_length=4)  # character(4)
    description = models.TextField()  # text
    # image = models.CharField(max_length=255, blank=True, null=True)  # character varying(255)
    created_at = models.DateTimeField()  # timestamp without time zone
    updated_at = models.DateTimeField()  # timestamp without time zone

    class Meta:
        db_table = "type_description"  # PostgreSQL 테이블 이름
        managed = False  # Django가 테이블을 관리하지 않도록 설정
