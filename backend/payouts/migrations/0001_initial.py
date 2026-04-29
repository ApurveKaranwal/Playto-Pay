from django.db import migrations, models
import django.core.validators
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Merchant",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["id"]},
        ),
        migrations.CreateModel(
            name="Payout",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("amount_paise", models.BigIntegerField(validators=[django.core.validators.MinValueValidator(1)])),
                ("status", models.CharField(choices=[("pending", "Pending"), ("processing", "Processing"), ("completed", "Completed"), ("failed", "Failed")], default="pending", max_length=20)),
                ("idempotency_key", models.CharField(max_length=255)),
                ("bank_account_id", models.CharField(max_length=255)),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("processing_started_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("merchant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="payouts", to="payouts.merchant")),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.CreateModel(
            name="LedgerEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("entry_type", models.CharField(choices=[("CREDIT", "Credit"), ("HOLD", "Hold"), ("DEBIT", "Debit"), ("RELEASE", "Release")], max_length=10)),
                ("amount_paise", models.BigIntegerField(validators=[django.core.validators.MinValueValidator(1)])),
                ("reference_id", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("merchant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="ledger_entries", to="payouts.merchant")),
                ("payout", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="ledger_entries", to="payouts.payout")),
            ],
            options={"ordering": ["created_at", "id"]},
        ),
        migrations.CreateModel(
            name="IdempotencyKey",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.CharField(max_length=255)),
                ("response_status_code", models.PositiveSmallIntegerField()),
                ("response_data", models.JSONField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("merchant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="idempotency_keys", to="payouts.merchant")),
                ("payout", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="idempotency_record", to="payouts.payout")),
            ],
        ),
        migrations.AddConstraint(
            model_name="payout",
            constraint=models.UniqueConstraint(fields=("merchant", "idempotency_key"), name="uniq_payout_idempotency_per_merchant"),
        ),
        migrations.AddConstraint(
            model_name="payout",
            constraint=models.CheckConstraint(condition=models.Q(("amount_paise__gt", 0)), name="payout_amount_paise_gt_zero"),
        ),
        migrations.AddConstraint(
            model_name="ledgerentry",
            constraint=models.CheckConstraint(condition=models.Q(("amount_paise__gt", 0)), name="ledger_amount_paise_gt_zero"),
        ),
        migrations.AddConstraint(
            model_name="idempotencykey",
            constraint=models.UniqueConstraint(fields=("merchant", "key"), name="uniq_idempotency_key_per_merchant"),
        ),
        migrations.AddIndex(
            model_name="ledgerentry",
            index=models.Index(fields=["merchant", "entry_type", "created_at"], name="payouts_led_merchan_f45ca4_idx"),
        ),
        migrations.AddIndex(
            model_name="ledgerentry",
            index=models.Index(fields=["payout", "entry_type"], name="payouts_led_payout__db246f_idx"),
        ),
    ]
