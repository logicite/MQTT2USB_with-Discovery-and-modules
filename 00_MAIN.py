#!/usr/bin/python3
# -*- coding: utf-8 -*-



#################################################
# apprendre à logger
#################################################
import logging      # pour les activités de logging
import os           # pour lire les variables système (ENVironnement)

default_log_level = logging.ERROR   # ou INFO
file_log_level = default_log_level

logger = logging.getLogger('EAR')
formatter = logging.Formatter('%(asctime)s - %(name)s / %(funcName)s - %(levelname)s - %(message)s')
logger.setLevel(default_log_level)

fh = logging.FileHandler(os.getenv('EAR_LOG_FILE', '/var/log/MQTT2USB/EAR.log'))
fh.setLevel(file_log_level)
fh.setFormatter(formatter)
logger.addHandler(fh)



#################################################
# lire le fichier de configuration
# voir aussi configParser pour d'autres formats de fichiers de config : https://docs.python.org/3/library/configparser.html
#################################################
logger.info('Lecture du fichier de configuration')

import json         # pour le fichier de configuration

config_file = os.getenv('EAR_CONF_FILE', 'config.json')
config = {}
try:
  with open(config_file) as json_data:
    config = json.load(json_data)
except Exception as e:
  logger.error("Echec du chargement de fichier de config")
  exit(1)

def config_ajout_valeurs(localFile, localDict, localCleAdded, localValueAdded):
  # ajouter des valeurs au dictionnaire config{}
  # si appel avec localDict, c'est une référence : changements dans la fonction affectent le dictionnaire hors de la fonction
  # si appel avec **localDict, c'est une copie de données donc aucun impact hors de la fonction

  # si la cle n'existait pas alors on la rajoute simplement
  if localCleAdded not in localDict:
    localDict[localCleAdded] = localValueAdded

  # si la cle existait
  else:
    # si la cle existait et que c'est une liste > on ajoute chaque valeur de la nouvelle liste
    if isinstance(localDict[localCleAdded], list):
      # on cherche à ajouter des éléments de liste à une liste
      for valueAdded in localValueAdded:
        if valueAdded not in localDict[localCleAdded]:
          localDict[localCleAdded].append(valueAdded)
        else:
          logger.warning("Fichier : %s - Cle : %s - Valeur : %s : existait déjà, non modifié" %(localFile, localCleAdded, localValueAdded))

    # si la cle existait et que ce n'est pas une liste > on ne modifie pas une clé déjà existante
    else:
      logger.warning("Fichier : %s - Cle : %s - Valeur : %s : existait déjà, non modifié" %(localFile, localCleAdded, localValueAdded))



fh.setLevel(config['log_level'])



#################################################
# connecter le port USB
#################################################
import time

logger.info('Définition du périphérique USB')

USB_present = False if config["USB_PORT"] == "" else True

if USB_present:
  import serial
  #The port is immediately opened on object creation, when a port is given
  #timeout = None: wait forever
  #timeout = 0: non-blocking mode (return immediately on read)
  #timeout = x: set timeout to x seconds
  myUSB = serial.Serial(port=config['USB_PORT'],baudrate=9600, timeout=0, write_timeout=0)

  # il faut laisser le temps à la carte ARDUINO de re-démarrer (se produit quand le port USB est initialisé)
  time.sleep(4)

  myUSB.buf = bytearray()
  #myUSB.open()

  def USB_linereader(localUSB):
    # lire ce qui arrive sur le port USB
    # voir aussi : https://stackoverflow.com/a/56240817
    i= localUSB.buf.find(b"\n")
    if i >= 0:
      r = localUSB.buf[:i+1]
      r = r.decode().strip()
      localUSB.buf = localUSB.buf[i+1:]
      return r

    i = max(1, min(2048, localUSB.in_waiting))
    data = localUSB.read(i)
    i = data.find(b"\n")
    if i >= 0:
      r = localUSB.buf + data[:i+1]
      r = r.decode().strip()
      localUSB.buf[0:] = data[i+1:]
      return r
    else:
      localUSB.buf.extend(data)



#################################################
# définir le client MQTT, sans s'y connecter pour l'instant
#################################################
logger.info('Définition du client MQTT')

import paho.mqtt.client as mqtt
import paho.mqtt.publish as publish
#on crée une nouvelle variable dans les objets mqtt.Client
mqtt.Client.flag_connected = False

myMQTT = mqtt.Client(client_id=config['MQTT_CLIENTID'])
myMQTT.reconnect_delay_set(min_delay=5, max_delay=120)
if config['MQTT_USER'] is not None:
  logger.info("MQTT Connexion de l'utilisateur %s.", config['MQTT_USER'])
  # pour se connecter avec un username & password
  myMQTT.username_pw_set(username=config['MQTT_USER'], password=config['MQTT_PASSWORD'])
  auth = {'username': config['MQTT_USER'], 'password': config['MQTT_PASSWORD']}

# définition des callbacks :
def MQTT_on_connect(client, userdata, flags, rc):
  if rc == 0:
    logger.info("MQTT Connexion - Return code: %s" % mqtt.connack_string(rc))
    client.flag_connected = True

    # ici on subscribe aux topics
    for [topicMQTT, topicUSB] in config['TOPICS']:
      logger.debug("MQTT Souscription au sujet : %s" % (topicMQTT+"/sb"))
      myMQTT.subscribe(topicMQTT + "/sb", 2)
      #if topicMQTT[-3:] == "IOT":
      #  MQTT_publish(topicMQTT, 'connexion') # la domotique devra répondre avec des instructions, en attendant on les demande avec 'I'
      #  MQTT_publish(topicMQTT, 'I')

    # ici on émet les messages DISCOVERY vers MQTT
    for [DISCOtype, DISCOmessage] in config['DISCOVERY']:
      DISCOtopic = config['DISCOVERY_prefix']+"/"+DISCOtype+"/"+DISCOmessage["unique_id"]+"/config"
      logger.debug( "MQTT DISCOVERY publication sur %s de : %s" % (DISCOtopic, json.dumps(DISCOmessage, ensure_ascii=False)) )
      MQTT_publish( DISCOtopic, json.dumps(DISCOmessage, ensure_ascii=False) )

  else:
    logger.warning("MQTT Erreur à la connexion - Return code: %s " % mqtt.connack_string(rc))
    exit(1)

def MQTT_on_disconnect(client, userdata, rc):
  if rc != 0:
    client.flag_connected = False
    logger.error("MQTT Déconnexion - Return code: %s" % mqtt.connack_string(rc))

def MQTT_on_publish(client, userdata, mid):
  logger.debug("MQTT Message publié : " + str(mid))

def MQTT_on_message(client, userdata, message):
  logger.debug("MQTT Message reçu : %s" % (message.topic))
  data_incoming = {
    'topic': message.topic,
    'payload': message.payload.decode('ascii'),
    'qos': message.qos
  }
  MQTT_analyze(data_incoming)

myMQTT.on_connect = MQTT_on_connect
myMQTT.on_disconnect = MQTT_on_disconnect
myMQTT.on_publish = MQTT_on_publish
myMQTT.on_message = MQTT_on_message
myMQTT.last_message=dict()



#################################################
# définir les fonctions locales du programme
#################################################
switcher_out = {
  True: "1",
  False: "0"
}

switcher_in = {
  "1": True,
  "True": True,
  "true": True,
  "0": False,
  "False": False,
  "false": False
}


def USB_publish(localUSB, localSujet, localMessage):
  if USB_present:
    localSend = str(localSujet) + ';' + str(localMessage) + '\n'
    try:
      logger.debug('USB_publish : destination %s / message %s' % (localSujet, localMessage))
      localUSB.write(localSend.encode('utf-8'))
    except Exception as e:
      logger.error('USB_publish : destinaion %s / message %s > Publish problem: %s' % (localSujet, localMessage, e))
      return 1

    return 0
  else:
    logger.debug("USB_publish non exécuté car pas de USB_PORT défini")
    return 1


def MQTT_publish(localSujet, localMessage):
  localMessage = switcher_out.get(localMessage, localMessage)	# transforme TRUE/FALSE en 1/0

  try:
    logger.debug('MQTT_publish : topic %s / payload %s' % (localSujet, localMessage))
    myMQTT.publish(localSujet, localMessage)
  except Exception as e:
    logger.error('MQTT_publish : topic %s / payload %s > Publish problem: %s' % (localSujet, localMessage, e))
    return 1

  return 0


def USB_analyze(localMessage):
  "détermine les actions à mener en fonction du message reçu"

  localMessage = str(localMessage).split(';')
  # localMessage[0] > destinataire
  # localMessage[1] > message

  Message_traite = False

  for [topicMQTT, topicUSB] in config['TOPICS']:
    if topicUSB == localMessage[0]:
      if MQTT_publish(topicMQTT + "/nb", localMessage[1]) == 0:
        Message_traite = True

  # chercher la fonction qui va peut-être utiliser aussi ce message
  for callME in USBfunc:
    logger.debug("Appel de la fonction de module : %s" % callME)
    if locals()[callME](localMessage) == 0:
      Message_traite = True

  # if localMessage[0] == "I":
  #  MQTT_publish_COM(localMessage[1])

  if not Message_traite:
    logger.warning( "Message USB non traité (%s)" % (localMessage) )


def MQTT_analyze(localMessage):
  "détermine les actions à mener en fonction du message reçu"

  topic = localMessage['topic']
  if topic[-3:] == "/sb":
    topic = localMessage['topic'][0:-3] # on enlève les 3 derniers caractères ("/sb")
  payload = localMessage['payload']
  payload = switcher_in.get(payload, payload)	# transforme 1/0 en TRUE/FALSE

  Message_traite = False

  for [topicMQTT, topicUSB] in config['TOPICS']:
    # les topicUSB vides ("") servent quand on veut subscribe à un topicMQTT sans renvoyer le message vers USB
    if topicMQTT == topic and topicUSB != "":
      if USB_publish(myUSB, topicUSB, payload) == 0:
        Message_traite = True

  # chercher la fonction qui va peut-être utiliser aussi ce message (topic, payload)
  for callME in MQTTfunc:
    logger.debug("Appel de la fonction de module : %s" % callME)
    if locals()[callME](topic, payload) == 0:
      Message_traite = True

  if not Message_traite:
    logger.warning( "Message MQTT non traité (%s)" % (localMessage) )



#################################################
# lire d'autres modules s'il y en a
#################################################
modules = os.listdir("./modules")
for module in modules:
  if module[-5:] == ".json":
    # si c'est un fichier de configuration
    # on lit le fichier de configuration et on rajoute des cles à config{}...
    config_added = {}
    try:
      with open("./modules/" + module) as json_data:
        config_added = json.load(json_data)
        for cle_added in config_added:
          if cle_added != "MODULE_ONLY":
            config_ajout_valeurs(module, config, cle_added, config_added[cle_added])

    except Exception as e:
      logger.error("Echec du chargement de fichier de config : %s" % (module))
      exit(1)

    # ... puis on lit le fichier .py s'il existe
    # s'il y a une fonction à exécuter immédiatement, elle le sera ici
    if module[:-5]+".py" in modules:
      exec(open("./modules/" + module[:-5] + ".py").read())



#################################################
# faire la liste finale des fonctions du programme
#################################################
# via https://stackoverflow.com/a/70672167
MQTTfunc = []
USBfunc = []
LOOPfunc = []

copy_dict = dict(locals())
for key, value in copy_dict.items():
  if "function" in str(value):
    if key[:13] == "MQTT_analyze_":
      MQTTfunc.append(key)
    if key[:12] == "USB_analyze_":
      USBfunc.append(key)
    if key[:7] == "loopME_":
      LOOPfunc.append(key)



#################################################
# main loop
#################################################
if __name__ == "__main__":
  logger.info("Démarrage général")

  # se connecter à MQTT
  myMQTT.connect(config['MQTT_HOST'], port=config['MQTT_PORT'], keepalive=config['MQTT_KEEPALIVE'])
  myMQTT.loop_start()


try:

  while True:
    time.sleep(1)

    if USB_present:
      r = USB_linereader(myUSB)
      if r:
        logger.debug("Début de USBanalyze : %s" % r)
        USB_analyze(r)

  # chercher les fonctions loopME des modules
    for callME in LOOPfunc:
      logger.debug("Appel de la fonction de module : %s" % callME)
      locals()[callME]()



# End program cleanly with keyboard
except KeyboardInterrupt:
  logger.info("Quit")

finally:
  logger.info("Arrêt général")
  myMQTT.loop_stop()
  if USB_present: myUSB.close
  time.sleep(2)
