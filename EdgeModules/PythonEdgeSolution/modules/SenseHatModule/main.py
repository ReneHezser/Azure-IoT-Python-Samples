# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for
# full license information.

import datetime
import time
import os
import sys
import uuid
import asyncio
import threading
from azure.iot.device.aio import IoTHubModuleClient
from azure.iot.device import Message
from sense_hat import SenseHat
import json
import random

maxAccX=0
maxAccY=0
maxAccZ=0
sumTemp=0
sumHum=0
sumPres=0
measurement_count=0

async def main():
    try:
        if not sys.version >= "3.5.3":
            raise Exception( "The sample requires python 3.5.3+. Current version of Python: %s" % sys.version )
        print ( "IoT Hub Client for Python" )

        try:
            sense = SenseHat()
            senseHatAvailable = True
        except Exception as e:
            senseHatAvailable = False
            print ( "SenseHat error %s " % e )

        # The client object is used to interact with your Azure IoT hub.
        module_client = IoTHubModuleClient.create_from_edge_environment()
        # connect the client.
        await module_client.connect()

        def write_on_sensehat(patch):
            print("the data in the desired properties patch was: {}".format(patch))
            try:
                if 'Message' not in patch:
                    raise ValueError("The Twin needs to contain a JSON object Message")
                data = patch["Message"]
                if 'color' not in data:
                    raise ValueError("The color has not been specified.")
                if 'text' not in data:
                    raise ValueError("The text needs to be specified")

                color = data["color"]
                r = color["red"]
                g = color["green"]
                b = color["blue"]
                print("Color: R=%s,G=%s,B=%s" % (r, g, b))
                text = data["text"]

                if senseHatAvailable:
                    if len(text) > 1:
                        sense.show_message(text, text_colour=(r,g,b))
                    else:
                        sense.show_letter(text, (r,g,b))
                
            except Exception as e:
                print("Twin patch error %s " % e)

        async def readSensors():
            global maxAccX
            global maxAccY
            global maxAccZ
            global sumTemp
            global sumHum
            global sumPres
            global measurement_count

            if senseHatAvailable:
                acceleration = sense.get_accelerometer_raw()
                x = acceleration['x']
                y = acceleration['y']
                z = acceleration['z']

                if maxAccX < abs(x): maxAccX = x
                if maxAccY < abs(y): maxAccY = y
                if maxAccZ < abs(z): maxAccZ = z

                # Take readings from all three sensors and round the values to one decimal place
                t = round(sense.get_temperature(), 1)
                p = round(sense.get_pressure(), 1)
                h = round(sense.get_humidity(), 1)
                sumTemp += t
                sumPres += p
                sumHum += h
            else:
                x = random.random()
                y = random.random()
                z = random.random()
                sumTemp += random.randint(100, 300)/10.0
                sumPres += random.randint(9000, 11000)/10.0
                sumHum += random.randint(100, 800)/10.0
                time.sleep(0.5)

            measurement_count += 1
            # print(measurement_count)

        async def sendData():
            global maxAccX
            global maxAccY
            global maxAccZ
            global sumTemp
            global sumHum
            global sumPres
            global measurement_count

            # get average
            if measurement_count != 0:
                t = round(sumTemp/measurement_count, 1)
                p = round(sumPres/measurement_count, 1)
                h = round(sumHum/measurement_count, 1)
                # print("received values from {0} measurements".format(measurement_count))
                message = '{{"temperature":{0},"pressure":{1},"humidity":{2},"accellerationX":{3},"accellerationY":{4},"accellerationZ":{5}}}'.format(str(t), str(p), str(h), str(maxAccX), str(maxAccY), str(maxAccZ))
                print(message)

                # msg = Message('{"temperature":' + str(t) +',"pressure":'+str(p)+',"humidity":'+str(h)+'}')
                msg = Message(message)
                # print("Sending message: %s" % msg)
                msg.message_id = uuid.uuid4()
                msg.correlation_id = "senseHat-"+str(uuid.uuid4())
                msg.content_encoding = "utf-8"
                msg.content_type = "application/json"                    
                await module_client.send_message_to_output(msg, "sensors")
                print("Message sent")
                
                maxAccX=0
                maxAccY=0
                maxAccZ=0
                sumTemp=0
                sumHum=0
                sumPres=0
                measurement_count=0

        # define behavior for receiving a twin patch
        async def twin_patch_handler(patch):
            write_on_sensehat(patch)
            await module_client.patch_twin_reported_properties(patch)

        # set the twin patch handler on the client
        module_client.on_twin_desired_properties_patch_received = twin_patch_handler

        # get current twin on startup to write to the senseHat
        twin = await module_client.get_twin()
        print("Got current twin to write to the senseHat.")
        if ('desired' in twin):
            write_on_sensehat(twin["desired"])
        else:
            print("desired property is missing in twin")

        print("Starting sensor readings")
        if 'ReadInterval' not in os.environ:
            readInterval = 5
        else:
            readInterval = int(os.environ['ReadInterval'])
        print("Sensor read interval: %s" % str(readInterval))

        counter = readInterval
        start = time.time()
        while True:
            try:
                time.sleep(0.1)
                # print("[%s] Reading sensors" % datetime.datetime.now())
                # if senseHatAvailable:
                #     # Take readings from all three sensors and round the values to one decimal place
                #     t = round(sense.get_temperature(), 1)
                #     p = round(sense.get_pressure(), 1)
                #     h = round(sense.get_humidity(), 1)
                # else:
                #     t = random.randint(100, 300)/10.0
                #     p = random.randint(9000, 11000)/10.0
                #     h = random.randint(100, 800)/10.0
                await readSensors()

                if time.time() - start > 1:
                    start = time.time()
                    counter -= 1

                if counter <= 0:
                    print("sending...")
                    await sendData()
                
                    # msg = Message('{"temperature":' + str(t) +',"pressure":'+str(p)+',"humidity":'+str(h)+'}')
                    # print("Sending message: %s" % msg)
                    # msg.message_id = uuid.uuid4()
                    # msg.correlation_id = "senseHat-"+str(uuid.uuid4())
                    # msg.content_encoding = "utf-8"
                    # msg.content_type = "application/json"                    
                    # await module_client.send_message_to_output(msg, "sensors")
                    # print("Message sent")

                    counter = readInterval
                    start = time.time()

                # time.sleep(readInterval)
            except Exception as e:
                print("Error reading sensors %s" % e)

        # Finally, shut down the client
        await module_client.shutdown()

    except Exception as e:
        print ( "Unexpected error %s " % e )
        raise

if __name__ == "__main__":
    asyncio.run(main())

    # If using Python 3.6 or below, use the following code instead of asyncio.run(main()):
    # loop = asyncio.get_event_loop()
    # loop.run_until_complete(main())
    # loop.close()