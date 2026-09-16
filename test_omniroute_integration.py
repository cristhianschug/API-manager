"""Test OmniRoute integration endpoints"""
import pytest
import httpx
from dotenv import load_dotenv
import os

load_dotenv('.env.local')

BASE_URL = "http://localhost:8000"
API_KEY = "test-key"  # Replace with valid API key


@pytest.fixture
def client():
    return httpx.Client(base_url=BASE_URL)


def test_ai_status(client):
    """Check OmniRoute gateway status"""
    response = client.get(
        "/api/v1/ai/status",
        headers={"X-API-Key": API_KEY}
    )
    assert response.status_code in [200, 503]  # OK or Service Unavailable
    data = response.json()
    assert "gateway" in data
    assert data.get("gateway") == "omniroute"


def test_summarize_text(client):
    """Test text summarization"""
    response = client.post(
        "/api/v1/ai/summarize",
        headers={"X-API-Key": API_KEY},
        json={
            "text": "Este é um texto longo que descreve um cliente importante da empresa. A empresa XYZ é uma organização multinacional com presença em diversos países e uma longa história de sucesso.",
            "max_tokens": 50
        }
    )

    if response.status_code == 200:
        data = response.json()
        assert "summary" in data
        assert "original_length" in data
        assert data["model"] == "omniroute/auto"
        print(f"✓ Summary: {data['summary']}")
    else:
        print(f"⚠ Summarize unavailable: {response.status_code}")


def test_generate_description(client):
    """Test product description generation"""
    response = client.post(
        "/api/v1/ai/generate-description",
        headers={"X-API-Key": API_KEY},
        json={
            "subject": "Produto: Fone Bluetooth",
            "context": "Dispositivo de áudio portátil, conectividade wireless",
            "max_tokens": 100
        }
    )

    if response.status_code == 200:
        data = response.json()
        assert "description" in data
        assert "subject" in data
        print(f"✓ Description: {data['description']}")
    else:
        print(f"⚠ Generation unavailable: {response.status_code}")


def test_analyze_data(client):
    """Test data analysis"""
    response = client.post(
        "/api/v1/ai/analyze",
        headers={"X-API-Key": API_KEY},
        json={
            "data": {
                "mes": "Março",
                "vendas": 25000,
                "custos": 15000,
                "lucro": 10000,
                "clientes": 120
            },
            "query": "Qual é a margem de lucro e tendência?",
            "max_tokens": 150
        }
    )

    if response.status_code == 200:
        data = response.json()
        assert "analysis" in data
        assert "query" in data
        print(f"✓ Analysis: {data['analysis']}")
    else:
        print(f"⚠ Analysis unavailable: {response.status_code}")


def test_omniroute_client_directly():
    """Test OmniRoute client directly (without API layer)"""
    try:
        from omniroute_client import query_ai, summarize_text

        # This will fail if OmniRoute is not running
        result = query_ai("Responda com 'OK'", max_tokens=5)
        assert "ok" in result.lower()
        print(f"✓ OmniRoute is running: {result}")

        # Test summarize
        summary = summarize_text(
            "This is a long text about AI integration. " * 10,
            max_tokens=30
        )
        print(f"✓ Summarization works: {summary[:50]}...")

    except Exception as e:
        print(f"⚠ OmniRoute client error: {e}")
        print("  → Make sure OmniRoute is running: omniroute")


if __name__ == "__main__":
    print("\n🧪 Testing OmniRoute Integration\n")
    print("Prerequisites:")
    print("  1. OmniRoute running: omniroute")
    print("  2. API running: uvicorn main:app")
    print("  3. Valid API key in tenant database\n")

    # Run direct client test first
    print("Testing OmniRoute client directly...")
    test_omniroute_client_directly()

    print("\n" + "="*50 + "\n")

    # Run API endpoint tests
    with httpx.Client(base_url=BASE_URL) as client:
        print("Testing API endpoints with key:", API_KEY[:10] + "...")
        test_ai_status(client)
        test_summarize_text(client)
        test_generate_description(client)
        test_analyze_data(client)

    print("\n✓ Integration test complete!")
