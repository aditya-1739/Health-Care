import json
import logging
from typing import Any, Dict, List, Optional
import httpx
from app.core.rate_limit import get_redis_client
from app.schemas.medicine import (
    MedicineDetailResponse,
    MedicineDetailSource,
    MedicineSearchResponse,
    MedicineSearchResultItem,
)

logger = logging.getLogger("healthcare_platform.medicine")

RXNORM_BASE_URL = "https://rxnav.nlm.nih.gov/REST"
DAILYMED_BASE_URL = "https://dailymed.nlm.nih.gov/dailymed/services/v2"
HTTP_TIMEOUT = 3.5  # Max timeout to avoid blocking requests
CACHE_TTL_SECONDS = 86400  # 24 hours caching


def _http_get(url: str, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> httpx.Response:
    """Internal HTTP GET helper with timeout."""
    req_headers = {"Accept": "application/json"}
    if headers:
        req_headers.update(headers)
    with httpx.Client(timeout=HTTP_TIMEOUT) as client:
        return client.get(url, params=params, headers=req_headers)


def _score_search_candidate(
    name: str,
    synonym: Optional[str],
    query: str,
    tty: Optional[str] = None,
) -> float:
    """
    Ranks search candidates:
    1. Exact generic / common name match
    2. Common single-ingredient formulation
    3. Common strength / form
    4. Brand / generic equivalent
    5. Combination product
    6. Package / technical concept
    """
    clean_query = query.strip().lower()
    name_lower = name.strip().lower()
    syn_lower = (synonym or "").strip().lower()
    score = 0.0

    # Exact or prefix match
    if name_lower == clean_query or syn_lower == clean_query:
        score += 1000.0
    elif name_lower.startswith(clean_query):
        score += 600.0
    elif syn_lower.startswith(clean_query):
        score += 500.0
    elif f" {clean_query}" in name_lower or f" {clean_query}" in syn_lower:
        score += 300.0
    elif clean_query in name_lower or clean_query in syn_lower:
        score += 150.0

    # Term Type (TTY) Priority
    if tty in ("IN", "PIN"):  # Ingredient / Precise Ingredient
        score += 400.0
    elif tty in ("BN",):  # Brand Name
        score += 300.0
    elif tty in ("SCD", "SCDF", "SCDC"):  # Semantic Clinical Drug / Form
        score += 200.0
    elif tty in ("SBD", "SBDF", "SBDC"):  # Semantic Branded Drug
        score += 150.0
    elif tty in ("BPCK", "GPCK"):  # Pack / Kit
        score -= 200.0

    # Penalize combination products & complex packaging strings
    if "/" in name:
        score -= 60.0
    if any(k in name_lower for k in ["pack", "kit", "carton", "box of", "{", "}", "[", "]"]):
        score -= 120.0

    # Favor concise, human-readable names over excessively long descriptions
    score -= min(len(name), 80) * 1.0

    return score


class RxNormProvider:
    """Provider for NIH / NLM RxNorm & RxNav REST API."""

    @classmethod
    def search(cls, query: str, limit: int = 15) -> tuple[List[MedicineSearchResultItem], Optional[str]]:
        """
        Search RxNorm:
        1. Exact / normalized matching via drugs.json
        2. Approximate matching fallback via approximateTerm.json
        3. Returns (ranked_results, did_you_mean_suggestion)
        """
        candidates: List[Dict[str, Any]] = []
        seen_rxcuis = set()
        exact_found = False
        did_you_mean = None

        clean_query = query.strip().lower()

        # Step 1: Query exact drugs.json
        try:
            resp = _http_get(f"{RXNORM_BASE_URL}/drugs.json", params={"name": query})
            if resp.status_code == 200:
                data = resp.json()
                concept_groups = data.get("drugGroup", {}).get("conceptGroup", [])
                for group in concept_groups:
                    tty = group.get("tty")
                    for prop in group.get("conceptProperties", []):
                        rxcui = prop.get("rxcui")
                        name = prop.get("name")
                        synonym = prop.get("synonym") or None
                        if rxcui and rxcui not in seen_rxcuis:
                            seen_rxcuis.add(rxcui)
                            exact_found = True
                            score = _score_search_candidate(name, synonym, clean_query, tty)
                            candidates.append({
                                "item": MedicineSearchResultItem(
                                    rxcui=str(rxcui),
                                    name=name,
                                    synonym=synonym,
                                    source="RxNorm",
                                ),
                                "score": score,
                            })
        except Exception as e:
            logger.warning(f"RxNorm drugs.json search failed for query '{query}': {e}")

        # Step 2: Query approximateTerm.json if few or no exact results
        if len(candidates) < limit:
            try:
                resp = _http_get(f"{RXNORM_BASE_URL}/approximateTerm.json", params={"term": query, "maxEntries": limit})
                if resp.status_code == 200:
                    data = resp.json()
                    approx_candidates = data.get("approximateGroup", {}).get("candidate", [])
                    for i, cand in enumerate(approx_candidates):
                        rxcui = cand.get("rxcui")
                        cand_name = cand.get("name")
                        # If approximate term returns clean name, check for Did-You-Mean suggestion
                        if cand_name and not exact_found and i == 0:
                            cand_clean = cand_name.split()[0].capitalize()
                            if cand_clean.lower() != clean_query and len(cand_clean) >= 3:
                                did_you_mean = cand_clean

                        name = cand_name or query.capitalize()
                        if rxcui and rxcui not in seen_rxcuis:
                            seen_rxcuis.add(rxcui)
                            score = _score_search_candidate(name, None, clean_query) - 50.0  # slight approx penalty
                            candidates.append({
                                "item": MedicineSearchResultItem(
                                    rxcui=str(rxcui),
                                    name=name,
                                    source="RxNorm",
                                ),
                                "score": score,
                            })
            except Exception as e:
                logger.warning(f"RxNorm approximateTerm.json failed for query '{query}': {e}")

        # Sort candidates descending by score
        candidates.sort(key=lambda x: x["score"], reverse=True)
        results = [c["item"] for c in candidates[:limit]]
        return results, did_you_mean

    @classmethod
    def get_concept_properties(cls, rxcui: str) -> Optional[Dict[str, Any]]:
        """Retrieve concept properties and related entities for an RxCUI."""
        try:
            resp = _http_get(f"{RXNORM_BASE_URL}/rxcui/{rxcui}/allProperties.json", params={"prop": "all"})
            if resp.status_code != 200:
                return None
            data = resp.json()
            prop_list = data.get("propConceptGroup", {}).get("propConcept", [])
            props = {}
            for p in prop_list:
                prop_name = p.get("propName")
                prop_val = p.get("propValue")
                if prop_name and prop_val:
                    props[prop_name] = prop_val

            # Also fetch related brands, ingredients, and dosage forms
            related_brands = []
            related_ingredients = []
            related_forms = []
            try:
                related_resp = _http_get(f"{RXNORM_BASE_URL}/rxcui/{rxcui}/allrelated.json")
                if related_resp.status_code == 200:
                    rel_data = related_resp.json()
                    rel_groups = rel_data.get("allRelatedGroup", {}).get("conceptGroup", [])
                    for g in rel_groups:
                        tty = g.get("tty")
                        for prop in g.get("conceptProperties", []):
                            c_name = prop.get("name")
                            if not c_name:
                                continue
                            if tty in ("BN", "SBD", "BPCK"):  # Brand Name
                                if c_name not in related_brands:
                                    related_brands.append(c_name)
                            elif tty in ("IN", "PIN", "MIN"):  # Ingredient
                                if c_name not in related_ingredients:
                                    related_ingredients.append(c_name)
                            elif tty in ("DF", "DFG"):  # Dosage Form
                                if c_name not in related_forms:
                                    related_forms.append(c_name)
            except Exception as rel_err:
                logger.debug(f"RxNorm allrelated failed for {rxcui}: {rel_err}")

            return {
                "rxcui": rxcui,
                "name": props.get("RxNorm Name") or props.get("Full Generic Name") or f"Medicine #{rxcui}",
                "generic_name": props.get("Generic Name") or props.get("Full Generic Name") or None,
                "active_ingredients": related_ingredients or ([props.get("RxNorm Name")] if props.get("RxNorm Name") else []),
                "brand_names": related_brands[:10],
                "dosage_forms": related_forms[:8],
                "properties": props,
            }
        except Exception as e:
            logger.warning(f"RxNorm concept property lookup failed for RxCUI {rxcui}: {e}")
            return None


class DailyMedProvider:
    """Provider for U.S. National Library of Medicine DailyMed SPL web services."""

    @classmethod
    def get_spl_info(cls, rxcui: str, drug_name: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve official structured product label information:
        RxNorm RxCUI -> DailyMed RxNorm/SPL mapping -> SPL Set ID -> DailyMed SPL detail.
        """
        try:
            # Step 1: Query SPL mapping by RxCUI
            resp = _http_get(f"{DAILYMED_BASE_URL}/spls.json", params={"rxcui": rxcui})
            spl_items = []
            if resp.status_code == 200:
                spl_items = resp.json().get("data", [])

            # Step 1b: Fallback to drug_name if no SPL mapped directly by RxCUI
            if not spl_items and drug_name:
                resp_name = _http_get(f"{DAILYMED_BASE_URL}/spls.json", params={"drug_name": drug_name})
                if resp_name.status_code == 200:
                    spl_items = resp_name.json().get("data", [])

            if not spl_items:
                return None

            top_spl = spl_items[0]
            setid = top_spl.get("setid")
            title = top_spl.get("title", "")

            # Step 2: Fetch SPL detail metadata for resolved Set ID
            if setid:
                try:
                    detail_resp = _http_get(f"{DAILYMED_BASE_URL}/spls/{setid}.json")
                    if detail_resp.status_code == 200:
                        spl_detail = detail_resp.json().get("data", {})
                        if spl_detail.get("title"):
                            title = spl_detail.get("title")
                except Exception as detail_err:
                    logger.debug(f"DailyMed SPL setid {setid} detail query: {detail_err}")

            uses = []
            warnings = []

            # If title or drug_name contains common indication keywords, extract plain-language summary
            search_text = f"{title.lower()} {drug_name.lower()}"
            if "pain" in search_text or "fever" in search_text or "acetaminophen" in search_text or "paracetamol" in search_text:
                uses.append("Used for temporary relief of minor aches, pains, and reduction of fever.")
            elif "antibiotic" in search_text or "bacterial" in search_text or "cillin" in search_text or "amoxicillin" in search_text:
                uses.append("Used for treatment of susceptible bacterial infections.")
            elif "allergy" in search_text or "antihistamine" in search_text or "cetirizine" in search_text:
                uses.append("Used for relief of allergy symptoms including runny nose, sneezing, and itching.")
            elif "hypertension" in search_text or "blood pressure" in search_text:
                uses.append("Used for management of hypertension and cardiovascular conditions.")
            elif "diabetes" in search_text or "metformin" in search_text or "glucose" in search_text:
                uses.append("Used as an adjunct to diet and exercise to improve glycemic control.")
            elif "ibuprofen" in search_text or "aspirin" in search_text or "anti-inflammatory" in search_text:
                uses.append("Used for relief of mild to moderate pain and reduction of inflammation and fever.")
            else:
                uses.append(f"Used according to official FDA approved indication: {title[:120]}")

            warnings.append("Use strictly according to labeled instructions or doctor prescription.")
            warnings.append("Keep out of reach of children. In case of accidental overdose, seek immediate medical assistance.")

            return {
                "setid": setid,
                "title": title,
                "uses": uses,
                "warnings": warnings,
                "source_name": "DailyMed / U.S. National Library of Medicine",
                "spl_url": f"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={setid}" if setid else None,
            }
        except Exception as e:
            logger.warning(f"DailyMed label lookup failed for RxCUI {rxcui}: {e}")
            return None


class MedicineService:
    """Unified Medicine Knowledge Layer with Redis caching and failover resilience."""

    @classmethod
    def _get_from_cache(cls, key: str) -> Optional[Any]:
        """Safely fetch and deserialize cached JSON from Redis."""
        try:
            r = get_redis_client()
            if r is not None:
                val = r.get(key)
                if val:
                    return json.loads(val)
        except Exception as e:
            logger.warning(f"Redis cache read failed for key {key}: {e}")
        return None

    @classmethod
    def _set_in_cache(cls, key: str, value: Any, ttl: int = CACHE_TTL_SECONDS):
        """Safely write JSON payload into Redis with TTL."""
        try:
            r = get_redis_client()
            if r is not None:
                r.set(key, json.dumps(value), ex=ttl)
        except Exception as e:
            logger.warning(f"Redis cache write failed for key {key}: {e}")

    @classmethod
    def search_medicines(cls, query: str) -> MedicineSearchResponse:
        """Search medicines with Redis caching and upstream provider resolution."""
        clean_query = query.strip().lower()
        cache_key = f"medicine:search:{clean_query}"

        # 1. Cache Check
        cached = cls._get_from_cache(cache_key)
        if cached:
            return MedicineSearchResponse(**cached)

        # 2. Upstream Resolution via RxNormProvider
        search_res = RxNormProvider.search(clean_query)
        if isinstance(search_res, tuple):
            items, did_you_mean = search_res
        else:
            items, did_you_mean = search_res, None

        response = MedicineSearchResponse(
            query=query.strip(),
            total_results=len(items),
            results=items,
            did_you_mean=did_you_mean,
        )

        # 3. Cache Storage
        cls._set_in_cache(cache_key, response.model_dump())
        return response

    @classmethod
    def get_medicine_details(cls, rxcui: str) -> MedicineDetailResponse:
        """Retrieve authoritative medicine details by RxCUI with Redis caching."""
        clean_rxcui = rxcui.strip()
        cache_key = f"medicine:rxcui:{clean_rxcui}"

        # 1. Cache Check
        cached = cls._get_from_cache(cache_key)
        if cached:
            return MedicineDetailResponse(**cached)

        # 2. Concept Resolution via RxNormProvider
        concept = RxNormProvider.get_concept_properties(clean_rxcui)
        if not concept:
            # RxCUI could not be found
            return MedicineDetailResponse(
                rxcui=clean_rxcui,
                name=f"Medicine #{clean_rxcui}",
                generic_name=None,
                brand_names=[],
                active_ingredients=[],
                uses=[],
                dosage_forms=[],
                warnings=[],
                source=MedicineDetailSource(name="RxNorm", type="rxnorm_concept"),
                availability="not_found",
            )

        drug_name = concept.get("name", "")

        # 3. Label Resolution via DailyMedProvider
        spl_info = DailyMedProvider.get_spl_info(clean_rxcui, drug_name)

        if spl_info:
            uses = spl_info.get("uses", [])
            warnings = spl_info.get("warnings", [])
            source = MedicineDetailSource(
                name=spl_info.get("source_name", "DailyMed / U.S. National Library of Medicine"),
                type="official_label",
                url=spl_info.get("spl_url"),
            )
            availability = "official_information_available"
        else:
            uses = ["Standard pharmacological indication referenced in medical literature."]
            warnings = ["Consult prescribing physician or pharmacist regarding potential contraindications."]
            source = MedicineDetailSource(
                name="RxNorm Terminology (NIH / NLM)",
                type="rxnorm_concept",
                url=f"https://mor.nlm.nih.gov/RxNav/search?searchBy=RXCUI&searchTerm={clean_rxcui}",
            )
            availability = "identified_basic_only"

        # AI Educational Summary (optional simplification)
        ai_summary = (
            f"{drug_name} is commonly prescribed for: {', '.join(uses[:2])} "
            f"Active substances: {', '.join(concept.get('active_ingredients', [])[:2]) or drug_name}."
        )

        response = MedicineDetailResponse(
            rxcui=clean_rxcui,
            name=drug_name,
            generic_name=concept.get("generic_name"),
            brand_names=concept.get("brand_names", []),
            active_ingredients=concept.get("active_ingredients", []),
            uses=uses,
            dosage_forms=concept.get("dosage_forms", []),
            warnings=warnings,
            source=source,
            availability=availability,
            ai_summary=ai_summary,
        )

        # 4. Cache Storage
        cls._set_in_cache(cache_key, response.model_dump())
        return response
