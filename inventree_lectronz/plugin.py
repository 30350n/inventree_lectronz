import json
from json import JSONDecodeError

from django.conf.urls import url
from django.http import HttpResponse, HttpResponseServerError

from part.views import PartDetail

from plugin import InvenTreePlugin
from plugin.mixins import PanelMixin, ScheduleMixin, EventMixin, SettingsMixin, UrlsMixin

from .lectronz_v1 import LectronzAPIMixin

class LectronzPlugin(
    LectronzAPIMixin, PanelMixin, SettingsMixin, ScheduleMixin, UrlsMixin, InvenTreePlugin
):
    """Plugin to integrate the Lectronz Marketplace into InvenTree"""

    NAME = "LectronzPlugin"
    SLUG = "lectronzplugin"
    TITLE = "Marketplace Integration - Lectronz"
    DESCRIPTION = ("Lectronz integration for InvenTree")
    VERSION = "0.1"
    AUTHOR = "Bobbe"
    LICENSE = "MIT"

    SETTINGS = {
        "API_TOKEN": {
            "name": "Lectronz API Token",
            "protected": True,
            "required": True,
        },
    }
    API_TOKEN_SETTING = "API_TOKEN"

    def get_custom_panels(self, view, request):
        panels = []

        if isinstance(view, PartDetail) and view.get_object().salable:
            self.products = self.get_products()
            panels.append({
                "title": "Lectronz Product",
                "icon": "fa-store",
                "content_template": "lectronz_product.html",
            })

        return panels

    def setup_urls(self):
        UPDATE_PRODUCT_LINK_URL = r"update_product_link(?:\.(?P<format>json))?$"
        return [
            url(UPDATE_PRODUCT_LINK_URL, self.update_product_link, name="update_product_link"),
        ]

    def update_product_link(self, request):
        try:
            data = json.loads(request.body)
        except JSONDecodeError:
            return HttpResponseServerError("failed to decode JSON")

        return HttpResponse("OK")

