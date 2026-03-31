"""
RFP Router — Community requests for proposals and vendor bidding.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from uuid import uuid4
from datetime import datetime

from backend.database import get_db
from backend.models_civic import CommunityRFP, VendorProposal, InfrastructureProject

router = APIRouter()


def get_db_dep():
    yield from get_db()


# --- Schemas ---

class RFPCreate(BaseModel):
    project_id: str
    title: str
    description: Optional[str] = None
    vertical: str
    requirements: Optional[dict] = {}
    budget_min_usd: Optional[float] = None
    budget_max_usd: Optional[float] = None
    submission_deadline: Optional[str] = None
    created_by_id: Optional[str] = None


class ProposalSubmit(BaseModel):
    vendor_id: str
    solution_id: Optional[str] = None
    price_usd: float
    timeline_days: Optional[int] = None
    proposal_details: Optional[dict] = {}
    cover_letter: Optional[str] = None


class ProposalScore(BaseModel):
    score: float  # 0-100
    status: Optional[str] = None  # shortlisted, accepted, rejected


# --- RFP CRUD ---

@router.post("/rfps")
def create_rfp(rfp: RFPCreate, db: Session = Depends(get_db_dep)):
    """Create a new Request for Proposals."""
    project = db.query(InfrastructureProject).filter(InfrastructureProject.id == rfp.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    new_rfp = CommunityRFP(
        id=str(uuid4()),
        project_id=rfp.project_id,
        title=rfp.title,
        description=rfp.description,
        vertical=rfp.vertical,
        requirements=rfp.requirements,
        budget_min_usd=rfp.budget_min_usd,
        budget_max_usd=rfp.budget_max_usd,
        submission_deadline=datetime.fromisoformat(rfp.submission_deadline) if rfp.submission_deadline else None,
        created_by_id=rfp.created_by_id,
        status="open",
    )
    db.add(new_rfp)
    db.commit()

    return {
        "id": new_rfp.id,
        "title": new_rfp.title,
        "status": "open",
        "project_id": rfp.project_id,
        "message": f"RFP '{new_rfp.title}' published. Vendors can now submit proposals.",
    }


@router.get("/rfps")
def list_rfps(
    vertical: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(default=20, le=100),
    db: Session = Depends(get_db_dep),
):
    """List open RFPs for vendors to bid on."""
    query = db.query(CommunityRFP)
    if vertical:
        query = query.filter(CommunityRFP.vertical == vertical)
    if status:
        query = query.filter(CommunityRFP.status == status)
    else:
        query = query.filter(CommunityRFP.status == "open")

    rfps = query.order_by(CommunityRFP.created_at.desc()).limit(limit).all()

    return [
        {
            "id": r.id,
            "title": r.title,
            "vertical": r.vertical,
            "project_id": r.project_id,
            "budget_range": f"${r.budget_min_usd:,.0f} - ${r.budget_max_usd:,.0f}" if r.budget_min_usd and r.budget_max_usd else None,
            "deadline": r.submission_deadline.isoformat() if r.submission_deadline else None,
            "status": r.status,
            "proposal_count": len(r.proposals) if r.proposals else 0,
        }
        for r in rfps
    ]


@router.get("/rfps/{rfp_id}")
def get_rfp(rfp_id: str, db: Session = Depends(get_db_dep)):
    """Get RFP details with all proposals."""
    rfp = db.query(CommunityRFP).filter(CommunityRFP.id == rfp_id).first()
    if not rfp:
        raise HTTPException(status_code=404, detail="RFP not found")

    return {
        "id": rfp.id,
        "title": rfp.title,
        "description": rfp.description,
        "vertical": rfp.vertical,
        "project_id": rfp.project_id,
        "requirements": rfp.requirements,
        "budget_min_usd": rfp.budget_min_usd,
        "budget_max_usd": rfp.budget_max_usd,
        "deadline": rfp.submission_deadline.isoformat() if rfp.submission_deadline else None,
        "status": rfp.status,
        "proposals": [
            {
                "id": p.id,
                "vendor_id": p.vendor_id,
                "price_usd": p.price_usd,
                "timeline_days": p.timeline_days,
                "status": p.status,
                "score": p.score,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in (rfp.proposals or [])
        ],
    }


# --- Vendor Proposals ---

@router.post("/rfps/{rfp_id}/proposals")
def submit_proposal(rfp_id: str, proposal: ProposalSubmit, db: Session = Depends(get_db_dep)):
    """Submit a vendor proposal for an RFP."""
    rfp = db.query(CommunityRFP).filter(CommunityRFP.id == rfp_id).first()
    if not rfp:
        raise HTTPException(status_code=404, detail="RFP not found")
    if rfp.status != "open":
        raise HTTPException(status_code=400, detail="RFP is no longer accepting proposals")

    # Check for duplicate vendor submission
    existing = (
        db.query(VendorProposal)
        .filter(VendorProposal.rfp_id == rfp_id)
        .filter(VendorProposal.vendor_id == proposal.vendor_id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Vendor has already submitted a proposal")

    new_proposal = VendorProposal(
        id=str(uuid4()),
        rfp_id=rfp_id,
        vendor_id=proposal.vendor_id,
        solution_id=proposal.solution_id,
        price_usd=proposal.price_usd,
        timeline_days=proposal.timeline_days,
        proposal_details=proposal.proposal_details,
        cover_letter=proposal.cover_letter,
        status="submitted",
    )
    db.add(new_proposal)
    db.commit()

    return {
        "id": new_proposal.id,
        "rfp_id": rfp_id,
        "status": "submitted",
        "message": "Proposal submitted successfully.",
    }


@router.put("/rfps/{rfp_id}/proposals/{proposal_id}/evaluate")
def evaluate_proposal(
    rfp_id: str,
    proposal_id: str,
    evaluation: ProposalScore,
    db: Session = Depends(get_db_dep),
):
    """Score and update status of a vendor proposal."""
    proposal = (
        db.query(VendorProposal)
        .filter(VendorProposal.id == proposal_id)
        .filter(VendorProposal.rfp_id == rfp_id)
        .first()
    )
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")

    proposal.score = evaluation.score
    if evaluation.status:
        proposal.status = evaluation.status

    db.commit()

    return {
        "proposal_id": proposal_id,
        "score": evaluation.score,
        "status": proposal.status,
    }


@router.post("/rfps/{rfp_id}/award/{proposal_id}")
def award_rfp(rfp_id: str, proposal_id: str, db: Session = Depends(get_db_dep)):
    """Award an RFP to a specific vendor proposal."""
    rfp = db.query(CommunityRFP).filter(CommunityRFP.id == rfp_id).first()
    if not rfp:
        raise HTTPException(status_code=404, detail="RFP not found")

    proposal = (
        db.query(VendorProposal)
        .filter(VendorProposal.id == proposal_id)
        .filter(VendorProposal.rfp_id == rfp_id)
        .first()
    )
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")

    # Award the winner
    proposal.status = "accepted"
    rfp.status = "awarded"

    # Reject all other proposals
    other_proposals = (
        db.query(VendorProposal)
        .filter(VendorProposal.rfp_id == rfp_id)
        .filter(VendorProposal.id != proposal_id)
        .all()
    )
    for p in other_proposals:
        if p.status not in ["rejected"]:
            p.status = "rejected"

    db.commit()

    return {
        "rfp_id": rfp_id,
        "status": "awarded",
        "winner": {
            "proposal_id": proposal.id,
            "vendor_id": proposal.vendor_id,
            "price_usd": proposal.price_usd,
            "timeline_days": proposal.timeline_days,
        },
        "message": "RFP awarded. Other proposals have been notified.",
    }
