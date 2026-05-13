Build a custom Odoo module for integrating Odoo with NetSuite. The integration architecture should be production-ready, configurable, scalable, and designed in a clean enterprise way instead of hardcoded flows.

The goal is to support both real-time and daily batch integrations dynamically through configuration. The system should allow administrators to configure how the integration behaves without changing code.

The module should include a configuration model where admins can manage:

* Integration mode:

  * Real-time sync
  * Daily batch sync
* Manual execution enable/disable
* Automatic scheduler enable/disable
* Retry configuration
* Batch size
* API endpoints
* Authentication credentials
* Debug logging
* Force resync permissions

The integration must support multiple execution scenarios.

If the integration mode is set to real-time:

* API calls should happen immediately after order confirmation or based on the configured business event.
* Failed requests should go into a retry queue instead of blocking the user interface.

If the integration mode is set to daily batch:

* Orders should be queued internally.
* A scheduled cron job should collect eligible orders and send them in a single consolidated payload.
* Manual execution should also be possible through UI buttons.

The module should support operational recovery features because ERP integrations fail frequently in real environments. Add manual action buttons in Odoo such as:

* Send to NetSuite
* Retry Failed Sync
* Force Resync
* Sync Now
* View Payload
* View API Response
* View Sync Logs

Button visibility and behavior should depend on configuration values and user permissions instead of being hardcoded.

The architecture should avoid directly calling APIs from button handlers. Instead:

* UI action creates integration job/queue record
* Background processor handles API communication
* Responses are logged
* Sync status is updated separately

Design proper logging and tracking tables/models for:

* Request payload
* Response payload
* Status
* Retry count
* Error messages
* Processing timestamps
* External NetSuite IDs

The module should also include:

* Retry mechanism for failed API calls
* Timeout handling
* Error queue management
* Manual recovery support
* Audit logs
* Batch processing support
* Scheduler/cron management

Since no real NetSuite environment is available initially, implement the integration using mock APIs first. The module should be testable using:

* Local Odoo Community Edition via Docker
* Mock API server (Postman Mock Server, Mockoon, Express.js mock server, etc.)

Create the system in a way that real NetSuite endpoints can later replace the mock APIs with minimal changes.

Also generate:

* Mermaid architecture diagrams
* Sequence diagrams for:

  * Real-time sync flow
  * Daily batch flow
  * Retry flow
  * Manual sync flow
  * Error handling flow
* Suggested database models
* Suggested module structure
* API flow explanation
* Queue/job processing design
* Recommended cron strategy
* Failure handling strategy

The implementation should follow clean modular architecture and enterprise integration best practices instead of tightly coupled logic.
