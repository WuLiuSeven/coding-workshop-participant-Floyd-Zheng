from mangum import Mangum
from app.main import app

# CloudFront sends /api/acme/...; strip that so routes like /incident still match
handler = Mangum(app, lifespan="auto", api_gateway_base_path="/api/acme")