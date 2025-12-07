from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("coupons", "0010_add_event_reward_campaigns"),
    ]

    operations = [
        migrations.AddField(
            model_name="invitecode",
            name="campaign_code",
            field=models.CharField(blank=True, max_length=40, null=True),
        ),
    ]

