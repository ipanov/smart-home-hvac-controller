"""FastAPI dashboard for SmartHVAC."""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

TEMPLATE_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))


class TargetTempRequest(BaseModel):
    target_temp: float


class HVACState:
    def __init__(self) -> None:
        self.inside_temp = 24.5
        self.outside_temp = 32.0
        self.target_temp = 24.0
        self.ac_mode = "cool"
        self.purifier_on = True
        self.battery_level = 45

    def to_dict(self) -> dict:
        return {
            "inside_temp": self.inside_temp,
            "outside_temp": self.outside_temp,
            "target_temp": self.target_temp,
            "ac_mode": self.ac_mode,
            "purifier_on": self.purifier_on,
            "battery_level": self.battery_level,
        }


def create_app() -> FastAPI:
    app = FastAPI(title="Smart HVAC Dashboard")
    state = HVACState()

    @app.get("/", response_class=HTMLResponse)
    async def dashboard(request: Request) -> HTMLResponse:
        data = state.to_dict()
        data["purifier_status"] = "On" if data["purifier_on"] else "Off"
        return templates.TemplateResponse(request, "dashboard.html", data)

    @app.get("/api/status")
    async def api_status() -> JSONResponse:
        return JSONResponse(content=state.to_dict())

    @app.post("/api/target-temp")
    async def api_target_temp(payload: TargetTempRequest) -> JSONResponse:
        state.target_temp = payload.target_temp
        return JSONResponse(content={"target_temp": state.target_temp})

    return app
