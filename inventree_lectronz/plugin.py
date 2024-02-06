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
        LINK_PRODUCT_URL = r"link_product(?:\.(?P<format>json))?$"
        return [url(LINK_PRODUCT_URL, self.link_product, name="link_product")]

    def link_product(self, request):
        try:
            data = json.loads(request.body)
        except JSONDecodeError:
            return HttpResponseServerError("failed to decode JSON")

        return HttpResponse("OK")

