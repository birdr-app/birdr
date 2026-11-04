"""About and Privacy: fixed, translated pages at their old CMS addresses."""

from __future__ import annotations

from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET

from jizz.marketing.i18n import locale_from_request, localize_path, translate
from jizz.marketing.pages import SITE_HOME, base_context, cms_path

STATIC_PAGES = {
    'about': {
        'template': 'marketing/about.html',
        'heading': 'About Motmot',
        'title': 'About Motmot – Bird Identification Training | Motmot',
        'description': (
            'Motmot is a free app to learn bird identification with photo, video and sound '
            'quizzes. Why it was built, where its data and media come from, and how to get in touch.'
        ),
    },
    'privacy': {
        'template': 'marketing/privacy.html',
        'heading': 'Privacy Policy',
        'title': 'Privacy Policy | Motmot',
        'description': (
            'How Motmot collects, uses and protects your personal information, and how to '
            'request its deletion.'
        ),
    },
}

# These pages used to be edited in the browser; their URLs are in app stores and OAuth
# settings, so they stay under /site/page/.
STATIC_PAGE_PATHS = [cms_path(slug) for slug in STATIC_PAGES]


@require_GET
def static_page(request, slug: str):
    page = STATIC_PAGES.get(slug)
    if page is None:
        raise Http404()
    path = cms_path(slug)
    context = base_context(
        request,
        title=translate(page['title']),
        description=translate(page['description']),
        path=path,
        breadcrumbs=[('Home', SITE_HOME), (page['heading'], path)],
    )
    return render(request, page['template'], context)


@require_GET
def pages_index_redirect(request):
    """The old list of editable pages; the home page links to both remaining ones."""
    return redirect(localize_path(SITE_HOME, locale_from_request(request)), permanent=True)
