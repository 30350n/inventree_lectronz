import json
from json import JSONDecodeError

from django.conf.urls import url
from django.http import HttpResponse, HttpResponseServerError

from part.models import Part
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

    LECTRONZ_PRODUCT_TAG = "lectronz_product"

    def update_product_link(self, request):
        try:
            data = json.loads(request.body)
        except JSONDecodeError:
            return HttpResponseServerError("failed to decode JSON")

        try:
            part_pk = data.get("part_pk")
            part = Part.objects.get(pk=part_pk)
        except Part.DoesNotExist:
            return HttpResponseServerError(f"part (pk={part_pk}) does not exist")

        if data.get("unlink"):
            part.tags.remove(self.LECTRONZ_PRODUCT_TAG)
            part.metadata.pop(self.LECTRONZ_PRODUCT_TAG, None)
            part.save()
            return HttpResponse("OK")

        if not ("product" in data and "product_options" in data):
            return HttpResponseServerError("invalid data (missing product or product_options)")

        try:
            part.metadata[self.LECTRONZ_PRODUCT_TAG] = {
                "id": int(data["product_id"]),
                "options": {int(k): int(v) for k, v in data["product_options"].items()},
            }
            part.tags.add(self.LECTRONZ_PRODUCT_TAG)
            part.save()
        except ValueError:
            return HttpResponseServerError("invalid data (non integer id)")
        except (TypeError, NameError):
            return HttpResponseServerError("invalid data (wrong type)")

        return HttpResponse("OK")

