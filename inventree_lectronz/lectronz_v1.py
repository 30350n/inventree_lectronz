from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from dateutil.parser import isoparse

from plugin.mixins import APICallMixin

class LectronzAPIMixin(APICallMixin):
    API_URL_SETTING = "NONE"

    _BATCH_SIZE = 25

    @property
    def api_url(self):
        return f"{self.API_METHOD}://lectronz.com/api/v1/"

    def get_orders(self, offset=0, limit=None, retries=5):
        if limit is not None:
            return self._get_orders(offset, limit, retries=retries)

        orders = []
        while True:
            more_orders = self._get_orders(offset, self._BATCH_SIZE, retries=retries)
            if more_orders is None:
                return None
            orders += more_orders
            offset += len(more_orders)
            if len(more_orders) < self._BATCH_SIZE:
                return orders

    def _get_orders(self, offset, limit, retries=5):
        url_args = {"offset": [offset], "limit": [limit]}
        for _ in range(retries + 1):
            if response := self.api_call("orders", url_args=url_args):
                if "errors" in response:
                    return None
                return [Order(**order) for order in response.get("orders", [])]
        return None

    def get_order(self, order_id, retries=5):
        for _ in range(retries + 1):
            if response := self.api_call(f"orders/{order_id}"):
                if "errors" in response:
                    return None
                return Order(**response)

    def get_products(self, offset=0, limit=None, retries=5):
        if limit is not None:
            return self._get_products(offset, limit, retries=retries)

        products = []
        while True:
            more_products = self._get_products(offset, self._BATCH_SIZE, retries=retries)
            if more_products is None:
                return None
            products += more_products
            offset += len(more_products)
            if len(more_products) < self._BATCH_SIZE:
                return products

    def _get_products(self, offset, limit, retries=5):
        url_args = {"offset": [offset], "limit": [limit]}
        for _ in range(retries + 1):
            if response := self.api_call("products", url_args=url_args):
                if "errors" in response:
                    return None
                return [Product(**product) for product in response.get("products", [])]
        return None

    def fulfill_order(self, order_id, tracking_code, tracking_url, retries=5):
        endpoint = f"orders/{order_id}"
        url_args = {
            "status": "fulfilled", "tracking_code": tracking_code, "tracking_url": tracking_url
        }
        for _ in range(retries + 1):
            if response := self.api_call(endpoint, method="PATCH", url_args=url_args):
                return response
        return None

def optional():
    return field(default=None, kw_only=True)

class ProductStatus(str, Enum):
    DRAFT = "draft"
    UNDER_REVIEW = "under_review"
    REVIEWED = "reviewed"
    ACTIVE = "active"
    RETIRED = "retired"
    PRE_ORDER = "pre_order"

class Currency(str, Enum):
    EUR = "EUR"
    USD = "USD"

@dataclass
class ProductLinks:
    documentation: str | None = optional()
    code: str | None = optional()
    design_files: str | None = optional()
    schematics: str | None = optional()
    bom: str | None = optional()

@dataclass
class ProductOptionChoice:
    id: int
    name: str
    price: float
    stock_available: float | None = optional()
    sku: str | None = optional()
    weight: float
    display_order: float | None = optional()

@dataclass
class ProductOption:
    id: int
    name: str
    explanation: str
    display_order: float | None = optional()
    choices: list[ProductOptionChoice]

    def __post_init__(self):
        if isinstance(self.choices, list):
            self.choices = [
                ProductOptionChoice(**choice)
                for choice in self.choices
                if isinstance(choice, dict)
            ]

@dataclass
class Product:
    id: int
    store_id: int
    store_url: str
    title: str
    status: ProductStatus
    price: float
    currency: Currency
    slug: str
    stock_available: float
    total_sold: float
    sku: str | None = optional()
    short_description: str
    description: str
    links: ProductLinks
    images: list[str]
    thumbnail: str | None = optional()
    weight: float
    weight_unit: str
    hs_code: str | None = optional()
    oshwa_uid: str | None = optional()
    product_options: list[ProductOption]
    published_at: datetime
    created_at: datetime
    updated_at: datetime
    url: str

    def __post_init__(self):
        if isinstance(self.status, str):
            self.status = ProductStatus(self.status)
        if isinstance(self.currency, str):
            self.currency = Currency(self.currency)
        if isinstance(self.links, dict):
            self.links = ProductLinks(**self.links)
        if isinstance(self.product_options, list):
            self.product_options = [
                ProductOption(**option)
                for option in self.product_options if isinstance(option, dict)
            ]
        for member in ("published_at", "created_at", "updated_at"):
            if (date_value := getattr(self, member)) and isinstance(date_value, str):
                setattr(self, member, isoparse(date_value))

class OrderStatus(str, Enum):
    PAYMENT_SUCCESS = "payment_success"
    FULFILLED = "fulfilled"
    REFUNDED = "refunded"

class CustomerLegalStatus(str, Enum):
    UNSPECIFIED = "unspecified"
    INDIVIDUAL = "individual"
    BUSINESS = "business"

class WeightUnit(str, Enum):
    KG = "kg"
    GR = "gr"
    LB = "lb"
    OZ = "oz"

@dataclass
class Address:
    first_name: str
    last_name: str
    organization: str
    street: str
    street_extension: str
    city: str
    postal_code: str
    state: str
    country: str
    country_code: str

@dataclass
class ShippingWeight:
    base: float
    total: float
    weight_unit: WeightUnit

    def __post_init__(self):
        if isinstance(self.weight_unit, str):
            self.weight_unit = WeightUnit(self.weight_unit)

@dataclass
class ItemOption:
    name: str
    choice: str
    sku: str | None = optional()
    weight: float

@dataclass
class Item:
    product_id: int
    product_name: str
    product_description: str
    sku: str | None = optional()
    price: float
    discount: float | None = optional()
    quantity: int
    weight: float
    options: list[ItemOption]

    def __post_init__(self):
        if isinstance(self.options, list):
            self.options = [
                ItemOption(**option) for option in self.options if isinstance(option, dict)
            ]

@dataclass
class Payment:
    provider: str
    reference: str

@dataclass
class Order:
    id: int
    status: OrderStatus
    store_id: int
    store_url: str
    customer_email: str
    customer_phone: str
    shipping_address: Address
    billing_address: Address
    billing_address_same_as_shipping_address: bool
    customer_tax_id: str
    customer_legal_status: CustomerLegalStatus
    shipping_method: str
    shipping_is_tracked: bool
    shipping_weight: ShippingWeight
    ioss_number: str | None = optional()
    items: list[Item]
    currency: Currency
    shipping_cost: float
    tax_applies_to_shipping: bool
    subtotal: float
    taxable_amount: float
    total_tax: float
    tax_rate: float
    total: float
    fulfilled_at: datetime | None = optional()
    tracking_code: str
    tracking_url: str
    lectronz_fee: float
    tax_collected: float
    discount_codes: str | None = optional()
    payment_fees: float | None = optional()
    payout: float | None = optional()
    payment: Payment
    created_at: datetime
    updated_at: datetime
    fulfill_until: str
    customer_note: str | None = optional()

    def __post_init__(self):
        if isinstance(self.status, str):
            self.status = OrderStatus(self.status)
        if isinstance(self.shipping_address, dict):
            self.shipping_address = Address(**self.shipping_address)
        if isinstance(self.billing_address, dict):
            self.billing_address = Address(**self.billing_address)
        if isinstance(self.customer_legal_status, str):
            self.customer_legal_status = CustomerLegalStatus(self.customer_legal_status)
        if isinstance(self.shipping_weight, dict):
            self.shipping_weight = ShippingWeight(**self.shipping_weight)
        if isinstance(self.items, list):
            self.items = [Item(**item) for item in self.items if isinstance(item, dict)]
        if isinstance(self.currency, str):
            self.currency = Currency(self.currency)
        if isinstance(self.payment, dict):
            self.payment = Payment(**self.payment)
        for member in ("fulfilled_at", "created_at", "updated_at"):
            if (date_value := getattr(self, member)) and isinstance(date_value, str):
                setattr(self, member, isoparse(date_value))

    @property
    def was_shipped(self):
        return self.fulfilled_at is not None
