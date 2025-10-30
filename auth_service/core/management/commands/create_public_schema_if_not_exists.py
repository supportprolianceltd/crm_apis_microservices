# auth_service/core/management/commands/create_public_schema_if_not_exists.py

from django.core.management.base import BaseCommand
from django_tenants.utils import get_public_schema_name, schema_exists
from django.db import connection

class Command(BaseCommand):
    help = "Ensure the public schema exists in the database"

    def handle(self, *args, **options):
        public_schema = get_public_schema_name()

        if schema_exists(public_schema):
            self.stdout.write(self.style.SUCCESS(f"Public schema '{public_schema}' already exists."))
            return

        with connection.cursor() as cursor:
            cursor.execute(f'CREATE SCHEMA {public_schema}')
        
        self.stdout.write(self.style.SUCCESS(f"Created public schema: {public_schema}"))