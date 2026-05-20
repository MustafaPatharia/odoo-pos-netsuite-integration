# NetSuite → Odoo Product Field Mapping

**Status**: Future Enhancement Request
**Date**: May 17, 2026

---

## ✅ Currently Implemented Fields

| NetSuite Field | Odoo Field | Type | Description |
|---|---|---|---|
| `id` | `x_netsuite_id` | String | NetSuite internal ID (unique) |
| `itemid` | `default_code` | String | Item SKU/Reference |
| `displayname` | `name` | String | Product name |
| `description` | `description` | Text | Product description |
| `baseprice` | `list_price` | Float | Sales price |
| `cost` | `standard_price` | Float | Cost price |
| `isinactive` | `active` | Boolean | Active status (inverted) |
| `quantityavailable` | Stock level | Float | Available quantity (updates stock) |

**Note**: Product sync currently handles these 8 fields. The integration is fully functional with this basic field set.

---

## 🔮 Potential Future Enhancements

The following fields are NOT currently implemented but could be added in future versions:

| NetSuite Field | Purpose | Priority |
|---|---|---|
| `category` | Product categorization | Medium |
| `uom` | Unit of measure | Low |
| `barcode` | POS scanning | Medium |
| `itemtype` | Product type (inventory/service) | Low |
| `imageurl` | Product images | Low |
| `weight` | Shipping calculations | Low |
| `volume` | Shipping calculations | Low |

---

## Current NetSuite API Response

```json
{
  "id": "1001",
  "itemid": "ITEM-001",
  "displayname": "Coffee - Espresso",
  "description": "Premium espresso blend",
  "baseprice": 3.50,
  "cost": 1.20,
  "isinactive": false,
  "quantityavailable": 50.0
}
```

This minimal payload is sufficient for current operations.
