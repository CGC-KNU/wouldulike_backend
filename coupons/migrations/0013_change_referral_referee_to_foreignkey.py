from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("coupons", "0012_change_invitecode_user_to_foreignkey"),
    ]

    operations = [
        migrations.AddField(
            model_name="referral",
            name="campaign_code",
            field=models.CharField(blank=True, max_length=40, null=True),
        ),
        migrations.AlterField(
            model_name="referral",
            name="referee",
            field=models.ForeignKey(
                db_constraint=False,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="referrals_received",
                to="accounts.User",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="referral",
            name="uq_ref_pair",
        ),
        migrations.AddConstraint(
            model_name="referral",
            constraint=models.UniqueConstraint(
                condition=models.Q(("campaign_code__isnull", True)),
                fields=("referrer", "referee"),
                name="uq_ref_pair_default",
            ),
        ),
        migrations.AddConstraint(
            model_name="referral",
            constraint=models.UniqueConstraint(
                condition=models.Q(("campaign_code__isnull", False)),
                fields=("referee", "campaign_code"),
                name="uq_ref_pair_event",
            ),
        ),
    ]

