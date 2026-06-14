from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings

app = FastAPI(
    title="Brinquedos da Mãe API",
    description="Sistema de gestão de vendas de brinquedos artesanais",
    version="2.0.0",
    debug=settings.debug,
)

# CORS: Aceita qualquer origem (para teste)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Para produção, troque por: ["https://mmb-frontend-production-f434.up.railway.app"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_v1_prefix)

@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
