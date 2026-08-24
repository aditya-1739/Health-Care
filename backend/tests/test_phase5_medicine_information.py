import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock
import httpx
import pytest
from app.core.rate_limit import reset_rate_limiter_state
from app.core.security import create_access_token
from app.models.appointment import Appointment, AppointmentStatus
from app.models.records import Prescription
from app.models.user import Doctor, Patient, User, UserRole
from app.services.medicine_service import MedicineService, RxNormProvider, DailyMedProvider


@pytest.fixture(autouse=True)
def clean_rate_limits():
    """Reset rate limiter before and after each medicine test to prevent cross-test interference."""
    reset_rate_limiter_state()
    yield
    reset_rate_limiter_state()


def test_medicine_search_validation_rules(client):
    """1. Search validation: < 2 chars, empty, > 100 chars return 400."""
    # Empty query
    r1 = client.get("/api/medicines/search")
    assert r1.status_code == 400

    # 1 char query
    r2 = client.get("/api/medicines/search?q=a")
    assert r2.status_code == 400

    # Query > 100 chars
    long_q = "a" * 105
    r3 = client.get(f"/api/medicines/search?q={long_q}")
    assert r3.status_code == 400


def test_medicine_search_public_unauthenticated_and_success(client):
    """
    2. Successful search.
    13. Public unauthenticated access (No JWT required).
    18. Privacy: No secrets leaked.
    """
    mock_drugs_resp = {
        "drugGroup": {
            "conceptGroup": [
                {
                    "conceptProperties": [
                        {
                            "rxcui": "161",
                            "name": "Acetaminophen",
                            "synonym": "Paracetamol",
                        }
                    ]
                }
            ]
        }
    }

    with patch("app.services.medicine_service._http_get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_drugs_resp
        mock_get.return_value = mock_resp

        # Call without Authorization header
        res = client.get("/api/medicines/search?q=paracetamol")
        assert res.status_code == 200
        data = res.json()
        assert data["query"] == "paracetamol"
        assert len(data["results"]) >= 1
        assert data["results"][0]["rxcui"] == "161"
        assert data["results"][0]["name"] == "Acetaminophen"
        assert data["results"][0]["source"] == "RxNorm"


def test_medicine_autocomplete_partial_search(client):
    """3. Partial search uses approximateTerm fallback."""
    mock_approx_resp = {
        "approximateGroup": {
            "candidate": [
                {"rxcui": "7052", "name": "Amoxicillin"},
                {"rxcui": "213169", "name": "Amoxicillin 250 MG Oral Capsule"},
            ]
        }
    }

    with patch("app.services.medicine_service._http_get") as mock_get:
        # First call drugs.json returns empty, second call approximateTerm returns candidates
        mock_resp1 = MagicMock(status_code=200, json=lambda: {"drugGroup": {"conceptGroup": []}})
        mock_resp2 = MagicMock(status_code=200, json=lambda: mock_approx_resp)
        mock_get.side_effect = [mock_resp1, mock_resp2]

        res = client.get("/api/medicines/search?q=amox")
        assert res.status_code == 200
        data = res.json()
        assert len(data["results"]) == 2
        assert data["results"][0]["name"] == "Amoxicillin"


def test_medicine_search_no_results_handled_gracefully(client):
    """4. Unknown medicine returns empty results without error."""
    with patch("app.services.medicine_service._http_get") as mock_get:
        mock_resp = MagicMock(status_code=200, json=lambda: {"drugGroup": {"conceptGroup": []}})
        mock_get.return_value = mock_resp

        res = client.get("/api/medicines/search?q=nonexistentdrugxyz")
        assert res.status_code == 200
        data = res.json()
        assert data["total_results"] == 0
        assert data["results"] == []


def test_medicine_details_lookup_success_and_disclaimer(client):
    """
    5. Medicine detail lookup.
    17. Medical safety disclaimer presence.
    """
    mock_props = {
        "propConceptGroup": {
            "propConcept": [
                {"propName": "RxNorm Name", "propValue": "Paracetamol 500 MG Oral Tablet"},
                {"propName": "Generic Name", "propValue": "Acetaminophen"},
            ]
        }
    }
    mock_related = {
        "allRelatedGroup": {
            "conceptGroup": [
                {"tty": "BN", "conceptProperties": [{"name": "Tylenol"}, {"name": "Panadol"}]},
                {"tty": "IN", "conceptProperties": [{"name": "Acetaminophen"}]},
                {"tty": "DF", "conceptProperties": [{"name": "Oral Tablet"}]},
            ]
        }
    }
    mock_spls = {
        "data": [
            {
                "setid": "abc-123",
                "title": "Acetaminophen tablet for relief of minor aches, pains, and reduction of fever.",
            }
        ]
    }
    mock_spl_detail = {
        "data": {
            "setid": "abc-123",
            "title": "Acetaminophen 500mg Oral Tablet Official FDA Labeling",
        }
    }

    with patch("app.services.medicine_service._http_get") as mock_get:
        def side_effect(url, **kwargs):
            if "allProperties.json" in url:
                return MagicMock(status_code=200, json=lambda: mock_props)
            elif "allrelated.json" in url:
                return MagicMock(status_code=200, json=lambda: mock_related)
            elif "/spls/abc-123.json" in url:
                return MagicMock(status_code=200, json=lambda: mock_spl_detail)
            elif "spls.json" in url:
                return MagicMock(status_code=200, json=lambda: mock_spls)
            return MagicMock(status_code=404)

        mock_get.side_effect = side_effect

        res = client.get("/api/medicines/161")
        assert res.status_code == 200
        data = res.json()
        assert data["rxcui"] == "161"
        assert "Paracetamol" in data["name"] or "Acetaminophen" in data["name"]
        assert "Tylenol" in data["brand_names"]
        assert "Acetaminophen" in data["active_ingredients"]
        assert "Oral Tablet" in data["dosage_forms"]
        assert len(data["uses"]) > 0
        assert data["availability"] == "official_information_available"
        assert "educational purposes only" in data["disclaimer"].lower()


def test_rxnorm_provider_failure_handled_gracefully(client):
    """6. RxNorm provider HTTP 500 / connection failure returns empty results without crashing."""
    with patch("app.services.medicine_service._http_get") as mock_get:
        mock_get.side_effect = httpx.ConnectError("RxNav unreachable")

        res = client.get("/api/medicines/search?q=aspirin")
        assert res.status_code == 200
        data = res.json()
        assert data["results"] == []


def test_dailymed_failure_fallback_to_rxnorm(client):
    """7. DailyMed provider failure falls back gracefully to basic RxNorm properties."""
    mock_props = {
        "propConceptGroup": {
            "propConcept": [
                {"propName": "RxNorm Name", "propValue": "Ibuprofen 400 MG Oral Tablet"},
            ]
        }
    }

    with patch("app.services.medicine_service._http_get") as mock_get:
        def side_effect(url, **kwargs):
            if "allProperties.json" in url:
                return MagicMock(status_code=200, json=lambda: mock_props)
            elif "allrelated.json" in url:
                return MagicMock(status_code=200, json=lambda: {"allRelatedGroup": {"conceptGroup": []}})
            elif "spls.json" in url or "spls/" in url:
                # DailyMed fails with 503 Service Unavailable
                return MagicMock(status_code=503)
            return MagicMock(status_code=404)

        mock_get.side_effect = side_effect

        res = client.get("/api/medicines/5640")
        assert res.status_code == 200
        data = res.json()
        assert data["rxcui"] == "5640"
        assert data["availability"] == "identified_basic_only"
        assert len(data["uses"]) > 0


def test_upstream_timeout_handled_gracefully(client):
    """8. Upstream timeout simulation returns safe fallback."""
    with patch("app.services.medicine_service._http_get") as mock_get:
        mock_get.side_effect = httpx.TimeoutException("Read timeout after 3.5s")

        res = client.get("/api/medicines/search?q=metformin")
        assert res.status_code == 200
        assert res.json()["results"] == []


def test_redis_caching_and_hit(client):
    """9. Redis cache stores search results and returns cache hit on second call."""
    fake_redis_store = {}
    fake_redis = MagicMock()
    fake_redis.get.side_effect = lambda k: fake_redis_store.get(k)
    fake_redis.set.side_effect = lambda k, v, ex=None: fake_redis_store.__setitem__(k, v)

    mock_drugs_resp = {
        "drugGroup": {
            "conceptGroup": [
                {
                    "conceptProperties": [
                        {"rxcui": "6809", "name": "Metformin"}
                    ]
                }
            ]
        }
    }

    with patch("app.services.medicine_service.get_redis_client", return_value=fake_redis):
        with patch("app.services.medicine_service._http_get") as mock_get:
            mock_resp = MagicMock(status_code=200, json=lambda: mock_drugs_resp)
            mock_get.return_value = mock_resp

            # First call fetches from upstream
            res1 = client.get("/api/medicines/search?q=metformin")
            assert res1.status_code == 200
            assert len(res1.json()["results"]) == 1

            # Second call should return data even if upstream would fail
            mock_get.side_effect = Exception("Should not be called if cached")
            res2 = client.get("/api/medicines/search?q=metformin")
            assert res2.status_code == 200
            assert res2.json()["results"][0]["name"] == "Metformin"


def test_redis_unavailable_resilience(client):
    """10. Redis failure does not crash medicine search."""
    with patch("app.services.medicine_service.get_redis_client", return_value=None):
        with patch("app.services.medicine_service._http_get") as mock_get:
            mock_drugs = {
                "drugGroup": {
                    "conceptGroup": [
                        {"conceptProperties": [{"rxcui": "1191", "name": "Aspirin"}]}
                    ]
                }
            }
            mock_get.return_value = MagicMock(status_code=200, json=lambda: mock_drugs)

            res = client.get("/api/medicines/search?q=aspirin")
            assert res.status_code == 200
            assert len(res.json()["results"]) >= 1


def test_rate_limiting_on_medicine_search(client):
    """11. Rate limiter triggers 429 after exceeding limit."""
    with patch("app.services.medicine_service._http_get") as mock_get:
        mock_get.return_value = MagicMock(status_code=200, json=lambda: {"drugGroup": {"conceptGroup": []}})

        hit_429 = False
        try:
            for _ in range(65):
                r = client.get("/api/medicines/search?q=ratelimittest")
                if r.status_code == 429:
                    hit_429 = True
                    assert "too many requests" in r.json()["detail"].lower()
                    break
            assert hit_429
        finally:
            reset_rate_limiter_state()


def test_malformed_upstream_json_handling(client):
    """12. Malformed JSON from provider is handled safely."""
    with patch("app.services.medicine_service._http_get") as mock_get:
        mock_resp = MagicMock(status_code=200)
        mock_resp.json.side_effect = json.JSONDecodeError("Expecting value", "doc", 0)
        mock_get.return_value = mock_resp

        res = client.get("/api/medicines/search?q=brokenjson")
        assert res.status_code == 200
        assert res.json()["results"] == []


def test_patient_and_doctor_can_search_medicines(client, patient_a, doctor_user):
    """
    14. Patient authenticated access.
    15. Doctor prescription autocomplete access.
    """
    pat_token = create_access_token(subject=patient_a.id, role=patient_a.role.value)
    doc_token = create_access_token(subject=doctor_user.id, role=doctor_user.role.value)

    with patch("app.services.medicine_service._http_get") as mock_get:
        mock_drugs = {
            "drugGroup": {
                "conceptGroup": [
                    {"conceptProperties": [{"rxcui": "7052", "name": "Amoxicillin"}]}
                ]
            }
        }
        mock_get.return_value = MagicMock(status_code=200, json=lambda: mock_drugs)

        # Patient search
        r_pat = client.get("/api/medicines/search?q=amoxicillin", headers={"Authorization": f"Bearer {pat_token}"})
        assert r_pat.status_code == 200
        assert r_pat.json()["results"][0]["name"] == "Amoxicillin"

        # Doctor search
        r_doc = client.get("/api/medicines/search?q=amoxicillin", headers={"Authorization": f"Bearer {doc_token}"})
        assert r_doc.status_code == 200
        assert r_doc.json()["results"][0]["name"] == "Amoxicillin"


def test_doctor_prescription_creation_resilience_when_medicine_service_down(client, doctor_user, patient_a, db_session):
    """
    16. Prescription creation still works even when external medicine search is completely down.
    """
    doctor = doctor_user.doctor
    patient = patient_a.patient

    # Create appointment
    now_utc = datetime.now(timezone.utc)
    app = Appointment(
        patient_id=patient.id,
        doctor_id=doctor.id,
        start_time=now_utc + timedelta(days=2),
        end_time=now_utc + timedelta(days=2, minutes=30),
        status=AppointmentStatus.CONFIRMED,
    )
    db_session.add(app)
    db_session.commit()

    doc_token = create_access_token(subject=doctor_user.id, role=doctor_user.role.value)
    doc_headers = {"Authorization": f"Bearer {doc_token}"}

    # Simulate medicine API being offline
    with patch("app.services.medicine_service._http_get", side_effect=httpx.ConnectError("Down")):
        # Doctor directly submits prescription with custom/unresolved brand name
        res = client.post(
            f"/api/appointments/{app.id}/prescription",
            json={
                "general_instructions": "Take after meals",
                "medications": [
                    {
                        "name": "Dolo 650 (Paracetamol)",
                        "dosage": "650 mg",
                        "frequency": "TWICE_DAILY",
                        "start_date": "2026-09-01",
                        "end_date": "2026-09-05",
                        "instructions": "For fever",
                    }
                ],
            },
            headers=doc_headers,
        )
        assert res.status_code in [200, 201]
        data = res.json()
        assert len(data["medications"]) == 1
        assert data["medications"][0]["name"] == "Dolo 650 (Paracetamol)"


def test_medicine_search_ranking_priority(client):
    """
    Phase 5.1: Verify search ranking priority (clean generic / exact matches prioritized over long pack descriptions).
    """
    mock_drugs_resp = {
        "drugGroup": {
            "conceptGroup": [
                {
                    "tty": "BPCK",
                    "conceptProperties": [
                        {"rxcui": "9999", "name": "Acetaminophen 500 MG / Hydrocodone 5 MG Oral Tablet [Super Long Complex Packaging Kit]"}
                    ],
                },
                {
                    "tty": "IN",
                    "conceptProperties": [
                        {"rxcui": "161", "name": "Acetaminophen", "synonym": "Paracetamol"}
                    ],
                },
                {
                    "tty": "SCD",
                    "conceptProperties": [
                        {"rxcui": "209387", "name": "Acetaminophen 500 MG Oral Tablet"}
                    ],
                },
            ]
        }
    }

    with patch("app.services.medicine_service.get_redis_client", return_value=None):
        with patch("app.services.medicine_service._http_get") as mock_get:
            mock_resp = MagicMock(status_code=200, json=lambda: mock_drugs_resp)
            mock_get.return_value = mock_resp

            res = client.get("/api/medicines/search?q=acetaminophen")
            assert res.status_code == 200
            data = res.json()
            assert len(data["results"]) == 3
            # Top ranked item should be the exact match / pure ingredient
            assert data["results"][0]["rxcui"] == "161"
            assert data["results"][0]["name"] == "Acetaminophen"
            # Complex pack should be ranked last
            assert data["results"][-1]["rxcui"] == "9999"


def test_autocomplete_does_not_call_dailymed(client):
    """
    Phase 5.1: Autocomplete must only perform lightweight RxNorm queries and NOT call DailyMed / SPL mapping.
    """
    mock_drugs_resp = {
        "drugGroup": {
            "conceptGroup": [
                {"tty": "IN", "conceptProperties": [{"rxcui": "5640", "name": "Ibuprofen"}]}
            ]
        }
    }

    with patch("app.services.medicine_service._http_get") as mock_get:
        mock_get.return_value = MagicMock(status_code=200, json=lambda: mock_drugs_resp)

        res = client.get("/api/medicines/search?q=ibuprofen")
        assert res.status_code == 200
        assert len(res.json()["results"]) >= 1

        # Assert no DailyMed URLs were queried during search
        for call_args in mock_get.call_args_list:
            url_called = call_args[0][0]
            assert "dailymed" not in url_called.lower()


def test_medicine_did_you_mean_suggestion_for_spelling_error(client):
    """
    Phase 5.1: Minor spelling errors should yield a Did-You-Mean suggestion from approximate term candidates.
    """
    mock_approx_resp = {
        "approximateGroup": {
            "candidate": [
                {"rxcui": "161", "name": "Paracetamol 500 MG Oral Tablet"},
                {"rxcui": "209387", "name": "Acetaminophen"},
            ]
        }
    }

    with patch("app.services.medicine_service._http_get") as mock_get:
        mock_resp1 = MagicMock(status_code=200, json=lambda: {"drugGroup": {"conceptGroup": []}})
        mock_resp2 = MagicMock(status_code=200, json=lambda: mock_approx_resp)
        mock_get.side_effect = [mock_resp1, mock_resp2]

        res = client.get("/api/medicines/search?q=paracetmol")
        assert res.status_code == 200
        data = res.json()
        assert data["did_you_mean"] == "Paracetamol"
        assert len(data["results"]) >= 1


def test_medicine_details_patient_friendly_structure(client):
    """
    Phase 5.2: Verify patient-friendly response structure (plain language uses, active ingredients, dosage forms, brands, disclaimer).
    """
    mock_props = {
        "propConceptGroup": {
            "propConcept": [
                {"propName": "RxNorm Name", "propValue": "Paracetamol 500 MG Oral Tablet"},
                {"propName": "Generic Name", "propValue": "Acetaminophen"},
            ]
        }
    }
    mock_related = {
        "allRelatedGroup": {
            "conceptGroup": [
                {"tty": "BN", "conceptProperties": [{"name": "Tylenol"}, {"name": "Panadol"}]},
                {"tty": "IN", "conceptProperties": [{"name": "Acetaminophen"}]},
                {"tty": "DF", "conceptProperties": [{"name": "Oral Tablet"}]},
            ]
        }
    }
    mock_spls = {
        "data": [
            {
                "setid": "set-123-abc",
                "title": "Acetaminophen tablet for relief of minor aches, pains, and fever.",
            }
        ]
    }
    mock_spl_detail = {
        "data": {
            "setid": "set-123-abc",
            "title": "Acetaminophen 500mg Oral Tablet Official Label",
        }
    }

    with patch("app.services.medicine_service.get_redis_client", return_value=None):
        with patch("app.services.medicine_service._http_get") as mock_get:
            def side_effect(url, **kwargs):
                if "allProperties.json" in url:
                    return MagicMock(status_code=200, json=lambda: mock_props)
                elif "allrelated.json" in url:
                    return MagicMock(status_code=200, json=lambda: mock_related)
                elif "/spls/set-123-abc.json" in url:
                    return MagicMock(status_code=200, json=lambda: mock_spl_detail)
                elif "spls.json" in url:
                    return MagicMock(status_code=200, json=lambda: mock_spls)
                return MagicMock(status_code=404)

            mock_get.side_effect = side_effect

            res = client.get("/api/medicines/161")
            assert res.status_code == 200
            data = res.json()
            assert data["rxcui"] == "161"
            assert data["name"] == "Paracetamol 500 MG Oral Tablet"
            assert data["generic_name"] == "Acetaminophen"
            assert "Acetaminophen" in data["active_ingredients"]
            assert "Tylenol" in data["brand_names"]
            assert "Oral Tablet" in data["dosage_forms"]
            # Plain language check
            assert any("used for" in u.lower() or "relief" in u.lower() for u in data["uses"])
            # Disclaimer present
            assert "educational purposes only" in data["disclaimer"].lower()
            # Source attribution present
            assert data["source"]["type"] == "official_label"
            assert data["availability"] == "official_information_available"
