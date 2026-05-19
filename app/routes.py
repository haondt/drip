from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, status
from fastapi.datastructures import FormData
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, Response, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
import logging
from .state import state
from . import scheduler
import asyncio
from .config import config
import os
from . import datetime_util as dt
import html
from .models import Feed, FeedEntry
from . import drip
from .jinja_filters import add_filters

_logger = logging.getLogger(__name__)

def add_routes(app: FastAPI):
    templates = Jinja2Templates(directory="app/templates")
    add_filters(templates)


    @app.get("/", response_class=HTMLResponse)
    async def root(request: Request):
        return RedirectResponse("feeds")

    @app.get("/feeds", response_class=HTMLResponse)
    async def feeds(request: Request):
        feeds = state.feeds.all()
        poll_states = state.poll_states.all()
        return templates.TemplateResponse(request, "feeds.html", {
            'feeds': feeds,
            'poll_states': poll_states,
            'config': config
        })

    @app.get("/feeds/new", response_class=HTMLResponse)
    async def get_new_feed(request: Request):
        return templates.TemplateResponse(request, "edit_feed.html", {
            'config': config
        })

    def _validate_upsert_feed(form: FormData):
        errors = {}
        if not form.get("name"):
            errors['name'] = 'The name cannot be empty'
        if not form.get("url"):
            errors['url'] = 'The url cannot be empty'
        if not form.get("tz"):
            errors['tz'] = 'The timezone was not supplied'
        period = form.get('period')
        if not (dt.validate_timespan_str(period) or dt.validate_cron_str(period)):
            errors['period'] = 'Cannot parse timespan'

        return errors

    def _normalize_string_or_none(s: str | None) -> str | None:
        if s is None:
            return None
        s = s.strip()
        if len(s) == 0:
            return None
        return s

    @app.post("/feeds/new", response_class=HTMLResponse)
    async def create_feed(request: Request):
        form = await request.form()
        errors = _validate_upsert_feed(form)
        headers = {}
        message = {}
        if len(errors) == 0:
            feed_id = state.feeds.add(Feed(
                name=form['name'],
                url=form['url'],
                period=form['period'],
                created=dt.now_iso(),
                creation_tz=form['tz'],
                user_agent=_normalize_string_or_none(form.get('user_agent')),
            ))
            headers={'Hx-Push-Url': f'/feeds/feed/{feed_id}'}
            message = { 'text': 'Feed created.'}

            drip.refresh_feed(feed_id)


        return templates.TemplateResponse(request, "edit_feed.html", {
            'errors': errors,
            'message': message,
            'config': config
            }, headers=headers)

    @app.get("/feeds/feed/{feed_id}", response_class=HTMLResponse)
    async def get_feed(request: Request, feed_id: int):
        feed = state.feeds.get(feed_id)
        if not feed:
            return RedirectResponse("/feeds")
        return templates.TemplateResponse(request, "edit_feed.html", {
            'errors': {},
            'message': {},
            'feed': feed,
            'config': config
            })


    @app.post("/feeds/feed/{feed_id}", response_class=HTMLResponse)
    async def update_feed(request: Request, feed_id: int):
        feed = state.feeds.get(feed_id)
        if not feed:
            return RedirectResponse("/feeds")

        form = await request.form()
        errors = _validate_upsert_feed(form)
        headers = {}
        message = {}
        if len(errors) == 0:
            feed.name = form['name']
            feed.url = form['url']
            feed.period = form['period']
            feed.creation_tz=form['tz']
            feed.user_agent=_normalize_string_or_none(form.get('user_agent'))

            state.feeds[feed_id] = feed
            message = { 'text': 'Feed updated.' }
        return templates.TemplateResponse(request, "edit_feed.html", {
            'errors': errors,
            'message': message,
            'config': config,
            }, headers=headers)

    @app.delete("/feeds/feed/{feed_id}", response_class=HTMLResponse)
    async def delete_feed(request: Request, feed_id: int):
        del state.feeds[feed_id]
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.post("/feeds/feed/{feed_id}/refresh", response_class=HTMLResponse)
    async def refresh_feed(request: Request, feed_id: int):
        scheduler.record_poll(feed_id)
        drip.refresh_feed(feed_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.get("/feeds/feed/{feed_id}/drip.atom")
    async def get_feed_atom(feed_id: int):
        fg = drip.query_feed(feed_id)
        xml = fg.atom_str(pretty=True)
        return Response(content=xml, media_type="application/atom+xml")

    @app.get("/feeds/feed/{feed_id}/drip.rss")
    async def get_feed_rss(feed_id: int):
        fg = drip.query_feed(feed_id)
        xml = fg.rss_str(pretty=True)
        return Response(content=xml, media_type="application/rss+xml")
    
    @app.get("/drops/drop/{drop_id}")
    async def get_drop_html(drop_id: str):
        feed_id, index = drop_id.split(':', 1)
        html = drip.get_drop_html(int(feed_id), index)
        return Response(content=html, media_type="text/html")

    @app.get("/hc")
    async def health_check():
        return "OK"

    @app.get("/static/logo.svg")
    async def serve_logo():
        logo_path = os.path.join(os.path.dirname(__file__), "static", "logo.svg")
        if not os.path.exists(logo_path):
            return Response(status_code=404)
        return FileResponse(path=logo_path)


