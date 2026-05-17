// In-memory storage for mock NetSuite data
const mockDatabase = {
  salesOrders: new Map(),
  customers: new Map(),
  items: new Map(),
  payments: new Map(),
  syncLogs: [],
  // NetSuite master data
  subsidiaries: new Map(),
  departments: new Map(),
  locations: new Map(),
  paymentMethods: new Map()
};

// Initialize mock customer data
mockDatabase.customers.set('1', {
  internalId: '1',
  entityId: 'CUST-001',
  companyName: 'Default Customer',
  email: 'customer@example.com',
  externalId: 'ODOO-CUST-001'
});

// Initialize mock item data (Products)
mockDatabase.items.set('1001', {
  id: '1001',
  itemid: 'ITEM-001',
  displayname: 'Coffee - Espresso',
  description: 'Premium espresso blend',
  baseprice: 3.50,
  cost: 1.20,
  isinactive: false,
  itemtype: 'InvtPart'
});

mockDatabase.items.set('1002', {
  id: '1002',
  itemid: 'ITEM-002',
  displayname: 'Coffee - Latte',
  description: 'Classic latte with steamed milk',
  baseprice: 4.50,
  cost: 1.50,
  isinactive: false,
  itemtype: 'InvtPart'
});

mockDatabase.items.set('1003', {
  id: '1003',
  itemid: 'ITEM-003',
  displayname: 'Pastry - Croissant',
  description: 'Fresh butter croissant',
  baseprice: 2.50,
  cost: 0.80,
  isinactive: false,
  itemtype: 'InvtPart'
});

mockDatabase.items.set('1004', {
  id: '1004',
  itemid: 'ITEM-004',
  displayname: 'Sandwich - Club',
  description: 'Classic club sandwich with turkey and bacon',
  baseprice: 8.50,
  cost: 3.20,
  isinactive: false,
  itemtype: 'InvtPart'
});

mockDatabase.items.set('1005', {
  id: '1005',
  itemid: 'ITEM-005',
  displayname: 'Juice - Orange',
  description: 'Freshly squeezed orange juice',
  baseprice: 3.00,
  cost: 0.90,
  isinactive: false,
  itemtype: 'InvtPart'
});

mockDatabase.items.set('1006', {
  id: '1006',
  itemid: 'ITEM-006',
  displayname: 'Muffin - Blueberry',
  description: 'Fresh blueberry muffin',
  baseprice: 3.25,
  cost: 1.00,
  isinactive: false,
  itemtype: 'InvtPart'
});

mockDatabase.items.set('1007', {
  id: '1007',
  itemid: 'ITEM-007',
  displayname: 'Tea - Green',
  description: 'Premium green tea',
  baseprice: 2.75,
  cost: 0.60,
  isinactive: false,
  itemtype: 'InvtPart'
});

mockDatabase.items.set('1008', {
  id: '1008',
  itemid: 'ITEM-008',
  displayname: 'Salad - Caesar',
  description: 'Caesar salad with chicken',
  baseprice: 9.50,
  cost: 3.80,
  isinactive: false,
  itemtype: 'InvtPart'
});

mockDatabase.items.set('1009', {
  id: '1009',
  itemid: 'ITEM-009',
  displayname: 'Bagel - Plain',
  description: 'Fresh plain bagel',
  baseprice: 2.00,
  cost: 0.50,
  isinactive: false,
  itemtype: 'InvtPart'
});

mockDatabase.items.set('1010', {
  id: '1010',
  itemid: 'ITEM-010',
  displayname: 'Smoothie - Berry',
  description: 'Mixed berry smoothie',
  baseprice: 5.50,
  cost: 2.00,
  isinactive: false,
  itemtype: 'InvtPart'
});

// Initialize NetSuite master data - Subsidiaries
mockDatabase.subsidiaries.set('1', {
  id: '1',
  name: 'Main Company',
  legalName: 'Main Company LLC',
  country: 'US',
  isElimination: false,
  isinactive: false
});

mockDatabase.subsidiaries.set('2', {
  id: '2',
  name: 'UK Subsidiary',
  legalName: 'UK Operations Ltd',
  country: 'GB',
  isElimination: false,
  isinactive: false
});

// Initialize Departments
mockDatabase.departments.set('1', {
  id: '1',
  name: 'Sales',
  isinactive: false
});

mockDatabase.departments.set('2', {
  id: '2',
  name: 'Operations',
  isinactive: false
});

mockDatabase.departments.set('3', {
  id: '3',
  name: 'Finance',
  isinactive: false
});

// Initialize Locations
mockDatabase.locations.set('1', {
  id: '1',
  name: 'Main Warehouse',
  address: '123 Main St, New York, NY 10001',
  isinactive: false
});

mockDatabase.locations.set('2', {
  id: '2',
  name: 'Downtown Store',
  address: '456 Downtown Ave, New York, NY 10002',
  isinactive: false
});

mockDatabase.locations.set('3', {
  id: '3',
  name: 'Uptown Store',
  address: '789 Uptown Blvd, New York, NY 10003',
  isinactive: false
});

// Initialize Payment Methods
mockDatabase.paymentMethods.set('1', {
  id: '1',
  name: 'Cash',
  creditcard: false,
  isinactive: false
});

mockDatabase.paymentMethods.set('2', {
  id: '2',
  name: 'Credit Card',
  creditcard: true,
  isinactive: false
});

mockDatabase.paymentMethods.set('3', {
  id: '3',
  name: 'Debit Card',
  creditcard: true,
  isinactive: false
});

mockDatabase.paymentMethods.set('4', {
  id: '4',
  name: 'Mobile Payment',
  creditcard: false,
  isinactive: false
});

module.exports = mockDatabase;
