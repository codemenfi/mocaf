from django.db import models
from wagtail.admin.edit_handlers import FieldPanel
from wagtail.core.fields import RichTextField
from wagtail.core.models import Page


class BlogPost(Page):
    tagline = models.CharField(max_length=255)
    body = RichTextField()
    device_groups = models.ManyToManyField('trips.DeviceGroup', blank=True)

    content_panels = Page.content_panels + [
        FieldPanel('tagline'),
        FieldPanel('body'),
    ]

    subpage_types = []
    parent_page_types = ['pages.BlogPostIndex']


class InfoPage(Page):
    body = RichTextField()
    device_groups = models.ManyToManyField('trips.DeviceGroup', blank=True)

    content_panels = Page.content_panels + [
        FieldPanel('body'),
    ]

    subpage_types = []
    parent_page_types = ['pages.InfoPageIndex']


class VisualisationGuidePage(Page):
    body = RichTextField()

    content_panels = Page.content_panels + [
        FieldPanel('body'),
    ]

    subpage_types = []
    parent_page_types = ['pages.VisualisationGuidePageIndex']


class VisualisationGuidePageIndex(Page):
    max_count = 1
    subpage_types = [VisualisationGuidePage]


class BlogPostIndex(Page):
    max_count = 1
    subpage_types = [BlogPost]


class InfoPageIndex(Page):
    max_count = 1
    subpage_types = [InfoPage]
