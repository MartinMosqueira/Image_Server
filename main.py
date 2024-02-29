from aiohttp import web
from jinja2 import Environment, FileSystemLoader
from services import upload_image, get_all_images, start_redis, delete_image


async def home_page(request):
    continuation_token = request.rel_url.query.get('continuation_token', None)
    print(f'Token Actual: {continuation_token}')
    response = await get_all_images(request, continuation_token, 7)

    url = response['images']
    token = response['continuation_token']

    template_loader = FileSystemLoader(searchpath='templates/')
    env = Environment(loader=template_loader)
    template = env.get_template('index.html')

    print(f'Token Enviado : {token}')
    rendered_template = template.render(images=url, last_token=token)
    return web.Response(text=rendered_template, content_type='text/html')


async def receive_token(request):
    data = await request.post()
    continuation_token_from_js = data.get('continuation_token_from_js', None)

    print(f'Token Recivido de javascript!!: {continuation_token_from_js}')

    response = await get_all_images(request, continuation_token_from_js)

    print(f'Nuevo Token Enviado : {response["continuation_token"]}')
    return web.json_response(response)


async def main():
    # start redis
    await start_redis()

    # create app
    app = web.Application()
    app.router.add_get('/', home_page)
    app.router.add_static('/static/', path='static', name='static')
    app.router.add_post('/app/up', upload_image)
    app.router.add_post('/app/receive_token', receive_token)
    app.router.add_delete('/app/delete_image', delete_image)

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
