const { v4: uuidv4 } = require('uuid');
const mockDatabase = require('../data/mock-database');

/**
 * Helper function to log sync operations
 */
function logSync(operation, status, data, error = null) {
  const log = {
    id: uuidv4(),
    timestamp: new Date().toISOString(),
    operation,
    status,
    data: JSON.stringify(data).substring(0, 500),
    error
  };
  mockDatabase.syncLogs.push(log);
  console.log(`[SYNC LOG] ${operation} - ${status}`, error || '');
  return log;
}

module.exports = { logSync };
