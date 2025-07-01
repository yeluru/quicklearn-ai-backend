import pytest
from fastapi.testclient import TestClient
from main import app

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c

# Example: Patch OpenAI and other external calls here if needed 