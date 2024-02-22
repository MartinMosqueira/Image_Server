from aiohttp import web
from jinja2 import Environment, FileSystemLoader
from services import upload_image, get_all_images


async def home_page(request):
    last_image = request.rel_url.query.get('last_image', 'beach.webp')
    response = await get_all_images(request, last_image, 7)

    url = response['images']
    last_show_image = response['last_show_image']

    template_loader = FileSystemLoader(searchpath='templates/')
    env = Environment(loader=template_loader)
    template = env.get_template('index.html')

    rendered_template = template.render(images=url, last_image=last_show_image)
    print(rendered_template)
    return web.Response(text=rendered_template, content_type='text/html')


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
