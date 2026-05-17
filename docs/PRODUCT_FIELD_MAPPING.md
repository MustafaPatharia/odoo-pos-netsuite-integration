# NetSuite → Odoo Product Field Mapping

**Date**: May 17, 2026
**For**: NetSuite Development Team

---

## ✅ Currently Mapped Fields

| NetSuite Field | Odoo Field | Status |
|---|---|---|
| `id` | `x_netsuite_id` | ✅ Mapped |
| `itemid` | `default_code` | ✅ Mapped |
| `displayname` | `name` | ✅ Mapped |
| `description` | `description` | ✅ Mapped |
| `baseprice` | `list_price` | ✅ Mapped |
| `cost` | `standard_price` | ✅ Mapped |
| `isinactive` | `active` | ✅ Mapped |

---

## 🔴 Additional Fields Needed from NetSuite

| NetSuite Field | Required/Optional | Description |
|---|---|---|
| `category` | Required | Product category name or ID for grouping items in Odoo |
| `uom` | Required | Unit of measure code (EA=Each, BOX=Box, KG=Kilogram, etc.) |
| `barcode` | Optional | Product UPC/EAN barcode for scanning |
| `itemtype` | Optional | Item type: InvtPart (inventory), Service, or NonInvtPart |
| `imageurl` | Optional | URL to product image (will be downloaded and stored in Odoo) |
| `weight` | Optional | Item weight in kilograms (for shipping calculations) |
| `volume` | Optional | Item volume in cubic meters (for shipping calculations) |

---

## 📄 Expected NetSuite Payload

### Current (Minimum)
```json
{
  "id": "1001",
  "itemid": "ITEM-001",
  "displayname": "Coffee - Espresso",
  "description": "Premium espresso blend",
  "baseprice": 3.50,
  "cost": 1.20,
  "isinactive": false
}
```

### Requested (Complete)
```json
{
  "id": "1001",
  "itemid": "ITEM-001",
  "displayname": "Coffee - Espresso",
  "description": "Premium espresso blend",
  "baseprice": 3.50,
  "cost": 1.20,
  "isinactive": false,
  "category": "Beverages",
  "uom": "EA",
  "barcode": "1234567890123",
  "itemtype": "InvtPart",
  "imageurl": "https://example.com/images/item-001.jpg",
  "weight": 0.5,
  "volume": 0.001
}
```

---

## 📝 Notes

- **category**: If not provided, all products default to "All" category
- **uom**: If not provided, defaults to "Units"
- **barcode**: Should be unique across all products
- **itemtype**: Maps to Odoo product type (InvtPart→Storable, Service→Service, NonInvtPart→Consumable)
- **weight/volume**: Used for shipping cost calculations

---

**Contact**: Odoo Integration Team
