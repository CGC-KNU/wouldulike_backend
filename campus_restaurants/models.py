from django.db import models


class CampusMenu(models.Model):
    menu_id = models.IntegerField(primary_key=True)
    menu_name = models.CharField(max_length=255)

    class Meta:
        db_table = 'menus_test'
        managed = False

    def __str__(self) -> str:
        return self.menu_name


class CampusRestaurant(models.Model):
    restaurant_id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=255, null=True, blank=True)
    phone_number = models.CharField(max_length=50, null=True, blank=True)
    zone = models.CharField(max_length=50, null=True, blank=True)
    category = models.CharField(max_length=50, null=True, blank=True)
    url = models.CharField(max_length=255, null=True, blank=True)
    menus = models.ManyToManyField(
        'CampusMenu',
        through='CampusRestaurantMenu',
        related_name='campus_restaurants',
    )

    class Meta:
        db_table = 'restaurants_test'
        managed = False

    def __str__(self) -> str:
        return self.name


class CampusRestaurantMenu(models.Model):
    id = models.BigAutoField(primary_key=True)
    restaurant = models.ForeignKey(
        'CampusRestaurant',
        models.DO_NOTHING,
        db_column='restaurant_id',
        related_name='menu_links',
    )
    menu = models.ForeignKey(
        'CampusMenu',
        models.DO_NOTHING,
        db_column='menu_id',
        related_name='restaurant_links',
    )

    class Meta:
        db_table = 'restaurant_menus_test'
        managed = False
        unique_together = (('restaurant', 'menu'),)

    def __str__(self) -> str:
        return f"{self.restaurant_id} -> {self.menu_id}"