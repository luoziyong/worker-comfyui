import os
import time
import uuid
import json
import threading

import oss2
import runpod
import requests
import websocket
from requests.adapters import HTTPAdapter, Retry

HOST = "127.0.0.1:3021"
OUTPUT_PATH = "/ComfyUI/output"
TEMP_PATH = "/ComfyUI/temp"
INPUT_PATH = "/ComfyUI/input"
NOSTREAMING = os.environ.get('NOSTREAMING', False) in ('true', '1', 't')

automatic_session = requests.Session()
retries = Retry(total=10, backoff_factor=0.1, status_forcelist=[502, 503, 504])
automatic_session.mount('http://', HTTPAdapter(max_retries=retries))


# ---------------------------------------------------------------------------- #
#                              Automatic Functions                             #
# ---------------------------------------------------------------------------- #
def wait_for_service(url):
    '''
    Check if the service is ready to receive requests.
    '''
    while True:
        try:
            requests.get(url, timeout=120)
            return
        except requests.exceptions.RequestException:
            print("Service not ready yet. Retrying...")
        except Exception as err:
            print("Error: ", err)

        time.sleep(0.2)

def queue_prompt(request):
    response = automatic_session.post(url=f'http://{HOST}/prompt',
                                      json=request, timeout=600)
    return response.json()

def websockets_api(request):
    client_id = request['client_id']
    if client_id is None:
        yield {"type": "execution_error", "data": {"exception_message": "client_id is required"}}
        return

    ws = websocket.WebSocket()
    ws.connect('ws://{}/ws?clientId={}'.format(HOST, client_id), timeout=10)
    prompt_id = queue_prompt(request)['prompt_id']

    start_time = time.time()
    while True:
        if time.time() - start_time > 120:
            yield {"type": "execution_error", "data": {"exception_message": "timeout"}}
            break

        out = ws.recv()
        if isinstance(out, str):
            message = json.loads(out)
            yield message
            if message['type'] == 'executing':
                data = message['data']
                if data['node'] is None and data['prompt_id'] == prompt_id:
                    break  # Execution is done
        else:
            continue  # previews are binary data
    ws.close()

def get_oss_client():
    endpoint_url = os.environ.get('BUCKET_ENDPOINT_URL', None)
    access_key_id = os.environ.get('BUCKET_ACCESS_KEY_ID', None)
    secret_access_key = os.environ.get('BUCKET_SECRET_ACCESS_KEY', None)
    bucket_name = os.environ.get('BUCKET_NAME', None)

    if endpoint_url and access_key_id and secret_access_key:
        auth = oss2.Auth(access_key_id, secret_access_key)
        bucket = oss2.Bucket(auth, endpoint_url, bucket_name)
    else:
        bucket = None

    return bucket

def upload_image(job_id, image_location, result_index=0, results_list=None):
    '''
    Upload a single file to bucket storage.
    '''
    bucket = get_oss_client()
    image_name = str(uuid.uuid4())[:8]
    file_directory = image_location.split('/')[-2]
    file_extension = os.path.splitext(image_location)[1]

    if bucket is None:
        print("No bucket endpoint set, saving to disk folder 'simulated_uploaded'")
        sim_upload_location = f"simulated_uploaded/{image_name}{file_extension}"

        if results_list is not None:
            results_list[result_index] = sim_upload_location

        return sim_upload_location

    key = f'{file_directory}/{job_id}/{image_name}{file_extension}'
    bucket.put_object_from_file(key, image_location)
    presigned_url = bucket.sign_url('GET', key, 3600, slash_safe=True)

    if results_list is not None:
        results_list[result_index] = presigned_url

    return presigned_url

def files(job_id, file_list):
    '''
    Uploads a list of files in parallel.
    Once all files are uploaded, the function returns the presigned URLs list.
    '''
    upload_progress = []  # List of threads
    file_urls = [None] * len(file_list)  # Resulting list of URLs for each file

    for index, selected_file in enumerate(file_list):
        new_upload = threading.Thread(
            target=upload_image,
            args=(job_id, selected_file, index, file_urls)
        )

        new_upload.start()
        upload_progress.append(new_upload)

    # Wait for all uploads to finish
    for upload in upload_progress:
        upload.join()

    return file_urls

def image_path(file_type, file_name):
    path = OUTPUT_PATH if file_type == 'output' else TEMP_PATH if file_type == 'temp' else INPUT_PATH
    return f'{path}/{file_name}'

def iamge_urls(job_id, message):
    if message['type'] == 'executed':
        data = message['data']
        if data['output'] is not None and data['output']['images'] is not None:
            images = data['output']['images']
            file_list = [image_path(image['type'], image['filename']) for image in images]
            print("Uploading files: ", file_list)
            if len(file_list) > 0:
                file_urls = files(job_id, file_list)
                for index, image in enumerate(images):
                    image['url'] = file_urls[index]
    return message

# ---------------------------------------------------------------------------- #
#                                RunPod Handler                                #
# ---------------------------------------------------------------------------- #
async def handler_streaming(event):
    '''
    This is the handler function that will be called by the serverless.
    '''
    print("Job received by handler: {}".format(event))

    job_id = event['id']
    input = event["input"]
    generator = websockets_api(input)

    for message in generator:
        output = iamge_urls(job_id, message)

        # Yield the output
        yield output

async def handler(event):
    '''
    This is the handler function that will be called by the serverless.
    '''
    print("Job received by handler: {}".format(event))

    job_id = event['id']
    input = event["input"]
    generator = websockets_api(input)

    outputs = []
    for message in generator:
        output = iamge_urls(job_id, message)
        outputs.append(output)

    return outputs

if __name__ == "__main__":
    wait_for_service(url=f'http://{HOST}')

    print("ComfyUI Service is ready. Starting RunPod...")

    if not NOSTREAMING:
        runpod.serverless.start({
            "handler": handler_streaming,
            "return_aggregate_stream": True
        })
    else:
        runpod.serverless.start({
            "handler": handler
        })
