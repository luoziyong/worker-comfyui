import time

import runpod
import websocket
import json
import requests
from requests.adapters import HTTPAdapter, Retry

HOST = "127.0.0.1:3021"

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
    ws = websocket.WebSocket()
    ws.connect('ws://{}/ws?clientId={}'.format(HOST, client_id))
    prompt_id = queue_prompt(request)['prompt_id']
    while True:
        out = ws.recv()
        if isinstance(out, str):
            message = json.loads(out)
            yield message
            if message['type'] == 'executing':
                data = message['data']
                if data['node'] is None and data['prompt_id'] == prompt_id:
                    break #Execution is done
        else:
            continue #previews are binary data
    ws.close()

# ---------------------------------------------------------------------------- #
#                                RunPod Handler                                #
# ---------------------------------------------------------------------------- #

async def handler_streaming(event):
    '''
    This is the handler function that will be called by the serverless.
    '''
    print("Job received by handler: {}".format(event))

    input = event["input"]
    generator = websockets_api(input)

    for message in generator:
        ret = message

        # Yield the output
        yield ret

if __name__ == "__main__":
    wait_for_service(url=f'http://{HOST}')

    print("ComfyUI Service is ready. Starting RunPod...")

    runpod.serverless.start({
        "handler": handler_streaming,
        "return_aggregate_stream": True
    })
