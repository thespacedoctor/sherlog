"""*API routes for the transient resource, mounted under /api/*"""

from django.urls import path

from apps.transients.api import (
    TransientCreateAPIView,
    TransientDetailAPIView,
    TransientListAPIView,
)

urlpatterns = [
    # SINGULAR RESOURCE: THE FIVE FUNDAMENTAL METHODS, SPLIT OVER THE
    # COLLECTION-LEVEL POST AND THE ITEM-LEVEL GET/PUT/PATCH/DELETE.
    path("transient/", TransientCreateAPIView.as_view(), name="api_transient_create"),
    path("transient/<uuid:uuid>/", TransientDetailAPIView.as_view(), name="api_transient_detail"),
    # PLURAL RESOURCE: LIST ONLY.
    path("transients/", TransientListAPIView.as_view(), name="api_transient_list"),
]
