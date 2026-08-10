from django.views.generic import DetailView, ListView, TemplateView

from apps.transients.mixins import SortableSearchableListMixin
from apps.transients.models import Transient

# THE LIST TABLE'S COLUMNS, IN ORDER: (MODEL FIELD, HEADING).
COLUMNS = (
    ("name", "Name"),
    ("origin", "Origin"),
    ("sherlock_classification", "Classification"),
    ("ra", "RA"),
    ("decl", "Dec"),
    ("created_at", "Added"),
)
DEFAULT_SORT = "name"
PAGE_SIZE = 50


class TransientIndexView(TemplateView):
    """*the singular resource page: what a transient is and where to find one*"""

    template_name = "transients/transient_index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Transient"
        context["page_subtitle"] = "UI and API endpoints for the transient resource."
        # ROUTES ARE LISTED AS DATA SO THE TEMPLATE STAYS A SIMPLE LOOP, THE SAME
        # SHAPE django-fundamentals' OWN HOMEPAGE TABLE USES.
        context["endpoints"] = [
            {
                "path": "/transients/",
                "methods": "GET",
                "kind": "UI",
                "description": "All transients, searchable and sortable.",
            },
            {
                "path": "/transient/",
                "methods": "GET",
                "kind": "UI",
                "description": "This page.",
            },
            {
                "path": "/transient/<uuid>/",
                "methods": "GET",
                "kind": "UI",
                "description": "A single transient and its attributes.",
            },
            {
                "path": "/api/transients/",
                "methods": "GET",
                "kind": "API",
                "description": "List transients — ?search=, ?ordering=, ?page=, 50 per page.",
            },
            {
                "path": "/api/transient/",
                "methods": "POST",
                "kind": "API",
                "description": "Create a transient.",
            },
            {
                "path": "/api/transient/<uuid>/",
                "methods": "GET, PUT, PATCH, DELETE",
                "kind": "API",
                "description": "Read, replace, update or delete a transient.",
            },
        ]
        return context


class TransientDetailView(DetailView):
    """*one transient and its attributes*"""

    model = Transient
    template_name = "transients/transient_detail.html"
    context_object_name = "transient"
    # uuid IS THE PRIMARY KEY, SO THE URL KWARG IS THE pk LOOKUP.
    pk_url_kwarg = "uuid"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = self.object.name
        context["page_subtitle"] = f"Transient from {self.object.origin}."
        return context


class TransientListView(SortableSearchableListMixin, ListView):
    """*all transients in a searchable, sortable, paginated table*

    Renders the table partial on its own for HTMX requests so typing in the
    search box swaps just the table, while a plain browser GET (no JavaScript)
    still returns the whole page.
    """

    model = Transient
    template_name = "transients/transient_list.html"
    partial_template_name = "transients/_transient_table.html"
    context_object_name = "transients"
    paginate_by = PAGE_SIZE

    columns = COLUMNS
    search_fields = ("name", "origin", "sherlock_classification")
    default_sort = DEFAULT_SORT
    tie_break_field = "uuid"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Transients"
        return context
