import asyncio
from aiohttp import web


async def get_all_images(request):
    return web.Response(text="Response from GET")


async def upload_image(request):
    return web.Response(text="Response from POST")


async def download_image(request):
    return web.Response(text="Response from GET")


async def delete_image(request):
    return web.Response(text="Response from DELETE")
