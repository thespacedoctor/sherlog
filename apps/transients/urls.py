"""*server-rendered UI routes for the transient resource*"""

from django.urls import path

from apps.transients.views import TransientDetailView, TransientIndexView, TransientListView

urlpatterns = [
    path("transient/", TransientIndexView.as_view(), name="transient_index"),
    path("transient/<uuid:uuid>/", TransientDetailView.as_view(), name="transient_detail"),
    path("transients/", TransientListView.as_view(), name="transient_list"),
]
