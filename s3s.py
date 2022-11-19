#!/usr/bin/env python
# s3s (ↄ) 2022 eli fessler (frozenpandaman), clovervidia
# Based on splatnet2statink (ↄ) 2017-2022 eli fessler (frozenpandaman), clovervidia
# https://github.com/frozenpandaman/s3s
# License: GPLv3

import json, os, requests, sys, mmh3, base64, math, time
import iksm, utils

A_VERSION = "0.2.0"

DEBUG = False

os.system("") # ANSI escape setup
if sys.version_info[1] >= 7: # only works on python 3.7+
	sys.stdout.reconfigure(encoding='utf-8') # note: please stop using git bash

# CONFIG.TXT CREATION
if getattr(sys, 'frozen', False): # place config.txt in same directory as script (bundled or not)
	app_path = os.path.dirname(sys.executable)
elif __file__:
	app_path = os.path.dirname(__file__)
config_path = os.path.join(app_path, "config.txt")

try:
	config_file = open(config_path, "r")
	CONFIG_DATA = json.load(config_file)
	config_file.close()
except (IOError, ValueError):
	print("Generating new config file.")
	CONFIG_DATA = {"api_key": "", "acc_loc": "", "gtoken": "", "bullettoken": "", "session_token": "", "f_gen": "https://api.imink.app/f"}
	config_file = open(config_path, "w")
	config_file.seek(0)
	config_file.write(json.dumps(CONFIG_DATA, indent=4, sort_keys=False, separators=(',', ': ')))
	config_file.close()
	config_file = open(config_path, "r")
	CONFIG_DATA = json.load(config_file)
	config_file.close()

# SET GLOBALS
API_KEY       = CONFIG_DATA["api_key"]       # for stat.ink
USER_LANG     = CONFIG_DATA["acc_loc"][:5]   # user input
USER_COUNTRY  = CONFIG_DATA["acc_loc"][-2:]  # nintendo account info
GTOKEN        = CONFIG_DATA["gtoken"]        # for accessing splatnet - base64 json web token
BULLETTOKEN   = CONFIG_DATA["bullettoken"]   # for accessing splatnet - base64
SESSION_TOKEN = CONFIG_DATA["session_token"] # for nintendo login
F_GEN_URL     = CONFIG_DATA["f_gen"]         # endpoint for generating f (imink API by default)

# SET HTTP HEADERS
DEFAULT_USER_AGENT = 'Mozilla/5.0 (Linux; Android 11; Pixel 5) ' \
						'AppleWebKit/537.36 (KHTML, like Gecko) ' \
						'Chrome/94.0.4606.61 Mobile Safari/537.36'
APP_USER_AGENT = str(CONFIG_DATA.get("app_user_agent", DEFAULT_USER_AGENT))


def write_config(tokens):
	'''Writes config file and updates the global variables.'''

	config_file = open(config_path, "w")
	config_file.seek(0)
	config_file.write(json.dumps(tokens, indent=4, sort_keys=False, separators=(',', ': ')))
	config_file.close()

	config_file = open(config_path, "r")
	CONFIG_DATA = json.load(config_file)

	global API_KEY
	API_KEY = CONFIG_DATA["api_key"]
	global USER_LANG
	USER_LANG = CONFIG_DATA["acc_loc"][:5]
	global USER_COUNTRY
	USER_COUNTRY = CONFIG_DATA["acc_loc"][-2:]
	global GTOKEN
	GTOKEN = CONFIG_DATA["gtoken"]
	global BULLETTOKEN
	BULLETTOKEN = CONFIG_DATA["bullettoken"]
	global SESSION_TOKEN
	SESSION_TOKEN = CONFIG_DATA["session_token"]

	config_file.close()


def headbutt():
	'''Returns a (dynamic!) header used for GraphQL requests.'''

	graphql_head = {
		'Authorization':    f'Bearer {BULLETTOKEN}', # update every time it's called with current global var
		'Accept-Language':  USER_LANG,
		'User-Agent':       APP_USER_AGENT,
		'X-Web-View-Ver':   iksm.get_web_view_ver(),
		'Content-Type':     'application/json',
		'Accept':           '*/*',
		'Origin':           iksm.SPLATNET3_URL,
		'X-Requested-With': 'com.nintendo.znca',
		'Referer':          f'{iksm.SPLATNET3_URL}?lang={USER_LANG}&na_country={USER_COUNTRY}&na_lang={USER_LANG}',
		'Accept-Encoding':  'gzip, deflate'
	}
	return graphql_head


def prefetch_checks(printout=False):
	'''Queries the SplatNet 3 homepage to check if our gtoken & bulletToken are still valid and regenerates them if not.'''

	if printout:
		print("Validating your tokens...", end='\r')

	iksm.get_web_view_ver() # setup

	if SESSION_TOKEN == "" or GTOKEN == "" or BULLETTOKEN == "":
		gen_new_tokens("blank")

	sha = utils.translate_rid["HomeQuery"]
	test = requests.post(utils.GRAPHQL_URL, data=utils.gen_graphql_body(sha), headers=headbutt(), cookies=dict(_gtoken=GTOKEN))
	if test.status_code != 200:
		if printout:
			print("\n")
		gen_new_tokens("expiry")
	else:
		if printout:
			print("Validating your tokens... done.\n")


def gen_new_tokens(reason, force=False):
	'''Attempts to generate new tokens when the saved ones have expired.'''

	manual_entry = False
	if force != True: # unless we force our way through
		if reason == "blank":
			print("Blank token(s).          ")
		elif reason == "expiry":
			print("The stored tokens have expired.")
		else:
			print("Cannot access SplatNet 3 without having played online.")
			sys.exit(0)

	if SESSION_TOKEN == "":
		print("Please log in to your Nintendo Account to obtain your session_token.")
		new_token = iksm.log_in(A_VERSION, APP_USER_AGENT)
		if new_token is None:
			print("There was a problem logging you in. Please try again later.")
		elif new_token == "skip":
			manual_entry = True
		else:
			print("\nWrote session_token to config.txt.")
		CONFIG_DATA["session_token"] = new_token
		write_config(CONFIG_DATA)
	elif SESSION_TOKEN == "skip":
		manual_entry = True

	if manual_entry: # no session_token ever gets stored
		print("\nYou have opted against automatic token generation and must manually input your tokens.\n")
		new_gtoken, new_bullettoken = iksm.enter_tokens()
		acc_lang = "en-US" # overwritten by user setting
		acc_country = "US"
		print("Using `US` for country by default. This can be changed in config.txt.")
	else:
		print("Attempting to generate new gtoken and bulletToken...")
		new_gtoken, acc_name, acc_lang, acc_country = iksm.get_gtoken(F_GEN_URL, SESSION_TOKEN, A_VERSION)
		new_bullettoken = iksm.get_bullet(new_gtoken, APP_USER_AGENT, acc_lang, acc_country)
	CONFIG_DATA["gtoken"] = new_gtoken # valid for 2 hours
	CONFIG_DATA["bullettoken"] = new_bullettoken # valid for 2 hours

	global USER_LANG
	if acc_lang != USER_LANG:
		acc_lang = USER_LANG
	CONFIG_DATA["acc_loc"] = f"{acc_lang}|{acc_country}"

	write_config(CONFIG_DATA)

	if manual_entry:
		print("Wrote tokens to config.txt.\n") # and updates acc_country if necessary...
	else:
		print(f"Wrote tokens for {acc_name} to config.txt.\n")


def encryptKey(uid: str):
	hash = mmh3.hash(uid, signed=False)
	key = hash & 0xff
	encrypted = base64.b64encode(bytearray([i ^ key for i in uid.encode()])).decode()
	return {'key': encrypted, 'h': hash}


def fetch_json():
	'''Returns results JSON from SplatNet 3'''

	sha = utils.translate_rid['LatestBattleHistoriesQuery']
	query = requests.post(utils.GRAPHQL_URL, data=utils.gen_graphql_body(sha), headers=headbutt(), cookies=dict(_gtoken=GTOKEN))
	query_resp = json.loads(query.text)['data']['latestBattleHistories']
	id = query_resp['historyGroups']['nodes'][0]['historyDetails']['nodes'][0]['id']
	detailId = utils.parseHistoryDetailId(id)
	uid = detailId['uid']
	timestamp = math.floor(time.time())
	keys = encryptKey(uid)

	sha = utils.translate_rid['myOutfitCommonDataEquipmentsQuery']
	query = requests.post(utils.GRAPHQL_URL, data=utils.gen_graphql_body(sha), headers=headbutt(), cookies=dict(_gtoken=GTOKEN))
	query_resp = json.loads(query.text)

	gears = {
		**keys,
		"timestamp": timestamp,
		'gear': query_resp
	}

	return gears


def set_language():
	'''Prompts the user to set their game language.'''

	if USER_LANG == "":
		print("Default locale is en-US. Press Enter to accept, or enter your own (see readme for list).")
		language_code = input("")

		if language_code == "":
			CONFIG_DATA["acc_loc"] = "en-US|US" # default
			write_config(CONFIG_DATA)
			return
		else:
			language_list = [
				"de-DE", "en-GB", "en-US", "es-ES", "es-MX", "fr-CA", "fr-FR",
				"it-IT", "ja-JP", "ko-KR", "nl-NL", "ru-RU", "zh-CN", "zh-TW"
			]
			while language_code not in language_list:
				print("Invalid language code. Please try entering it again:")
				language_code = input("")
			CONFIG_DATA["acc_loc"] = f"{language_code}|US" # default to US until set by ninty
			write_config(CONFIG_DATA)
	return


def main():
	'''Main process, including I/O and setup.'''

	print('\033[93m\033[1m' + "s3s-gear" + '\033[0m\033[93m' + f" v{A_VERSION}" + '\033[0m')

	# setup
	#######
	set_language()

	prefetch_checks(printout=True)
	print("Fetching your JSON files to export locally. This might take a while...")
	# fetch_json() calls prefetch_checks() to gen or check tokens
	gears = fetch_json()

	cwd = os.getcwd()
	with open(os.path.join(cwd, 'gears.json'), 'w') as f:
		json.dump(gears, f, indent=4, sort_keys=False, ensure_ascii=False)
		print("Created gears.json with information about all your gears.")

if __name__ == "__main__":
	main()
