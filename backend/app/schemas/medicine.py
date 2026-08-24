from typing import List, Optional
from pydantic import BaseModel, Field


class MedicineSearchResultItem(BaseModel):
    rxcui: str = Field(..., description="RxNorm Concept Unique Identifier")
    name: str = Field(..., description="Standardized medicine name")
    generic_name: Optional[str] = Field(None, description="Active ingredient or generic name")
    synonym: Optional[str] = Field(None, description="Common synonym or brand name")
    dosage_form: Optional[str] = Field(None, description="Dosage form e.g. Oral Tablet, Capsule")
    source: str = Field("RxNorm", description="Official terminology provider source")


class MedicineSearchResponse(BaseModel):
    query: str
    total_results: int
    results: List[MedicineSearchResultItem]
    did_you_mean: Optional[str] = None


class MedicineDetailSource(BaseModel):
    name: str = Field(..., description="Source name, e.g., RxNorm, DailyMed / U.S. FDA SPL")
    type: str = Field(..., description="official_label, rxnorm_concept")
    url: Optional[str] = None


class MedicineDetailResponse(BaseModel):
    rxcui: str
    name: str
    generic_name: Optional[str] = None
    brand_names: List[str] = []
    active_ingredients: List[str] = []
    uses: List[str] = []
    dosage_forms: List[str] = []
    warnings: List[str] = []
    source: MedicineDetailSource
    availability: str = Field(
        ...,
        description="official_information_available | identified_basic_only | not_found",
    )
    disclaimer: str = Field(
        default=(
            "This information is provided for general educational purposes only and is not "
            "a substitute for advice, diagnosis, or treatment by a qualified healthcare professional."
        ),
        description="Standard medical safety disclaimer",
    )
    ai_summary: Optional[str] = Field(None, description="Optional simplified educational summary")
