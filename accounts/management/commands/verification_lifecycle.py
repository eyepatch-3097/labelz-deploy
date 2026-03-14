from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import User, Org
from accounts.emailing import (
    send_verification_reminder_email,
    send_account_closure_email,
)


class Command(BaseCommand):
    help = "Send verification reminders and remove unverified accounts on day 15."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would happen without sending emails or deleting users.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        now = timezone.now()

        users = (
            User.objects
            .filter(email_is_verified=False)
            .select_related("org")
            .order_by("date_joined")
        )

        self.stdout.write(f"Found {users.count()} unverified user(s).")

        for user in users:
            age_days = (now - user.date_joined).days

            # Day 15+: send closure email, then delete user, then delete org if empty
            if age_days >= 15:
                if dry_run:
                    self.stdout.write(
                        f"[DRY RUN] Would send closure email and delete user {user.email} (age_days={age_days})"
                    )
                    continue

                org_id = user.org_id
                email = user.email

                try:
                    send_account_closure_email(email)
                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(f"Closure email failed for {email}: {e}")
                    )
                    # Continue anyway, or return/skip depending on your preference

                with transaction.atomic():
                    user.delete()

                    if org_id:
                        org = Org.objects.filter(id=org_id).first()
                        if org and not org.users.exists():
                            org.delete()

                self.stdout.write(
                    self.style.SUCCESS(f"Deleted unverified user {email}")
                )
                continue

            # Day 14 reminder
            if age_days >= 14 and user.verification_reminder_stage < 2:
                if dry_run:
                    self.stdout.write(
                        f"[DRY RUN] Would send day-14 reminder to {user.email}"
                    )
                    continue

                try:
                    send_verification_reminder_email(user.email, day=14)
                    user.verification_reminder_stage = 2
                    user.save(update_fields=["verification_reminder_stage"])
                    self.stdout.write(
                        self.style.SUCCESS(f"Sent day-14 reminder to {user.email}")
                    )
                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(f"Day-14 reminder failed for {user.email}: {e}")
                    )
                continue

            # Day 7 reminder
            if age_days >= 7 and user.verification_reminder_stage < 1:
                if dry_run:
                    self.stdout.write(
                        f"[DRY RUN] Would send day-7 reminder to {user.email}"
                    )
                    continue

                try:
                    send_verification_reminder_email(user.email, day=7)
                    user.verification_reminder_stage = 1
                    user.save(update_fields=["verification_reminder_stage"])
                    self.stdout.write(
                        self.style.SUCCESS(f"Sent day-7 reminder to {user.email}")
                    )
                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(f"Day-7 reminder failed for {user.email}: {e}")
                    )
