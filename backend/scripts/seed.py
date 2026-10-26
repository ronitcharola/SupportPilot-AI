import asyncio
import json
import logging
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from app.database import AsyncSessionLocal, engine, Base
from app.models.user import User, Customer
from app.models.workspace import Workspace, WorkspaceMembership, WorkspaceSettings
from app.models.ticket import Ticket, TicketMessage, TicketAssignment
from app.models.knowledge import KnowledgeDocument
from app.models.ai import ActionProposal
from app.services.auth_service import hash_password
from app.services.audit_service import record_audit_event
from app.services.knowledge_service import create_document_from_text, ingest_document

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("seed")

DEFAULT_PASSWORD = "SupportPilot2026!"

def utc_now() -> datetime:
    return datetime.now(timezone.utc)


ACME_KNOWLEDGE_DOCUMENTS = [
    (
        "Refund & Duplicate Charge Policy",
        """Refund & Duplicate Charge Policy

Duplicate charges: if a customer is billed twice for the same invoice within a 24-hour window, the duplicate charge is refunded in full. Agents must verify both transactions in the billing ledger before proposing a refund. Refund proposals always require supervisor approval before money is returned.

Annual plans: annual subscriptions can be refunded within 14 days of renewal when the workspace has had no logins since the renewal date. After 14 days, annual charges are non-refundable, but the plan can be cancelled to stop future renewals.

Monthly plans and proration: when a workspace upgrades from monthly to annual billing mid-cycle, the unused portion of the current month is credited automatically on the next invoice. Downgrades take effect at the end of the current billing period.

Processing times: approved refunds are returned to the original payment method within 5 business days. Card issuers can take up to 10 business days to display the credit.

Refund limits: support agents may propose refunds up to $200. Anything above $200 needs a supervisor and is recorded in the approval queue.""",
    ),
    (
        "Shipping, Delivery & Damaged Orders",
        """Shipping, Delivery & Damaged Orders

Dispatch: orders placed before 2:00 PM local warehouse time ship the same business day. Next-day shipping guarantees delivery on the next business day, not on weekends or public holidays.

Tracking: tracking numbers are emailed as soon as the carrier scans the parcel. If tracking has not updated for 48 hours, open a carrier investigation with the order number and the last scan location.

Delays: weather events, customs holds and carrier hub backlogs can add 1-3 business days. Customers with a delayed next-day shipment are eligible for a shipping-fee refund; the product price is not refunded unless the parcel is lost.

Damaged or missing items: report damage within 48 hours of delivery with photos of the packaging and the item. Verified damage is replaced at no cost. Replacements above the agent auto-approval limit require supervisor sign-off.

Lost parcels: a parcel is considered lost after 10 business days without a scan update. Lost parcels are replaced or refunded after human approval.""",
    ),
    (
        "SAML 2.0 Single Sign-On with Okta",
        """SAML 2.0 Single Sign-On with Okta

Prerequisites: an Okta administrator account and the Enterprise plan.

Setup steps:
1. In SupportPilot, open Settings > Security > Single Sign-On and choose SAML 2.0.
2. Copy the SupportPilot Entity ID and the Assertion Consumer Service (ACS) URL.
3. In Okta, create a new SAML 2.0 application and paste both values.
4. Download the Okta identity provider metadata XML and upload it in SupportPilot, or paste the metadata URL.
5. Map the Okta email claim to the SupportPilot email attribute and set the Name ID format to emailAddress.
6. Assign the SupportPilot application to the required Okta groups, then enable SSO.

Testing: use the Test SSO button before enforcing SSO for everyone. Keep at least one admin with password login until SSO is verified.

Troubleshooting: the error "invalid identity provider" usually means the user's subject claim is missing after an identity migration. Re-sync the user in Okta or backfill the subject claim, then ask the user to sign in again.""",
    ),
    (
        "Nonprofit & Education Discounts",
        """Nonprofit & Education Discounts

Eligibility: registered 501(c)(3) nonprofits, accredited schools and universities, and public libraries qualify for 25% off the Team plan.

How to apply: send the determination letter or an official education verification document to billing@acme.com from the workspace owner's email address. The discount is applied to the next invoice and does not apply retroactively.

Renewal: discounted workspaces must re-verify eligibility every 12 months. If verification lapses, the workspace renews at list price.

Restrictions: the nonprofit rate cannot be combined with other promotions and applies to a single workspace per organization.

Enterprise: nonprofits needing SSO, audit logs or custom data retention should contact sales about the Enterprise nonprofit rate.""",
    ),
    (
        "Account Access & Password Reset",
        """Account Access & Password Reset

Password reset: use the Forgot password link on the sign-in page. The reset link expires after 30 minutes and can only be used once. If the email does not arrive, check spam and confirm the address on the account.

Locked accounts: five failed password attempts lock an account for 15 minutes. Admins can unlock a workspace member from Settings > Team.

SSO users: accounts that sign in through SAML do not have a SupportPilot password. Reset the password in the identity provider instead, then ask the user to sign in through the SSO button.

Two-factor authentication: admins can require 2FA for the whole workspace. Recovery codes are shown once when 2FA is enabled; store them securely.

Suspicious activity: if a user reports unexpected logins, an admin should revoke active sessions from Settings > Security and rotate API keys. Escalate confirmed account takeover attempts to the security team immediately.""",
    ),
]

BETA_KNOWLEDGE_DOCUMENTS = [
    (
        "Beta Industries Returns Policy",
        """Beta Industries Returns Policy

Customers may return unused items within 30 days of delivery for a refund. Items must be in original packaging. Return shipping is free for defective products and paid by the customer otherwise.

Custom and clearance items are final sale. Refunds are issued to the original payment method within 7 business days after the warehouse inspects the return.""",
    ),
]


async def seed_knowledge_documents(db, workspace_id: str, user_id, documents):
    """Creates and indexes demo knowledge documents idempotently."""
    for title, content in documents:
        existing = await db.execute(
            select(KnowledgeDocument).where(
                KnowledgeDocument.workspace_id == workspace_id,
                KnowledgeDocument.title == title,
            )
        )
        document = existing.scalar_one_or_none()
        if document:
            if document.status != "indexed":
                await ingest_document(db, workspace_id, document.id)
                logger.info("Reindexed knowledge document: %s", title)
            continue

        created = await create_document_from_text(
            db, workspace_id, user_id, title=title, content=content
        )
        indexed = await ingest_document(db, workspace_id, created.id)
        if indexed.status == "indexed":
            logger.info("Seeded knowledge document: %s (%s chunks)", title, indexed.chunk_count)
        else:
            logger.warning("Knowledge document failed to index: %s (%s)", title, indexed.error_message)

async def seed_data():
    logger.info("Starting database seeding...")
    async with AsyncSessionLocal() as db:
        # 1. Primary Workspace: Acme Corp
        res = await db.execute(select(Workspace).where(Workspace.slug == "acme-corp"))
        acme_ws = res.scalar_one_or_none()
        if not acme_ws:
            acme_ws = Workspace(
                name="Acme Corp Support",
                slug="acme-corp",
                is_active=True,
            )
            db.add(acme_ws)
            await db.flush()
            logger.info("Created Acme Corp workspace.")

            ws_settings = WorkspaceSettings(
                workspace_id=acme_ws.id,
                llm_provider="mock",
                llm_model="mock-gpt-4o",
                embedding_provider="mock",
                embedding_dimension=1536,
                similarity_threshold=0.72,
                auto_escalate_urgency_threshold=0.85,
                proposal_expiry_hours=24,
            )
            db.add(ws_settings)

        # 2. Seed Admin: admin@acme.com
        res = await db.execute(select(User).where(User.email == "admin@acme.com"))
        admin_user = res.scalar_one_or_none()
        if not admin_user:
            admin_user = User(
                email="admin@acme.com",
                password_hash=hash_password(DEFAULT_PASSWORD),
                full_name="Alice Admin",
                is_active=True,
            )
            db.add(admin_user)
            await db.flush()
            logger.info("Created admin user: admin@acme.com")

        # Admin Membership
        res = await db.execute(
            select(WorkspaceMembership).where(
                WorkspaceMembership.workspace_id == acme_ws.id,
                WorkspaceMembership.user_id == admin_user.id,
            )
        )
        if not res.scalar_one_or_none():
            db.add(WorkspaceMembership(workspace_id=acme_ws.id, user_id=admin_user.id, role="admin"))

        # 3. Seed Support Agent: agent@acme.com
        res = await db.execute(select(User).where(User.email == "agent@acme.com"))
        agent_user = res.scalar_one_or_none()
        if not agent_user:
            agent_user = User(
                email="agent@acme.com",
                password_hash=hash_password(DEFAULT_PASSWORD),
                full_name="Bob Support",
                is_active=True,
            )
            db.add(agent_user)
            await db.flush()
            logger.info("Created agent user: agent@acme.com")

        # Agent Membership
        res = await db.execute(
            select(WorkspaceMembership).where(
                WorkspaceMembership.workspace_id == acme_ws.id,
                WorkspaceMembership.user_id == agent_user.id,
            )
        )
        if not res.scalar_one_or_none():
            db.add(WorkspaceMembership(workspace_id=acme_ws.id, user_id=agent_user.id, role="support_agent"))

        # 4. Seed Customer: customer@acme.com
        res = await db.execute(
            select(Customer).where(
                Customer.workspace_id == acme_ws.id,
                Customer.email == "customer@acme.com",
            )
        )
        charlie_cust = res.scalar_one_or_none()
        if not charlie_cust:
            charlie_cust = Customer(
                workspace_id=acme_ws.id,
                email="customer@acme.com",
                name="Charlie Customer",
                external_reference="CUST-9821",
            )
            db.add(charlie_cust)
            await db.flush()
            logger.info("Created demo customer: customer@acme.com")

        # 5. Isolation Testing Workspace: Beta Industries
        res = await db.execute(select(Workspace).where(Workspace.slug == "beta-industries"))
        beta_ws = res.scalar_one_or_none()
        if not beta_ws:
            beta_ws = Workspace(
                name="Beta Industries",
                slug="beta-industries",
                is_active=True,
            )
            db.add(beta_ws)
            await db.flush()

            db.add(WorkspaceSettings(workspace_id=beta_ws.id))

            res = await db.execute(select(User).where(User.email == "admin@beta.com"))
            beta_admin = res.scalar_one_or_none()
            if not beta_admin:
                beta_admin = User(
                    email="admin@beta.com",
                    password_hash=hash_password(DEFAULT_PASSWORD),
                    full_name="Bella Beta",
                    is_active=True,
                )
                db.add(beta_admin)
                await db.flush()

            db.add(WorkspaceMembership(workspace_id=beta_ws.id, user_id=beta_admin.id, role="admin"))
            logger.info("Created Beta Industries workspace and admin.")

        # 6. Seed Demo Tickets in Acme Corp
        t1_check = await db.execute(select(Ticket).where(Ticket.workspace_id == acme_ws.id, Ticket.ticket_number == 1001))
        if not t1_check.scalar_one_or_none():
            ticket1 = Ticket(
                workspace_id=acme_ws.id,
                ticket_number=1001,
                customer_id=charlie_cust.id,
                assigned_agent_id=agent_user.id,
                subject="Subscription renewal billed twice on corporate card",
                description="Our finance department noticed two charges of $149 on our Amex card for this month's renewal. Can you please check and refund the extra charge?",
                status="pending_approval",
                priority="urgent",
                category="billing",
                ai_intent="duplicate_charge_refund",
                ai_confidence=0.96,
                ai_sentiment="concerned",
                ai_summary="Customer was charged $149 twice on Oct 24th for Invoice #INV-9821. Recommending full refund of duplicate charge.",
                created_at=utc_now() - timedelta(hours=3),
                updated_at=utc_now() - timedelta(minutes=45),
            )
            db.add(ticket1)
            await db.flush()

            # Messages
            db.add(TicketMessage(
                workspace_id=acme_ws.id,
                ticket_id=ticket1.id,
                sender_type="customer",
                sender_customer_id=charlie_cust.id,
                body="Our finance department noticed two charges of $149 on our Amex card for this month's renewal. Can you please check and refund the extra charge?",
                is_internal_note=False,
                created_at=utc_now() - timedelta(hours=3),
            ))
            db.add(TicketMessage(
                workspace_id=acme_ws.id,
                ticket_id=ticket1.id,
                sender_type="agent",
                sender_user_id=agent_user.id,
                body="Verified Stripe ledger. Indeed two charges with transaction IDs tx_101 and tx_102 occurred within 4 seconds due to a network retry glitch. Proposing refund proposal.",
                is_internal_note=True,
                created_at=utc_now() - timedelta(hours=2),
            ))
            db.add(TicketMessage(
                workspace_id=acme_ws.id,
                ticket_id=ticket1.id,
                sender_type="agent",
                sender_user_id=agent_user.id,
                body="Hello Charlie, thank you for reaching out. We have confirmed the duplicate charge in our billing ledger and our supervisor is reviewing the refund authorization right now.",
                is_internal_note=False,
                created_at=utc_now() - timedelta(minutes=45),
            ))
            logger.info("Seeded Ticket #1001 with messages and internal notes.")

        t2_check = await db.execute(select(Ticket).where(Ticket.workspace_id == acme_ws.id, Ticket.ticket_number == 1002))
        if not t2_check.scalar_one_or_none():
            ticket2 = Ticket(
                workspace_id=acme_ws.id,
                ticket_number=1002,
                customer_id=charlie_cust.id,
                assigned_agent_id=agent_user.id,
                subject="Expedited shipping delay on Order #ORD-4412",
                description="I paid for next-day shipping yesterday morning but the tracking hasn't updated since Chicago. When will it arrive?",
                status="in_progress",
                priority="high",
                category="shipping",
                ai_intent="shipping_inquiry",
                ai_confidence=0.89,
                ai_summary="Package delayed in transit due to winter storm in Chicago hub. Estimated delivery updated to tomorrow morning.",
                created_at=utc_now() - timedelta(hours=5),
                updated_at=utc_now() - timedelta(hours=1),
            )
            db.add(ticket2)
            await db.flush()

            db.add(TicketMessage(
                workspace_id=acme_ws.id,
                ticket_id=ticket2.id,
                sender_type="customer",
                sender_customer_id=charlie_cust.id,
                body="I paid for next-day shipping yesterday morning but the tracking hasn't updated since Chicago. When will it arrive?",
                is_internal_note=False,
                created_at=utc_now() - timedelta(hours=5),
            ))
            db.add(TicketMessage(
                workspace_id=acme_ws.id,
                ticket_id=ticket2.id,
                sender_type="agent",
                sender_user_id=agent_user.id,
                body="Hi Charlie, I checked with our carrier logistics team. The shipment is on vehicle out of the local sorting facility now.",
                is_internal_note=False,
                created_at=utc_now() - timedelta(hours=1),
            ))
            logger.info("Seeded Ticket #1002.")

        t3_check = await db.execute(select(Ticket).where(Ticket.workspace_id == acme_ws.id, Ticket.ticket_number == 1003))
        if not t3_check.scalar_one_or_none():
            ticket3 = Ticket(
                workspace_id=acme_ws.id,
                ticket_number=1003,
                customer_id=charlie_cust.id,
                assigned_agent_id=None,
                subject="How do I configure SAML SSO with Okta?",
                description="We are rolling out SupportPilot across our enterprise. Where can we input our Okta metadata XML URL to enable SAML 2.0?",
                status="open",
                priority="medium",
                category="technical_issues",
                ai_intent="sso_configuration",
                ai_confidence=0.92,
                ai_summary="Customer asking for SAML/SSO setup documentation with Okta provider.",
                created_at=utc_now() - timedelta(hours=1),
                updated_at=utc_now() - timedelta(hours=1),
            )
            db.add(ticket3)
            await db.flush()

            db.add(TicketMessage(
                workspace_id=acme_ws.id,
                ticket_id=ticket3.id,
                sender_type="customer",
                sender_customer_id=charlie_cust.id,
                body="We are rolling out SupportPilot across our enterprise. Where can we input our Okta metadata XML URL to enable SAML 2.0?",
                is_internal_note=False,
                created_at=utc_now() - timedelta(hours=1),
            ))
            logger.info("Seeded Ticket #1003.")

        # 7. Additional demo customers (workspace-scoped, idempotent)
        demo_customers = [
            ("priya@example.com", "Priya Patel", "CUST-4410"),
            ("marcus@example.com", "Marcus Webb", "CUST-7731"),
            ("dana@northwind.io", "Dana Whitfield", "CUST-1188"),
        ]
        customer_by_email = {"customer@acme.com": charlie_cust}
        for email, name, external_ref in demo_customers:
            res = await db.execute(
                select(Customer).where(Customer.workspace_id == acme_ws.id, Customer.email == email)
            )
            cust = res.scalar_one_or_none()
            if not cust:
                cust = Customer(
                    workspace_id=acme_ws.id,
                    email=email,
                    name=name,
                    external_reference=external_ref,
                )
                db.add(cust)
                await db.flush()
                logger.info("Created demo customer: %s", email)
            customer_by_email[email] = cust

        # 8. Additional demo tickets covering every status/priority/category band
        demo_tickets = [
            {
                "number": 1004,
                "customer": "marcus@example.com",
                "assigned": agent_user.id,
                "subject": "Locked out after SSO migration",
                "description": "Since the Okta migration this morning my account returns 'invalid identity provider'. I need access to close month-end books.",
                "status": "in_progress",
                "priority": "high",
                "category": "account_access",
                "ai_intent": "login_failure",
                "ai_confidence": 0.93,
                "ai_sentiment": "frustrated",
                "ai_summary": "Customer locked out after Okta SSO cutover. Identity mapping likely missing the user's new subject claim.",
                "age_hours": 8,
                "messages": [
                    (
                        "customer",
                        "Since the Okta migration this morning my account returns 'invalid identity provider'. I need access to close month-end books.",
                        False,
                        8,
                    ),
                    (
                        "agent",
                        "Confirmed: their legacy subject claim was not carried over. Engineering has been asked to backfill it before the 5pm batch.",
                        True,
                        7,
                    ),
                    (
                        "agent",
                        "Hi Marcus, we found the identity mapping gap and are backfilling your Okta subject claim. I will confirm here as soon as the sync completes.",
                        False,
                        6,
                    ),
                ],
            },
            {
                "number": 1005,
                "customer": "priya@example.com",
                "assigned": agent_user.id,
                "subject": "Order #ORD-8891 arrived damaged",
                "description": "The ceramic pour-over set arrived with two cracked cones. Photos attached to the original email.",
                "status": "escalated",
                "priority": "high",
                "category": "orders",
                "ai_intent": "damaged_goods",
                "ai_confidence": 0.91,
                "ai_sentiment": "disappointed",
                "ai_summary": "Damaged shipment reported with photo evidence. Replacement or refund requires supervisor sign-off above the auto-approval limit.",
                "escalated": True,
                "escalation_reason": "Replacement value exceeds the agent auto-approval limit; supervisor review required.",
                "age_hours": 26,
                "messages": [
                    (
                        "customer",
                        "The ceramic pour-over set arrived with two cracked cones. Photos attached to the original email.",
                        False,
                        26,
                    ),
                    (
                        "agent",
                        "Photos verified against the packing checklist. Replacement value is above my approval limit, escalating for supervisor sign-off.",
                        True,
                        25,
                    ),
                ],
            },
            {
                "number": 1006,
                "customer": "priya@example.com",
                "assigned": None,
                "subject": "Move us to the annual plan mid-cycle",
                "description": "We are on monthly billing but want to switch to annual now. Will the remaining month be prorated?",
                "status": "open",
                "priority": "medium",
                "category": "billing",
                "ai_intent": "plan_change",
                "ai_confidence": 0.84,
                "ai_sentiment": "neutral",
                "ai_summary": "Customer asks about proration when switching from monthly to annual billing mid-cycle.",
                "age_hours": 2,
                "messages": [
                    (
                        "customer",
                        "We are on monthly billing but want to switch to annual now. Will the remaining month be prorated?",
                        False,
                        2,
                    ),
                ],
            },
            {
                "number": 1007,
                "customer": "dana@northwind.io",
                "assigned": agent_user.id,
                "subject": "Nonprofit discount eligibility",
                "description": "Northwind is a registered 501(c)(3). Do you offer a nonprofit rate for the team plan?",
                "status": "waiting_for_customer",
                "priority": "low",
                "category": "product_questions",
                "ai_intent": "pricing_question",
                "ai_confidence": 0.88,
                "ai_sentiment": "positive",
                "ai_summary": "Prospective nonprofit customer asking about discounted team pricing.",
                "age_hours": 30,
                "messages": [
                    (
                        "customer",
                        "Northwind is a registered 501(c)(3). Do you offer a nonprofit rate for the team plan?",
                        False,
                        30,
                    ),
                    (
                        "agent",
                        "Hi Dana, yes. Please send your 501(c)(3) determination letter and I will attach the discount to your account.",
                        False,
                        28,
                    ),
                ],
            },
            {
                "number": 1008,
                "customer": "marcus@example.com",
                "assigned": agent_user.id,
                "subject": "Accidental annual renewal refund",
                "description": "I meant to downgrade before renewal and was charged for a full year. Please refund the annual charge.",
                "status": "pending_approval",
                "priority": "urgent",
                "category": "refunds",
                "ai_intent": "refund_request",
                "ai_confidence": 0.95,
                "ai_sentiment": "concerned",
                "ai_summary": "Renewal completed 6 days ago for an unused annual plan. A refund proposal is awaiting agent approval.",
                "age_hours": 4,
                "messages": [
                    (
                        "customer",
                        "I meant to downgrade before renewal and was charged for a full year. Please refund the annual charge.",
                        False,
                        4,
                    ),
                    (
                        "agent",
                        "Renewal date confirmed as 6 days ago and the workspace has no logins since. Refund proposal created for approval.",
                        True,
                        3,
                    ),
                    (
                        "agent",
                        "Hi Marcus, I have submitted the refund for approval. You will hear from us as soon as it is authorised.",
                        False,
                        2,
                    ),
                ],
            },
        ]

        for spec in demo_tickets:
            existing = await db.execute(
                select(Ticket).where(
                    Ticket.workspace_id == acme_ws.id,
                    Ticket.ticket_number == spec["number"],
                )
            )
            if existing.scalar_one_or_none():
                continue

            customer = customer_by_email[spec["customer"]]
            created = utc_now() - timedelta(hours=spec["age_hours"])
            ticket = Ticket(
                workspace_id=acme_ws.id,
                ticket_number=spec["number"],
                customer_id=customer.id,
                assigned_agent_id=spec["assigned"],
                subject=spec["subject"],
                description=spec["description"],
                status=spec["status"],
                priority=spec["priority"],
                category=spec["category"],
                ai_intent=spec.get("ai_intent"),
                ai_confidence=spec.get("ai_confidence"),
                ai_sentiment=spec.get("ai_sentiment"),
                ai_summary=spec.get("ai_summary"),
                is_escalated=spec.get("escalated", False),
                escalation_reason=spec.get("escalation_reason"),
                created_at=created,
                updated_at=created + timedelta(hours=1),
            )
            db.add(ticket)
            await db.flush()

            for sender_type, body, is_note, hours_ago in spec["messages"]:
                db.add(
                    TicketMessage(
                        workspace_id=acme_ws.id,
                        ticket_id=ticket.id,
                        sender_type=sender_type,
                        sender_user_id=agent_user.id if sender_type == "agent" else None,
                        sender_customer_id=customer.id if sender_type == "customer" else None,
                        body=body,
                        is_internal_note=is_note,
                        created_at=utc_now() - timedelta(hours=hours_ago),
                    )
                )

            if spec["assigned"]:
                db.add(
                    TicketAssignment(
                        workspace_id=acme_ws.id,
                        ticket_id=ticket.id,
                        assigned_by_user_id=admin_user.id,
                        assigned_to_user_id=spec["assigned"],
                        reason="Seeded demo assignment",
                        created_at=created + timedelta(minutes=15),
                    )
                )
            logger.info("Seeded Ticket #%s.", spec["number"])

        # 8b. Phase 5 demo action proposals awaiting human approval.
        proposal_specs = [
            {
                "ticket_number": 1008,
                "action_type": "issue_refund",
                "params": {
                    "amount": 348.00,
                    "currency": "USD",
                    "reason": "Annual plan renewed 6 days ago without any usage.",
                },
                "rationale": (
                    "Customer downgraded in intent but the annual renewal still charged. "
                    "Refund is within policy and the account has no logins since renewal."
                ),
                "ai_confidence": 0.93,
                "expires_hours": 20,
            },
            {
                "ticket_number": 1005,
                "action_type": "issue_refund",
                "params": {
                    "amount": 640.00,
                    "currency": "USD",
                    "reason": "Damaged replacement order requires a full refund above the agent limit.",
                },
                "rationale": (
                    "Replacement value exceeds the $250 agent auto-approval limit, so an Admin "
                    "must approve the refund before funds are returned."
                ),
                "ai_confidence": 0.88,
                "expires_hours": 18,
            },
        ]

        for spec in proposal_specs:
            ticket_res = await db.execute(
                select(Ticket).where(
                    Ticket.workspace_id == acme_ws.id,
                    Ticket.ticket_number == spec["ticket_number"],
                )
            )
            ticket = ticket_res.scalar_one_or_none()
            if not ticket:
                continue
            existing_proposal = await db.execute(
                select(ActionProposal).where(
                    ActionProposal.workspace_id == acme_ws.id,
                    ActionProposal.ticket_id == ticket.id,
                    ActionProposal.action_type == spec["action_type"],
                )
            )
            if existing_proposal.scalar_one_or_none():
                continue

            created = utc_now()
            proposal = ActionProposal(
                workspace_id=acme_ws.id,
                ticket_id=ticket.id,
                proposed_by_ai_provider="mock",
                action_type=spec["action_type"],
                action_params_json=json.dumps(spec["params"]),
                rationale=spec["rationale"],
                ai_confidence=spec["ai_confidence"],
                status="pending",
                created_at=created,
                expires_at=created + timedelta(hours=spec["expires_hours"]),
            )
            db.add(proposal)
            await db.flush()
            await record_audit_event(
                db,
                workspace_id=acme_ws.id,
                event_category="proposal",
                event_type="proposal_created",
                actor=agent_user,
                ticket_id=ticket.id,
                proposal_id=proposal.id,
                details={
                    "action_type": spec["action_type"],
                    "params": spec["params"],
                    "source": "seed",
                },
            )
            logger.info("Seeded proposal for Ticket #%s.", spec["ticket_number"])

        # 9. Phase 3 knowledge base documents (chunked + embedded for RAG)
        await seed_knowledge_documents(db, acme_ws.id, admin_user.id, ACME_KNOWLEDGE_DOCUMENTS)

        beta_admin_res = await db.execute(select(User).where(User.email == "admin@beta.com"))
        beta_admin_user = beta_admin_res.scalar_one_or_none()
        await seed_knowledge_documents(
            db,
            beta_ws.id,
            beta_admin_user.id if beta_admin_user else None,
            BETA_KNOWLEDGE_DOCUMENTS,
        )

        await db.commit()
    logger.info("Seeding completed successfully.")

if __name__ == "__main__":
    asyncio.run(seed_data())
