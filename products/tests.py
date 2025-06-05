from types import SimpleNamespace

from django.test import TestCase
from rest_framework.test import APIRequestFactory

from .views import IsAdminOrReadOnly, IsReviewOwnerOrReadOnly


class PermissionTests(TestCase):
    """Protect catalog and review ownership rules."""

    def setUp(self):
        self.factory = APIRequestFactory()

    def test_catalog_allows_public_reads(self):
        request = self.factory.get('/api/products/')
        request.user = SimpleNamespace(is_authenticated=False, is_staff=False)

        self.assertTrue(IsAdminOrReadOnly().has_permission(request, None))

    def test_catalog_restricts_writes_to_staff(self):
        request = self.factory.post('/api/products/')
        request.user = SimpleNamespace(is_authenticated=True, is_staff=False)

        self.assertFalse(IsAdminOrReadOnly().has_permission(request, None))

    def test_review_changes_are_owner_only(self):
        owner = object()
        other_user = object()
        review = SimpleNamespace(user=owner)
        permission = IsReviewOwnerOrReadOnly()

        request = self.factory.patch('/api/reviews/review-id/')
        request.user = other_user
        self.assertFalse(permission.has_object_permission(request, None, review))

        request.user = owner
        self.assertTrue(permission.has_object_permission(request, None, review))
