# scripts/seed_db.py
"""
Seed script: populate test data.
Run: python scripts/seed_db.py
"""

import asyncio
from uuid import uuid4
from app.db.session import init_db_engine, init_session_factory
from app.db.init_db import create_tables
from app.models import Campaign, Contact, DNCEntry, CampaignStatus, ContactStatus, DNCSource


async def seed_db():
    """Seed database with test data."""
    # Initialize engine and session
    await init_db_engine()
    session_factory = await init_session_factory()

    # Create tables if they don't exist
    try:
        await create_tables()
        print("✓ Tables created")
    except Exception as e:
        print(f"Note: {e}")

    async with session_factory() as session:
        # Check if test campaign already exists
        from sqlalchemy import select
        result = await session.execute(
            select(Campaign).where(Campaign.name == "Test Campaign")
        )
        existing = result.scalars().first()

        if not existing:
            campaign = Campaign(
                id=uuid4(),
                name="Test Campaign",
                status=CampaignStatus.DRAFT,
                prompt_template={
                    "persona": "Friendly Operations Assistant",
                    "objective": "Test call",
                },
                llm_config={
                    "model": "gpt-4o",
                    "temperature": 0.7,
                    "max_tokens": 2000,
                },
            )
            session.add(campaign)
            await session.flush()
            campaign_id = campaign.id
            print(f"✓ Campaign created: {campaign_id}")
        else:
            campaign_id = existing.id
            print(f"✓ Campaign already exists: {campaign_id}")

        # Check if DNC contact exists
        result = await session.execute(
            select(Contact).where(Contact.phone_number == "+919876543210")
        )
        dnc_contact_exists = result.scalars().first() is not None

        if not dnc_contact_exists:
            dnc_contact = Contact(
                id=uuid4(),
                phone_number="+919876543210",
                first_name="DNC",
                last_name="Test",
                timezone="Asia/Kolkata",
                campaign_id=campaign_id,
                status=ContactStatus.PENDING,
            )
            session.add(dnc_contact)
            await session.flush()
            print(f"✓ DNC contact created: +919876543210")
        else:
            print(f"✓ DNC contact already exists: +919876543210")

        # Add to DNC registry
        result = await session.execute(
            select(DNCEntry).where(DNCEntry.phone_number == "+919876543210")
        )
        dnc_exists = result.scalars().first() is not None

        if not dnc_exists:
            dnc_entry = DNCEntry(
                id=uuid4(),
                phone_number="+919876543210",
                source=DNCSource.MANUAL,
            )
            session.add(dnc_entry)
            print(f"✓ DNC registry entry created: +919876543210")
        else:
            print(f"✓ DNC registry entry already exists: +919876543210")

        # Check if clean contact exists
        result = await session.execute(
            select(Contact).where(Contact.phone_number == "+919876543211")
        )
        clean_contact_exists = result.scalars().first() is not None

        if not clean_contact_exists:
            clean_contact = Contact(
                id=uuid4(),
                phone_number="+919876543211",
                first_name="Clean",
                last_name="Lead",
                timezone="Asia/Kolkata",
                campaign_id=campaign_id,
                status=ContactStatus.PENDING,
            )
            session.add(clean_contact)
            print(f"✓ Clean contact created: +919876543211")
        else:
            print(f"✓ Clean contact already exists: +919876543211")

        # Commit all changes
        await session.commit()
        print("✓ All data committed")


if __name__ == "__main__":
    asyncio.run(seed_db())
    print("\n✓ Seed complete!")
