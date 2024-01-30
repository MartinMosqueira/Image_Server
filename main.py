from aiohttp import web
from services import get_all_images, upload_image, download_image, delete_image


async def main():
    # create app
    app = web.Application()
    app.router.add_get('/app/images', get_all_images)
    app.router.add_post('/app/up', upload_image)
    app.router.add_get('/app/download', download_image)
    app.router.add_delete('/app/delete', delete_image)

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
