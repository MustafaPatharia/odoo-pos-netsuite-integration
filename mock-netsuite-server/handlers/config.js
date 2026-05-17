const { logSync } = require('../utils/logger');

/**
 * Handle Get Configuration
 */
function handleGetConfig(req, res) {
  console.log('\n=== Configuration Request ===');

  // NetSuite returns configuration for Odoo
  const config = {
    success: true,
    configuration: {
      // Retry settings
      retry_enabled: true,
      max_retries: 3,
      retry_delay_minutes: 5,

      // Email settings
      send_email_on_failure: true,
      notification_email: 'admin@example.com',

      // Batch settings
      batch_size: 100,

      // Sync schedules
      hourly_sync_enabled: true,
      end_of_day_sync_time: '23:59',
      end_of_day_sync_enabled: true,

      // Logging
      enable_debug_logging: true,
      log_retention_days: 30,

      // Business rules
      sync_on_invoice_confirm: true,
      require_payment_before_sync: false,

      // Timeouts
      connection_timeout: 30,
      request_timeout: 60
    }
  };

  logSync('GET_CONFIG', 'success', config);
  res.json(config);
}

module.exports = { handleGetConfig };
