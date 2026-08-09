from urllib.parse import urlencode

from django.db.models import Q
from django.views.generic import DetailView, ListView, TemplateView

from apps.transients.models import Transient

# THE LIST TABLE'S COLUMNS, IN ORDER: (MODEL FIELD, HEADING).
COLUMNS = (
    ("name", "Name"),
    ("origin", "Origin"),
    ("ra", "RA"),
    ("decl", "Dec"),
    ("created_at", "Added"),
)
# COLUMNS THE TABLE MAY BE SORTED ON. ANYTHING ELSE IN ?sort= IS IGNORED — THE
# VALUE GOES STRAIGHT INTO order_by(), SO IT MUST NEVER BE USER-CHOSEN.
SORTABLE_FIELDS = tuple(field for field, label in COLUMNS)
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


class TransientListView(ListView):
    """*all transients in a searchable, sortable, paginated table*

    Renders the table partial on its own for HTMX requests so typing in the
    search box swaps just the table, while a plain browser GET (no JavaScript)
    still returns the whole page.
    """

    model = Transient
    template_name = "transients/transient_list.html"
    context_object_name = "transients"
    paginate_by = PAGE_SIZE

    def get_sort(self):
        """*the validated sort column and direction for this request*

        **Return:**

        - ``sortField`` -- one of ``SORTABLE_FIELDS``
        - ``sortDir`` -- "asc" or "desc"

        **Usage:**

        ```python
        sortField, sortDir = self.get_sort()
        ```
        """
        sortField = self.request.GET.get("sort", DEFAULT_SORT)
        if sortField not in SORTABLE_FIELDS:
            sortField = DEFAULT_SORT
        sortDir = "desc" if self.request.GET.get("dir") == "desc" else "asc"
        return sortField, sortDir

    def get_queryset(self):
        queryset = super().get_queryset()

        searchTerm = self.request.GET.get("q", "").strip()
        if searchTerm:
            queryset = queryset.filter(Q(name__icontains=searchTerm) | Q(origin__icontains=searchTerm))

        sortField, sortDir = self.get_sort()
        orderBy = f"-{sortField}" if sortDir == "desc" else sortField
        # A SECOND, UNIQUE KEY KEEPS PAGINATION STABLE WHEN THE SORT COLUMN TIES
        # (EVERY ROW SHARES AN origin, FOR INSTANCE).
        return queryset.order_by(orderBy, "uuid")

    def get_template_names(self):
        # HTMX SWAPS THE TABLE ALONE; A NORMAL REQUEST GETS THE FULL PAGE.
        if self.request.headers.get("HX-Request"):
            return ["transients/_transient_table.html"]
        return [self.template_name]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        sortField, sortDir = self.get_sort()
        context["page_title"] = "Transients"
        context["search_term"] = self.request.GET.get("q", "").strip()
        context["sort_field"] = sortField
        context["sort_dir"] = sortDir

        # COLUMN HEADERS ARE LINKS. THEIR HREFS ARE BUILT HERE RATHER THAN IN
        # THE TEMPLATE BECAUSE EACH HAS TO CARRY THE CURRENT SEARCH TERM AND
        # FLIP THE DIRECTION OF WHICHEVER COLUMN IS ALREADY SORTED.
        columns = []
        for field, label in COLUMNS:
            nextDir = "desc" if (field == sortField and sortDir == "asc") else "asc"
            columns.append(
                {
                    "field": field,
                    "label": label,
                    "is_sorted": field == sortField,
                    "dir": sortDir if field == sortField else "",
                    "url": "?" + urlencode({"q": context["search_term"], "sort": field, "dir": nextDir}),
                }
            )
        context["columns"] = columns

        # EVERYTHING EXCEPT ?page=, FOR THE PAGINATION LINKS TO APPEND TO.
        context["querystring"] = urlencode(
            {"q": context["search_term"], "sort": sortField, "dir": sortDir}
        )
        return context
