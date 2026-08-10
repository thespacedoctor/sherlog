"""*shared list behaviour: search, whitelisted sorting, HTMX partial swap*

Used by the transient list and by every vetting run tab, so the sort whitelist,
the querystring plumbing and the HTMX rule live in one place.
"""

from urllib.parse import urlencode

from django.db.models import Q


class SortableSearchableListMixin:
    """*add ``?q=``, ``?sort=``, ``?dir=`` and an HTMX partial to a ``ListView``*

    A subclass declares:

    - ``columns`` -- tuple of (order_by field, heading) in display order
    - ``search_fields`` -- tuple of fields the ``?q=`` term matches on
    - ``default_sort`` -- the column used when none is given
    - ``tie_break_field`` -- a unique field keeping pagination stable
    - ``partial_template_name`` -- rendered alone for HTMX requests

    **Usage:**

    ```python
    class TransientListView(SortableSearchableListMixin, ListView):
        columns = (("name", "Name"), ("ra", "RA"))
        search_fields = ("name", "origin")
    ```
    """

    columns = ()
    search_fields = ()
    default_sort = None
    tie_break_field = "pk"
    partial_template_name = None

    def get_sortable_fields(self):
        """*the fields ``?sort=`` is allowed to name*

        **Return:**

        - ``fields`` -- tuple of orderable field names

        **Usage:**

        ```python
        fields = self.get_sortable_fields()
        ```
        """
        return tuple(field for field, label in self.columns)

    def get_sort(self):
        """*the validated sort column and direction for this request*

        **Return:**

        - ``sortField`` -- a field from ``columns``
        - ``sortDir`` -- "asc" or "desc"

        **Usage:**

        ```python
        sortField, sortDir = self.get_sort()
        ```
        """
        sortableFields = self.get_sortable_fields()
        defaultSort = self.default_sort or (sortableFields[0] if sortableFields else "pk")

        sortField = self.request.GET.get("sort", defaultSort)
        # THE VALUE GOES STRAIGHT INTO order_by(), SO IT MUST NEVER BE
        # USER-CHOSEN — ANYTHING OFF THE WHITELIST FALLS BACK.
        if sortField not in sortableFields:
            sortField = defaultSort
        sortDir = "desc" if self.request.GET.get("dir") == "desc" else "asc"
        return sortField, sortDir

    def get_search_term(self):
        """*the trimmed ``?q=`` term, or an empty string*"""
        return self.request.GET.get("q", "").strip()

    def get_base_queryset(self):
        """*the rows to search and sort, before ``?q=`` and ``?sort=`` apply*

        Override this rather than ``get_queryset`` — that one belongs to the
        mixin, and replacing it would drop the searching and sorting.

        **Return:**

        - ``queryset`` -- the unfiltered, unsorted queryset

        **Usage:**

        ```python
        def get_base_queryset(self):
            return Transient.objects.filter(origin="lasair")
        ```
        """
        return super().get_queryset()

    def get_queryset(self):
        queryset = self.get_base_queryset()

        searchTerm = self.get_search_term()
        if searchTerm and self.search_fields:
            matches = Q()
            for field in self.search_fields:
                matches |= Q(**{f"{field}__icontains": searchTerm})
            queryset = queryset.filter(matches)

        sortField, sortDir = self.get_sort()
        orderBy = f"-{sortField}" if sortDir == "desc" else sortField
        # A SECOND, UNIQUE KEY KEEPS PAGINATION STABLE WHEN THE SORT COLUMN TIES
        # (EVERY ROW SHARING AN origin, FOR INSTANCE).
        return queryset.order_by(orderBy, self.tie_break_field)

    def get_template_names(self):
        # HTMX SWAPS THE TABLE ALONE; A NORMAL REQUEST GETS THE FULL PAGE.
        if self.partial_template_name and self.request.headers.get("HX-Request"):
            return [self.partial_template_name]
        return super().get_template_names()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        sortField, sortDir = self.get_sort()
        searchTerm = self.get_search_term()

        context["search_term"] = searchTerm
        context["sort_field"] = sortField
        context["sort_dir"] = sortDir

        # COLUMN HEADERS ARE LINKS. THEIR HREFS ARE BUILT HERE RATHER THAN IN
        # THE TEMPLATE BECAUSE EACH HAS TO CARRY THE CURRENT SEARCH TERM AND
        # FLIP THE DIRECTION OF WHICHEVER COLUMN IS ALREADY SORTED.
        columns = []
        for field, label in self.columns:
            nextDir = "desc" if (field == sortField and sortDir == "asc") else "asc"
            columns.append(
                {
                    "field": field,
                    "label": label,
                    "is_sorted": field == sortField,
                    "dir": sortDir if field == sortField else "",
                    "url": "?" + urlencode({"q": searchTerm, "sort": field, "dir": nextDir}),
                }
            )
        context["columns"] = columns

        # EVERYTHING EXCEPT ?page=, FOR THE PAGINATION LINKS TO APPEND TO.
        context["querystring"] = urlencode({"q": searchTerm, "sort": sortField, "dir": sortDir})
        return context
