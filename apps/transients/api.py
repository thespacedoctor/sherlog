from rest_framework import filters, generics
from rest_framework.pagination import PageNumberPagination

from apps.transients.models import Transient
from apps.transients.serializers import TransientSerializer

# 50 ITEMS A PAGE, MATCHING THE UI TABLE. SET ON THE VIEW RATHER THAN IN
# settings.REST_FRAMEWORK BECAUSE A GLOBAL DEFAULT_PAGINATION_CLASS WOULD ALSO
# RESHAPE EVERY dj-rest-auth RESPONSE django-fundamentals SERVES.
PAGE_SIZE = 50


class TransientPagination(PageNumberPagination):
    """*page-number pagination, 50 transients a page*"""

    page_size = PAGE_SIZE
    page_size_query_param = "page_size"
    max_page_size = 500


class TransientCreateAPIView(generics.CreateAPIView):
    """*POST /api/transient/ — create a single transient*"""

    queryset = Transient.objects.all()
    serializer_class = TransientSerializer


class TransientDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    """*GET/PUT/PATCH/DELETE /api/transient/<uuid>/ — one transient*"""

    queryset = Transient.objects.all()
    serializer_class = TransientSerializer
    lookup_field = "uuid"


class TransientListAPIView(generics.ListAPIView):
    """*GET /api/transients/ — searchable, sortable, paginated list*"""

    queryset = Transient.objects.all()
    serializer_class = TransientSerializer
    pagination_class = TransientPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "origin"]
    ordering_fields = ["name", "origin", "ra", "decl", "created_at"]
    ordering = ["name"]
