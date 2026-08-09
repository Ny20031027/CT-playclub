from django.test import TestCase
from rest_framework.test import APIClient

from .models import User
from .serializers import UserSerializer


class BlackGoldIdTests(TestCase):
    def test_ensure_display_id_is_numeric_unique_and_stable(self):
        first = User.objects.create_user(username='black_gold_first')
        second = User.objects.create_user(username='black_gold_second')

        first_id = first.ensure_display_id()
        second_id = second.ensure_display_id()

        self.assertRegex(first_id, r'^\d{9}$')
        self.assertRegex(second_id, r'^\d{9}$')
        self.assertNotEqual(first_id, second_id)
        self.assertEqual(first.ensure_display_id(), first_id)

    def test_serializer_rejects_invalid_or_duplicate_display_id(self):
        existing = User.objects.create_user(username='black_gold_existing')
        existing.display_id = '123456789'
        existing.save(update_fields=['display_id'])
        target = User.objects.create_user(username='black_gold_target')

        invalid = UserSerializer(target, data={'display_id': '1234567890'}, partial=True)
        self.assertFalse(invalid.is_valid())

        duplicate = UserSerializer(target, data={'display_id': '123456789'}, partial=True)
        self.assertFalse(duplicate.is_valid())

    def test_only_admin_can_update_display_id_endpoint(self):
        client = APIClient()
        admin = User.objects.create_superuser(username='black_gold_admin', password='test-pass')
        target = User.objects.create_user(username='black_gold_managed')
        client.force_authenticate(user=admin)

        response = client.patch(
            f'/api/account/users/{target.id}/display-id/',
            {'display_id': '7654321'},
            format='json',
        ).json()

        self.assertEqual(response['code'], 200)
        target.refresh_from_db()
        self.assertEqual(target.display_id, '7654321')
