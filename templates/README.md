# templates/

Project-level template overrides go here. To override a `django_fundamentals`
template, create a file at the same relative path — this directory is listed
first in `TEMPLATES[0]["DIRS"]`, so it takes precedence.

```
templates/django_fundamentals/layouts/app.html          # the app shell
templates/django_fundamentals/organisms/footer.html     # the footer
templates/django_fundamentals/atoms/button.html         # all buttons
templates/django_fundamentals/home.html                 # the default homepage
```

For colours and dimensions you do **not** need an override — edit
`static/src/tokens.css` instead.

Note that Tailwind scans this directory, so any classes you use here are
included in the build automatically.
