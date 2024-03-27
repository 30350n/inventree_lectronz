import inspect, json, logging
from datetime import date, datetime
from json import JSONDecodeError

from dateutil.rrule import *
from django.core.validators import MaxValueValidator, MinValueValidator
from django.http import HttpResponse, HttpResponseServerError, JsonResponse
from django.urls import re_path

from company.models import Company
from order.models import SalesOrder, SalesOrderShipment
from order.views import SalesOrderDetail
from part.models import Part
from part.views import PartDetail

from plugin import InvenTreePlugin
from plugin.mixins import EventMixin, PanelMixin, ScheduleMixin, SettingsMixin, UrlsMixin

from .create_sales_order import LECTRONZ_ORDER_TAG, LECTRONZ_PRODUCT_TAG, create_sales_order
from .lectronz_v1 import LectronzAPIMixin
from .templatetags import VALID_CUSTOMER_REFERENCE

logger = logging.getLogger("lectronzplugin")

class LectronzPlugin(
    LectronzAPIMixin,
    PanelMixin,
    ScheduleMixin,
    EventMixin,
    UrlsMixin,
    SettingsMixin,
    InvenTreePlugin,
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
        "TARGET_ORDER_PROCESSING_TIME": {
            "name": "Target Order Processing Time",
            "description": "Number of days until an Order is overdue",
            "units": "days",
            "default": 3,
            "validator": [int, MinValueValidator(0), MaxValueValidator(14)],
        },
        "ORDER_PROCESSING_BUSINESS_DAYS_ONLY": {
            "name": "Order Processing on Business Days Only",
            "description": "Only use Business Days (Mon-Fri) when calculating Order Due Date",
            "default": True,
            "validator": bool,
        },
        "SYNC_SCHEDULE_MINUTES": {
            "name": "Sync Schedule",
            "description": "Synchronize Lectronz orders every <n> minutes",
            "units": "minutes",
            "default": 60,
            "validator": [int, MinValueValidator(5)],
        },
        "SYNC_FULFILLED": {
            "name": "Sync Fulfilled",
            "description": "Synchronize all orders, including fulfilled ones",
            "default": False,
            "validator": bool,
        },
    }
    API_TOKEN_SETTING = "API_TOKEN"

    products = {}

    def get_custom_panels(self, view, request):
        panels = []

        lectronz = self.get_lectronz_company()

        if isinstance(view, PartDetail) and view.get_object().salable:
            if not self.products:
                self.update_products()
            panels.append({
                "title": "Lectronz Product",
                "icon": "fa-store",
                "content_template": "lectronz_product.html",
            })
        elif isinstance(view, SalesOrderDetail) and view.get_object().customer == lectronz:
            panels.append({
                "title": "Lectronz Order",
                "icon": "fa-store",
                "content_template": "lectronz_order.html",
            })

        return panels

    def setup_urls(self):
        return [
            re_path(
                r"update_product_link(?:\.(?P<format>json))?$",
                self.update_product_link,
                name="update_product_link"
            ),
            re_path(
                r"update_order(?:\.(?P<format>json))?$", self.update_order, name="update_order"
            ),
        ]

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
            part.tags.remove(LECTRONZ_PRODUCT_TAG)
            part.metadata.pop(LECTRONZ_PRODUCT_TAG, None)
            part.save()
            return HttpResponse("OK")

        if not ("product_id" in data and "product_options" in data):
            return self.http_error("Invalid data (missing product_id or product_options)")

        part.metadata[LECTRONZ_PRODUCT_TAG] = {
            "id": data["product_id"],
            "options": data["product_options"],
        }
        part.tags.add(LECTRONZ_PRODUCT_TAG)
        part.save()

        return HttpResponse("OK")

    def update_order(self, request):
        try:
            data: dict = json.loads(request.body)
        except JSONDecodeError:
            return self.http_error("Failed to decode JSON")

        try:
            order_pk = data.get("order_pk")
            sales_order = SalesOrder.objects.get(pk=order_pk)
        except Part.DoesNotExist:
            return self.http_error(f"Order (pk={order_pk}) does not exist")

        customer_reference = sales_order.customer_reference
        if not (match := VALID_CUSTOMER_REFERENCE.fullmatch(customer_reference)):
            return self.http_error(f"Invalid customer reference '{customer_reference}'")

        order_id = match.group(1)
        if not (order := self.get_order(order_id, retries=0)):
            return self.http_error(f"Failed to get order #{order_id} from Lectronz")

        if not (lectronz := self.get_lectronz_company()) or not lectronz.is_customer:
            return self.http_error("Lectronz Company is not set or not a customer")

        if not self.products:
            self.update_products()

        target_date = self.get_order_target_date(order.created_at)
        create_sales_order(lectronz, order, self.products, target_date, sales_order)

        if sync_errors := sales_order.metadata[LECTRONZ_ORDER_TAG].get("sync_errors"):
            return JsonResponse({"sync_errors": sync_errors})

        return HttpResponse("OK")

    def get_scheduled_tasks(self):
        return {
            "sync_lectronz_orders": {
                "func": "sync_lectronz_orders",
                "schedule": "I",
                "minutes": self.get_setting("SYNC_SCHEDULE_MINUTES") or 60,
            },
        }

    order_offset = 0

    def sync_lectronz_orders(self):
        if not (lectronz := self.get_lectronz_company()) or not lectronz.is_customer:
            logger.error(
                "sync_lectronz_orders error: Lectronz Company is not set or not a customer"
            )
            return

        self.update_products()

        if not (orders := self.get_orders(offset=self.order_offset)):
            return

        sync_fulfilled = self.get_setting("SYNC_FULFILLED")
        for order in orders:
            self.order_offset += 1
            if order.was_shipped or sync_fulfilled:
                target_date = self.get_order_target_date(order.created_at)
                create_sales_order(lectronz, order, self.products, target_date)

    def wants_process_event(self, event):
        return event == "salesordershipment.completed"

    def process_event(self, event, *args, **kwargs):
        assert event == "salesordershipment.completed"

        shipment = SalesOrderShipment.objects.get(pk=kwargs.get("id"))
        sales_order = shipment.order

        if not (lectronz := self.get_lectronz_company()):
            return
        if shipment.order.customer != lectronz:
            return

        if not isinstance(order_metadata := sales_order.metadata.get(LECTRONZ_ORDER_TAG), dict):
            order_metadata = sales_order.metadata[LECTRONZ_ORDER_TAG] = {}

        if not (order_id := order_metadata.get("id")):
            order_id = sales_order.customer_reference[1:]

        response = self.fulfill_order(order_id, shipment.tracking_number, shipment.link)
        if response is None:
            order_metadata.get("sync_errors", []).append(
                f"Failed to fulfill order with id '{order_id}' (no response from Lectronz API)"
            )
        elif errors := response.get("errors"):
            error_detail = ", ".join(
                f"{error.get('status')}: {detail}" for error in errors
                if (detail := error.get("detail") or error.get("title"))
            )
            order_metadata.get("sync_errors", []).append(
                f"Failed to fulfill order with id '{order_id}' ({error_detail})"
            )
        else:
            order_metadata["fulfilled"] = str(date.today())

        sales_order.save()

    def get_order_target_date(self, created_at: datetime):
        BUSINESS_DAYS = (MO, TU, WE, TH, FR)
        processing_days = self.get_setting("TARGET_ORDER_PROCESSING_TIME")
        only_business_days = self.get_setting("ORDER_PROCESSING_BUSINESS_DAYS_ONLY")
        return rrule(
            DAILY, byweekday=BUSINESS_DAYS if only_business_days else None, dtstart=created_at
        )[processing_days]

    def update_products(self):
        if products := self.get_products():
            self.products = {product.id: product for product in products}

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
