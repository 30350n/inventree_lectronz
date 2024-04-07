[![pypi](https://img.shields.io/pypi/v/inventree-lectronz)](https://pypi.org/project/inventree-lectronz/)
[![python](https://img.shields.io/badge/Python-3.8+-blue)](https://www.python.org/)
[![mit](https://img.shields.io/badge/license-MIT-lightgrey)](LICENSE)

# InvenTree Lectronz

This InvenTree plugin integrates the [Lectronz](https://lectronz.com/) marketplace into
InvenTree.

## Features

- [x] **Automatic order synchronization**<br>
  *For each new Lectronz order the plugin will automatically create a InvenTree Sales Order.*
- [x] **Automatic order fulfillment**<br>
  *Lectronz orders will be automatically fulfilled if you complete a Sales Order Shipment.*
- [ ] **Automatic stock synchronization**<br>
  *Not possible yet, see [`lektronz-marketplace#33`](https://github.com/omzlo/lektronz-marketplace/issues/33).*

## Installation

Available via pypi: [`inventree-lectronz`](https://pypi.org/project/inventree-lectronz/)

1. Install the plugin according to the
   [Plugin Installation Instructions](https://docs.inventree.org/en/latest/extend/plugins/install/).
2. The plugin requires **Schedule**, **Event**, **URL**, **Navigation** and **App** integrations
   to function correctly. Enable all these integrations under `Settings -> Plugins`.

## Usage

### Initial Setup

Navigate to the plugin settings under `Settings -> Marketplace Integration - Lectronz` and
enter your **Lectronz API Token**. Also set the **Lectronz Company** to the company which acts
as the customer for all Lectronz orders.

### Linking Products

For proper stock tracking you will have to link a **Salable InvenTree Part** to each of your
Lectronz Products.

1. Go to the Part page in Inventree.<br>
   (There should be a new **Lectronz Product** Panel (this will only show up if the Part is
   marked **Salable**.)
2. Select the Lectronz Product (and any product options) you want to link the Part to.

Example:

![Example of the Lectronz Product Panel](images/link_product.png)

Note: Unlinked products will still appear in your Sales Orders, but you won't be able to
allocate Stock to them. You can link a product later and update the Sales Order though.

### Fulfilling Orders

Lectronz Orders will be automatically fulfilled once you complete a Shipment for a Sales Order.

Note: If the order requires a tracking number you have to provide it in the Shipment
information. (You can optionally also include a tracking link).

Example:

![Example of a Shipment which will automatically fulfill an order](images/shipment.png)

## Credits

- [InvenTree](https://inventree.org/) ([@SchrodingersGat](https://github.com/SchrodingersGat)
  and [@matmair](https://github.com/matmair))<br>
  This project wouldn't exist without their brilliant work on creating the awesome open-source
  inventory management solution.

- [Lectronz](https://lectronz.com/) ([@omzlo](https://github.com/omzlo))<br>
  The marketplace for makers and open-source hardware.

## License

- This project is licensed under the [MIT](LICENSE) license.
