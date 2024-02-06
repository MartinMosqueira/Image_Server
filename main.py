from aiohttp import web
from services import upload_image


async def home_page(request):
    return web.FileResponse('templates/index.html')


async def main():
    # create app
    app = web.Application()
    app.router.add_get('/', home_page)
    app.router.add_static('/static/', path='static', name='static')
    app.router.add_post('/app/up', upload_image)

    # create server
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', 8080)

    # start server
    await site.start()

    print("Server in http://localhost:8080/")


if __name__ == '__main__':
    import asyncio

    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
    loop.run_forever()
