import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from app.core.rate_limit import rate_limiter
from app.schemas.medicine import MedicineDetailResponse, MedicineSearchResponse
from app.services.medicine_service import MedicineService

logger = logging.getLogger("healthcare_platform.medicine_api")

router = APIRouter(prefix="/medicines", tags=["Medicines"])


@router.get(
    "/search",
    response_model=MedicineSearchResponse,
    summary="Public medicine search and autocomplete",
    dependencies=[Depends(rate_limiter("medicine_public", max_requests=60, window_seconds=60))],
)
def search_medicines_endpoint(
    q: Optional[str] = Query(None, description="Medicine name or generic term (min 2 characters)"),
):
    """
    Publicly accessible medicine search and autocomplete endpoint powered by RxNorm.
    Does not require user authentication or JWT.
    """
    if not q or len(q.strip()) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Search query must contain at least 2 characters.",
        )

    clean_q = q.strip()
    if len(clean_q) > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Search query exceeds maximum length of 100 characters.",
        )

    return MedicineService.search_medicines(clean_q)


@router.get(
    "/{rxcui}",
    response_model=MedicineDetailResponse,
    summary="Public medicine detailed official information",
    dependencies=[Depends(rate_limiter("medicine_public", max_requests=60, window_seconds=60))],
)
def get_medicine_details_endpoint(
    rxcui: str,
):
    """
    Publicly accessible medicine details endpoint combining RxNorm terminology and DailyMed SPL labeling.
    Does not require user authentication or JWT.
    """
    clean_rxcui = rxcui.strip()
    if not clean_rxcui or len(clean_rxcui) > 30:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid RxCUI identifier.",
        )

    return MedicineService.get_medicine_details(clean_rxcui)
