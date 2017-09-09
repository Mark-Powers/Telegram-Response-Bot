import requests
import json
import re
import time
import threading
import os
import imp

from roll import Roll
from character import Character
from character import CharacterManager
from config import Config
from trigger import Trigger
from plugin import Plugin


class Bot:
	def __init__(self, config):
		self.username = config.get_bot_username()
		self.directory = config.get_bot_dir()
		self.base_url = "https://api.telegram.org/bot"+config.get_token()+"/"
		self.sleep_interval = config.get_sleep_interval()

		self.plugins = []
		for plugin in config.get_plugins():
			print(plugin)
			mod = __import__("plugins." + plugin)
			self.plugins.append(eval("mod."+plugin+".load()"))
		print(self.plugins)

	def start(self):
		last_update = 0
		while True:
			get_updates = json.loads(requests.get(self.base_url + 'getUpdates', params=dict(offset=(last_update+1))).text)

			for update in get_updates['result']:
				last_update = update['update_id']
				if 'message' in update and 'text' in update['message']:
					try:
						user = update['message']['from']['username']
					except:
						user = str(update['message']['from']['id'])
					message = update['message']['text']
					message = message.replace("@"+self.username, "")
					c_id = update['message']['chat']['id']
					print(str(last_update)+": "+user)
					if message.startswith("/"): # Message is a command
						command = Command(user, message, c_id)
						if command.get_command() in commands:
							try:
								commands[command.get_command()](command)
							except Exception as e:
								send_message(c_id, "I'm afraid I can't do that.\n'"+str(e)+"'")
					elif message.startswith("silence"):
						if "reply_to_message" in update['message']:
							reply = update['message']["reply_to_message"]
							u_id = reply["from"]["id"]
							name = reply["from"]["first_name"]
							timeout_member(c_id, u_id, name, 5)
					else: # Message is normal
						#reply = triggers.parse(message)
						continue
						if reply:
							send_message(c_id, reply)
			time.sleep(self.sleep_interval)

bot = Bot(Config("config.txt"))

dice_format_pattern = re.compile("\d+d\d+", re.IGNORECASE)

# triggers = Trigger(bot_dir+"/triggers")
# print("TRIGGERS")
# print(triggers.get_keys())
#
# pasta = Pasta(bot_dir+"/pasta")
# print("\nPASTA:")
# print(pasta.get_keys())
#
# char_man = CharacterManager(bot_dir+"/characters")
# print("\nCHARACTERS:")
# print(char_man.get_users())

def send_message(id, message):
	requests.get(url + 'sendMessage', params=dict(chat_id=id, text=message))

def restrict_chat_member(id, u_id, name, state):
	reply = requests.get(url + "restrictChatMember", params=dict(chat_id=id, user_id=u_id, can_send_messages=state))
	if reply.ok:
		if state:
			send_message(id, name + " can talk again.")
		else:
			send_message(id, name + " has been silenced!")
	else:
		send_message(id, "I'm afraid I can't do that.\n" + str(reply.status_code))

def timeout_member(id, u_id, name, minutes):
	restrict_chat_member(id, u_id, name, False)
	t = threading.Timer(minutes*60, restrict_chat_member, [id, u_id, name, True])
	t.start()

def add_trigger(command):
	parts = command.get_args().splitlines()
	if len(parts) > 1 and triggers.add(parts[0], parts[1:]):
		send_message(command.get_id(), "Added trigger: " + parts[0])
	else:
		send_message(command.get_id(), "Invalid syntax")

def list_trigger(command):
	if triggers.get_keys():
		send_message(command.get_id(), "\n".join(triggers.get_keys()))
	else:
		send_message(command.get_id(), "No triggers set!")

def add_pasta(command):
	parts = command.get_args().split("\n",1)
	if len(parts) == 2:
		pasta.add(parts[0], parts[1])
		send_message(command.get_id(), "Added pasta: " + parts[0])
	else:
		send_message(command.get_id(), "Invalid syntax")

def list_pasta(command):
	if pasta.get_keys():
		send_message(command.get_id(), "\n".join(pasta.get_keys()))
	else:
		send_message(command.get_id(), "No pasta set!")

def send_pasta(command):
	send_message(command.get_id(), pasta.get_pasta(command.get_args))

def send_applause(command):
	for i in range(0,3):
		send_message(command.get_id(), u"😎//")

def roll_dice(command):
	user = command.get_sender()
	if command.get_mention():
		user = command.get_mention()
	rolls = []
	constant = []
	mods = []
	parts = command.get_args().split("+")
	for part in parts:
		if "-" in part:
			try:
				index = part.index("-",1)
				new_part = part[index:]
				part = part[:index]
				parts.append(new_part)
			except:
				pass # part is just a plain negative number
		part = part.strip()
		if dice_format_pattern.search(part):
			rolls.append(Roll(part))
		elif part.replace("-","",1).isdigit():
			constant.append(int(part))
		else:
			if char_man.has_character(user) and part in char_man.get_character(user).stats:
				mods.append(part)
	result = user + " rolled:"
	total = 0
	for roll in rolls:
		total += roll.sum()
		result += "\n(" + ", ".join(str(s) for s in roll.rolls) + ") = " + str(roll.sum())
	for mod in mods:
		mod_value = int((char_man.get_character(user).stats[mod]-10)/2)
		total += mod_value
		result += "\n + " + mod +" (" + str(mod_value) + ")"
	for c in constant:
		total += c
		result += "\n + " + str(c)
	result += "\n = " + str(total)
	send_message(command.get_id(), result)

def show_stats(command):
	user = command.get_sender()
	if command.get_mention():
		user = command.get_mention()
	if char_man.has_character(user):
		send_message(command.get_id(), char_man.get_character(user).stat_string())
	else:
		send_message(command.get_id(), user + " does not have a character!")

def show_inventory(command):
	user = command.get_sender()
	if command.get_mention():
		user = command.get_mention()
	if char_man.has_character(user):
		send_message(command.get_id(), char_man.get_character(user).inventory_string())
	else:
		send_message(command.get_id(), user + " does not have a character!")

def set_stat(command):
	user = command.get_sender()
	if command.get_mention():
		user = command.get_mention()
	if char_man.has_character(user):
		# TODO could stats be multiple words?
		parts = command.get_args().split(" ")
		if len(parts)==2:
			char_man.get_character(user).set_stat(parts[0], int(parts[1]))
			char_man.save_char(user)
			show_stats(command)
		else:
			send_message(command.get_id(), "Invalid syntax arguments!")
	else:
		send_message(command.get_id(), user + " does not have a character!")

def give_item(command):
	user = command.get_sender()
	if command.get_mention():
		user = command.get_mention()
	if char_man.has_character(user):
		if command.get_args():
			parts = command.get_args().split("|")
			item = parts[0].strip()
			amount = 1
			desc = "no description"
			if len(parts) > 1 and parts[1].strip().isdigit():
				amount = int(parts[1].strip())
			if len(parts) > 2:
				desc = parts[2].strip()
			char_man.get_character(user).give_item(item, amount, desc)
			char_man.save_char(user)
			show_inventory(command)
		else:
			send_message(command.get_id(), "Requires at least one argument!")
	else:
		send_message(command.get_id(), user + " does not have a character!")

def create_character(command):
	if message.get_args():
		char_man.add_character(message.get_sender(), Character(message))
		char_man.save_char(message.get_sender())
		send_message(c_id, "Created character '" + message.get_args() + "'' for player " + user)
	else:
		send_message(c_id, "Name your character!")

class Command:
	def __init__(self, sender, message, id):
		message = message.strip()
		if " " in message:
			args_index = message.index(" ")
		else:
			args_index = len(message)
		self.command = message[:args_index]
		message = message[args_index+1:]

		user_match = re.search("@(\w+)", message)
		if user_match:
			self.mention = user_match.group(1)
		else:
			self.mention = ""
		message = message.replace("@"+user,"",1).strip()
		self.args = message.strip()
		self.sender = sender
		self.id = id

	def get_sender(self):
		return self.sender

	def get_id(self):
		return self.id

	def get_command(self):
		return self.command

	def get_mention(self):
		return self.mention

	def get_args(self):
		return self.args

commands = {
	"/newtrigger": add_trigger,
	"/newpasta": add_pasta,
	"/listtrigger": list_trigger,
	"/listpasta": list_pasta,
	"/applause": send_applause,
	"/pasta": send_pasta,
	"/r": roll_dice,
	"/roll": roll_dice,
	"/create_character": create_character,
	"/show_stats": show_stats,
	"/show_inventory": show_inventory,
	"/set_stat": set_stat,
	"/give_item": give_item
}

bot.start()
