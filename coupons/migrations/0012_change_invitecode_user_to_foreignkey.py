from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("coupons", "0011_add_invite_code_campaign_code"),
    ]

    operations = [
        migrations.AlterField(
            model_name="invitecode",
            name="user",
            field=models.ForeignKey(
                db_constraint=False,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="invite_codes",
                to="accounts.User",
            ),
        ),
        migrations.AddConstraint(
            model_name="invitecode",
            constraint=models.UniqueConstraint(
                condition=models.Q(("campaign_code__isnull", True)),
                fields=("user",),
                name="uq_invite_code_user_default",
            ),
        ),
    ]

