from typing import List
from azure.storage.blob import AccessPolicy, BlobServiceClient, ContainerSasPermissions
from azure.storage.blob import generate_container_sas
from azure.iot.hub import DigitalTwinClient
import azure.functions as func

import os
import sys
import logging
import json
from datetime import datetime, timedelta

connect_timeout_in_seconds = 10
response_timeout_in_seconds = 10

try:
    CONNECTION_STRING = os.environ['AZURE_STORAGE_CONNECTION_STRING']
except KeyError:
    print("AZURE_STORAGE_CONNECTION_STRING must be set.")
    sys.exit(1)

try:
    CONTAINER_NAME = os.environ['AZURE_STORAGE_CONTAINER_NAME']
except KeyError:
    print("AZURE_STORAGE_CONTAINER_NAME must be set.")
    sys.exit(1)

try:
    IOTHUB_CONNECTION_STRING = os.getenv("IOTHUB_CONNECTION_STRING")
except KeyError:
    print("IOTHUB_CONNECTION_STRING must be set.")
    sys.exit(1)

def main(events: List[func.EventHubEvent]):
    for event in events:
        logging.info('Python EventHub trigger processed an event: %s', event.get_body().decode('utf-8'))

        try:
            device_id = event.iothub_metadata["connection-device-id"]
            token = create_container_access_token()
            call_device_method(device_id, "TriggerDeviceToCloudServiceResponse", token)
        except Exception as error:
            print(error)


def create_container_access_token():
    service_client = BlobServiceClient.from_connection_string(CONNECTION_STRING)
    container_client = service_client.get_container_client(CONTAINER_NAME)

    # Create access policyF
    access_policy = AccessPolicy(permission=ContainerSasPermissions(read=True),
                                 expiry=datetime.utcnow() + timedelta(hours=1),
                                 start=datetime.utcnow() - timedelta(minutes=1))
    identifiers = {'my-access-policy-id': access_policy}

    # Set the access policy on the container
    container_client.set_container_access_policy(signed_identifiers=identifiers)

    # Use access policy to generate a sas token
    sas_token = generate_container_sas(
        container_client.account_name,
        container_client.container_name,
        account_key=container_client.credential.account_key,
        policy_id='my-access-policy-id'
    )

    return sas_token

def call_device_method(device_id, command_name, payload):
    digital_twin_client = DigitalTwinClient(IOTHUB_CONNECTION_STRING)

    invoke_command_result = digital_twin_client.invoke_command(
        device_id, command_name, payload, connect_timeout_in_seconds, response_timeout_in_seconds
    )
    if invoke_command_result:
        print(invoke_command_result)
    else:
        print("No invoke_command_result found")