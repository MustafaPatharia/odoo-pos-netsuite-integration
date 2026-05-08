#!/bin/bash

echo "Starting Odoo POS - NetSuite Integration..."
echo "=========================================="
echo ""

# Start services
echo "Starting Docker services..."
docker-compose up -d

echo ""
echo "Waiting for services to be ready..."
sleep 10

echo ""
echo "=========================================="
echo "Services Status:"
echo "=========================================="
docker-compose ps

echo ""
echo "=========================================="
echo "Access URLs:"
echo "=========================================="
echo "Odoo: http://localhost:8069"
echo "  - Email: admin"
echo "  - Password: admin"
echo ""
echo "Mock NetSuite: http://localhost:3000"
echo "  - Health: http://localhost:3000/health"
echo "  - Logs: http://localhost:3000/api/sync-logs"
echo ""
echo "PostgreSQL: localhost:5432"
echo "  - User: odoo"
echo "  - Password: odoo"
echo "  - Database: postgres"
echo ""
echo "=========================================="
echo "Next Steps:"
echo "=========================================="
echo "1. Open http://localhost:8069 in your browser"
echo "2. Login with admin/admin"
echo "3. Go to Apps and install 'NetSuite POS Integration'"
echo "4. Configure at: NetSuite → Configuration"
echo "5. Test connection to mock server"
echo ""
echo "To view logs:"
echo "  docker-compose logs -f odoo"
echo "  docker-compose logs -f mock-netsuite"
echo ""
echo "To stop services:"
echo "  docker-compose down"
echo ""
