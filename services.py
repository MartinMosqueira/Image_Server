import asyncio
import io
from aiohttp import web
import boto3
from dotenv import load_dotenv
import os
import time
import concurrent.futures

load_dotenv()


async def get_all_images(request):
    pass


def upload_to_s3(file_content, file_name, s3_client):
    s3_client.put_object(Body=file_content,
                         Bucket=os.environ.get('AWS_BUCKET'),
                         Key=file_name)


async def upload_image(request):
    time_start = time.time()
    try:
        data = await request.post()
        images = data.getall('imagenInput')

        s3_client = boto3.client('s3',
                                 aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
                                 aws_secret_access_key=os.environ.get('AWS_ACCESS_SECRET_KEY'),
                                 region_name=os.environ.get('AWS_REGION')
                                 )

        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = []

            for image in images:
                file_content = image.file.read()
                file_name = image.filename

                future = executor.submit(upload_to_s3, file_content, file_name, s3_client)
                futures.append(future)

            concurrent.futures.wait(futures)

        return web.Response(text="Imágenes subidas correctamente", status=200)

    except Exception as e:
        print(f"Error al subir imágenes: {e}")
        return web.Response(text="Error al subir imágenes", status=500)

    finally:
        time_end = time.time()
        print(f"Tiempo de ejecución: {time_end - time_start} segundos")


async def download_image(request):
    return web.Response(text="Response from GET")


async def delete_image(request):
    return web.Response(text="Response from DELETE")
