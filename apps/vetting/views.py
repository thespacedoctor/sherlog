from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, F, FilteredRelation, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import ListView

from apps.transients.mixins import SortableSearchableListMixin
from apps.transients.models import Transient
from apps.transients.views import COLUMNS, DEFAULT_SORT, PAGE_SIZE
from apps.vetting.forms import VettingForm
from apps.vetting.models import (
    OTHER_REASON,
    TABS,
    VERDICT_AMBIGUOUS,
    VERDICT_CORRECT,
    VERDICT_INCORRECT,
    WRONG_CLASSIFICATION,
    WRONG_RANK,
    SherlockVetting,
    VettingReason,
)

# EACH TAB'S EXTRA FILTER ON TOP OF "EVERY ROW FOR THIS VERSION".
TAB_FILTERS = {
    "all": Q(),
    "unvetted": Q(vetted_as__isnull=True),
    "correct": Q(vetted_as=VERDICT_CORRECT),
    "incorrect": Q(vetted_as=VERDICT_INCORRECT),
    "ambiguous": Q(vetted_as=VERDICT_AMBIGUOUS),
}


def run_queryset(version):
    """*transients in a vetting run, with their verdict annotated on*

    A ``FilteredRelation`` joins only this version's vetting row, so the result
    is one row per transient carrying ``vetted_as`` (True, False or None) and
    ``vetted_by`` (the vetting user's username, or None if that account was
    since deleted) — the table, its sorting and its searching stay the same
    code the plain transient list uses.

    **Key Arguments:**

    - ``version`` -- the Sherlock version being vetted

    **Return:**

    - ``queryset`` -- ``Transient`` queryset annotated with ``vetted_as`` and ``vetted_by``

    **Usage:**

    ```python
    queryset = run_queryset("v0.0.0").filter(vetted_as__isnull=True)
    ```
    """
    return (
        Transient.objects.annotate(
            vetting=FilteredRelation(
                "vettings", condition=Q(vettings__sherlock_version=version)
            )
        )
        .filter(vetting__isnull=False)
        .annotate(
            vetted_as=F("vetting__sherlock_correct"),
            vetted_by=F("vetting__user__username"),
        )
    )


def run_counts(version):
    """*the four tab counts for a version, in one query*

    **Key Arguments:**

    - ``version`` -- the Sherlock version being vetted

    **Return:**

    - ``counts`` -- dict keyed by tab name

    **Usage:**

    ```python
    counts = run_counts("v0.0.0")
    ```
    """
    return SherlockVetting.objects.filter(sherlock_version=version).aggregate(
        all=Count("pk"),
        unvetted=Count("pk", filter=Q(sherlock_correct__isnull=True)),
        correct=Count("pk", filter=Q(sherlock_correct=VERDICT_CORRECT)),
        incorrect=Count("pk", filter=Q(sherlock_correct=VERDICT_INCORRECT)),
        ambiguous=Count("pk", filter=Q(sherlock_correct=VERDICT_AMBIGUOUS)),
    )


def next_unvetted(version, exclude_uuid=None):
    """*a random transient still awaiting a verdict for this version*

    Random rather than sequential so two people vetting at once are unlikely to
    land on the same transient.

    **Key Arguments:**

    - ``version`` -- the Sherlock version being vetted
    - ``exclude_uuid`` -- a transient to skip, normally the one just vetted

    **Return:**

    - ``vetting`` -- a ``SherlockVetting`` row, or ``None`` if the run is done

    **Usage:**

    ```python
    vetting = next_unvetted("v0.0.0", exclude_uuid=transient.uuid)
    ```
    """
    queryset = SherlockVetting.objects.filter(
        sherlock_version=version, sherlock_correct__isnull=True
    )
    if exclude_uuid:
        queryset = queryset.exclude(transient_id=exclude_uuid)
    return queryset.order_by("?").first()


def get_run_or_404(version):
    """*the vetting rows for a version, 404ing if the run does not exist*"""
    run = SherlockVetting.objects.filter(sherlock_version=version)
    if not run.exists():
        raise Http404(f"no vetting run for Sherlock version {version}")
    return run


class VettingRunView(SortableSearchableListMixin, ListView):
    """*one Sherlock version's vetting run: four tabbed tables of transients*"""

    template_name = "vetting/run.html"
    partial_template_name = "transients/_transient_table.html"
    context_object_name = "transients"
    paginate_by = PAGE_SIZE

    columns = COLUMNS
    search_fields = ("name", "origin_name")
    default_sort = DEFAULT_SORT
    tie_break_field = "uuid"

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.version = kwargs["version"]
        self.tab = kwargs.get("tab", "all")

    def get_base_queryset(self):
        if self.tab not in TAB_FILTERS:
            raise Http404(f"no such tab: {self.tab}")
        get_run_or_404(self.version)
        return run_queryset(self.version).filter(TAB_FILTERS[self.tab])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        counts = run_counts(self.version)

        context["version"] = self.version
        context["vetting_version"] = self.version
        context["show_vetted_as"] = True
        context["current_tab"] = self.tab
        context["page_title"] = f"Vetting {self.version}"
        context["page_subtitle"] = "Has Sherlock classified these transients correctly?"
        context["tabs"] = [
            {
                "name": name,
                "label": label,
                "count": counts[name],
                "url": reverse(
                    "vetting_run" if name == "all" else "vetting_run_tab",
                    kwargs={"version": self.version}
                    if name == "all"
                    else {"version": self.version, "tab": name},
                ),
                "is_current": name == self.tab,
            }
            for name, label in TABS
        ]
        return context


class VetTransientView(LoginRequiredMixin, View):
    """*vet one transient for one Sherlock version, then move on to the next*"""

    template_name = "vetting/vet_transient.html"

    def get_vetting(self, version, uuid):
        get_run_or_404(version)
        vetting = get_object_or_404(
            SherlockVetting.objects.select_related("transient"),
            sherlock_version=version,
            transient_id=uuid,
        )
        # PINNED BEFORE THE FORM READS crossmatch_tree() FOR ITS RANK CHOICES.
        vetting.transient.crossmatch_version = version
        return vetting

    def render_form(self, request, vetting, form):
        counts = run_counts(vetting.sherlock_version)
        # THE PAGE IS A JUDGEMENT ON ONE VERSION'S WORK, SO THE TABLE AND THE SKY
        # VIEW SHOW THAT VERSION'S MATCHES AND NO OTHER.
        vetting.transient.crossmatch_version = vetting.sherlock_version
        return render(
            request,
            self.template_name,
            {
                "vetting": vetting,
                "transient": vetting.transient,
                "version": vetting.sherlock_version,
                "form": form,
                "remaining": counts["unvetted"],
                "page_title": vetting.transient.name,
                "page_subtitle": f"Vetting Sherlock {vetting.sherlock_version}.",
                # THE TEMPLATE COMPARES THE CHOSEN REASON AGAINST THESE TO
                # DECIDE WHICH FOLLOW-UP FIELD TO REVEAL.
                "wrong_rank": WRONG_RANK,
                "wrong_classification": WRONG_CLASSIFICATION,
                "other_reason": OTHER_REASON,
            },
        )

    def get(self, request, version, uuid):
        vetting = self.get_vetting(version, uuid)
        # A TRANSIENT ALREADY VETTED IS STILL EDITABLE — THE FORM OPENS ON THE
        # EXISTING VERDICT'S COMMENT AND HOST RANK.
        form = VettingForm(
            transient=vetting.transient,
            version=version,
            initial={
                "user_comment": vetting.user_comment,
                "sherlock_correct_host": vetting.sherlock_correct_host,
                "incorrect_reason": vetting.incorrect_reason,
                "corrected_classification": vetting.corrected_classification,
            },
        )
        return self.render_form(request, vetting, form)

    def post(self, request, version, uuid):
        vetting = self.get_vetting(version, uuid)
        form = VettingForm(request.POST, transient=vetting.transient, version=version)

        if not form.is_valid():
            return self.render_form(request, vetting, form)

        reason = form.cleaned_data["reason"]

        vetting.sherlock_correct = form.cleaned_data["sherlock_correct"]
        vetting.user_comment = form.cleaned_data["user_comment"]
        vetting.sherlock_correct_host = form.cleaned_data["sherlock_correct_host"]
        # ONLY "incorrect" CARRIES REJECTION DETAIL, AND RE-VETTING SOMETHING
        # FROM incorrect TO correct OR ambiguous MUST CLEAR WHAT WAS THERE.
        is_incorrect = vetting.sherlock_correct == VERDICT_INCORRECT
        vetting.incorrect_reason = reason if is_incorrect else ""
        vetting.corrected_classification = (
            form.cleaned_data["corrected_classification"] if is_incorrect else ""
        )
        vetting.user = request.user
        vetting.save()

        # A REASON TYPED IN JOINS THE DROPDOWN FOR EVERY OTHER TRANSIENT IN THIS
        # RUN, FOR EVERYONE.
        if reason and reason not in dict(VettingReason.choices_for(version)):
            VettingReason.objects.get_or_create(
                sherlock_version=version,
                reason=reason,
                defaults={"created_by": request.user},
            )

        nextVetting = next_unvetted(version, exclude_uuid=uuid)
        if nextVetting is None:
            messages.success(
                request,
                f"All transients have now been vetted for Sherlock {version}.",
            )
            return redirect("vetting_run", version=version)
        return redirect(nextVetting.get_absolute_url())
