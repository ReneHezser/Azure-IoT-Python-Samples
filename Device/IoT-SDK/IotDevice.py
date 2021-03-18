# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.
import random
import time
import threading
import os
import asyncio
import json

# Using the Python Device SDK for IoT Hub:
#   https://github.com/Azure/azure-iot-sdk-python
from azure.iot.device import ProvisioningDeviceClient, IoTHubDeviceClient, Message, MethodResponse
from azure.core.exceptions import AzureError
from azure.storage.blob import BlobClient

# The device connection string to authenticate the device with your IoT hub.
# Using the Azure CLI:
# az iot hub device-identity show-connection-string --hub-name {YourIoTHubName} --device-id MyNodeDevice --output table
# Connect directly to IoT Hub
CONNECTION_STRING = ""
# Connect vie DPS
DPS_ID_SCOPE = ""
DPS_REGISTRATION_ID = ""
DPS_REGISTRATION_KEY = ""
DPS_GLOBAL_SERVICE_ENDPOINT = "global.azure-devices-provisioning.net"

# Define the JSON message to send to IoT Hub.
TEMPERATURE = 21.0
HUMIDITY = 45
MSG_TXT = '{{"temperature": {temperature},"humidity": {humidity}}}'

INTERVAL = 1
JSON_FILE = 'config.json'


def iothub_client_init():
    # Create an IoT Hub client
    client = IoTHubDeviceClient.create_from_connection_string(CONNECTION_STRING)
    return client


def provisioning_client_init():
    client = ProvisioningDeviceClient.create_from_symmetric_key(DPS_GLOBAL_SERVICE_ENDPOINT, DPS_REGISTRATION_ID, DPS_ID_SCOPE, DPS_REGISTRATION_KEY)
    registrationResult = client.register()
    return 'HostName=' + registrationResult.registration_state.assigned_hub + ';DeviceId=' + DPS_REGISTRATION_ID + ';SharedAccessKey=' + DPS_REGISTRATION_KEY


def device_method_listener(device_client):
    global INTERVAL
    while True:
        method_request = device_client.receive_method_request()
        print("\nMethod callback called with:\nmethodName = {method_name}\npayload = {payload}".format(method_name=method_request.name, payload=method_request.payload))
        if method_request.name == "SetTelemetryInterval":
            try:
                INTERVAL = int(method_request.payload)
            except ValueError:
                response_payload = {"Response": "Invalid parameter"}
                response_status = 400
            else:
                response_payload = {"Response": "Executed direct method {}".format(method_request.name)}
                response_status = 200
        elif method_request.name == "UploadFile":
            try:
                filename = method_request.payload
                response_status, response_payload = asyncio.run(upload_blob(device_client, filename))
            except ValueError:
                response_payload = {"Response": "Invalid filename passed as body"}
        elif method_request.name == "ChangeParameter":
            try:
                # parameter = json.loads(method_request.payload)
                parameter = method_request.payload
                response_status, response_payload = asyncio.run(change_parameter(device_client, parameter))
            except ValueError:
                response_status = 400
                response_payload = {"Response": "Invalid parameter passed as body"}
        else:
            response_payload = {
                "Response": "Direct method {} not defined".format(method_request.name)}
            response_status = 404

        method_response = MethodResponse(method_request.request_id, response_status, payload=response_payload)
        device_client.send_method_response(method_response)


async def main():
    try:
        print("IoT Hub device sending periodic messages, press Ctrl-C to exit")

        # Start a thread to listen
        device_method_thread = threading.Thread(target=device_method_listener, args=(client,))
        device_method_thread.daemon = True
        device_method_thread.start()

        while True:
            # Build the message with simulated telemetry values.
            temperature = TEMPERATURE + (random.random() * 15)
            humidity = HUMIDITY + (random.random() * 20)
            msg_txt_formatted = MSG_TXT.format(temperature=temperature, humidity=humidity)
            message = Message(msg_txt_formatted)

            # Add a custom application property to the message.
            # An IoT hub can filter on these properties without access to the message body.
            if temperature > 30:
                message.custom_properties["temperatureAlert"] = "true"
            else:
                message.custom_properties["temperatureAlert"] = "false"

            # Send the message.
            print("Sending message: {}".format(message))
            client.send_message(message)
            print("Message sent")
            time.sleep(INTERVAL)

    except Exception as ex:
        print("\nException:")
        print(ex)

    except KeyboardInterrupt:
        print("\nIoTHubDeviceClient sample stopped")

    finally:
        # Finally, disconnect the client
        await client.disconnect()


async def upload_blob(device_client, filename):
    blob_name = os.path.basename(filename)
    storage_info = device_client.get_storage_info_for_blob(blob_name)
    success, result = await store_blob(storage_info, filename)

    response = {"Response": blob_name}
    return (200 if success else 400, response)


async def store_blob(blob_info, file_name):
    try:
        sas_url = "https://{}/{}/{}{}".format(
            blob_info["hostName"],
            blob_info["containerName"],
            blob_info["blobName"],
            blob_info["sasToken"]
        )

        print("\nUploading file: {} to Azure Storage as blob: {} in container {}\n".format(file_name, blob_info["blobName"], blob_info["containerName"]))

        # Upload the specified file
        with BlobClient.from_blob_url(sas_url) as blob_client:
            with open(file_name, "rb") as f:
                result = blob_client.upload_blob(f, overwrite=True)
                return (True, result)

    except FileNotFoundError as ex:
        # catch file not found and add an HTTP status code to return in notification to IoT Hub
        ex.status_code = 404
        return (False, ex)

    except AzureError as ex:
        # catch Azure errors that might result from the upload operation
        return (False, ex)


async def change_parameter(device_client, parameter):
    with open(JSON_FILE, 'r') as infile:
        filecontent = json.load(infile)
    infile.close()

    # filecontent[parameter]=
    for key in parameter:
        print(key, parameter[key])
        filecontent[key] = parameter[key]

    with open(JSON_FILE, 'w') as outfile:
        json.dump(filecontent, outfile)
    outfile.close()

    response = {"Response": "OK"}
    return (200, response)

if __name__ == '__main__':
    print("IoT Hub Quickstart - Simulated device with method listener and file upload")
    print("Press Ctrl-C to exit")

    # use DPS to get the IoT Hub ConnectionString
    if CONNECTION_STRING == '':
        CONNECTION_STRING = provisioning_client_init()

    client = iothub_client_init()

    asyncio.run(main())
