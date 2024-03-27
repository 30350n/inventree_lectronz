from datetime import date, datetime

from django.db.models import Model, Q
from django.db.models.manager import BaseManager
from djmoney.money import Money

from company.models import Company
from order.models import (
    SalesOrder, SalesOrderExtraLine, SalesOrderLineItem, SalesOrderShipment, SalesOrderStatus
)
from part.models import Part

from .lectronz_v1 import Item as OrderItem, Order, OrderStatus, Product

LECTRONZ_PRODUCT_TAG = "lectronz_product"
LECTRONZ_ORDER_TAG = "lectronz_order"

def create_sales_order(
    lectronz: Company,
    order: Order,
    products: dict[int, Product],
    target_date: datetime,
    sales_order: SalesOrder = None,
):
    existing_sales_orders = SalesOrder.objects.filter(
        customer=lectronz, customer_reference__exact=f"#{order.id}"
    )
    if not sales_order and existing_sales_orders.exists():
        return

    sales_order_status = {
        OrderStatus.PAYMENT_SUCCESS: SalesOrderStatus.IN_PROGRESS,
        OrderStatus.FULFILLED: SalesOrderStatus.SHIPPED,
        OrderStatus.REFUNDED:
            SalesOrderStatus.RETURNED if order.was_shipped else SalesOrderStatus.CANCELLED,
    }[order.status]

    currency = order.currency.value

    sales_order_data = {
        "customer": lectronz,
        "status": sales_order_status.value,
        "customer_reference": f"#{order.id}",
        "shipment_date": order.fulfilled_at,
        "description":
            f"Customer Note: \"{order.customer_note}\"" if order.customer_note else "",
        "link": f"https://lectronz.com/seller/orders/{order.id}/edit",
        "target_date": target_date,
        "creation_date": order.created_at,
        "order_currency": None if currency == lectronz.currency else currency,
    }

    if sales_order:
        update_object_with_dict(sales_order, sales_order_data)
    else:
        sales_order = SalesOrder.objects.create(**sales_order_data)

    if not isinstance(order_metadata := sales_order.metadata.get(LECTRONZ_ORDER_TAG), dict):
        order_metadata = sales_order.metadata[LECTRONZ_ORDER_TAG] = {}
    order_metadata["synced"] = str(date.today())
    order_metadata["sync_errors"] = []
    order_metadata["id"] = order.id
    order_metadata["total"] = order.total

    create_extra_lines(sales_order, order)

    parts = Part.objects.filter(tags__name__in=[LECTRONZ_PRODUCT_TAG])
    line_items = SalesOrderLineItem.objects.filter(order=sales_order)
    for item in order.items:
        create_line_item(sales_order, parts, line_items, order, item, products)

    if order.was_shipped:
        create_shipment(sales_order, order)

    sales_order.save()
    return sales_order

def create_extra_lines(sales_order: SalesOrder, order: Order):
    extra_lines = SalesOrderExtraLine.objects.filter(order=sales_order)

    shipping_line_data = {
        "description": f"Shipping Method: {order.shipping_method}",
        "quantity": 1,
        "price": Money(order.shipping_cost, order.currency.value),
    }
    if shipping_line := extra_lines.filter(reference__exact="Shipping").first():
        update_object_with_dict(shipping_line, shipping_line_data)
    else:
        shipping_line = SalesOrderExtraLine.objects.create(
            order=sales_order, reference="Shipping", **shipping_line_data
        )

    sales_tax_line_data = {
        "description": f"Tax Rate: {order.tax_rate:.1f}%",
        "quantity": 1,
        "price": Money(max(order.tax_collected, order.total_tax), order.currency.value),
    }
    if sales_tax_line := extra_lines.filter(reference__exact="Sales Tax").first():
        update_object_with_dict(sales_tax_line, sales_tax_line_data)
    else:
        sales_tax_line = SalesOrderExtraLine.objects.create(
            order=sales_order, reference="Sales Tax", **sales_tax_line_data,
        )

    return [shipping_line, sales_tax_line]

def create_line_item(
    sales_order: SalesOrder,
    product_parts: BaseManager[Part],
    existing_line_items: BaseManager[SalesOrderLineItem],
    order: Order,
    order_item: OrderItem,
    products: dict[int, Product],
):
    reference = (
        f"{order_item.product_name} | "
        + ", ".join((f"{option.name}: {option.choice}" for option in order_item.options))
    ).strip()
    product_id = order_item.product_id

    if not (product := products.get(product_id)):
        sales_order.metadata[LECTRONZ_ORDER_TAG]["sync_errors"].append(
            f"Failed to find Lectronz Product '{reference}' (id={product_id})"
        )
        return None

    metadata_filter = {f"metadata__{LECTRONZ_PRODUCT_TAG}__id": product_id}

    part = None
    for product_part in product_parts.filter(**metadata_filter):
        if not (options := product_part.metadata[LECTRONZ_PRODUCT_TAG].get("options")):
            continue

        for option in order_item.options:
            if options.get(option.name) not in {option.choice, "lectronzplugin_all"}:
                break
        else:
            if part:
                sales_order.metadata[LECTRONZ_ORDER_TAG]["sync_errors"].append(
                    f"Found multiple Parts linked to Product '{reference}' (id={product_id})"
                )
                return None
            part = product_part

    if not part:
        sales_order.metadata[LECTRONZ_ORDER_TAG]["sync_errors"].append(
            f"Found no Part linked to Product '{reference}' (id={product_id})"
        )

    line_item_data = {
        "part": part,
        "sale_price": Money(order_item.price, order.currency.value),
        "shipped": float(order_item.quantity) if order.was_shipped else 0.0,
        "notes":
            f"Product ID: {product_id}"
            + f", Discount: {order_item.discount:.1f}%" if order_item.discount else "",
        "reference": reference,
        "quantity": float(order_item.quantity),
        "link": product.url if product else None,
    }

    line_items = existing_line_items.filter(Q(part=part) | Q(reference__exact=reference))
    if line_items.count() > 1:
        sales_order.metadata[LECTRONZ_ORDER_TAG]["sync_errors"].append(
            f"Failed to update line item for Product '{reference}' (id={product_id})"
        )
        return None
    elif line_item := line_items.first():
        update_object_with_dict(line_item, line_item_data)
    else:
        line_item = SalesOrderLineItem.objects.create(order=sales_order, **line_item_data)

    return line_item

def create_shipment(sales_order: SalesOrder, order: Order):
    shipment = None
    existing_shipments = SalesOrderShipment.objects.filter(order=sales_order)

    shipment_data = {
        "shipment_date": order.fulfilled_at,
        "tracking_number": order.tracking_code,
        "invoice_number": f"#{order.id}",
        "link": order.tracking_url,
    }
    if len(existing_shipments) == 1:
        shipment = existing_shipments.first()
        update_object_with_dict(shipment, shipment_data)
    elif not existing_shipments.exists():
        shipment = SalesOrderShipment.objects.create(order=sales_order, **shipment_data)

    return shipment

def update_object_with_dict(obj: Model, update: dict, save=True):
    for field, value in update.items():
        setattr(obj, field, value)
    if save:
        obj.save()
