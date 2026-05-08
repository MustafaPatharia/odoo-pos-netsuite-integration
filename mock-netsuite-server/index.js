const express = require('express');
const bodyParser = require('body-parser');
const cors = require('cors');
const morgan = require('morgan');

const app = express();
const router = express.Router();

// Use mock-netsuite if available, otherwise use built-in mock
let mockNetsuite;
try {
  mockNetsuite = require('@scottybee84/mock-netsuite');
  console.log('Using @scottybee84/mock-netsuite package');
} catch (err) {
  console.log('mock-netsuite package not available, using built-in mock');
  mockNetsuite = null;
}

const PORT = process.env.PORT || 3000;

// Middleware
app.use(cors());
app.use(bodyParser.json());
app.use(bodyParser.urlencoded({ extended: true }));
app.use(morgan('dev'));

// If mock-netsuite package is available, use it
if (mockNetsuite) {
  // Initialize mock-netsuite with configuration
  const mockConfig = {
    port: PORT,
    debug: true,
    // Add any specific configuration needed
  };

  // Use the mock-netsuite middleware or routes
  // Note: Actual implementation depends on the package API
  app.use('/api', mockNetsuite.router || mockNetsuite);

} else {
  // Use our custom built-in mock implementation
  const builtInMock = require('./built-in-mock');
  app.use('/api', builtInMock);
}

// Health check endpoint (always available)
app.get('/health', (req, res) => {
  res.json({
    status: 'ok',
    message: 'Mock NetSuite server is running',
    timestamp: new Date().toISOString(),
    using: mockNetsuite ? '@scottybee84/mock-netsuite' : 'built-in-mock'
  });
});

// Start server
app.listen(PORT, '0.0.0.0', () => {
  console.log(`Mock NetSuite server is running on port ${PORT}`);
  console.log(`Health check: http://localhost:${PORT}/health`);
  console.log(`API Base URL: http://localhost:${PORT}/api`);
  console.log(`Using: ${mockNetsuite ? '@scottybee84/mock-netsuite' : 'built-in-mock'}`);
});

module.exports = app;
