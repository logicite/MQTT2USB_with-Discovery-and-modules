#!/usr/bin/python3
# -*- coding: utf-8 -*-

import asyncio
from bleak import BleakScanner


# à partir de la liste des noms [MODULE_ONLY] :
# créer les items pour DICOVERY
LYWSD_uuids = config_added["MODULE_ONLY"]

for n in LYWSD_uuids:

  confME = \
    [\
      ["sensor",\
        {\
          "name": "Xiaomi "+n+"-temp",\
          "unique_id": n+"-temp",\
          "device class": "temperature",\
          "state_topic": "thermometre/ATC_"+n,\
          "unit_of_measurement": "°C",\
          "value_template": "{{ value_json.temp | is_defined }}",\
        }\
      ],\
      ["sensor",\
        {\
          "name": "Xiaomi "+n+"-hum",\
          "unique_id": n+"-hum",\
          "device class": "humidity",\
          "state_topic": "thermometre/ATC_"+n,\
          "unit_of_measurement": "%",\
          "value_template": "{{ value_json.hum | is_defined }}",\
        }\
      ],
      ["sensor",\
        {\
          "name": "Xiaomi "+n+"-bat",\
          "unique_id": n+"-bat",\
          "device class": "battery",\
          "state_topic": "thermometre/ATC_"+n,\
          "unit_of_measurement": "%",\
          "value_template": "{{ value_json.bat | is_defined }}",\
        }\
      ]\
    ]

  confDEV = \
    {\
      "identifiers": ["Xiaomi "+n],\
      "manufacturer": "Logicite",\
      "model": "Mijia 2",\
      "name": "Xiaomi Mijia "+n,\
      "sw_version": "1.0"\
    }

  confME[0][1]["dev"] = confDEV
  confME[1][1]["dev"] = confDEV
  confME[2][1]["dev"] = confDEV

  config_ajout_valeurs(module, config, "DISCOVERY", confME)


scan_interval_LYWSD = 60 * 5
scan_last_LYWSD = time.time() - scan_interval_LYWSD - 1


def MQTT_analyze_LYWSD(localTopic, localMessage):
  "détermine les actions à mener pour des topics dédiés à ce module"

  Message_traite = False

  # s'il faut changer l'intervalle de mise à jour des données
  if localTopic == "thermometre/scan_interval_LYWSD":
    try:
      scan_interval_LYWSD = int(localMessage)
      Message_traite = True
    except:
      return

  if not Message_traite:
    return 1

  return 0


async def BLEscan_LYWSD():
  "on scanne les BLE advertising data autour de nous, si le délai de mise à jour est dépassé"

  # on suppose que le scan va réussir, donc on empeche de lancer un nouveau scan, mais on sauvegarde temporairement le moment du dernier scan
  global scan_last_LYWSD
  scan_last_LYWSD_temp = scan_last_LYWSD
  scan_last_LYWSD = time.time()

  devices = await BleakScanner.discover(return_adv=True)

  #if len(devices) ==0: return 0

  scan_failure_LYWSD = False

  for d, a in devices.values():
    if d.name[-6:] in LYWSD_uuids:
        localValue = list(d.details["props"]["ServiceData"].values())[0].hex()

        # inspiré par https://github.com/JsBergbau/MiTemperature2/blob/c25ab3645199aa5c802d4c852f760dc82ba2bf27/LYWSD03MMC.py#L640
        LYWSD_Temperature = int.from_bytes(bytearray.fromhex(localValue[12:16]),byteorder='big',signed=True)/10.
        LYWSD_Humidity = int.from_bytes(bytearray.fromhex(localValue[16:18]),byteorder='big',signed=True)
        LYWSD_BatPercentage = int(localValue[18:20], 16)
        LYWSD_BatVoltage = int(localValue[20:24], 16) /1000

        sendMe = """{"temp" : """ + str(LYWSD_Temperature) + """ , "hum" : """ + str(LYWSD_Humidity) + """ , "bat" : """ + str(LYWSD_BatPercentage) + "}"
        if MQTT_publish("thermometre/" + d.name, sendMe) != 0:
          scan_failure_LYWSD = True

        time.sleep(0.5)

  # si les scans n'ont pas été correctement publiés sur MQTT, on remet l'ancien moment du dernier scan (pour en relancer un bientôt)
  if scan_failure_LYWSD:
    scan_last_LYWSD = scan_last_LYWSD_temp


def loopME_LYWSD():
  if time.time() - scan_last_LYWSD > scan_interval_LYWSD:
    asyncio.run(BLEscan_LYWSD())


if __name__ == "__main__":
  pass









##{'path': '/org/bluez/hci0/dev_A4_C1_38_BB_63_3A', 'props': {'Address': 'A4:C1:38:BB:63:3A', 'AddressType': 'public', 'Name': 'ATC_BB633A', 'Alias': 'ATC_BB633A', 'Paired': False, 'Trusted': False, 'Blocked': False, 'LegacyPairing': False, 'RSSI': -77, 'Connected': False, 'UUIDs': [], 'Adapter': '/org/bluez/hci0', 'ServiceData': {'0000181a-0000-1000-8000-00805f9b34fb': bytearray(b'\xa4\xc18\xbbc:\x00\xc4EX\x0b\xbck')}, 'ServicesResolved': False}}


##print (b'\xa4\xc18\xbbc:\x00\xde@T\x0b\x99\x16'.hex())
##a4c138bb633a00de40540b9916

##print (int.from_bytes(bytearray.fromhex('a4c138bb633a00c445580bbc6b'[12:16]),byteorder='big',signed=True)/10.)

##température : print (int.from_bytes(bytearray.fromhex(b'\xa4\xc18\xbbc:\x00\xcfCY\x0b\xc0S'.hex()[12:16]),byteorder='big',signed=True)/10.)
##humidité : print (int.from_bytes(bytearray.fromhex(b'\xa4\xc18\xbbc:\x00\xcfCY\x0b\xc0S'.hex()[16:18]),byteorder='big',signed=True)) 




# def LYWSD_analyze(localName, localValue):
#   LYWSD_Temperature = int.from_bytes(bytearray.fromhex(localValue.hex()[12:16]),byteorder='big',signed=True)/10.
#   LYWSD_Humidity = int.from_bytes(bytearray.fromhex(localValue.hex()[16:18]),byteorder='big',signed=True)
#   LYWSD_BatPercentage = int(localValue.hex()[18:20], 16)
#   LYWSD_BatVoltage = int(localValue.hex()[20:24], 16) /1000

#   sendMe = """{"temp" : """ + LYWSD_Temperature + """, "hum" : """ + LYWSD_Humidity + """, "bat" : """ + LYWSD_BatPercentage + "}"

#   if MQTT_publish("thermometre/" + localName, sendMe) != 0:
#     return 1

#   return 0















  # configME = \
  # [\
  #   ["sensor",\
  #     {\
  #       "name": "Xiaomi "+n+"-temp",\
  #       "unique_id": n+".temp",\
  #       "device class": "temperature",\
  #       "state_topic": "thermometre/"+n,\
  #       "unit_of_measurement": "°C",\
  #       "value_template": "{{ value_json.temp | is_defined }}",\

  #       "dev":\
  #       {\
  #         "identifiers": ["Xiaomi "+n],\
  #         "manufacturer": "Logicite",\
  #         "model": "Mijia 2",\
  #         "name": "Xiaomi Mijia "+n,\
  #         "sw_version": "1.0"\
  #         }\
  #     }\
  #   ]\
  # ]
  # config_ajout_valeurs(module, config, "DISCOVERY", configME)

  # configME = [\
  #   ["sensor",\
  #     {\
  #       "name": "Xiaomi "+n+"-hum",\
  #       "unique_id": n+".hum",\
  #       "device class": "humidity",\
  #       "state_topic": "thermometre/"+n,\
  #       "unit_of_measurement": "%",\
  #       "value_template": "{{ value_json.hum | is_defined }}",\

  #       "dev":\
  #       {\
  #         "identifiers": ["Xiaomi "+n],\
  #         "manufacturer": "Logicite",\
  #         "model": "Mijia 2",\
  #         "name": "Xiaomi Mijia "+n,\
  #         "sw_version": "1.0"\
  #         }\
  #      }\
  #      ]\
  # ]
  # config_ajout_valeurs(module, config, "DISCOVERY", configME)

  # configME = [\
  #   ["sensor",\
  #     {\
  #       "name": "Xiaomi "+n+"-bat",\
  #       "unique_id": n+".bat",\
  #       "device class": "battery",\
  #       "state_topic": "thermometre/"+n,\
  #       "unit_of_measurement": "%",\
  #       "value_template": "{{ value_json.bat | is_defined }}",\

  #       "dev":\
  #       {\
  #         "identifiers": ["Xiaomi "+n],\
  #         "manufacturer": "Logicite",\
  #         "model": "Mijia 2",\
  #         "name": "Xiaomi Mijia "+n,\
  #         "sw_version": "1.0"\
  #         }\
  #      }\
  #      ]\
  # ]
  # config_ajout_valeurs(module, config, "DISCOVERY", configME)
