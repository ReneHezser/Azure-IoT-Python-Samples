# SenseHat for Rasperry Pi
Module Twin:
```json
"properties": {
		"desired": {
			"Message": {
				"text": "Azure IoT Edge",
				"color": {
					"red": 0,
					"green": 0,
					"blue": 255
				}
			},
			"$metadata": {
```

The module needs to run in privileged mode to access the GPIOs.

## Environment Variables
- ```ReadInterval``` (in seconds) controls how often sensors are read and values sent do Azure IoT Hub. It will default to 5 seconds, if not specified.