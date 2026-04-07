"""Dashboard — web UI and REST API for managing restaurants."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from config import settings
from src.database import Restaurant, SessionLocal, get_restaurant_by_assistant_id
from src import vapi_service

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="src/templates")


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _flash_redirect(url: str, message: str, flash_type: str = "success") -> RedirectResponse:
    """Redirect with a flash message encoded in query params."""
    sep = "&" if "?" in url else "?"
    return RedirectResponse(
        url=f"{url}{sep}_flash={message}&_flash_type={flash_type}",
        status_code=303,
    )


def _extract_flash(request: Request) -> dict:
    return {
        "flash_message": request.query_params.get("_flash"),
        "flash_type": request.query_params.get("_flash_type", "success"),
    }


# ===================================================================
# PAGE ROUTES (HTML)
# ===================================================================


@router.get("/", response_class=HTMLResponse)
async def restaurant_list(request: Request):
    with SessionLocal() as db:
        restaurants = db.query(Restaurant).order_by(Restaurant.created_at.desc()).all()
        data = [
            type("R", (), {**r.to_dict(), "is_active": r.is_active, "created_at": r.created_at})
            for r in restaurants
        ]
    return templates.TemplateResponse(
        request,
        "restaurant_list.html",
        context={"restaurants": data, **_extract_flash(request)},
    )


@router.get("/restaurants/new", response_class=HTMLResponse)
async def restaurant_new_form(request: Request):
    return templates.TemplateResponse(
        request,
        "restaurant_form.html",
        context={"restaurant": None, **_extract_flash(request)},
    )


@router.get("/restaurants/{restaurant_id}", response_class=HTMLResponse)
async def restaurant_detail(request: Request, restaurant_id: str):
    with SessionLocal() as db:
        r = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
        if not r:
            return _flash_redirect("/", "Restaurant not found", "error")
        data = type("R", (), {**r.to_dict(), "is_active": r.is_active, "created_at": r.created_at})
    return templates.TemplateResponse(
        request,
        "restaurant_detail.html",
        context={
            "restaurant": data,
            "server_url": settings.server_url,
            **_extract_flash(request),
        },
    )


@router.get("/restaurants/{restaurant_id}/edit", response_class=HTMLResponse)
async def restaurant_edit_form(request: Request, restaurant_id: str):
    with SessionLocal() as db:
        r = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
        if not r:
            return _flash_redirect("/", "Restaurant not found", "error")
        data = type("R", (), r.to_dict())
    return templates.TemplateResponse(
        request,
        "restaurant_form.html",
        context={"restaurant": data, **_extract_flash(request)},
    )


# ===================================================================
# API ROUTES (form submissions -> redirect)
# ===================================================================


@router.post("/api/restaurants")
async def create_restaurant(
    name: str = Form(...),
    reservation_system: str = Form("ontopo"),
    venue_id: str = Form(""),
    city: str = Form("tel-aviv"),
    phone_number: str = Form(""),
    vapi_phone_number_id: str = Form(""),
    tabit_organization_id: str = Form(""),
    tabit_api_key: str = Form(""),
):
    """Create a new restaurant and provision a Vapi assistant."""
    with SessionLocal() as db:
        restaurant = Restaurant(
            name=name,
            reservation_system=reservation_system,
            venue_id=venue_id,
            city=city,
            phone_number=phone_number,
            vapi_phone_number_id=vapi_phone_number_id or None,
            tabit_organization_id=tabit_organization_id,
            tabit_api_key=tabit_api_key,
        )

        if settings.vapi_api_key:
            try:
                vapi_data = await vapi_service.create_assistant(name)
                restaurant.vapi_assistant_id = vapi_data.get("id")
                logger.info("Vapi assistant created: %s", restaurant.vapi_assistant_id)
            except Exception as exc:
                logger.warning("Failed to create Vapi assistant: %s", exc)

        db.add(restaurant)
        db.commit()
        rid = restaurant.id

    return _flash_redirect(
        f"/restaurants/{rid}",
        f"Restaurant '{name}' created successfully!",
    )


@router.post("/api/restaurants/{restaurant_id}")
async def update_restaurant(
    restaurant_id: str,
    name: str = Form(...),
    reservation_system: str = Form("ontopo"),
    venue_id: str = Form(""),
    city: str = Form("tel-aviv"),
    phone_number: str = Form(""),
    vapi_phone_number_id: str = Form(""),
    tabit_organization_id: str = Form(""),
    tabit_api_key: str = Form(""),
):
    """Update an existing restaurant and sync the Vapi assistant."""
    with SessionLocal() as db:
        r = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
        if not r:
            return _flash_redirect("/", "Restaurant not found", "error")

        r.name = name
        r.reservation_system = reservation_system
        r.venue_id = venue_id
        r.city = city
        r.phone_number = phone_number
        r.vapi_phone_number_id = vapi_phone_number_id or r.vapi_phone_number_id
        r.tabit_organization_id = tabit_organization_id
        r.tabit_api_key = tabit_api_key
        r.updated_at = datetime.now(timezone.utc)

        if r.vapi_assistant_id and settings.vapi_api_key:
            try:
                await vapi_service.update_assistant(r.vapi_assistant_id, name)
            except Exception as exc:
                logger.warning("Failed to update Vapi assistant: %s", exc)

        db.commit()
        rid = r.id

    return _flash_redirect(
        f"/restaurants/{rid}",
        f"Restaurant '{name}' updated!",
    )


@router.post("/api/restaurants/{restaurant_id}/toggle")
async def toggle_restaurant(restaurant_id: str):
    """Toggle a restaurant's active status."""
    with SessionLocal() as db:
        r = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
        if not r:
            return _flash_redirect("/", "Restaurant not found", "error")
        r.is_active = not r.is_active
        r.updated_at = datetime.now(timezone.utc)
        status = "activated" if r.is_active else "deactivated"
        db.commit()

    return _flash_redirect("/", f"'{r.name}' {status}")


@router.post("/api/restaurants/{restaurant_id}/delete")
async def delete_restaurant(restaurant_id: str):
    """Delete a restaurant and its Vapi assistant."""
    with SessionLocal() as db:
        r = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
        if not r:
            return _flash_redirect("/", "Restaurant not found", "error")

        rname = r.name

        if r.vapi_assistant_id and settings.vapi_api_key:
            try:
                await vapi_service.delete_assistant(r.vapi_assistant_id)
            except Exception as exc:
                logger.warning("Failed to delete Vapi assistant: %s", exc)

        db.delete(r)
        db.commit()

    return _flash_redirect("/", f"'{rname}' deleted")


@router.post("/api/restaurants/{restaurant_id}/deploy")
async def deploy_vapi_assistant(restaurant_id: str):
    """Manually trigger Vapi assistant creation for a restaurant."""
    if not settings.vapi_api_key:
        return _flash_redirect(
            f"/restaurants/{restaurant_id}",
            "VAPI_API_KEY is not configured",
            "error",
        )

    with SessionLocal() as db:
        r = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
        if not r:
            return _flash_redirect("/", "Restaurant not found", "error")

        try:
            vapi_data = await vapi_service.create_assistant(r.name)
            r.vapi_assistant_id = vapi_data.get("id")
            r.updated_at = datetime.now(timezone.utc)
            db.commit()
            return _flash_redirect(
                f"/restaurants/{restaurant_id}",
                f"Vapi assistant deployed: {r.vapi_assistant_id}",
            )
        except Exception as exc:
            logger.exception("Deploy failed")
            return _flash_redirect(
                f"/restaurants/{restaurant_id}",
                f"Deploy failed: {exc}",
                "error",
            )
