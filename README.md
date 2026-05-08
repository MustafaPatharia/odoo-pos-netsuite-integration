# Odoo POS - NetSuite Integration

Production-ready integration module for syncing Odoo Point of Sale orders with NetSuite ERP.

## Features

### Core Capabilities
- ✅ **Dual Sync Modes**: Real-time and batch synchronization
- ✅ **Configurable Integration**: No code changes required for configuration
- ✅ **Queue-Based Processing**: Non-blocking background sync
- ✅ **Automatic Retry**: Intelligent retry mechanism for failed syncs
- ✅ **Comprehensive Logging**: Full audit trail of all sync operations
- ✅ **Manual Recovery**: UI buttons for manual sync and recovery
- ✅ **Batch Processing**: Efficient bulk sync capabilities
- ✅ **Mock Server Included**: Test without NetSuite environment

### Technical Highlights
- Clean modular architecture
- Enterprise-grade error handling
- Scalable queue processing
- Configurable retry policies
- Detailed API logging
- Role-based permissions
- Cron-based schedulers
- RESTful API integration

## Architecture

### High-Level Architecture

\`\`\`mermaid
graph TB
    subgraph "Odoo POS"
        POS[POS Orders] --> Hooks[Order Hooks]
        Hooks --> Queue[Sync Queue]
        Queue --> Processor[Queue Processor]
        Config[Configuration] --> Processor
        Processor --> API[API Client]
    end

    subgraph "NetSuite"
        NS[NetSuite API]
    end

    API -->|HTTP/REST| NS
    NS -->|Response| API
    API --> Logs[Sync Logs]
    Processor --> Logs

    subgraph "Background Jobs"
        Cron1[Batch Processor] --> Queue
        Cron2[Retry Handler] --> Queue
    end

    subgraph "UI Controls"
        Manual[Manual Sync] --> Queue
        Resync[Force Resync] --> Queue
    end
\`\`\`

### Data Flow Diagram

\`\`\`mermaid
sequenceDiagram
    participant User
    participant POS as POS Order
    participant Queue as Sync Queue
    participant Worker as Queue Processor
    participant API as API Client
    participant NS as NetSuite
    participant Log as Sync Log

    User->>POS: Confirm Order
    POS->>Queue: Create Queue Item

    alt Real-time Mode
        Queue->>Worker: Process Immediately
    else Batch Mode
        Note over Queue: Wait for Cron
        Worker->>Queue: Poll Queue
    end

    Worker->>API: Prepare Payload
    API->>NS: POST /salesorder

    alt Success
        NS-->>API: 201 Created {id, tranId}
        API-->>Worker: Success Response
        Worker->>POS: Update Status = Synced
        Worker->>Log: Log Success
        Worker->>Queue: Mark Complete
    else Failure
        NS-->>API: 4xx/5xx Error
        API-->>Worker: Error Response
        Worker->>Log: Log Failure

        alt Retry Enabled
            Worker->>Queue: Status = Retry
            Note over Queue: Will retry later
        else Max Retries Reached
            Worker->>Queue: Status = Failed
            Worker->>POS: Update Status = Failed
        end
    end
\`\`\`

### Real-time Sync Flow

\`\`\`mermaid
sequenceDiagram
    participant Order as POS Order
    participant Config
    participant Queue
    participant API
    participant NetSuite
    participant Log

    Order->>Order: state = 'paid'
    Order->>Config: Check if auto_sync enabled
    Config-->>Order: sync_mode = 'realtime'

    Order->>Queue: Create queue item (priority=10)
    Queue->>Queue: status = 'pending'

    Order->>Order: Commit transaction

    Queue->>API: _process_queue_items()
    API->>NetSuite: POST /api/salesorder

    alt Success
        NetSuite-->>API: 201 {id, tranId}
        API->>Order: Update netsuite_id, status='synced'
        API->>Log: Create success log
        API->>Queue: status = 'success'
    else Error
        NetSuite-->>API: Error response
        API->>Log: Create error log
        API->>Queue: status = 'retry' or 'failed'
    end
\`\`\`

### Batch Sync Flow

\`\`\`mermaid
sequenceDiagram
    participant Cron
    participant Config
    participant Queue
    participant API
    participant NetSuite
    participant Orders

    Cron->>Config: Check batch_mode
    Config-->>Cron: enabled

    Cron->>Queue: Get pending items (limit=batch_size)
    Queue-->>Cron: Return 50 items

    loop For each batch item
        Cron->>API: Process queue item
        API->>NetSuite: POST /api/salesorder
        NetSuite-->>API: Response
        API->>Orders: Update status
        API->>Queue: Update queue status
    end

    Cron->>Cron: Commit all changes
\`\`\`

### Retry Flow

\`\`\`mermaid
sequenceDiagram
    participant Cron as Retry Cron
    participant Queue
    participant API
    participant NetSuite
    participant Config

    Cron->>Queue: Find items with status='retry'
    Queue-->>Cron: Items with retry_count < max_attempts

    loop For each retry item
        Cron->>Queue: Check retry_count

        alt Can retry
            Queue->>API: Process item
            API->>NetSuite: Attempt sync

            alt Success
                NetSuite-->>API: 201 Success
                API->>Queue: status = 'success'
            else Still failing
                NetSuite-->>API: Error
                API->>Queue: retry_count++

                alt More attempts available
                    API->>Queue: schedule next retry
                else Max attempts reached
                    API->>Queue: status = 'failed'
                end
            end
        end
    end
\`\`\`

### Manual Sync Flow

\`\`\`mermaid
sequenceDiagram
    participant User
    participant UI
    participant Order
    participant Queue
    participant API
    participant NetSuite

    User->>UI: Click "Sync to NetSuite"
    UI->>Order: action_sync_to_netsuite()

    Order->>Order: Check if already synced

    alt Force Resync
        User->>UI: Click "Force Resync"
        Order->>Order: Reset sync status
    end

    Order->>Queue: Create queue item (priority=5, mode='manual')
    Queue->>Queue: status = 'pending'

    Order->>API: _process_queue_items()
    API->>NetSuite: POST /api/salesorder

    NetSuite-->>API: Response
    API->>Order: Update sync status
    API-->>UI: Show notification
    UI-->>User: "Sync Initiated"
\`\`\`

### Error Handling Flow

\`\`\`mermaid
graph TD
    Start[Sync Request] --> Queue[Add to Queue]
    Queue --> Process[Process Queue Item]
    Process --> API[API Client Call]
    API --> Check{Response?}

    Check -->|Success| UpdateOrder[Update Order Status]
    UpdateOrder --> LogSuccess[Log Success]
    LogSuccess --> End[Complete]

    Check -->|Error| LogError[Log Error]
    LogError --> RetryCheck{Retry Enabled?}

    RetryCheck -->|Yes| CountCheck{Retry Count < Max?}
    CountCheck -->|Yes| Schedule[Schedule Retry]
    Schedule --> Wait[Wait for Next Attempt]
    Wait --> Process

    CountCheck -->|No| MarkFailed[Mark as Failed]
    RetryCheck -->|No| MarkFailed
    MarkFailed --> NotifyUser[Notify User]
    NotifyUser --> End
\`\`\`

## Database Models

### netsuite.config
Configuration settings for the integration.

| Field | Type | Description |
|-------|------|-------------|
| name | Char | Configuration name |
| active | Boolean | Enable/disable integration |
| api_url | Char | NetSuite API endpoint |
| sync_mode | Selection | realtime / batch |
| enable_manual_sync | Boolean | Allow manual triggers |
| enable_auto_sync | Boolean | Auto-sync on order confirm |
| batch_size | Integer | Records per batch |
| enable_retry | Boolean | Auto-retry failed syncs |
| max_retry_attempts | Integer | Maximum retry count |
| retry_delay_minutes | Integer | Delay between retries |

### netsuite.sync.queue
Queue of pending sync operations.

| Field | Type | Description |
|-------|------|-------------|
| reference | Char | Order reference (POS/001) |
| record_type | Selection | sales_order / customer / payment |
| record_id | Integer | Odoo record ID |
| status | Selection | pending / processing / success / failed / retry |
| priority | Integer | Processing priority |
| retry_count | Integer | Number of retry attempts |
| request_payload | Text | JSON request data |
| response_payload | Text | JSON response data |
| netsuite_id | Char | NetSuite internal ID |
| netsuite_tran_id | Char | NetSuite transaction number |

### netsuite.sync.log
Audit log of all sync operations.

| Field | Type | Description |
|-------|------|-------------|
| reference | Char | Order reference |
| record_type | Selection | Type of record synced |
| status | Selection | success / failed / warning |
| operation | Selection | create / update / delete |
| request_payload | Text | Full request sent |
| response_payload | Text | Full response received |
| error_message | Text | Error details if failed |
| execution_time_ms | Integer | API call duration |
| netsuite_id | Char | NetSuite record ID |

### pos.order (Extended)
Extended POS Order with sync fields.

| Field | Type | Description |
|-------|------|-------------|
| netsuite_sync_status | Selection | not_synced / queued / synced / failed |
| netsuite_id | Char | NetSuite internal ID |
| netsuite_tran_id | Char | NetSuite transaction number |
| netsuite_sync_date | Datetime | Last sync timestamp |
| netsuite_error | Text | Last error message |
| netsuite_sync_count | Integer | Number of sync attempts |

## Installation & Setup

### Prerequisites
- Docker & Docker Compose
- Git

### Quick Start

1. **Clone Repository**
\`\`\`bash
git clone https://github.com/MustafaPatharia/odoo-pos-netsuite-integration.git
cd odoo-pos-netsuite-integration
\`\`\`

2. **Start Services**
\`\`\`bash
docker-compose up -d
\`\`\`

This will start:
- PostgreSQL (port 5432)
- Odoo (port 8069)
- Mock NetSuite Server (port 3000)

3. **Access Odoo**
- URL: http://localhost:8069
- Email: admin
- Password: admin

4. **Install Module**
- Go to Apps
- Search for "NetSuite POS Integration"
- Click Install

5. **Configure Integration**
- Navigate to: NetSuite → Configuration
- API URL: `http://mock-netsuite:3000/api`
- Choose sync mode (Real-time or Batch)
- Click "Test Connection"

### Mock NetSuite Server

Test the mock server directly:

\`\`\`bash
# Health check
curl http://localhost:3000/health

# Create test sales order
curl -X POST http://localhost:3000/api/salesorder \\
  -H "Content-Type: application/json" \\
  -d '{
    "entity": "1",
    "items": [
      {"item": "Product A", "quantity": 2, "rate": 50.00}
    ]
  }'

# View sync logs
curl http://localhost:3000/api/sync-logs
\`\`\`

## Usage

### Real-time Sync

1. Create and confirm a POS order
2. Order automatically queues for sync
3. Background processor syncs immediately
4. Check sync status in order form

### Batch Sync

1. Set sync mode to "Batch" in configuration
2. Orders accumulate in queue
3. Cron job processes batch daily
4. Or trigger manual batch processing

### Manual Sync

From POS Order:
- **Sync to NetSuite**: Sync single order
- **Force Resync**: Resync already synced order
- **View Sync Logs**: See sync history
- **View Queue**: Check queue status

From Order List:
- Select multiple orders
- Actions → Sync to NetSuite

### Retry Failed Syncs

Failed syncs automatically retry based on configuration:
- Max retry attempts: 3 (configurable)
- Retry delay: 5 minutes (configurable)
- Manual retry available from sync logs

## Configuration Options

### Sync Modes

**Real-time Sync**
- Syncs immediately on order confirmation
- Non-blocking (uses queue)
- Best for: Low-volume, urgent sync needs

**Batch Sync**
- Accumulates orders in queue
- Processes in scheduled batches
- Best for: High-volume, scheduled sync

### Sync Triggers

- **On Order Confirmation**: Trigger when POS order confirmed
- **On Payment**: Trigger when payment received

### Retry Configuration

- **Enable Retry**: Auto-retry failed syncs
- **Max Attempts**: Maximum retry count (0-10)
- **Retry Delay**: Minutes between attempts

### Logging

- **Enable Debug Logging**: Detailed debug info
- **Log Payload**: Store request/response JSON

## API Endpoints (Mock Server)

### Sales Orders

**Create Sales Order**
\`\`\`
POST /api/salesorder
Content-Type: application/json

{
  "entity": "customer_id",
  "tranDate": "2024-01-15",
  "currency": "USD",
  "items": [
    {
      "item": "product_sku",
      "quantity": 2,
      "rate": 100.00
    }
  ],
  "externalId": "ODOO-POS-123"
}
\`\`\`

**Response**
\`\`\`json
{
  "success": true,
  "id": "uuid",
  "tranId": "SO-123456",
  "externalId": "ODOO-POS-123"
}
\`\`\`

### Batch Operations

**Batch Create**
\`\`\`
POST /api/batch
Content-Type: application/json

{
  "operations": [
    {
      "type": "salesorder",
      "data": { ... }
    }
  ]
}
\`\`\`

### Sync Logs

**Get Sync Logs**
\`\`\`
GET /api/sync-logs?limit=100&operation=CREATE_SALES_ORDER&status=success
\`\`\`

## Security & Permissions

### User Groups

**NetSuite User**
- View sync status and logs
- Read-only access

**NetSuite Manager**
- All user permissions
- Manage configuration
- Trigger manual syncs
- Force resync
- Modify queue items

### Access Control

Configured via `ir.model.access.csv`:
- netsuite.config: User (read), Manager (full)
- netsuite.sync.queue: User (read), Manager (full)
- netsuite.sync.log: User (read), Manager (read/write)

## Cron Jobs

### Batch Queue Processor
- **Frequency**: Every 1 hour
- **Function**: Process pending batch items
- **Configuration**: Adjustable via cron settings

### Retry Handler
- **Frequency**: Every 30 minutes
- **Function**: Retry failed syncs
- **Configuration**: Honors max_retry_attempts

## Troubleshooting

### Integration Not Working

1. Check configuration is active
2. Test connection to NetSuite
3. Verify auto-sync is enabled
4. Check Odoo logs for errors

### Orders Not Syncing

1. Check sync mode configuration
2. Verify order state is 'paid' or 'done'
3. Check sync queue for pending items
4. Review sync logs for errors

### Sync Failures

1. View sync log for error details
2. Check NetSuite server connectivity
3. Verify API credentials
4. Review request payload for data issues
5. Manually retry from sync log

### Performance Issues

1. Reduce batch size
2. Increase cron frequency
3. Enable batch mode instead of real-time
4. Review slow API calls in logs

## Development

### Project Structure

\`\`\`
odoo-pos-netsuite-integration/
├── docker-compose.yml
├── odoo-config/
│   └── odoo.conf
├── addons/
│   └── netsuite_pos_integration/
│       ├── __init__.py
│       ├── __manifest__.py
│       ├── models/
│       │   ├── netsuite_config.py
│       │   ├── netsuite_sync_queue.py
│       │   ├── netsuite_sync_log.py
│       │   ├── netsuite_api_client.py
│       │   ├── pos_order.py
│       │   └── res_partner.py
│       ├── views/
│       │   ├── netsuite_config_views.xml
│       │   ├── netsuite_sync_queue_views.xml
│       │   ├── netsuite_sync_log_views.xml
│       │   ├── pos_order_views.xml
│       │   └── netsuite_menu.xml
│       ├── security/
│       │   ├── netsuite_security.xml
│       │   └── ir.model.access.csv
│       ├── data/
│       │   ├── netsuite_cron_data.xml
│       │   └── netsuite_sync_status_data.xml
│       └── wizards/
│           └── netsuite_manual_sync_wizard.py
└── mock-netsuite-server/
    ├── package.json
    ├── index.js
    ├── built-in-mock.js
    └── Dockerfile
\`\`\`

### Extending the Module

**Add New Record Types**

1. Add selection option to `record_type` field
2. Implement handler in `netsuite_api_client.py`
3. Create queue items from source model
4. Update views to show new type

**Custom Field Mapping**

Modify payload in `netsuite_api_client.py`:

\`\`\`python
def create_sales_order(self, pos_order, config):
    order_data = {
        'entity': pos_order.partner_id.netsuite_id,
        'custom_field': pos_order.custom_field,  # Add here
        # ...
    }
\`\`\`

## Production Deployment

### Replace Mock Server with Real NetSuite

1. Update `api_url` in configuration
2. Add OAuth credentials
3. Implement OAuth signature (see TODO in api_client)
4. Test with NetSuite sandbox first
5. Deploy to production

### Recommended Settings

- Sync Mode: Batch
- Batch Size: 100
- Enable Retry: True
- Max Retries: 5
- Log Payload: False (performance)
- Debug Logging: False

### Monitoring

- Monitor sync logs daily
- Set up alerts for failed syncs
- Review execution times
- Track queue backlog

## License

LGPL-3

## Support

For issues and questions:
- GitHub Issues: https://github.com/MustafaPatharia/odoo-pos-netsuite-integration/issues
- Email: support@yourcompany.com

## Changelog

### Version 1.0.0 (2024)
- Initial release
- Real-time and batch sync
- Queue-based processing
- Retry mechanism
- Comprehensive logging
- Mock NetSuite server
- Full UI controls
