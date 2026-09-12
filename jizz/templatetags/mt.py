from django import template
from django.urls import reverse
from django.utils.safestring import mark_safe

from jizz.marketing.i18n import localize_path, translate
from jizz.marketing.local_names import country_display_name, species_display_name

register = template.Library()


@register.simple_tag
def mt(message, **kwargs):
    return translate(message, **kwargs)


@register.filter(name='mpath')
def mpath(path):
    return localize_path(str(path or ''))


@register.simple_tag
def murl(name, **kwargs):
    return localize_path(reverse(name, kwargs=kwargs))


@register.filter
def local_country(country):
    return country_display_name(country)


@register.filter
def local_species(species):
    return species_display_name(species)


@register.filter
def mtjs(message):
    """JSON-string fragment for use inside a JS string literal."""
    return mark_safe(translate(message).replace('\\', '\\\\').replace("'", "\\'").replace('\n', '\\n'))
