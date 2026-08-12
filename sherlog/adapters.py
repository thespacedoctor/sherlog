"""*local override of django_fundamentals' allauth adapter*"""

from django.conf import settings
from django_fundamentals.adapters import DEV_CONFIRMATION_URL_SESSION_KEY
from django_fundamentals.adapters import AccountAdapter as BaseAccountAdapter

# WHEN TRUE, STASHES THE CONFIRMATION URL IN THE SESSION REGARDLESS OF DEBUG. SEE settings.py —
# THIS EXISTS SO PRODUCTION CAN RUN WITH DEBUG = False (NO STACK TRACES LEAKED) WHILE STILL
# SHOWING THE LINK ON verification_sent.html DURING THE SMTP-LESS INTERIM.
SHOW_DEV_LINK_SETTING = "SHERLOG_SHOW_DEV_CONFIRMATION_LINK"


class AccountAdapter(BaseAccountAdapter):
    """*django_fundamentals' dev-confirmation-link convenience, gated on a project setting instead of DEBUG*"""

    def get_email_confirmation_url(self, request, emailconfirmation):
        """*build the confirmation URL, additionally stashing it in the session when SHERLOG_SHOW_DEV_CONFIRMATION_LINK is on*

        **Key Arguments:**

        - ``request`` -- the current request
        - ``emailconfirmation`` -- the allauth ``EmailConfirmation`` instance

        **Return:**

        - ``confirmationUrl`` -- the absolute confirmation URL
        """
        # BaseAccountAdapter ALREADY STASHES UNDER DEBUG, SO THIS IS PURELY ADDITIVE.
        confirmationUrl = super().get_email_confirmation_url(request, emailconfirmation)

        if (
            getattr(settings, SHOW_DEV_LINK_SETTING, False)
            and request is not None
            and hasattr(request, "session")
        ):
            request.session[DEV_CONFIRMATION_URL_SESSION_KEY] = confirmationUrl

        return confirmationUrl
