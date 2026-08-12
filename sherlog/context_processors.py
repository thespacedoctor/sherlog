"""*local template context processors*"""

from django.conf import settings
from django_fundamentals.adapters import DEV_CONFIRMATION_URL_SESSION_KEY

from .adapters import SHOW_DEV_LINK_SETTING


def dev_confirmation_link(request):
    """*surface the stashed email-confirmation link when SHERLOG_SHOW_DEV_CONFIRMATION_LINK is on*

    django_fundamentals' own ``design`` context processor only does this under
    ``DEBUG``. This mirrors it under the separate ``SHERLOG_SHOW_DEV_CONFIRMATION_LINK``
    setting instead, so production can show the link without ``DEBUG`` being on. See
    ``adapters.AccountAdapter``, which does the corresponding stash.

    **Key Arguments:**

    - ``request`` -- the current request

    **Return:**

    - ``context`` -- dict with ``df_dev_confirmation_url`` when the setting is on, else empty
    """
    if not getattr(settings, SHOW_DEV_LINK_SETTING, False) or not hasattr(request, "session"):
        return {}

    return {"df_dev_confirmation_url": request.session.get(DEV_CONFIRMATION_URL_SESSION_KEY)}
