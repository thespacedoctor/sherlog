from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    # django_fundamentals.urls INCLUDES A DEFAULT HOMEPAGE AT "/". OVERRIDE IT BY EITHER
    # ADDING templates/django_fundamentals/home.html, OR BY DEFINING YOUR OWN
    # path("", ...) ABOVE THIS LINE (THE RESOLVER MATCHES THE FIRST PATTERN).
    path("", include("django_fundamentals.urls")),
    # ADD YOUR OWN APPS' URLS BELOW. THE API IS KEPT ON ITS OWN /api/ PREFIX,
    # SEPARATE FROM THE SERVER-RENDERED FRONTEND.
    path("", include("apps.transients.urls")),
    path("", include("apps.vetting.urls")),
    path("api/", include("apps.transients.api_urls")),
]
