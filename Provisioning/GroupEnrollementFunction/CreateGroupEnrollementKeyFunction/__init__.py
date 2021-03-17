import os
import logging

import azure.functions as func
from provisioningserviceclient import ProvisioningServiceClient

import hashlib
import hmac
import base64


def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    device_id = req.params.get('deviceid')
    if not device_id:
        try:
            req_body = req.get_json()
        except ValueError:
            pass
        else:
            device_id = req_body.get('deviceid')

    if device_id:
        attestation_key = get_attestation_key()
        device_key = get_derived_device_key(device_id, attestation_key)
        return func.HttpResponse(device_key)
        # return func.HttpResponse(f"Creating a key for device '{device_id}'...")
    else:
        return func.HttpResponse(
            "This HTTP triggered function executed successfully. Pass a deviceid in the query string or in the request body for a personalized response.",
            status_code=200
        )


def get_attestation_key():
    connection_string = os.environ['DpsConnectionString']
    psc = ProvisioningServiceClient.create_from_connection_string(connection_string)
    group_name = os.environ['DpsEnrollmentGroupName']
    attestation_mechanism = psc.get_enrollment_group_attestation_mechanism(group_name)
    primary_key = attestation_mechanism.symmetric_key.primary_key
    return primary_key


def get_derived_device_key(registration_id, key):
    message = bytes(registration_id, 'utf-8')
    secret = base64.b64decode(key)

    signature = base64.b64encode(hmac.new(secret, message, digestmod=hashlib.sha256).digest())
    return signature
