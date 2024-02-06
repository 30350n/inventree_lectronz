import inspect, json, logging
from json import JSONDecodeError

from django.http import HttpResponse, HttpResponseServerError
from django.urls import re_path

from company.models import Company
from part.models import Part
from part.views import PartDetail

from plugin import InvenTreePlugin
from plugin.mixins import PanelMixin, ScheduleMixin, EventMixin, SettingsMixin, UrlsMixin

from .lectronz_v1 import LectronzAPIMixin

logger = logging.getLogger("lectronzplugin")

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
        "LECTRONZ_COMPANY_ID": {
            "name": "Lectronz Company",
            "description": "The Company which acts as a Customer for all Lectronz Orders",
            "model": "company.company",
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
        return [
            re_path(
                r"update_product_link(?:\.(?P<format>json))?$",
                self.update_product_link,
                name="update_product_link"
            ),
        ]

    LECTRONZ_PRODUCT_TAG = "lectronz_product"

    def update_product_link(self, request):
        try:
            data: dict = json.loads(request.body)
        except JSONDecodeError:
            return self.http_error("failed to decode JSON")

        try:
            part_pk = data.get("part_pk")
            part = Part.objects.get(pk=part_pk)
        except Part.DoesNotExist:
            return self.http_error(f"Part (pk={part_pk}) does not exist")

        if data.get("unlink"):
            part.tags.remove(self.LECTRONZ_PRODUCT_TAG)
            part.metadata.pop(self.LECTRONZ_PRODUCT_TAG, None)
            part.save()
            return HttpResponse("OK")

        if not ("product_id" in data and "product_options" in data):
            return self.http_error("Invalid data (missing product_id or product_options)")

        part.metadata[self.LECTRONZ_PRODUCT_TAG] = {
            "id": data["product_id"],
            "options": data["product_options"],
        }
        part.tags.add(self.LECTRONZ_PRODUCT_TAG)
        part.save()

        return HttpResponse("OK")

    def get_lectronz_company(self):
        if customer_pk := self.get_setting("LECTRONZ_COMPANY_ID"):
            try:
                return Company.objects.get(pk=customer_pk)
            except Company.DoesNotExist:
                return None

        lectronz_customers = Company.objects.filter(name__icontains="lectronz")
        if len(lectronz_customers) != 1:
            return None

        self.set_setting("LECTRONZ_COMPANY_ID", lectronz_customers.first().pk)
        return lectronz_customers.first()

    def http_error(self, error_msg):
        logger.error(f"{inspect.stack()[1].function} error: {error_msg}")
        return HttpResponseServerError(error_msg)
