# 🟪 Billing Service

Subscription and usage-based billing service for M-PESA SaaS platform.

## 📋 Overview

The Billing Service handles all monetization aspects of the platform including:

- Subscription management (plans, upgrades, cancellations)
- Usage metering and tracking
- Invoice generation and management
- Payment processing (M-PESA integration)
- Usage alerts and notifications

## 🏗️ Architecture

┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ API Layer │────▶│ Service Layer │────▶│ Model Layer │
│ (FastAPI) │ │ (Business │ │ (SQLAlchemy) │
│ │ │ Logic) │ │ │
└─────────────────┘ └─────────────────┘ └─────────────────┘
│ │ │
▼ ▼ ▼
┌─────────────────────────────────────────────────────────────┐
│ PostgreSQL │
│ Redis │
│ Kafka │
└─────────────────────────────────────────────────────────────┘

##

Core Endpoints
Plans
GET /api/v1/plans - List all plans

GET /api/v1/plans/{plan_id} - Get plan details

POST /api/v1/plans - Create plan (admin)

POST /api/v1/plans/calculate-price - Calculate subscription price

Subscriptions
POST /api/v1/subscriptions - Create subscription

GET /api/v1/subscriptions/tenant/{tenant_id} - List tenant subscriptions

GET /api/v1/subscriptions/{subscription_id} - Get subscription

POST /api/v1/subscriptions/{subscription_id}/upgrade - Upgrade plan

POST /api/v1/subscriptions/{subscription_id}/cancel - Cancel subscription

Usage
POST /api/v1/usage/track - Track usage event

GET /api/v1/usage/current/{tenant_id} - Get current usage

GET /api/v1/usage/summary/{tenant_id} - Get usage summary

GET /api/v1/usage/limits/{tenant_id} - Get usage limits

Invoices
GET /api/v1/invoices/tenant/{tenant_id} - List tenant invoices

GET /api/v1/invoices/{invoice_id} - Get invoice details

GET /api/v1/invoices/{invoice_id}/pdf - Download invoice PDF

POST /api/v1/invoices/{invoice_id}/pay - Mark invoice as paid

📊 Data Models
Plan
json
{
"id": "uuid",
"plan_id": "professional",
"name": "Professional",
"price": 9900,
"currency": "KES",
"interval": "monthly",
"features": ["Real-time Analytics", "50,000 transactions/month"],
"limits": {"transactions": 50000, "users": 10}
}
Subscription
json
{
"id": "uuid",
"tenant_id": "uuid",
"plan": {...},
"status": "active",
"current_period_start": "2026-03-01T00:00:00Z",
"current_period_end": "2026-03-31T23:59:59Z",
"auto_renew": true
}
Invoice
json
{
"id": "uuid",
"invoice_number": "INV-202503-123456",
"status": "paid",
"total": 9900,
"currency": "KES",
"due_date": "2026-03-15",
"items": [...]
}
🔌 Kafka Events
Published Events
usage-events - Real-time usage tracking

billing-events - Billing cycle events

payment-events - Payment notifications

Subscribed Topics
tenant-events - Tenant lifecycle events

subscription-events - Subscription changes

📈 Monitoring
Prometheus metrics at /metrics

Structured JSON logging

Sentry integration for error tracking

Health check at /health

Consumer status monitoring

🧪 Testing
bash

# Run tests

pytest

# With coverage

pytest --cov=src tests/

# Load test

locust -f tests/locustfile.py
🤝 Integration Dependencies
Tenant Service - For tenant validation

Payment Service - For processing payments

Auth Service - For authentication

Analytics API - For usage reporting

📝 License
MIT License - see LICENSE file for details

👨‍💻 Author

GitHub: @Black-opps

text

## 🚀 **Quick Setup Script**

.\setup-billing-service.ps1

## This complete Billing Service implementation includes:

✅ Full subscription management with multiple plans

✅ Usage metering with Kafka integration

✅ Invoice generation and PDF creation

✅ M-PESA payment processing

✅ Usage alerts at configurable thresholds

✅ Proration calculations for upgrades

✅ Grace period handling

✅ Comprehensive API endpoints

✅ Background tasks for monthly billing

✅ Prometheus metrics

✅ Docker support

The service is production-ready and follows all best practices for a FinTech billing platform! 🎉

```

```
