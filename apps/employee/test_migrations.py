import importlib
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import Mock

from django.test import SimpleTestCase


class StarFieldsMigrationTests(SimpleTestCase):
    def run_migration(self, existing_columns):
        migration = importlib.import_module(
            'apps.employee.migrations.0030_add_star_fields'
        )
        employee_model = SimpleNamespace(
            _meta=SimpleNamespace(db_table='emp_employee')
        )
        apps = Mock()
        apps.get_model.return_value = employee_model

        connection = Mock()
        connection.cursor.return_value = nullcontext(Mock())
        connection.introspection.get_table_description.return_value = [
            SimpleNamespace(name=name) for name in existing_columns
        ]
        schema_editor = Mock(connection=connection)

        migration.ensure_star_fields(apps, schema_editor)
        return [
            call.args[1].name for call in schema_editor.add_field.call_args_list
        ]

    def test_adds_both_fields_when_missing(self):
        self.assertEqual(
            self.run_migration(set()),
            ['is_star', 'star_sort'],
        )

    def test_skips_existing_field_and_adds_only_missing_field(self):
        self.assertEqual(
            self.run_migration({'is_star'}),
            ['star_sort'],
        )

    def test_skips_both_fields_when_they_already_exist(self):
        self.assertEqual(
            self.run_migration({'is_star', 'star_sort'}),
            [],
        )
