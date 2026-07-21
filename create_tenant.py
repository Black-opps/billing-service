# services/billing-service/create_tenant.py
"""
Script to create tenant in Billing Service database
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uuid
from datetime import datetime, timedelta

from src.database import SessionLocal
from src.models.plan import Plan
from src.models.subscription import Subscription, SubscriptionStatus


def create_tenant():
    db = SessionLocal()

    try:
        # Get free plan
        plan = db.query(Plan).filter(Plan.id == "free").first()
        if not plan:
            plan = Plan(
                id="free",
                name="Free",
                description="Free tier for testing",
                price=0,
                billing_interval="monthly",
                limits={"transactions": 100000, "uploads": 1000},
            )
            db.add(plan)
            db.commit()
            db.refresh(plan)
            print("✅ Free plan created")

        # Create subscription for tenant
        tenant_id = "tenant_jonahmucheru_gmail.com"
        existing = (
            db.query(Subscription).filter(Subscription.tenant_id == tenant_id).first()
        )

        if existing:
            print(f"✅ Tenant already exists: {tenant_id}")
            return

        subscription = Subscription(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            plan_id=plan.id,
            status=SubscriptionStatus.ACTIVE,
            billing_interval="monthly",
            unit_price=0,
            quantity=1,
            current_period_start=datetime.utcnow(),
            current_period_end=datetime.utcnow() + timedelta(days=30),
            auto_renew=True,
        )
        db.add(subscription)
        db.commit()
        print(f"✅ Tenant created: {tenant_id}")

    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    create_tenant()
