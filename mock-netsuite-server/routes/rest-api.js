const express = require('express');
const router = express.Router();
const mockDatabase = require('../data/mock-database');

/**
 * GET /services/rest/record/v1/{recordType} - List records
 * NetSuite REST API Record Browser
 */
router.get('/:recordType', (req, res) => {
  try {
    const { recordType } = req.params;
    const { limit = 100, offset = 0 } = req.query;

    console.log(`\n=== NetSuite REST API: GET /${recordType} ===`);

    let dataMap = null;

    // Map record type to data store
    switch (recordType.toLowerCase()) {
      case 'subsidiary':
        dataMap = mockDatabase.subsidiaries;
        break;
      case 'department':
        dataMap = mockDatabase.departments;
        break;
      case 'location':
        dataMap = mockDatabase.locations;
        break;
      case 'paymentmethod':
        dataMap = mockDatabase.paymentMethods;
        break;
      case 'inventoryitem':
      case 'item':
        dataMap = mockDatabase.items;
        break;
      default:
        return res.status(404).json({
          'o:errorCode': 'INVALID_RECORD_TYPE',
          'o:errorDetails': [{
            detail: `Invalid record type: ${recordType}`,
            'o:errorCode': 'INVALID_RECORD_TYPE'
          }],
          title: 'Invalid Record Type',
          status: 404
        });
    }

    // Convert Map to array and apply pagination
    const allRecords = Array.from(dataMap.values());
    
    // For inventory items, randomize prices and costs for testing
    let recordsToReturn = allRecords;
    if (recordType.toLowerCase() === 'inventoryitem' || recordType.toLowerCase() === 'item') {
      console.log('⚡ Generating RANDOM prices and costs for inventory items...');
      recordsToReturn = allRecords.map(item => {
        const randomPrice = (Math.random() * 15 + 2).toFixed(2); // $2-$17
        const randomCost = (parseFloat(randomPrice) * (Math.random() * 0.5 + 0.3)).toFixed(2); // 30-80% of price
        
        return {
          ...item,
          baseprice: parseFloat(randomPrice),
          cost: parseFloat(randomCost),
          isinactive: Math.random() > 0.95 ? true : false, // 5% chance inactive
          description: `${item.description} (Updated: ${new Date().toLocaleTimeString()})`
        };
      });
    }
    
    const paginatedRecords = recordsToReturn.slice(offset, offset + parseInt(limit));

    // NetSuite REST API response format
    const response = {
      items: paginatedRecords,
      count: paginatedRecords.length,
      hasMore: (offset + paginatedRecords.length) < allRecords.length,
      offset: parseInt(offset),
      totalResults: allRecords.length,
      links: [
        {
          rel: 'self',
          href: `/services/rest/record/v1/${recordType}?limit=${limit}&offset=${offset}`
        }
      ]
    };

    if (response.hasMore) {
      response.links.push({
        rel: 'next',
        href: `/services/rest/record/v1/${recordType}?limit=${limit}&offset=${parseInt(offset) + parseInt(limit)}`
      });
    }

    console.log(`✓ Returned ${paginatedRecords.length} ${recordType} records`);
    res.json(response);

  } catch (error) {
    console.error('REST API error:', error);
    res.status(500).json({
      'o:errorCode': 'INTERNAL_ERROR',
      'o:errorDetails': [{
        detail: error.message,
        'o:errorCode': 'INTERNAL_ERROR'
      }],
      title: 'Internal Server Error',
      status: 500
    });
  }
});

/**
 * GET /services/rest/record/v1/{recordType}/{id} - Get specific record
 */
router.get('/:recordType/:id', (req, res) => {
  try {
    const { recordType, id } = req.params;

    console.log(`\n=== NetSuite REST API: GET /${recordType}/${id} ===`);

    let dataMap = null;

    // Map record type to data store
    switch (recordType.toLowerCase()) {
      case 'subsidiary':
        dataMap = mockDatabase.subsidiaries;
        break;
      case 'department':
        dataMap = mockDatabase.departments;
        break;
      case 'location':
        dataMap = mockDatabase.locations;
        break;
      case 'paymentmethod':
        dataMap = mockDatabase.paymentMethods;
        break;
      case 'inventoryitem':
      case 'item':
        dataMap = mockDatabase.items;
        break;
      default:
        return res.status(404).json({
          'o:errorCode': 'INVALID_RECORD_TYPE',
          'o:errorDetails': [{
            detail: `Invalid record type: ${recordType}`,
            'o:errorCode': 'INVALID_RECORD_TYPE'
          }],
          title: 'Invalid Record Type',
          status: 404
        });
    }

    // Find record by ID
    const record = dataMap.get(id);

    if (!record) {
      return res.status(404).json({
        'o:errorCode': 'RECORD_NOT_FOUND',
        'o:errorDetails': [{
          detail: `${recordType} record with id ${id} not found`,
          'o:errorCode': 'RECORD_NOT_FOUND'
        }],
        title: 'Record Not Found',
        status: 404
      });
    }

    console.log(`✓ Found ${recordType}: ${record.name}`);

    // Return single record (not wrapped in array)
    res.json(record);

  } catch (error) {
    console.error('REST API error:', error);
    res.status(500).json({
      'o:errorCode': 'INTERNAL_ERROR',
      'o:errorDetails': [{
        detail: error.message,
        'o:errorCode': 'INTERNAL_ERROR'
      }],
      title: 'Internal Server Error',
      status: 500
    });
  }
});

module.exports = router;
