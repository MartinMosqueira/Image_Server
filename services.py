import asyncio
import json

from aiohttp import web
import boto3
from dotenv import load_dotenv
import os
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from PIL import Image
import io

load_dotenv()

last_show_image = 'beach.webp'


async def get_all_images(request, starter=None, max_keys=7):
    s3_client = boto3.client('s3',
                             aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
                             aws_secret_access_key=os.environ.get('AWS_ACCESS_SECRET_KEY'),
                             region_name=os.environ.get('AWS_REGION')
                             )

    paginator = s3_client.get_paginator('list_objects_v2')
    images = []
    pageNumber = 0
    page_iterator = paginator.paginate(Bucket=os.environ.get('AWS_BUCKET'),
                                       StartAfter=starter,
                                       PaginationConfig={'PageSize': max_keys})
    for page in page_iterator:
        pageNumber += 1
        for content in page['Contents']:
            url = s3_client.generate_presigned_url('get_object',
                                                   Params={'Bucket': os.environ.get('AWS_BUCKET'),
                                                           'Key': content['Key']},
                                                   ExpiresIn=300)
            images.append(url)
        last_show_image = page['Contents'][-1]['Key']
        print(f'Page {pageNumber}')
        print(images)
        print(f'Last image: {last_show_image}')
        break

    response_data = {
        'images': images,
        'last_show_image': last_show_image
    }

    return response_data


def encode_webp(image_data):
    pillow_image = Image.open(io.BytesIO(image_data))

    if pillow_image.mode != 'RGB':
        pillow_image = pillow_image.convert('RGB')

    webp_data = io.BytesIO()
    pillow_image.save(webp_data, 'WEBP', quality=80)
    return webp_data.getvalue()


def upload_to_s3(file_content, file_name, s3_client):
    s3_client.put_object(Body=file_content,
                         Bucket=os.environ.get('AWS_BUCKET'),
                         Key=file_name)


async def upload_image(request):
    time_start = time.monotonic()
    try:
        data = await request.post()
        images = data.getall('imagenInput')

        parts = [image.file.read() for image in images]
        names = [image.filename for image in images]

        with ProcessPoolExecutor() as executor:
            tasks = []
            for part in parts:
                task = asyncio.get_event_loop().run_in_executor(executor, encode_webp, part)
                tasks.append(task)

            results = await asyncio.gather(*tasks)

        # Subir las imágenes a S3
        s3_client = boto3.client('s3',
                                 aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
                                 aws_secret_access_key=os.environ.get('AWS_ACCESS_SECRET_KEY'),
                                 region_name=os.environ.get('AWS_REGION')
                                 )

        with ThreadPoolExecutor() as executor:
            tasks = []
            for name, result in zip(names, results):
                task = asyncio.get_event_loop().run_in_executor(executor, upload_to_s3, result, f'{name}.webp',
                                                                s3_client)
                tasks.append(task)

            await asyncio.gather(*tasks)

        return web.Response(text="Imágenes subidas correctamente", status=200)

    except Exception as e:
        print(f"Error al subir imágenes: {e}")
        return web.Response(text="Error al subir imágenes", status=500)

    finally:
        time_end = time.monotonic()
        print(f"Tiempo de ejecución: {time_end - time_start} segundos")


async def download_image(request):
    return web.Response(text="Response from GET")


async def delete_image(request):
    return web.Response(text="Response from DELETE")
