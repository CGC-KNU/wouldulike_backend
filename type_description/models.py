from django.db import models

class TypeDescription(models.Model):
    id = models.AutoField(primary_key=True)
    type_code = models.CharField(max_length=4, null=False)
    type_name = models.CharField(max_length=255, null=False)
    description = models.TextField(null=False)
    # image = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    description_detail = models.TextField(blank=True, null=True)
    menu_and_mbti = models.TextField(blank=True, null=True)
    meal_example = models.TextField(blank=True, null=True)
    matching_type = models.TextField(blank=True, null=True)
    non_matching_type = models.TextField(blank=True, null=True)
    type_summary = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "type_description"
        managed = False