import asyncio
import concurrent

from aiohttp import web
import boto3
from dotenv import load_dotenv
import os
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from PIL import Image
import io
import redis
from pathlib import Path
import json
from urllib.parse import urlparse

load_dotenv()
redis_client = None


async def start_redis():
    global redis_client
    redis_client = redis.Redis(host=os.environ.get('REDIS_HOST'), port=os.environ.get('REDIS_PORT'))
    return redis_client


def list_objects_v2_sync(s3_client, list_objects_params):
    return s3_client.list_objects_v2(**list_objects_params)


async def get_all_images(request, continuation_token, max_keys=7):
    r = redis_client

    continuation_token_str = str(continuation_token) if continuation_token is None else continuation_token

    cached_images = r.get(continuation_token_str)

    if cached_images:
        print(f'Hay imágenes en la caché de Redis para token: {continuation_token_str}')
        cached_data = eval(cached_images)
        response_data = {
            'images': cached_data['images'],
            'continuation_token': cached_data['continuation_token']
        }
        print(f'Imagenes de redis get_all_images: {cached_data["images"]}')
    else:
        s3_client = boto3.client('s3',
                                 aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
                                 aws_secret_access_key=os.environ.get('AWS_ACCESS_SECRET_KEY'),
                                 region_name=os.environ.get('AWS_REGION')
                                 )

        images = []
        list_objects_params = {
            'Bucket': os.environ.get('AWS_BUCKET'),
            'MaxKeys': max_keys,
        }
        if continuation_token and continuation_token.lower() != 'none':
            print(f'hay token: {continuation_token}')
            list_objects_params['ContinuationToken'] = str(continuation_token)

        print(f'Parametros: {list_objects_params}')

        with ThreadPoolExecutor() as executor:
            response = await asyncio.get_event_loop().run_in_executor(executor, list_objects_v2_sync, s3_client,
                                                                      list_objects_params)

        if 'Contents' in response:
            with ThreadPoolExecutor() as executor:
                tasks = []
                for content in response['Contents']:
                    task = asyncio.get_event_loop().run_in_executor(executor, s3_client.generate_presigned_url,
                                                                    'get_object',
                                                                    {'Bucket': os.environ.get('AWS_BUCKET'),
                                                                     'Key': content['Key']},
                                                                    300)
                    tasks.append(task)

                images = await asyncio.gather(*tasks)

            r.setex(continuation_token_str, 300,
                    str({'images': images, 'continuation_token': response.get('NextContinuationToken')}))

        print(f'Nuevo Token de get_all_images: {response.get("NextContinuationToken")}')
        print(f'Imagenes de get_all_images: {images}')

        response_data = {
            'images': images,
            'continuation_token': response.get('NextContinuationToken')
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
                webp_filename = f'{Path(name).stem}.webp'

                task = asyncio.get_event_loop().run_in_executor(executor, upload_to_s3, result, webp_filename,
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


def get_all_tokens_redis():
    r = redis_client

    return r.keys('*')


async def search_image_redis(tokenRedis, nameImage):
    r = redis_client
    content = r.get(tokenRedis)

    if content:
        content_str = content.decode('utf-8')

        content_fixed = content_str.replace("'", "\"")

        try:
            data = json.loads(content_fixed)

            images = data.get('images', [])

            for image_url in images:
                parsed_url = urlparse(image_url)
                image_name = parsed_url.path.split("/")[-1].split(".webp")[0]

                if nameImage == image_name:
                    print(f"Imagen econtrada: {image_url}")
                    return image_url

        except Exception as e:
            print(f"Error al decodificar JSON: {e}")
    return ''


async def search_all_images_redis(nameImage):
    tokens = await asyncio.to_thread(get_all_tokens_redis)

    for token in tokens:
        result = await search_image_redis(token, nameImage)

        if result != '':
            return result


async def search_image(request):
    print("Buscando imagen")
    data = await request.post()
    search = data.get('search', None)

    if search is not None:
        image_url = await search_all_images_redis(search)
        print(f"Imagen encontrada: {image_url}")
        if image_url:
            return web.Response(text=image_url if image_url else '')
        else:
            print(f"Buscando en AWS")
            s3_client = boto3.client('s3',
                                     aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
                                     aws_secret_access_key=os.environ.get('AWS_ACCESS_SECRET_KEY'),
                                     region_name=os.environ.get('AWS_REGION')
                                     )
            max_keys = 5
            pages = 0

            paginator = s3_client.get_paginator('list_objects_v2')

            with ThreadPoolExecutor() as executor:
                futures = [executor.submit(paginator.paginate,
                                           Bucket=os.environ.get('AWS_BUCKET'),
                                           PaginationConfig={'PageSize': max_keys})]

                for future in concurrent.futures.as_completed(futures):
                    for page in future.result():
                        pages += 1
                        print(f"Page: {pages}")
                        for content in page['Contents']:
                            if search in content['Key']:
                                print(content['Key'])
                                return web.Response(text=s3_client.generate_presigned_url('get_object',
                                                                                          {'Bucket': os.environ.get(
                                                                                              'AWS_BUCKET'),
                                                                                              'Key': content['Key']},
                                                                                          300))

