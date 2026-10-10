import logging

from aiohttp import web

log = logging.getLogger(__name__)


# async health check
async def health_check(request):
  return web.Response(text="ok", status=200)


def create_app() -> web.Application:
  app = web.Application()
  app.router.add_get('/', health_check)  # Root path for AWS App Runner default health check
  app.router.add_get('/health', health_check)
  return app


async def run_health_server() -> web.AppRunner:
  runner = web.AppRunner(create_app())
  await runner.setup()
  site = web.TCPSite(runner, '0.0.0.0', 8080)
  await site.start()
  log.info("Health check server started on port 8080")
  return runner
